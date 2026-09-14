"""LOT 위험점수 임계값별 탐지 성능과 비용 가정을 비교한다."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sweep(truth_file: Path, risk_file: Path, thresholds: list[int] | None = None,
          defect_loss_krw: float = 5_000_000, review_cost_krw: float = 500_000,
          output_file: Path | None = None, current_threshold: int = 55) -> dict[str, object]:
    thresholds = thresholds or list(range(20, 81, 5))
    truth = {r["lot_id"].upper(): r["is_injected_risk"].strip() == "1" for r in _rows(truth_file)}
    scores = {r["lot_id"].upper(): float(r["risk_score"]) for r in _rows(risk_file)}
    if set(truth) != set(scores):
        raise ValueError("정답표와 위험점수 결과의 LOT 집합이 일치하지 않습니다")
    results = []
    for threshold in thresholds:
        predicted = {lot: score >= threshold for lot, score in scores.items()}
        tp = sum(truth[x] and predicted[x] for x in truth)
        fp = sum(not truth[x] and predicted[x] for x in truth)
        fn = sum(truth[x] and not predicted[x] for x in truth)
        tn = len(truth) - tp - fp - fn
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        review_cost = (tp + fp) * review_cost_krw
        avoided_loss = tp * defect_loss_krw
        missed_loss = fn * defect_loss_krw
        net_benefit = avoided_loss - review_cost
        results.append({
            "threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 6), "recall": round(recall, 6),
            "review_cost_krw": round(review_cost), "avoided_loss_krw": round(avoided_loss),
            "missed_loss_krw": round(missed_loss), "net_benefit_krw": round(net_benefit),
            "roi": round(net_benefit / review_cost, 6) if review_cost else 0.0,
        })
    best_net = max(r["net_benefit_krw"] for r in results)
    net_leaders = [r["threshold"] for r in results if r["net_benefit_krw"] == best_net]
    current = next((r for r in results if r["threshold"] == current_threshold), None)
    balanced = [r["threshold"] for r in results if r["precision"] >= 0.6 and r["recall"] >= 0.6]
    summary = {
        "status": "READY", "scope": "synthetic_assumption_test_only",
        "assumptions": {"defect_loss_per_lot_krw": defect_loss_krw,
                        "review_cost_per_alert_lot_krw": review_cost_krw},
        "current_threshold": current_threshold, "current": current,
        "net_benefit_leaders": net_leaders, "balanced_candidates": balanced, "results": results,
        "warning": "같은 합성자료에서 고른 후보값이며 기업 운영 임계값 또는 확정 ROI가 아닙니다",
    }
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="임계값별 탐지·비용 민감도 비교")
    parser.add_argument("truth_file", type=Path)
    parser.add_argument("risk_file", type=Path)
    parser.add_argument("--defect-loss", type=float, default=5_000_000)
    parser.add_argument("--review-cost", type=float, default=500_000)
    parser.add_argument("--output", type=Path, default=Path("results/threshold_tradeoff.json"))
    args = parser.parse_args()
    result = sweep(args.truth_file, args.risk_file, defect_loss_krw=args.defect_loss,
                   review_cost_krw=args.review_cost, output_file=args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
