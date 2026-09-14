"""경계 신호와 비결함 공정 이상을 섞어 고정 경보규칙을 시험한다."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

from enterprise_pipeline import run_pipeline
from evaluate_synthetic_pilot import evaluate
from generate_enterprise_pilot_fixture import generate


def _read(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _write(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare_noisy_fixture(raw_dir: Path) -> dict[str, object]:
    """20개 강신호 결함, 10개 약신호 결함, 10개 비결함 강신호를 만든다."""
    generate(raw_dir, lots=1_000, vehicles=10_000, claims=300)
    truth_path = raw_dir / "synthetic_ground_truth.csv"
    inspection_path = raw_dir / "공정검사.csv"
    truth_rows, truth_fields = _read(truth_path)
    inspection_rows, inspection_fields = _read(inspection_path)

    strong_true = {f"LOT-PILOT-{i + 1:05d}" for i in range(0, 1_000, 50)}
    eligible = [i for i in range(1_000) if i not in range(0, 1_000, 50) and i % 4 in (2, 3)]
    weak_true = {f"LOT-PILOT-{i + 1:05d}" for i in eligible[:10]}
    strong_false = {f"LOT-PILOT-{i + 1:05d}" for i in eligible[10:20]}

    for row in truth_rows:
        lot_id = row["lot_id"]
        if lot_id in weak_true:
            row["is_injected_risk"] = "1"
            row["injected_reason"] = "WEAK_LATENT_DEFECT"
        elif lot_id in strong_false:
            row["is_injected_risk"] = "0"
            row["injected_reason"] = "PROCESS_ANOMALY_WITHOUT_DEFECT"
    for row in inspection_rows:
        lot_id = row["부품LOT번호"]
        if lot_id in weak_true:
            row["공정편차Z"], row["재검률"] = "1.500", "0.0400"
        elif lot_id in strong_false:
            row["공정편차Z"], row["재검률"] = "3.200", "0.1200"

    _write(truth_path, truth_rows, truth_fields)
    _write(inspection_path, inspection_rows, inspection_fields)
    scenario = {"strong_true": len(strong_true), "weak_true": len(weak_true),
                "strong_false": len(strong_false), "true_risk_total": len(strong_true | weak_true)}
    (raw_dir / "robustness_scenario.json").write_text(
        json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return scenario


def run(output_root: Path, project_root: Path) -> dict[str, object]:
    if output_root.exists():
        shutil.rmtree(output_root)
    raw_dir = output_root / "raw"
    scenario = prepare_noisy_fixture(raw_dir)
    pipeline = run_pipeline(raw_dir, project_root / "enterprise_data" / "demo_company_mapping.json",
                            project_root / "enterprise_data" / "enterprise_analysis_rules.json",
                            output_root / "pipeline")
    if pipeline["status"] != "READY":
        raise RuntimeError("잡음 합성자료 파이프라인이 차단됐습니다")
    metrics = evaluate(raw_dir / "synthetic_ground_truth.csv",
                       output_root / "pipeline" / "current" / "02_analysis" / "lot_risk_results.csv",
                       output_root / "robustness_evaluation.json")
    result = {"status": "READY", "scenario": scenario, "metrics": metrics,
              "interpretation": "합성 경계조건 스트레스 시험이며 실제 기업 성능이 아닙니다"}
    (output_root / "robustness_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="합성 잡음·경계조건 강건성 시험")
    parser.add_argument("--output-root", type=Path, default=Path("results/synthetic_robustness"))
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    print(json.dumps(run(args.output_root.resolve(), project_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
