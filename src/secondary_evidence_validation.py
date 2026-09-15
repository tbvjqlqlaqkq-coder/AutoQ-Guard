"""경계점수 SAFETY LOT를 독립적인 2차 증거로 재분류한다."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path

SIGNAL_FIELDS = ["lot_id", "repeat_anomaly_count", "early_claim_count", "failure_code_concentration", "supplier_repeat_count"]

def _read(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))

def evidence_score(row: dict[str, str]) -> int:
    score = 0
    if int(row["repeat_anomaly_count"]) >= 2: score += 30
    if int(row["early_claim_count"]) >= 2: score += 30
    if float(row["failure_code_concentration"]) >= 0.6: score += 25
    if int(row["supplier_repeat_count"]) >= 2: score += 15
    return score

def evaluate(truth_file: Path, risk_file: Path, signal_file: Path, output_file: Path | None = None, evidence_threshold: int = 60) -> dict[str, object]:
    truth = {r["lot_id"].upper(): r["is_injected_risk"].strip() == "1" for r in _read(truth_file)}
    risks = {r["lot_id"].upper(): r for r in _read(risk_file) if r["safety_class"].upper() == "SAFETY"}
    signals = {r["lot_id"].upper(): r for r in _read(signal_file)}
    if set(risks) != set(signals): raise ValueError("SAFETY 위험결과와 2차 증거 LOT가 일치하지 않습니다")
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}; decisions = []
    for lot_id, risk in risks.items():
        primary = float(risk["risk_score"]); secondary = evidence_score(signals[lot_id])
        predicted = primary >= 95 or (35 <= primary < 95 and secondary >= evidence_threshold)
        actual = truth[lot_id]; key = "tp" if actual and predicted else "fn" if actual else "fp" if predicted else "tn"; counts[key] += 1
        decisions.append({"lot_id": lot_id, "primary_score": primary, "secondary_score": secondary, "alert": predicted})
    counts["precision"] = round(counts["tp"]/(counts["tp"]+counts["fp"]),6) if counts["tp"]+counts["fp"] else 0.0
    counts["recall"] = round(counts["tp"]/(counts["tp"]+counts["fn"]),6) if counts["tp"]+counts["fn"] else 0.0
    result={"status":"READY","scope":"synthetic_secondary_evidence_test_only","evidence_threshold":evidence_threshold,"metrics":counts,"decisions":decisions,
            "data_boundary":"is_injected_risk는 평가에만 사용되며 evidence_score 입력에 포함되지 않습니다",
            "warning":"합성 2차 신호 기능시험이며 실제 기업 성능이 아닙니다"}
    if output_file:
        output_file.parent.mkdir(parents=True,exist_ok=True); output_file.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8-sig")
    return result

def build_synthetic_signals(truth_file: Path, risk_file: Path, output_file: Path) -> None:
    """재현 가능한 기능시험용 신호를 생성한다. 정답 사용 사실은 manifest에 공개한다."""
    truth={r["lot_id"].upper():r["is_injected_risk"].strip()=="1" for r in _read(truth_file)}
    safety=[r for r in _read(risk_file) if r["safety_class"].upper()=="SAFETY"]
    weak_true=[r["lot_id"].upper() for r in safety if truth[r["lot_id"].upper()] and float(r["risk_score"])==40]
    boundary_false=[r["lot_id"].upper() for r in safety if not truth[r["lot_id"].upper()] and float(r["risk_score"])==40]
    supported_true=set(weak_true[:4]); partial_true=set(weak_true[4:5]); misleading_false=set(boundary_false[:3]); rows=[]
    for r in safety:
        lot=r["lot_id"].upper(); supported=lot in supported_true or lot in misleading_false
        partial=lot in partial_true
        rows.append({"lot_id":lot,"repeat_anomaly_count":3 if supported else 1 if partial else 0,"early_claim_count":2 if supported else 1 if partial else 0,"failure_code_concentration":"0.80" if supported else "0.55" if partial else "0.10","supplier_repeat_count":2 if supported else 1 if partial else 0})
    output_file.parent.mkdir(parents=True,exist_ok=True)
    with output_file.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=SIGNAL_FIELDS); writer.writeheader(); writer.writerows(rows)
    output_file.with_suffix(".manifest.json").write_text(json.dumps({"synthetic":True,"label_used_to_construct_fixture":True,"supported_weak_true":len(supported_true),"partial_weak_true":len(partial_true),"misleading_normal":len(misleading_false)},ensure_ascii=False,indent=2),encoding="utf-8-sig")

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("truth_file",type=Path); parser.add_argument("risk_file",type=Path); parser.add_argument("--signals",type=Path,default=Path("results/secondary_evidence/signals.csv")); parser.add_argument("--output",type=Path,default=Path("results/secondary_evidence/evaluation.json")); args=parser.parse_args()
    build_synthetic_signals(args.truth_file,args.risk_file,args.signals); print(json.dumps(evaluate(args.truth_file,args.risk_file,args.signals,args.output),ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
