"""안전등급별로 균등한 약한 결함·비결함 이상을 만들어 정책을 검증한다."""
from __future__ import annotations
import argparse, csv, json, shutil
from pathlib import Path
from enterprise_pipeline import run_pipeline
from generate_enterprise_pilot_fixture import generate
from safety_class_policy import compare

CLASSES = ("SAFETY", "POWERTRAIN", "CONVENIENCE", "SOFTWARE")

def _read(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle); return list(reader), list(reader.fieldnames or [])

def _write(path: Path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)

def prepare(raw_dir: Path) -> dict[str, object]:
    generate(raw_dir, lots=1_000, vehicles=10_000, claims=300)
    truth, truth_fields = _read(raw_dir / "synthetic_ground_truth.csv")
    inspections, inspection_fields = _read(raw_dir / "공정검사.csv")
    lots, _ = _read(raw_dir / "협력사부품입고.csv")
    lot_class = {r["부품LOT번호"]: r["안전등급"] for r in lots}
    original_true = {r["lot_id"] for r in truth if r["is_injected_risk"] == "1"}
    available = {name: [r["부품LOT번호"] for r in lots if r["안전등급"] == name and r["부품LOT번호"] not in original_true] for name in CLASSES}
    weak = {name: set(available[name][:5]) for name in CLASSES}
    false = {name: set(available[name][5:10]) for name in CLASSES}
    weak_all = set().union(*weak.values()); false_all = set().union(*false.values())
    for row in truth:
        if row["lot_id"] in weak_all:
            row["is_injected_risk"], row["injected_reason"] = "1", "STRATIFIED_WEAK_DEFECT"
        elif row["lot_id"] in false_all:
            row["injected_reason"] = "STRATIFIED_PROCESS_ANOMALY_WITHOUT_DEFECT"
    for row in inspections:
        if row["부품LOT번호"] in weak_all:
            row["공정편차Z"], row["재검률"] = "1.500", "0.0400"
        elif row["부품LOT번호"] in false_all:
            row["공정편차Z"], row["재검률"] = "3.200", "0.1200"
    _write(raw_dir / "synthetic_ground_truth.csv", truth, truth_fields); _write(raw_dir / "공정검사.csv", inspections, inspection_fields)
    scenario = {"original_strong_true": len(original_true), "weak_true_by_class": {k: len(v) for k, v in weak.items()}, "strong_false_by_class": {k: len(v) for k, v in false.items()}, "lot_class_count": {k: sum(1 for v in lot_class.values() if v == k) for k in CLASSES}}
    (raw_dir / "stratified_scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return scenario

def run(output_root: Path, project_root: Path) -> dict[str, object]:
    if output_root.exists(): shutil.rmtree(output_root)
    raw = output_root / "raw"; scenario = prepare(raw)
    pipeline = run_pipeline(raw, project_root / "enterprise_data" / "demo_company_mapping.json", project_root / "enterprise_data" / "enterprise_analysis_rules.json", output_root / "pipeline")
    if pipeline["status"] != "READY": raise RuntimeError("계층화 합성자료 파이프라인이 차단됐습니다")
    comparison = compare(raw / "synthetic_ground_truth.csv", output_root / "pipeline" / "current" / "02_analysis" / "lot_risk_results.csv", output_root / "safety_policy_comparison.json")
    result = {"status": "READY", "scenario": scenario, "comparison": comparison, "warning": "합성 계층화 기능시험이며 실제 기업 성능이 아닙니다"}
    (output_root / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig"); return result

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-root", type=Path, default=Path("results/stratified_safety_validation")); args = parser.parse_args(); root = Path(__file__).resolve().parents[1]
    print(json.dumps(run(args.output_root.resolve(), root), ensure_ascii=False, indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
