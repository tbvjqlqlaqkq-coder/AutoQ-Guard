"""Illustrative workload/break-even conditions, NOT measured enterprise ROI."""
import csv, hashlib, json, math
from collections import defaultdict, Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODELS=('fixed_rule','logistic_regression','random_forest')
KEY=('BRAND','MODEL','YEAR','CAT')

def simulate(rows,model,capacity,review_cost,monthly_cost,setup_cost,action_cost,success,overlap):
    vals=(capacity,review_cost,monthly_cost,setup_cost,action_cost,success,overlap)
    if any(not math.isfinite(x) or x<0 for x in vals) or capacity!=int(capacity):
        raise ValueError('Finite nonnegative values and integer capacity required')
    if success>1 or overlap>1:raise ValueError('Rates must be in [0,1]')
    months=defaultdict(list)
    seen=set()
    for r in rows:
        k=tuple(r[x] for x in KEY)+(r['MONTH'],)
        if k in seen:raise ValueError('Duplicate group-month')
        seen.add(k)
        if int(r['Y12']) not in (0,1) or int(r[model]) not in (0,1):raise ValueError('Binary labels required')
        months[r['MONTH']].append(r)
    details=[]; repeated=Counter()
    for month,rs in sorted(months.items()):
        alarms=[r for r in rs if int(r[model])]
        for r in alarms:repeated[tuple(r[x] for x in KEY)]+=1
        n=len(alarms);tp=sum(int(r['Y12']) for r in alarms);done=min(capacity,n)
        # Uniform random review expectation: no use of Y12 to prioritize.
        p=done/n if n else 0
        details.append(dict(month=month,alerts=n,reviewed=done,unreviewed=n-done,
                            expected_reviewed_positive_rows=tp*p,expected_reviewed_negative_rows=(n-tp)*p))
    reviewed=sum(x['reviewed'] for x in details)
    positive=sum(x['expected_reviewed_positive_rows'] for x in details)
    units=positive*success*(1-overlap)
    total=setup_cost+monthly_cost*len(months)+review_cost*reviewed+action_cost*positive
    return dict(model=model,monthly_capacity=capacity,months=details,
      alerts=sum(x['alerts'] for x in details),reviewed=reviewed,
      unreviewed=sum(x['unreviewed'] for x in details),
      unique_alerted_groups=len(repeated),repeat_alert_rows=sum(v-1 for v in repeated.values()),
      expected_reviewed_positive_rows=positive,
      hypothetical_incremental_effective_positive_row_units=units,
      assumed_incremental_cost_krw=total,
      break_even_avoided_loss_krw_per_positive_row_unit=total/units if units>0 else None)

def main():
    source=ROOT/'results/purged_ml/test_predictions.csv'
    with source.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    assumptions=dict(review_cost=50000,monthly_cost=500000,setup_cost=3000000,
                     action_cost=200000,success=0.5,overlap=0.3)
    result={'status':'ILLUSTRATIVE_BREAK_EVEN_NOT_ENTERPRISE_ROI',
      'assumptions':assumptions,'assumption_origin':'Illustrative placeholders, not company observations or market quotes',
      'review_policy':'Uniform random review expectation within month; no backlog carryover, no oracle prioritization',
      'baseline':'Existing response held unchanged; overlap reduces hypothetical incremental benefit; no claim of actual baseline measurement',
      'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'scenarios':[simulate(rows,m,c,**assumptions) for c in (50,100,300) for m in MODELS],
      'limitations':['Positive group-months are not incidents, faulty parts, campaigns, or vehicles.',
        'Repeated positive months may concern the same recall: do not multiply by a campaign-level loss.',
        'Expected review positives describe retrospective association, not proven actionable defects.',
        'Unreviewed alerts are dropped for this scenario, not queued into later months.',
        'No actual prevention, customer benefit, savings or ROI is established.',
        'Safety response is not overridden by capacity or cost limits.']}
    out=ROOT/'results/capacity_break_even';out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for s in result['scenarios']:
        print(json.dumps({k:v for k,v in s.items() if k!='months'},ensure_ascii=False))

if __name__=='__main__':main()
