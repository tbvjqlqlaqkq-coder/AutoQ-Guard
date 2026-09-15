"""경보되지 않은 경계점수 SAFETY LOT의 사람 검토 순위를 계산한다."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from secondary_evidence_validation import evidence_score

def _read(path:Path):
    with path.open(encoding="utf-8-sig",newline="") as handle:return list(csv.DictReader(handle))

def priority_score(signal:dict[str,str])->float:
    return round(min(int(signal["repeat_anomaly_count"]),3)*10 + min(int(signal["early_claim_count"]),3)*10 + float(signal["failure_code_concentration"])*30 + min(int(signal["supplier_repeat_count"]),3)*5,3)

def build_queue(truth_file:Path,risk_file:Path,signal_file:Path,daily_capacity:int=3,output_file:Path|None=None)->dict[str,object]:
    if daily_capacity<1:raise ValueError("daily_capacity는 1 이상이어야 합니다")
    truth={r["lot_id"].upper():r["is_injected_risk"].strip()=="1" for r in _read(truth_file)}
    risks={r["lot_id"].upper():r for r in _read(risk_file) if r["safety_class"].upper()=="SAFETY"}
    signals={r["lot_id"].upper():r for r in _read(signal_file)}
    if set(risks)!=set(signals):raise ValueError("SAFETY 위험결과와 2차 증거 LOT가 일치하지 않습니다")
    queue=[]
    for lot,risk in risks.items():
        primary=float(risk["risk_score"]); secondary=evidence_score(signals[lot]); already_alert=primary>=95 or (35<=primary<95 and secondary>=60)
        if 35<=primary<95 and not already_alert:
            queue.append({"lot_id":lot,"primary_score":primary,"secondary_score":secondary,"review_priority":priority_score(signals[lot])})
    queue.sort(key=lambda row:(-row["review_priority"],row["lot_id"]))
    for index,row in enumerate(queue):row["rank"]=index+1;row["review_day"]=index//daily_capacity+1
    true_watch=sum(1 for row in queue if truth[row["lot_id"]]); reviewed=queue[:daily_capacity]; found=sum(1 for row in reviewed if truth[row["lot_id"]])
    result={"status":"READY","scope":"synthetic_watch_capacity_test_only","daily_capacity":daily_capacity,"queue_count":len(queue),"true_defects_in_queue":true_watch,"day1_review_count":len(reviewed),"day1_true_defects_found":found,"day1_detection_rate":round(found/true_watch,6) if true_watch else 0.0,"queue":queue,"label_boundary":"정답은 사후 평가에만 사용되고 순위 계산에는 포함되지 않습니다","warning":"합성 용량시험이며 기업 인력계획이 아닙니다"}
    if output_file:
        output_file.parent.mkdir(parents=True,exist_ok=True);output_file.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8-sig")
    return result

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("truth_file",type=Path);p.add_argument("risk_file",type=Path);p.add_argument("signal_file",type=Path);p.add_argument("--capacity",type=int,default=3);p.add_argument("--output",type=Path,default=Path("results/watch_review_queue.json"));a=p.parse_args();print(json.dumps(build_queue(a.truth_file,a.risk_file,a.signal_file,a.capacity,a.output),ensure_ascii=False,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
