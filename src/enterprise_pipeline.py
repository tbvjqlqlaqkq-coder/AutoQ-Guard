"""기업 원본 데이터부터 검색 가능한 DB까지 실행하는 통합 파이프라인."""

from __future__ import annotations

import argparse
import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

from enterprise_database import build_database, search_database
from enterprise_import import import_and_validate
from enterprise_risk_analyzer import analyze


STAGES = ["IMPORT_VALIDATE", "RISK_ANALYSIS", "DATABASE_BUILD", "SMOKE_SEARCH"]


def _write_summary(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def run_pipeline(raw_dir: Path, mapping_file: Path, rules_file: Path, output_root: Path) -> dict:
    """모든 단계를 순서대로 실행한다. 실패 뒤 단계는 실행하지 않는다."""
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%SZ")
    output_root = output_root.resolve()
    run_dir = output_root / "runs" / run_id
    # 같은 초에 재실행해도 기존 결과를 덮지 않는다.
    suffix = 1
    while run_dir.exists():
        run_dir = output_root / "runs" / f"{run_id}_{suffix:02d}"
        suffix += 1
    run_dir.mkdir(parents=True)

    summary = {
        "pipeline_version": "1.0", "run_id": run_dir.name, "status": "RUNNING",
        "started_at_utc": started.isoformat(), "raw_dir": str(raw_dir.resolve()),
        "mapping_file": str(mapping_file.resolve()), "rules_file": str(rules_file.resolve()),
        "run_dir": str(run_dir),
        "stages": [{"name": name, "status": "NOT_RUN"} for name in STAGES],
    }

    def stage(name: str) -> dict:
        return next(item for item in summary["stages"] if item["name"] == name)

    try:
        stage("IMPORT_VALIDATE")["status"] = "RUNNING"
        imported = import_and_validate(raw_dir.resolve(), mapping_file.resolve(), run_dir / "01_import")
        stage("IMPORT_VALIDATE").update(status=imported["status"], result=imported)
        if imported["status"] != "READY":
            raise RuntimeError("기업 원본 변환 또는 데이터 검증 실패")

        stage("RISK_ANALYSIS")["status"] = "RUNNING"
        analyzed = analyze(run_dir / "01_import" / "standardized", run_dir / "02_analysis", rules_file.resolve())
        stage("RISK_ANALYSIS").update(status=analyzed["status"], result=analyzed)
        if analyzed["status"] != "READY":
            raise RuntimeError("위험분석 실행 차단")

        stage("DATABASE_BUILD")["status"] = "RUNNING"
        built = build_database(
            run_dir / "01_import" / "standardized", run_dir / "02_analysis",
            run_dir / "03_database" / "automotive_quality.db", run_dir / "03_database",
        )
        stage("DATABASE_BUILD").update(status=built["status"], result=built)
        if built["status"] != "READY":
            raise RuntimeError("데이터베이스 구축 차단")

        stage("SMOKE_SEARCH")["status"] = "RUNNING"
        rows = search_database(run_dir / "03_database" / "automotive_quality.db", risk_level="HIGH")
        smoke = {"status": "READY", "high_risk_result_count": len(rows), "results": rows[:10]}
        _write_summary(run_dir / "04_smoke_search.json", smoke)
        stage("SMOKE_SEARCH").update(status="READY", result={"high_risk_result_count": len(rows)})

        summary["status"] = "READY"
        summary["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary["decision_gate_passed"] = bool(analyzed.get("decision_gate_passed"))
        summary["decision_notice"] = (
            "표본 기준 통과. 담당자 승인 후 의사결정 보조자료로 사용 가능"
            if summary["decision_gate_passed"] else
            "파이프라인은 정상이나 표본 기준 미달. 실제 운영·리콜 의사결정에는 사용 금지"
        )
        _write_summary(run_dir / "pipeline_summary.json", summary)

        # 정상 완료본만 current로 발행한다. 기존 정상본은 실패 실행으로 덮지 않는다.
        current = output_root / "current"
        publish = output_root / ".current_building"
        if publish.exists():
            shutil.rmtree(publish)
        shutil.copytree(run_dir, publish)
        backup = output_root / ".current_previous"
        if backup.exists():
            shutil.rmtree(backup)
        if current.exists():
            current.rename(backup)
        publish.rename(current)
        if backup.exists():
            shutil.rmtree(backup)
        summary["published_current"] = str(current)
        _write_summary(run_dir / "pipeline_summary.json", summary)
        _write_summary(current / "pipeline_summary.json", summary)
        return summary
    except Exception as exc:
        running = next((item for item in summary["stages"] if item["status"] == "RUNNING"), None)
        if running:
            running["status"] = "BLOCKED"
        summary["status"] = "BLOCKED"
        summary["failed_stage"] = running["name"] if running else next(
            (item["name"] for item in summary["stages"] if item["status"] == "BLOCKED"), "UNKNOWN"
        )
        summary["reason"] = str(exc)
        summary["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary["traceback_file"] = str(run_dir / "pipeline_error.txt")
        (run_dir / "pipeline_error.txt").write_text(traceback.format_exc(), encoding="utf-8-sig")
        _write_summary(run_dir / "pipeline_summary.json", summary)
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="기업 자동차 품질 통합 파이프라인")
    parser.add_argument("raw_dir", type=Path)
    parser.add_argument("mapping_file", type=Path)
    parser.add_argument("--rules", type=Path, default=Path("enterprise_data/enterprise_analysis_rules.json"))
    parser.add_argument("--output-root", type=Path, default=Path("results/enterprise_pipeline"))
    args = parser.parse_args()
    result = run_pipeline(args.raw_dir, args.mapping_file, args.rules, args.output_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
