from __future__ import annotations

import csv
import hashlib
import json
import random
import statistics
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def number(value, default=0.0):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def public_backtest():
    panel_path = DATA / "public" / "monthly_panel.csv"
    recalls_path = DATA / "public" / "recall_detection_12m.csv"
    panel = read_csv(panel_path)
    recalls = read_csv(recalls_path)

    previous = {}
    episodes = []
    for row in panel:
        key = (row["BRAND"], row["MODEL"], row["YEAR"], row["CAT"])
        alert = int(number(row["ALERT"]))
        if alert and not previous.get(key, 0):
            episodes.append(row)
        previous[key] = alert

    true_alerts = sum(int(number(row["Y12"])) for row in episodes)
    detected = [row for row in recalls if row["12개월판정"] == "탐지"]
    lead = [number(row["선행개월"]) for row in detected if row["선행개월"].strip()]
    summary = load_json(DATA / "public" / "dataset_summary.json")

    return {
        "evidence_class": "A_PUBLIC_OBSERVED",
        "source": "NHTSA-derived saved public dataset",
        "complaints": summary["complaints"],
        "recall_records": len(recalls),
        "investigation_records": summary["investigation_records"],
        "alert_episodes": len(episodes),
        "true_alerts": true_alerts,
        "precision": true_alerts / len(episodes),
        "detected_recalls": len(detected),
        "detection_rate_12m": len(detected) / len(recalls),
        "median_lead_months": statistics.median(lead),
        "rule": summary["rule"],
        "hashes": {
            "monthly_panel.csv": sha256(panel_path),
            "recall_detection_12m.csv": sha256(recalls_path),
        },
    }


def confusion(rows, prediction):
    tp = fp = tn = fn = 0
    for row in rows:
        label = row["_label"]
        pred = row[prediction]
        if pred and label:
            tp += 1
        elif pred and not label:
            fp += 1
        elif not pred and label:
            fn += 1
        else:
            tn += 1
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "recall": tp / (tp + fn) if tp + fn else 0,
        "precision": tp / (tp + fp) if tp + fp else 0,
        "false_alarm_rate": fp / (fp + tn) if fp + tn else 0,
    }


def synthetic_lot_test():
    input_path = DATA / "synthetic" / "lot_backtest.csv"
    rule_path = DATA / "synthetic" / "fixed_rule.json"
    rows = read_csv(input_path)
    rule = load_json(rule_path)
    rows.sort(key=lambda row: datetime.fromisoformat(row["production_date"]))
    split = max(1, int(len(rows) * 0.7))
    train, test = rows[:split], rows[split:]

    default_count = number(rule["default_vehicle_count"], 80)
    normal_rate = (
        sum(number(row["field_signals_180d"]) for row in train)
        / sum(number(row.get("vehicle_count"), default_count) for row in train)
    )

    for row in test:
        vehicle_count = number(row.get("vehicle_count"), default_count)
        signals = number(row["field_signals_180d"])
        field_rate = signals / vehicle_count if vehicle_count else 0
        ratio = field_rate / normal_rate if normal_rate else 0
        baseline = (
            signals >= number(rule["minimum_field_signals"])
            and ratio >= number(rule["minimum_rate_ratio"])
        )
        candidate = rule["enterprise_candidate"]
        process_flag = (
            number(row["process_z"]) >= number(candidate["process_z_min"])
            or number(row["recheck_rate"]) >= number(candidate["recheck_rate_min"])
        )
        row["_label"] = int(number(row["actual_defect"]) >= 1)
        row["_baseline"] = int(baseline)
        row["_candidate"] = int(baseline and process_flag)

    baseline = confusion(test, "_baseline")
    candidate = confusion(test, "_candidate")
    gates = rule["gates"]
    passed = (
        baseline["recall"] >= number(gates["recall_min"])
        and baseline["precision"] >= number(gates["precision_min"])
        and baseline["false_alarm_rate"] <= number(gates["false_alarm_rate_max"])
    )
    return {
        "evidence_class": "B_SYNTHETIC_FUNCTION_TEST",
        "warning": "합성 LOT 데이터의 기능시험이며 실제 기업 성능이 아닙니다.",
        "rule_version": rule["rule_version"],
        "rule_sha256": sha256(rule_path),
        "total_lots": len(rows),
        "reference_lots": len(train),
        "blind_test_lots": len(test),
        "normal_reference_rate": normal_rate,
        "baseline": baseline,
        "enterprise_candidate": candidate,
        "gate_pass": passed,
    }


def percentile(values, p):
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def economic_simulation(runs=20_000, seed=20260730):
    rng = random.Random(seed)
    designs = [
        (240, 50_000_000, 0.00, 0),
        (240, 20_000_000, 0.00, 0),
        (480, 30_000_000, 0.00, 0),
        (480, 20_000_000, 0.10, 15_000_000),
    ]
    selected = None
    for vehicle_mode, fixed_mode, success_fee_rate, success_fee_cap in designs:
        net_values, roi_values = [], []
        for _ in range(runs):
            vehicles = rng.triangular(vehicle_mode * 0.75, vehicle_mode * 1.25, vehicle_mode)
            success = rng.triangular(0.35, 0.70, 0.50)
            field_cost = rng.triangular(400_000, 600_000, 485_000)
            early_cost = rng.triangular(180_000, 260_000, 210_000)
            fixed = rng.triangular(fixed_mode * 0.90, fixed_mode * 1.10, fixed_mode)
            false_vehicles = rng.triangular(0, max(80, vehicle_mode * 0.50), vehicle_mode * 0.10)

            prevented = vehicles * success
            avoided = prevented * field_cost
            early = prevented * early_cost
            false_cost = false_vehicles * 30_000
            inventory = (vehicles + false_vehicles) * 10_000
            fee = min(avoided * success_fee_rate, success_fee_cap)
            total = early + false_cost + inventory + fixed + fee
            net = avoided - total
            roi = net / total if total else 0
            net_values.append(net)
            roi_values.append(roi)
        selected = (vehicle_mode, fixed_mode, success_fee_rate, success_fee_cap, net_values, roi_values)

    vehicle_mode, fixed_mode, success_fee_rate, success_fee_cap, net_values, roi_values = selected

    prevented = vehicle_mode * 0.50
    avoided = prevented * 485_000
    total = prevented * 210_000 + vehicle_mode * 10_000 + fixed_mode
    total += min(avoided * success_fee_rate, success_fee_cap)
    deterministic_net = avoided - total

    return {
        "evidence_class": "C_ASSUMPTION_SIMULATION",
        "warning": "합성 규모와 비용 가정 기반 예상치이며 기업 ROI 확정값이 아닙니다.",
        "seed": seed,
        "runs": runs,
        "design": "D_단계지급형",
        "fixed_fee_krw": fixed_mode,
        "success_fee_rate": success_fee_rate,
        "success_fee_cap_krw": success_fee_cap,
        "deterministic": {
            "prevented_vehicles": prevented,
            "avoided_loss_krw": avoided,
            "total_cost_krw": total,
            "net_benefit_krw": deterministic_net,
            "roi": deterministic_net / total,
        },
        "monte_carlo": {
            "expected_net_krw": statistics.fmean(net_values),
            "median_net_krw": statistics.median(net_values),
            "p10_net_krw": percentile(net_values, 0.10),
            "p90_net_krw": percentile(net_values, 0.90),
            "median_roi": statistics.median(roi_values),
            "probability_positive_net": sum(x > 0 for x in net_values) / runs,
            "probability_roi_at_least_10pct": sum(x >= 0.10 for x in roi_values) / runs,
        },
    }


def verify(public, synthetic):
    reference = load_json(DATA / "public" / "reference_metrics_12m.json")
    checks = {
        "public_recall_records": public["recall_records"] == reference["recall_events"],
        "public_detected_recalls": public["detected_recalls"] == reference["detected_recalls"],
        "public_alert_episodes": public["alert_episodes"] == reference["alert_episodes"],
        "public_true_alerts": public["true_alerts"] == reference["true_alerts"],
        "public_detection_rate": abs(public["detection_rate_12m"] - reference["recall_detection_rate"]) < 1e-12,
        "public_precision": abs(public["precision"] - reference["alert_precision"]) < 1e-12,
        "public_median_lead": abs(public["median_lead_months"] - reference["median_lead_months"]) < 0.05,
        "synthetic_rule_locked": synthetic["rule_version"] == "G3-LOCKED-1.0",
    }
    return {"all_passed": all(checks.values()), "checks": checks}


def write_outputs(public, synthetic, economics, verification):
    RESULTS.mkdir(parents=True, exist_ok=True)
    combined = {
        "project_status": "개인 프로젝트 PoC 완성",
        "enterprise_status": "기업 내부 데이터 실증 전",
        "public_backtest": public,
        "synthetic_function_test": synthetic,
        "economic_simulation": economics,
        "reproducibility": verification,
    }
    (RESULTS / "project_results.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with (RESULTS / "result_classification.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["등급", "의미", "대표 결과", "사용 가능한 주장", "금지되는 주장"])
        writer.writerow([
            "A 공개 관측", "실제 공개데이터 백테스트",
            f"12개월 탐지율 {public['detection_rate_12m']:.1%}, 정밀도 {public['precision']:.1%}, 중앙 선행 {public['median_lead_months']:.1f}개월",
            "리콜 전 선행 신호 가능성을 확인했다", "기업 성능과 기업 ROI가 확정됐다",
        ])
        writer.writerow([
            "B 합성 기능시험", "합성 LOT 기반 연결·경보 기능 검증",
            f"블라인드 시험 {synthetic['blind_test_lots']} LOT, Gate {'통과' if synthetic['gate_pass'] else '미통과'}",
            "LOT 단위 분석 흐름이 작동한다", "실제 생산라인 탐지 성능이다",
        ])
        writer.writerow([
            "C 가정 시뮬레이션", "명시적 비용·규모 가정의 경제성 범위",
            f"기준 ROI {economics['deterministic']['roi']:.1%}, ROI 10% 이상 확률 {economics['monte_carlo']['probability_roi_at_least_10pct']:.1%}",
            "가정 조건에서 예상 손익 범위를 산출했다", "기업 ROI가 보장된다",
        ])
        writer.writerow([
            "D 기업 실증", "기업 내부 데이터로 측정할 미래 단계",
            "공정·LOT·차량·보증수리·원가 필요",
            "기업 데이터 적용 시 실제 수치를 측정할 수 있다", "데이터 투입 전 성과를 확정한다",
        ])

    report = f"""자동차 품질위험 조기경보 PoC 재현성 결과

[상태]
- 개인 프로젝트: 완성
- 기업 성능 검증: 미실시
- 전체 재현성 검사: {"통과" if verification["all_passed"] else "실패"}

[A. 공개데이터 관측 결과]
- 불만 데이터: {public["complaints"]:,}건
- 리콜 레코드: {public["recall_records"]:,}건
- 12개월 탐지율: {public["detection_rate_12m"]:.1%}
- 경보 정밀도: {public["precision"]:.1%}
- 중앙 선행기간: {public["median_lead_months"]:.1f}개월

[B. 합성 LOT 기능시험]
- 전체 LOT: {synthetic["total_lots"]:,}
- 블라인드 LOT: {synthetic["blind_test_lots"]:,}
- Gate: {"통과" if synthetic["gate_pass"] else "미통과"}
- 주의: 실제 기업 성능이 아님

[C. 가정 기반 경제성]
- 기준 순편익: {economics["deterministic"]["net_benefit_krw"]:,.0f}원
- 기준 ROI: {economics["deterministic"]["roi"]:.1%}
- ROI 10% 이상 확률: {economics["monte_carlo"]["probability_roi_at_least_10pct"]:.1%}
- 주의: 기업 ROI 확정값이 아님

[기업 데이터가 들어오면 확정 가능한 값]
- 실제 LOT-차량 연결률
- 실제 탐지율·정밀도·오탐 비용
- 예방 또는 범위 축소 가능 차량 수
- 직접 회피손실과 실현 ROI
"""
    (RESULTS / "reproduction_report.txt").write_text(report, encoding="utf-8-sig")

    manifest_targets = [
        DATA / "public" / "monthly_panel.csv",
        DATA / "public" / "recall_detection_12m.csv",
        DATA / "synthetic" / "lot_backtest.csv",
        DATA / "synthetic" / "fixed_rule.json",
        Path(__file__).resolve(),
    ]
    manifest = "\n".join(
        f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in manifest_targets
    )
    (RESULTS / "MANIFEST.sha256").write_text(manifest + "\n", encoding="ascii")


def main():
    public = public_backtest()
    synthetic = synthetic_lot_test()
    economics = economic_simulation()
    verification = verify(public, synthetic)
    write_outputs(public, synthetic, economics, verification)
    print("완료: results/project_results.json")
    print("재현성 검사:", "통과" if verification["all_passed"] else "실패")
    return 0 if verification["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
