"""로컬 대시보드의 동시 검색 안정성과 응답시간을 측정한다."""

from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from enterprise_dashboard import make_handler


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percent)))
    return ordered[index]


def run_concurrency_test(project_root: Path, requests: int = 1000, workers: int = 20) -> dict:
    stress_current = project_root / "results" / "enterprise_stress_test" / "pipeline" / "current"
    database = stress_current / "03_database" / "automotive_quality.db"
    summary = stress_current / "pipeline_summary.json"
    ui = project_root / "ui" / "index.html"
    if not database.exists():
        raise FileNotFoundError("대량 데이터베이스가 없습니다. 대량데이터_성능시험을 먼저 실행하세요.")

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(database, summary, ui))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    def request_one(index: int) -> dict:
        lot_id = f"LOT-{index % 2000:07d}"
        url = f"http://127.0.0.1:{port}/api/search?{urlencode({'lot_id': lot_id})}"
        started = time.perf_counter()
        try:
            with urlopen(url, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
                status_code = response.status
            elapsed = (time.perf_counter() - started) * 1000
            correct = status_code == 200 and payload.get("status") == "READY" and payload.get("count") == 10 and all(
                row.get("lot_id") == lot_id for row in payload.get("results", [])
            )
            return {"ok": correct, "ms": elapsed, "error": None if correct else "잘못된 검색 결과"}
        except Exception as exc:
            return {"ok": False, "ms": (time.perf_counter() - started) * 1000, "error": type(exc).__name__}

    wall_started = time.perf_counter()
    results = []
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(request_one, index) for index in range(requests)]
            for future in as_completed(futures):
                results.append(future.result())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    wall_seconds = time.perf_counter() - wall_started

    durations = [row["ms"] for row in results]
    successes = sum(row["ok"] for row in results)
    errors: dict[str, int] = {}
    for row in results:
        if row["error"]:
            errors[row["error"]] = errors.get(row["error"], 0) + 1
    checks = {
        "all_requests_completed": len(results) == requests,
        "success_rate_100_percent": successes == requests,
        "no_database_locked_error": not any("lock" in name.lower() for name in errors),
        "p95_under_1000ms": percentile(durations, 0.95) < 1000,
    }
    report = {
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "configuration": {"requests": requests, "concurrent_workers": workers, "database_lots": 2000, "database_vins": 20000},
        "results": {
            "completed_requests": len(results), "successful_requests": successes,
            "success_rate": successes / requests if requests else 0,
            "wall_seconds": round(wall_seconds, 3),
            "throughput_requests_per_second": round(requests / wall_seconds, 2) if wall_seconds else 0,
            "average_response_ms": round(statistics.mean(durations), 3) if durations else 0,
            "p50_response_ms": round(percentile(durations, 0.50), 3),
            "p95_response_ms": round(percentile(durations, 0.95), 3),
            "maximum_response_ms": round(max(durations), 3) if durations else 0,
            "errors": errors,
        },
        "checks": checks,
        "limitations": [
            "한 대의 PC 내부 통신 시험으로 실제 사내망 지연은 포함하지 않습니다.",
            "조회 전용 시험이며 여러 사용자가 동시에 데이터를 수정하는 상황은 포함하지 않습니다.",
            "기업 운영용 서버 규모와 사용자 수에 따른 별도 부하시험이 필요합니다.",
        ],
    }
    output = project_root / "results" / "enterprise_concurrency_test"
    output.mkdir(parents=True, exist_ok=True)
    (output / "concurrency_test_result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="자동차 품질 화면 동시접속 시험")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=20)
    args = parser.parse_args()
    if args.requests < 1 or args.workers < 1 or args.workers > 200:
        raise SystemExit("requests>=1, workers=1~200 이어야 합니다.")
    result = run_concurrency_test(Path(__file__).resolve().parents[1], args.requests, args.workers)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
