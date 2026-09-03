"""Month-end, fully followed-up retrospective evaluation of the locked rule.

Cohort eligibility uses first observed signal, never future recall membership.
This is a restricted surveillance cohort, not all vehicles or an unseen holdout.
"""
import argparse
import calendar
import csv
import hashlib
import json
from collections import defaultdict, Counter
from datetime import date
from pathlib import Path
from public_validation_audit import rule, metrics

ROOT = Path(__file__).resolve().parents[1]
KEYS = ('BRAND','MODEL','YEAR','CAT')

def month_index(s):
    d=date.fromisoformat(s)
    return d.year*12+d.month-1

def month_end(s):
    d=date.fromisoformat(s)
    return d.replace(day=calendar.monthrange(d.year,d.month)[1])

def label_end(s, horizon=12):
    m=month_index(s)+horizon
    y,mo=divmod(m,12)
    return date(y,mo+1,calendar.monthrange(y,mo+1)[1])

def classify(rows, outcome_end):
    """Do not use labels or future events for eligibility or alert decisions."""
    groups=defaultdict(list)
    for r in rows: groups[tuple(r[k] for k in KEYS)].append(r)
    out=[]
    for key,rs in sorted(groups.items()):
        seen=False
        for r in sorted(rs,key=lambda x:x['MONTH']):
            seen=seen or any(float(r[k])>0 for k in ('COMPLAINTS','SERIOUS','INVESTIGATIONS'))
            mature=label_end(r['MONTH'])<=outcome_end
            status='UNOBSERVED_COHORT' if not seen else ('EVALUABLE' if mature else 'PENDING_FOLLOWUP')
            # All immature labels are withheld, including known positives.
            out.append({**r,'evaluation_status':status,'prediction_at':str(month_end(r['MONTH'])),
                        'label_window_end':str(label_end(r['MONTH'])),
                        'evaluation_label':int(r['Y12']) if status=='EVALUABLE' else None,
                        'prediction':rule(r)})
    return out

def evaluate(rows, outcome_end):
    tagged=classify(rows,outcome_end)
    test=[r for r in tagged if r['MONTH']>='2025-01-01']
    eligible=[r for r in test if r['evaluation_status']=='EVALUABLE']
    return tagged,{
        'status':'CORRECTED_RETROSPECTIVE_NOT_PROSPECTIVE_VALIDATION',
        'outcome_analysis_end':str(outcome_end),
        'outcome_end_basis':'Explicit truncation in original stage16/analyze.py; not a completeness certificate.',
        'prediction_time':'month end; outcomes are next 12 complete calendar months',
        'cohort':'from first observed complaint/serious/investigation signal; excludes never-observed groups',
        'rule_changed':False,'test_status_counts':dict(Counter(r['evaluation_status'] for r in test)),
        'full_followup_missing_test_rows':sum(label_end(r['MONTH'])>outcome_end for r in test),
        'corrected_test':metrics(eligible),
        'legacy_test_for_reference':metrics([r for r in rows if r['MONTH']>='2025-01-01']),
        'limitations':['Not an independent holdout; all periods previously examined.',
          'First-observed cohort is a restricted proxy, not historical fleet exposure; never-observed vehicles excluded.',
          'Stored Y12 and signal contents are used; historical publication snapshots unavailable.',
          'I3 opening dates are not verified public availability dates.',
          'No actual prevention rate, vehicle counts or monetary ROI is established.',
          'Legacy ML comparison is not used; purged mature-label retraining remains separate.']}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--panel',type=Path,default=ROOT/'data/public/monthly_panel.csv')
    parser.add_argument('--out',type=Path,default=ROOT/'results/mature_public_backtest')
    args=parser.parse_args()
    with args.panel.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    tagged,result=evaluate(rows,date(2026,6,30))
    result['source_sha256']=hashlib.sha256(args.panel.read_bytes()).hexdigest()
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    fields=list(KEYS)+['MONTH','prediction_at','label_window_end','evaluation_status','prediction','evaluation_label']
    with (args.out/'evaluation_rows.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(tagged)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
