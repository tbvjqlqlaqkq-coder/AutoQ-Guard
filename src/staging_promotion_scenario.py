"""합성 기업자료로 격리→후보→비교→반영 차단을 재현하는 통합 시나리오."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from enterprise_dashboard import build_staged_candidate, compare_candidate, promote_candidate
from enterprise_pipeline import run_pipeline


TABLES = ("part_lot.csv", "process_inspection.csv", "vehicle_build.csv", "warranty_claim.csv", "cost_master.csv")


def run_scenario(root: Path, output_root: Path) -> dict:
    run_id = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    run_dir = output_root.resolve() / run_id
    baseline_root, staging = run_dir / "baseline", run_dir / "staging"
    baseline = run_pipeline(
        root / "enterprise_data" / "demo_company_raw",
        root / "enterprise_data" / "demo_company_mapping.json",
        root / "enterprise_data" / "enterprise_analysis_rules.json",
        baseline_root,
    )
    if baseline["status"] != "READY":
        raise RuntimeError("기준 파이프라인 생성 실패")
    current = baseline_root / "current"
    standardized = current / "01_import" / "standardized"
    for number, table in enumerate(TABLES, 1):
        folder = staging / f"approved-{number:02d}"
        folder.mkdir(parents=True)
        target = folder / table
        shutil.copy2(standardized / table, target)
        with target.open(encoding="utf-8-sig") as handle:
            row_count = sum(1 for _ in handle) - 1
        manifest = {"status":"STAGED_NOT_LOADED", "table":table, "approval_token":f"scenario-token-{number}",
                    "rows":row_count, "staged_file":str(target)}
        (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    candidate = build_staged_candidate(staging, root / "enterprise_data" / "enterprise_analysis_rules.json")
    comparison = compare_candidate(current / "03_database" / "automotive_quality.db", staging, candidate["run_id"])
    blocked_reason = ""
    try:
        promote_candidate(current / "03_database" / "automotive_quality.db", current / "pipeline_summary.json",
                          staging, candidate["run_id"], comparison["promotion_token"], "PROMOTE")
    except ValueError as exc:
        blocked_reason = str(exc)
    result = {"status":"PASS" if comparison["status"] == "REVIEW_ONLY" and blocked_reason else "FAIL",
              "scenario_run_id":run_id, "approved_tables":len(TABLES), "candidate":candidate,
              "comparison":{key:value for key,value in comparison.items() if key != "promotion_token"},
              "promotion_attempt":"BLOCKED" if blocked_reason else "UNEXPECTED_PROMOTION", "blocked_reason":blocked_reason,
              "live_database_unchanged":comparison["delta"] == {key:0 for key in comparison["delta"]}}
    (run_dir / "scenario_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="AutoQ-Guard 격리·승인 통합 시나리오")
    parser.add_argument("--output-root", type=Path, default=root / "results" / "staging_promotion_scenario")
    args = parser.parse_args()
    result = run_scenario(root, args.output_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
