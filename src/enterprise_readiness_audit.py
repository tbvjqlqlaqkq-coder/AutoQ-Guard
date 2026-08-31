"""프로젝트의 PoC 완료 증거와 기업 운영 미검증 항목을 자동 분리한다."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def audit(project: Path, run_tests: bool = True) -> dict:
    pipeline = read_json(project / "results/enterprise_pipeline/current/pipeline_summary.json")
    stress = read_json(project / "results/enterprise_stress_test/stress_test_result.json")
    concurrency = read_json(project / "results/enterprise_concurrency_test/concurrency_test_result.json")
    database = project / "results/enterprise_pipeline/current/03_database/automotive_quality.db"
    db_integrity = False
    if database.exists():
        connection = sqlite3.connect(database)
        try:
            db_integrity = connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            connection.close()

    test_result = {"executed": False, "passed": False, "return_code": None}
    if run_tests:
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=project, capture_output=True, text=True, timeout=120,
        )
        test_result = {
            "executed": True, "passed": completed.returncode == 0,
            "return_code": completed.returncode,
            "summary": (completed.stderr or completed.stdout).strip().splitlines()[-1] if (completed.stderr or completed.stdout).strip() else "",
        }

    poc_gates = [
        {"id": "P1", "name": "기업 형식 변환·오류검사", "passed": pipeline.get("stages", [{}])[0].get("status") == "READY" if pipeline.get("stages") else False},
        {"id": "P2", "name": "LOT 위험·VIN·손익 분석", "passed": pipeline.get("stages", [{}, {}])[1].get("status") == "READY" if len(pipeline.get("stages", [])) > 1 else False},
        {"id": "P3", "name": "검색 데이터베이스 무결성", "passed": db_integrity},
        {"id": "P4", "name": "검색 화면과 API", "passed": (project / "ui/index.html").exists() and (project / "src/enterprise_dashboard.py").exists()},
        {"id": "P5", "name": "2만 VIN 대량 처리시험", "passed": stress.get("status") == "PASSED" and stress.get("checks", {}).get("row_count_match") is True},
        {"id": "P6", "name": "20명·1천 요청 동시조회", "passed": concurrency.get("status") == "PASSED" and concurrency.get("results", {}).get("success_rate") == 1.0},
        {"id": "P7", "name": "전체 자동시험", "passed": test_result["passed"]},
    ]
    enterprise_gates = [
        {"id": "E1", "name": "실제 기업 데이터 예측 정확도 검증", "status": "NEEDS_COMPANY_DATA", "owner": "기업 품질·생산 부서"},
        {"id": "E2", "name": "실제 비용·예방률·ROI 확정", "status": "NEEDS_COMPANY_DATA", "owner": "기업 품질·재무 부서"},
        {"id": "E3", "name": "사내 인증·권한·개인정보·보안 심사", "status": "NEEDS_COMPANY_ENVIRONMENT", "owner": "기업 IT·보안 부서"},
        {"id": "E4", "name": "MES·QMS·ERP·보증시스템 연동", "status": "NEEDS_COMPANY_ENVIRONMENT", "owner": "기업 IT·현업 부서"},
        {"id": "E5", "name": "운영서버 장애복구·백업·모니터링", "status": "NEEDS_DEPLOYMENT", "owner": "기업 IT 운영 부서"},
        {"id": "E6", "name": "출고보류·리콜 판단 승인 절차", "status": "NEEDS_GOVERNANCE", "owner": "기업 품질·법무·경영 부서"},
    ]
    passed = sum(item["passed"] for item in poc_gates)
    report = {
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": "POC_COMPLETE_ENTERPRISE_VALIDATION_REQUIRED" if passed == len(poc_gates) else "POC_INCOMPLETE",
        "poc_readiness": {"passed": passed, "total": len(poc_gates), "gates": poc_gates},
        "enterprise_production_readiness": {"verified": 0, "total": len(enterprise_gates), "gates": enterprise_gates},
        "evidence": {
            "stress_pipeline_seconds": stress.get("performance", {}).get("pipeline_seconds"),
            "stress_average_search_ms": stress.get("performance", {}).get("average_search_ms"),
            "concurrency_success_rate": concurrency.get("results", {}).get("success_rate"),
            "concurrency_p95_ms": concurrency.get("results", {}).get("p95_response_ms"),
            "automated_tests": test_result,
        },
        "approved_claim": "공개·합성데이터로 기업 데이터 연결 구조와 PoC 작동성을 검증했으며, 기업 데이터 제공 시 정확도와 경제성을 검증할 준비가 됐습니다.",
        "prohibited_claims": [
            "실제 기업에서 리콜을 예방했다.", "실제 기업 ROI가 확정됐다.",
            "현대자동차·기아·협력사 시스템에 적용 완료됐다.", "실제 결함 예측 정확도가 검증됐다.",
        ],
    }
    output = project / "results/enterprise_readiness"
    output.mkdir(parents=True, exist_ok=True)
    (output / "readiness_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return report


def write_markdown(project: Path, report: dict) -> Path:
    poc = report["poc_readiness"]
    lines = [
        "# 자동차 품질 조기대응 프로젝트 최종 준비도 보고서", "",
        "## 최종 결론", "",
        f"- PoC 기술 검증: **{poc['passed']}/{poc['total']} 통과**",
        "- 기업 운영 검증: **기업 데이터·사내 환경이 없어 미확정**", "",
        "현재 단계는 기업 데이터를 받으면 파일 구조를 맞추고 정확도·손익 검증을 시작할 수 있는 완성형 PoC입니다. 기업 운영시스템 적용 완료 단계는 아닙니다.", "",
        "## 완료된 PoC 항목", "",
        "| 구분 | 항목 | 결과 |", "|---|---|---|",
    ]
    for gate in poc["gates"]:
        lines.append(f"| {gate['id']} | {gate['name']} | {'통과' if gate['passed'] else '미통과'} |")
    lines += ["", "## 기업에서 추가 검증할 항목", "", "| 구분 | 항목 | 필요한 주체 |", "|---|---|---|"]
    for gate in report["enterprise_production_readiness"]["gates"]:
        lines.append(f"| {gate['id']} | {gate['name']} | {gate['owner']} |")
    evidence = report["evidence"]
    lines += [
        "", "## 현재 성능 증거", "",
        f"- 2,000 LOT·20,000 VIN 전체 처리: {evidence['stress_pipeline_seconds']}초",
        f"- 단일 LOT 평균 검색: {evidence['stress_average_search_ms']}ms",
        f"- 20명·1,000건 동시조회 성공률: {evidence['concurrency_success_rate'] * 100:.0f}%",
        f"- 동시조회 95% 응답시간: {evidence['concurrency_p95_ms']}ms 이하", "",
        "## 기업·면접 제출 시 사용할 표현", "", f"> {report['approved_claim']}", "",
        "## 사용하면 안 되는 표현", "",
    ]
    lines += [f"- {claim}" for claim in report["prohibited_claims"]]
    path = project / "results/enterprise_readiness/최종_기업적용_준비도.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="자동차 품질 프로젝트 최종 준비도 점검")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    report = audit(project, run_tests=not args.skip_tests)
    markdown = write_markdown(project, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"보고서: {markdown}")
    return 0 if report["overall_status"] == "POC_COMPLETE_ENTERPRISE_VALIDATION_REQUIRED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
