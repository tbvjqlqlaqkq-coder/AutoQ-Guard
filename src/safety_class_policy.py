"""단일 임계값과 안전등급별 경보 정책을 비교한다."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path

DEFAULT_POLICY = {"SAFETY": 35, "POWERTRAIN": 45, "CONVENIENCE": 55, "SOFTWARE": 55}

def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

def _metrics(rows: list[dict[str, object]], thresholds: dict[str, int]) -> dict[str, object]:
    by_class: dict[str, dict[str, int]] = {}; total = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for row in rows:
        safety_class = str(row["safety_class"]); predicted = float(row["risk_score"]) >= thresholds[safety_class]; actual = bool(row["actual"])
        bucket = by_class.setdefault(safety_class, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        key = "tp" if actual and predicted else "fn" if actual else "fp" if predicted else "tn"
        bucket[key] += 1; total[key] += 1
    for bucket in [total, *by_class.values()]:
        bucket["precision"] = round(bucket["tp"] / (bucket["tp"] + bucket["fp"]), 6) if bucket["tp"] + bucket["fp"] else 0.0
        bucket["recall"] = round(bucket["tp"] / (bucket["tp"] + bucket["fn"]), 6) if bucket["tp"] + bucket["fn"] else 0.0
        bucket["alerts"] = bucket["tp"] + bucket["fp"]
    return {"thresholds": thresholds, "total": total, "by_class": by_class}

def compare(truth_file: Path, risk_file: Path, output_file: Path | None = None, baseline_threshold: int = 55, candidate_policy: dict[str, int] | None = None) -> dict[str, object]:
    truth = {r["lot_id"].upper(): r["is_injected_risk"].strip() == "1" for r in _read(truth_file)}
    risk_rows = _read(risk_file)
    if set(truth) != {r["lot_id"].upper() for r in risk_rows}: raise ValueError("정답표와 위험점수 결과의 LOT 집합이 일치하지 않습니다")
    rows = [{"safety_class": r["safety_class"].upper(), "risk_score": float(r["risk_score"]), "actual": truth[r["lot_id"].upper()]} for r in risk_rows]
    classes = sorted({str(r["safety_class"]) for r in rows}); candidate = dict(DEFAULT_POLICY if candidate_policy is None else candidate_policy)
    if set(candidate) != set(classes): raise ValueError("정책의 안전등급과 결과자료의 안전등급이 일치해야 합니다")
    baseline = _metrics(rows, {name: baseline_threshold for name in classes}); policy = _metrics(rows, candidate)
    result = {"status": "READY", "scope": "synthetic_policy_candidate_only", "baseline": baseline, "class_policy": policy,
              "delta": {"alerts": policy["total"]["alerts"] - baseline["total"]["alerts"], "false_negatives": policy["total"]["fn"] - baseline["total"]["fn"], "false_positives": policy["total"]["fp"] - baseline["total"]["fp"]},
              "governance": {"automatic_recall": False, "safety_alert_requires_human_review": True, "threshold_change_requires_approval": True},
              "warning": "합성자료에서 비교한 정책 후보이며 기업 운영 임계값 또는 실제 성능이 아닙니다"}
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True); output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description="안전등급별 경보 정책 비교"); parser.add_argument("truth_file", type=Path); parser.add_argument("risk_file", type=Path); parser.add_argument("--output", type=Path, default=Path("results/safety_class_policy.json")); args = parser.parse_args()
    print(json.dumps(compare(args.truth_file, args.risk_file, args.output), ensure_ascii=False, indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
