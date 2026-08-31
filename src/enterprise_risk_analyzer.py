"""검증된 기업 표준데이터로 LOT 위험, 영향 VIN, 예상 손익을 계산한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from enterprise_data_validator import read_csv_safely, validate_directory


def read_standardized(folder: Path, filename: str) -> list[dict[str, str]]:
    rows, _, _ = read_csv_safely(folder / filename)
    return rows


def action_for(safety_class: str, statuses: set[str], level: str) -> tuple[str, str]:
    if level == "NORMAL":
        return "MONITOR", "출고 유지·정상 추세 모니터링"
    shipped = bool(statuses & {"SHIPPED", "FIELD"})
    if safety_class == "SAFETY":
        return ("URGENT_SAFETY_REVIEW", "장착 VIN 긴급 특정·안전 리콜 여부 검토") if shipped else (
            "HOLD_SHIPMENT", "LOT 격리·출고보류·전수검사"
        )
    if safety_class == "SOFTWARE":
        return ("OTA_CAMPAIGN", "대상 VIN OTA 배포·실패차량 입고") if shipped else (
            "SOFTWARE_BLOCK", "수정버전 검증 전 출고보류"
        )
    if safety_class == "CONVENIENCE":
        return ("SERVICE_CAMPAIGN", "무상점검·보증연장·필요차량만 교체") if shipped else (
            "REWORK", "공정 내 재작업·기능검사"
        )
    return ("TARGETED_REPAIR", "고위험 VIN 선별점검·부품 선확보") if shipped else (
        "SELECTIVE_HOLD", "고위험 LOT 재검·선별 출고보류"
    )


def risk_score(max_z: float, max_recheck: float, claim_count: int, claim_rate: float,
               reference_claim_rate: float, safety_class: str) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    if max_z >= 3:
        score += 30
        reasons.append(f"공정편차 {max_z:.2f}σ≥3")
    elif max_z >= 2:
        score += 20
        reasons.append(f"공정편차 {max_z:.2f}σ≥2")
    if max_recheck >= 0.10:
        score += 25
        reasons.append(f"재검률 {max_recheck:.1%}≥10%")
    elif max_recheck >= 0.07:
        score += 15
        reasons.append(f"재검률 {max_recheck:.1%}≥7%")
    field_threshold = max(0.02, reference_claim_rate * 1.5)
    if claim_count >= 3:
        score += 25
        reasons.append(f"보증수리 {claim_count}건≥3")
    elif claim_rate >= field_threshold and claim_count > 0:
        score += 20
        reasons.append(f"수리율 {claim_rate:.1%}≥기준 {field_threshold:.1%}")
    elif claim_count > 0:
        score += 10
        reasons.append(f"보증수리 {claim_count}건")
    if safety_class == "SAFETY" and reasons:
        score += 20
        reasons.append("안전 핵심부품 가중치")
    elif safety_class == "POWERTRAIN" and reasons:
        score += 10
        reasons.append("주행 영향부품 가중치")
    return min(score, 100), reasons


def analyze(standardized: Path, output_dir: Path, rules_file: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    validation = validate_directory(standardized, output_dir / "preanalysis_validation")
    if validation["status"] != "READY":
        summary = {"status": "BLOCKED", "analysis_allowed": False, "reason": "입력데이터 오류검사 미통과"}
        (output_dir / "enterprise_analysis_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8-sig"
        )
        return summary

    rules = json.loads(rules_file.read_text(encoding="utf-8-sig"))
    lots = read_standardized(standardized, "part_lot.csv")
    inspections = read_standardized(standardized, "process_inspection.csv")
    vehicles = read_standardized(standardized, "vehicle_build.csv")
    claims = read_standardized(standardized, "warranty_claim.csv")
    costs = read_standardized(standardized, "cost_master.csv")

    inspection_by_lot = defaultdict(list)
    vehicle_by_lot = defaultdict(list)
    claims_by_vin = defaultdict(list)
    for row in inspections:
        inspection_by_lot[row["lot_id"].upper()].append(row)
    for row in vehicles:
        vehicle_by_lot[row["lot_id"].upper()].append(row)
    for row in claims:
        claims_by_vin[row["vin"].upper()].append(row)
    cost_by_part = {row["part_number"].upper(): row for row in costs}

    total_vehicle_links = len(vehicles)
    total_claim_links = sum(len(claims_by_vin.get(row["vin"].upper(), [])) for row in vehicles)
    reference_claim_rate = total_claim_links / total_vehicle_links if total_vehicle_links else 0
    lot_results = []
    affected = []
    fixed_program_cost = float(rules["fixed_program_cost_krw"])

    for lot in lots:
        lot_id = lot["lot_id"].upper()
        part_number = lot["part_number"].upper()
        safety_class = lot["safety_class"].upper()
        lot_inspections = inspection_by_lot.get(lot_id, [])
        lot_vehicles = vehicle_by_lot.get(lot_id, [])
        unique_vins = sorted({row["vin"].upper() for row in lot_vehicles})
        lot_claims = [claim for vin in unique_vins for claim in claims_by_vin.get(vin, [])]
        max_z = max((float(row["process_z"]) for row in lot_inspections), default=0.0)
        max_recheck = max((float(row["recheck_rate"]) for row in lot_inspections), default=0.0)
        claim_count = len(lot_claims)
        claim_rate = claim_count / len(unique_vins) if unique_vins else 0.0
        score, reasons = risk_score(max_z, max_recheck, claim_count, claim_rate, reference_claim_rate, safety_class)
        level = "HIGH" if score >= int(rules["high_score_min"]) else "WATCH" if score >= int(rules["watch_score_min"]) else "NORMAL"
        statuses = {row["shipment_status"].upper() for row in lot_vehicles}
        action_code, action = action_for(safety_class, statuses, level)

        cost = cost_by_part.get(part_number)
        economic_status = "CALCULATED" if cost and unique_vins else "NOT_CALCULATED"
        prevented = avoided = early = compensation = net = roi = 0.0
        if economic_status == "CALCULATED" and level != "NORMAL":
            success_rate = float(rules["intervention_success_rate"][safety_class])
            prevented = len(unique_vins) * success_rate
            field_per_vehicle = float(cost["field_repair_cost_krw"]) + float(cost["customer_compensation_krw"])
            avoided = prevented * field_per_vehicle
            early = prevented * float(cost["early_action_cost_krw"])
            compensation = prevented * float(cost["customer_compensation_krw"])
            net = avoided - early
            roi = net / early if early else 0.0

        result = {
            "lot_id": lot_id,
            "supplier_id": lot["supplier_id"].upper(),
            "part_number": part_number,
            "safety_class": safety_class,
            "risk_score": score,
            "risk_level": level,
            "risk_reasons": " | ".join(reasons) if reasons else "경보기준 미만",
            "max_process_z": round(max_z, 6),
            "max_recheck_rate": round(max_recheck, 6),
            "vehicle_count": len(unique_vins),
            "warranty_claim_count": claim_count,
            "warranty_claim_rate": round(claim_rate, 6),
            "action_code": action_code,
            "recommended_action": action,
            "economic_status": economic_status,
            "estimated_prevented_vehicles": round(prevented, 3),
            "estimated_avoided_loss_krw": round(avoided),
            "estimated_early_action_cost_krw": round(early),
            "estimated_net_benefit_krw": round(net),
            "estimated_direct_roi": round(roi, 6),
        }
        lot_results.append(result)
        if level != "NORMAL":
            for row in lot_vehicles:
                affected.append({
                    "vin": row["vin"].upper(), "lot_id": lot_id, "model": row["model"],
                    "shipment_status": row["shipment_status"].upper(), "risk_level": level,
                    "action_code": action_code,
                })

    lot_results.sort(key=lambda row: (-row["risk_score"], row["lot_id"]))
    with (output_dir / "lot_risk_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(lot_results[0].keys()) if lot_results else ["lot_id"])
        writer.writeheader()
        writer.writerows(lot_results)
    with (output_dir / "affected_vehicles.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["vin", "lot_id", "model", "shipment_status", "risk_level", "action_code"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(affected)

    direct_avoided = sum(row["estimated_avoided_loss_krw"] for row in lot_results)
    direct_early = sum(row["estimated_early_action_cost_krw"] for row in lot_results)
    program_net = direct_avoided - direct_early - fixed_program_cost
    program_cost = direct_early + fixed_program_cost
    minimums = rules["minimum_records_for_decision"]
    sufficiency_checks = {
        "lots": len(lot_results) >= int(minimums["lots"]),
        "vehicle_links": total_vehicle_links >= int(minimums["vehicle_links"]),
        "warranty_claims": len(claims) >= int(minimums["warranty_claims"]),
    }
    decision_gate_passed = all(sufficiency_checks.values())
    summary = {
        "status": "READY",
        "analysis_allowed": True,
        "rule_version": rules["rule_version"],
        "evidence_warning": "규칙 기반 예상치이며 실제 결함 확정 또는 리콜 결정을 의미하지 않습니다",
        "lot_count": len(lot_results),
        "high_risk_lots": sum(row["risk_level"] == "HIGH" for row in lot_results),
        "watch_lots": sum(row["risk_level"] == "WATCH" for row in lot_results),
        "affected_vehicle_links": len(affected),
        "data_sufficiency": "SUFFICIENT" if decision_gate_passed else "INSUFFICIENT",
        "decision_gate_passed": decision_gate_passed,
        "sufficiency_checks": sufficiency_checks,
        "decision_warning": "표본수 기준 미달로 운영·리콜 의사결정에 사용할 수 없습니다" if not decision_gate_passed else "표본수 기준 통과. 담당부서 승인 후 파일럿 의사결정에 사용합니다",
        "reference_claim_rate": reference_claim_rate,
        "estimated_prevented_vehicles": sum(row["estimated_prevented_vehicles"] for row in lot_results),
        "estimated_avoided_loss_krw": direct_avoided,
        "estimated_early_action_cost_krw": direct_early,
        "fixed_program_cost_krw": fixed_program_cost,
        "estimated_program_net_benefit_krw": program_net,
        "estimated_program_roi": program_net / program_cost if program_cost else 0,
        "economic_warning": "기업 비용·성공률 가정에 따른 값이며 실제 ROI 확정값이 아닙니다",
    }
    (output_dir / "enterprise_analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8-sig"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="기업 LOT 위험·VIN·손익 분석")
    parser.add_argument("standardized_dir", type=Path)
    parser.add_argument("--rules", type=Path, default=Path("enterprise_data/enterprise_analysis_rules.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/enterprise_analysis"))
    args = parser.parse_args()
    result = analyze(args.standardized_dir.resolve(), args.output_dir.resolve(), args.rules.resolve())
    print(f"분석결과: {result['status']}")
    if result["status"] == "READY":
        print(f"고위험 LOT: {result['high_risk_lots']} / 영향 VIN 연결: {result['affected_vehicle_links']}")
    print(f"결과폴더: {args.output_dir.resolve()}")
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
