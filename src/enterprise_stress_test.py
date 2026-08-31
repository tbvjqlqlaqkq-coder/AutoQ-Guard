"""대량 합성 기업 데이터로 전체 파이프라인의 성능과 정합성을 시험한다."""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sqlite3
import time
import tracemalloc
from pathlib import Path

from enterprise_database import search_database
from enterprise_pipeline import run_pipeline


TABLES = {
    "part_lot.csv": {
        "source_file": "lots.csv",
        "columns": {"lot_id": "lot", "supplier_id": "supplier", "part_number": "part", "safety_class": "class", "received_at": "received", "quantity": "qty"},
        "transforms": {"lot_id": "upper", "supplier_id": "upper", "part_number": "upper", "safety_class": "upper", "received_at": "datetime", "quantity": "integer"},
    },
    "process_inspection.csv": {
        "source_file": "inspections.csv",
        "columns": {"inspection_id": "inspection", "lot_id": "lot", "process_id": "process", "measured_at": "measured", "process_z": "z", "recheck_rate": "recheck"},
        "transforms": {"inspection_id": "upper", "lot_id": "upper", "process_id": "upper", "measured_at": "datetime", "process_z": "number", "recheck_rate": "percent_to_rate"},
    },
    "vehicle_build.csv": {
        "source_file": "vehicles.csv",
        "columns": {"vin": "vehicle", "lot_id": "lot", "model": "model", "production_at": "produced", "shipment_status": "status"},
        "transforms": {"vin": "upper", "lot_id": "upper", "production_at": "datetime", "shipment_status": "upper"},
    },
    "warranty_claim.csv": {
        "source_file": "claims.csv",
        "columns": {"claim_id": "claim", "vin": "vehicle", "claim_at": "claimed", "failure_code": "failure", "repair_cost_krw": "repair_cost"},
        "transforms": {"claim_id": "upper", "vin": "upper", "claim_at": "datetime", "failure_code": "upper", "repair_cost_krw": "number"},
    },
    "cost_master.csv": {
        "source_file": "costs.csv",
        "columns": {"part_number": "part", "early_action_cost_krw": "early_cost", "field_repair_cost_krw": "field_cost", "customer_compensation_krw": "compensation"},
        "transforms": {"part_number": "upper", "early_action_cost_krw": "number", "field_repair_cost_krw": "number", "customer_compensation_krw": "number"},
    },
}


def write_csv(path: Path, headers: list[str], rows) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def vin_for(index: int) -> str:
    return f"KMHST{index:012d}"  # 5자 접두어 + 12자리 숫자 = 17자리


def generate_dataset(raw: Path, mapping: Path, lots: int, vehicles_per_lot: int, seed: int = 20260805) -> dict:
    rng = random.Random(seed)
    raw.mkdir(parents=True, exist_ok=True)
    parts = max(20, lots // 10)
    suppliers = max(10, lots // 40)
    safety_classes = ["SAFETY", "POWERTRAIN", "CONVENIENCE", "SOFTWARE"]
    lot_rows, inspection_rows, vehicle_rows, claim_rows = [], [], [], []
    vehicle_index = 0
    claim_index = 0
    high_lots = set(range(0, lots, 20))  # 5%에 명확한 공정 이상 신호
    watch_lots = set(range(10, lots, 20))

    for lot_index in range(lots):
        lot_id = f"LOT-{lot_index:07d}"
        part = f"PART-{lot_index % parts:05d}"
        safety = safety_classes[lot_index % len(safety_classes)]
        lot_rows.append([lot_id, f"SUP-{lot_index % suppliers:04d}", part, safety, "2026-01-02 08:00:00", vehicles_per_lot + 5])
        for inspection_offset in range(2):
            if lot_index in high_lots:
                z, recheck = 3.2 + inspection_offset * 0.1, "12%"
            elif lot_index in watch_lots:
                z, recheck = 2.2, "7%"
            else:
                z, recheck = round(rng.uniform(0.1, 1.5), 3), "2%"
            inspection_rows.append([f"INSP-{lot_index:07d}-{inspection_offset}", lot_id, f"PROC-{inspection_offset+1}", "2026-01-03 10:00:00", z, recheck])
        for vehicle_offset in range(vehicles_per_lot):
            vin = vin_for(vehicle_index)
            vehicle_rows.append([vin, lot_id, f"MODEL-{lot_index % 5}", "2026-01-04 12:00:00", "SHIPPED" if vehicle_offset % 3 else "BEFORE_SHIPMENT"])
            # 전체 약 20%, 고위험 LOT은 더 높은 비율로 보증수리 생성
            claim_probability = 0.45 if lot_index in high_lots else 0.18
            if rng.random() < claim_probability:
                claim_rows.append([f"CLAIM-{claim_index:08d}", vin, "2026-03-01", "QUALITY-SIGNAL", 480000])
                claim_index += 1
            vehicle_index += 1

    cost_rows = [[f"PART-{index:05d}", 180000, 480000, 50000] for index in range(parts)]
    write_csv(raw / "lots.csv", ["lot", "supplier", "part", "class", "received", "qty"], lot_rows)
    write_csv(raw / "inspections.csv", ["inspection", "lot", "process", "measured", "z", "recheck"], inspection_rows)
    write_csv(raw / "vehicles.csv", ["vehicle", "lot", "model", "produced", "status"], vehicle_rows)
    write_csv(raw / "claims.csv", ["claim", "vehicle", "claimed", "failure", "repair_cost"], claim_rows)
    write_csv(raw / "costs.csv", ["part", "early_cost", "field_cost", "compensation"], cost_rows)
    mapping.write_text(json.dumps({"company_profile": "STRESS_TEST_V1", "tables": TABLES}, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return {"lots": lots, "inspections": len(inspection_rows), "vehicles": len(vehicle_rows), "claims": len(claim_rows), "parts": parts, "expected_high_signal_lots": len(high_lots)}


def run_stress_test(project_root: Path, lots: int, vehicles_per_lot: int, searches: int) -> dict:
    work = project_root / "results" / "enterprise_stress_test"
    if work.exists():
        shutil.rmtree(work)
    raw, mapping = work / "generated_raw", work / "stress_mapping.json"
    counts = generate_dataset(raw, mapping, lots, vehicles_per_lot)
    tracemalloc.start()
    start = time.perf_counter()
    pipeline = run_pipeline(raw, mapping, project_root / "enterprise_data" / "enterprise_analysis_rules.json", work / "pipeline")
    pipeline_seconds = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    db = work / "pipeline" / "current" / "03_database" / "automotive_quality.db"
    checks = {"pipeline_ready": pipeline["status"] == "READY", "decision_gate_passed": bool(pipeline.get("decision_gate_passed"))}
    db_counts = {}
    search_seconds = None
    search_accuracy = None
    if db.exists():
        connection = sqlite3.connect(db)
        try:
            for table in ("part_lot", "process_inspection", "vehicle_build", "warranty_claim", "lot_risk_result"):
                db_counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            checks["database_integrity"] = connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            connection.close()
        search_start = time.perf_counter()
        correct = 0
        for index in range(searches):
            lot_id = f"LOT-{index % lots:07d}"
            rows = search_database(db, lot_id=lot_id)
            correct += bool(rows) and all(row["lot_id"] == lot_id for row in rows)
        search_seconds = time.perf_counter() - search_start
        search_accuracy = correct / searches if searches else 1.0
    checks["row_count_match"] = (
        db_counts.get("part_lot") == counts["lots"] and
        db_counts.get("process_inspection") == counts["inspections"] and
        db_counts.get("vehicle_build") == counts["vehicles"] and
        db_counts.get("warranty_claim") == counts["claims"]
    )
    checks["search_accuracy_100_percent"] = search_accuracy == 1.0
    result = {
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "configuration": {"seed": 20260805, "lots": lots, "vehicles_per_lot": vehicles_per_lot, "searches": searches},
        "generated_counts": counts, "database_counts": db_counts, "checks": checks,
        "performance": {
            "pipeline_seconds": round(pipeline_seconds, 3), "peak_python_memory_mb": round(peak / 1024 / 1024, 2),
            "search_total_seconds": round(search_seconds or 0, 3),
            "average_search_ms": round((search_seconds or 0) * 1000 / max(searches, 1), 3),
            "search_accuracy": search_accuracy,
        },
        "limitations": [
            "합성데이터 성능시험이며 실제 기업의 서버·보안·동시접속 환경을 재현하지 않습니다.",
            "단일 PC·단일 사용자 기준이므로 기업 운영 성능 보증값이 아닙니다.",
            "예측 정확도가 아니라 데이터 처리와 검색 정합성을 검증한 시험입니다.",
        ],
    }
    (work / "stress_test_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="자동차 품질 시스템 대량 데이터 시험")
    parser.add_argument("--lots", type=int, default=2000)
    parser.add_argument("--vehicles-per-lot", type=int, default=10)
    parser.add_argument("--searches", type=int, default=500)
    args = parser.parse_args()
    if args.lots < 10 or args.vehicles_per_lot < 1 or args.searches < 1:
        raise SystemExit("lots>=10, vehicles-per-lot>=1, searches>=1 이어야 합니다.")
    result = run_stress_test(Path(__file__).resolve().parents[1], args.lots, args.vehicles_per_lot, args.searches)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
