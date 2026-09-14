"""합성 정답 LOT와 파이프라인 경보를 비교해 탐지 지표를 계산한다."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate(truth_file: Path, risk_file: Path, output_file: Path | None = None,
             positive_levels: tuple[str, ...] = ("HIGH",)) -> dict[str, object]:
    truth_rows, risk_rows = _read(truth_file), _read(risk_file)
    truth = {row["lot_id"].upper(): row["is_injected_risk"].strip() == "1" for row in truth_rows}
    predicted = {row["lot_id"].upper(): row["risk_level"].upper() in positive_levels for row in risk_rows}
    missing_predictions = sorted(set(truth) - set(predicted))
    unknown_predictions = sorted(set(predicted) - set(truth))
    if missing_predictions or unknown_predictions:
        raise ValueError("정답표와 예측 결과의 LOT 집합이 일치하지 않습니다")

    tp = sum(truth[key] and predicted[key] for key in truth)
    fp = sum(not truth[key] and predicted[key] for key in truth)
    fn = sum(truth[key] and not predicted[key] for key in truth)
    tn = sum(not truth[key] and not predicted[key] for key in truth)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    result = {
        "evaluation_scope": "synthetic_functional_test_only",
        "positive_levels": list(positive_levels), "lots": len(truth),
        "true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
        "precision": round(precision, 6), "recall": round(recall, 6),
        "specificity": round(specificity, 6), "f1": round(f1, 6),
        "warning": "합성 규칙 정답에 대한 기능시험이며 실제 기업 탐지 성능이 아닙니다",
    }
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="합성 기업 파일럿 탐지 지표 평가")
    parser.add_argument("truth_file", type=Path)
    parser.add_argument("risk_file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("results/enterprise_pilot_fixture/evaluation.json"))
    args = parser.parse_args()
    print(json.dumps(evaluate(args.truth_file, args.risk_file, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
