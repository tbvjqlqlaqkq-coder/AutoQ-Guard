"""SAFETY 점수 임계값의 미탐·오탐 전선을 계산한다."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path

def _read(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))

def analyze(truth_file: Path, risk_file: Path, thresholds: list[int] | None = None, output_file: Path | None = None) -> dict[str, object]:
    thresholds = thresholds or list(range(20, 101, 5))
    truth = {r["lot_id"].upper(): r["is_injected_risk"].strip() == "1" for r in _read(truth_file)}
    safety = [r for r in _read(risk_file) if r["safety_class"].upper() == "SAFETY"]
    if not safety: raise ValueError("SAFETY 결과가 없습니다")
    rows = []
    for threshold in thresholds:
        tp = fp = fn = tn = 0
        for row in safety:
            actual = truth[row["lot_id"].upper()]; predicted = float(row["risk_score"]) >= threshold
            if actual and predicted: tp += 1
            elif actual: fn += 1
            elif predicted: fp += 1
            else: tn += 1
        rows.append({"threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                     "precision": round(tp / (tp + fp), 6) if tp + fp else 0.0,
                     "recall": round(tp / (tp + fn), 6) if tp + fn else 0.0})
    zero_miss = [r for r in rows if r["fn"] == 0]
    best_zero_miss = min(zero_miss, key=lambda r: (r["fp"], -r["threshold"])) if zero_miss else None
    score_groups: dict[str, dict[str, int]] = {}
    for row in safety:
        score = str(float(row["risk_score"])); group = score_groups.setdefault(score, {"true": 0, "false": 0})
        group["true" if truth[row["lot_id"].upper()] else "false"] += 1
    overlaps = {score: counts for score, counts in score_groups.items() if counts["true"] and counts["false"]}
    result = {"status": "READY", "scope": "synthetic_safety_threshold_only", "results": rows,
              "best_zero_miss": best_zero_miss, "overlapping_scores": overlaps,
              "threshold_alone_is_sufficient": not bool(overlaps),
              "next_requirement": "겹친 점수를 분리할 시간추세·검사유형·고장코드 등 추가 특징이 필요합니다" if overlaps else "기업자료로 임계값을 재검증합니다",
              "warning": "합성자료 민감도 시험이며 기업 운영 기준이 아닙니다"}
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True); output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("truth_file",type=Path); parser.add_argument("risk_file",type=Path); parser.add_argument("--output",type=Path,default=Path("results/safety_threshold_frontier.json")); args=parser.parse_args()
    print(json.dumps(analyze(args.truth_file,args.risk_file,output_file=args.output),ensure_ascii=False,indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
