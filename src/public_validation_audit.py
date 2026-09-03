"""Read-only retrospective audit; does not tune rules or claim new holdout."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'data' / 'public'
OUT = Path(__file__).resolve().parents[1] / 'results' / 'public_validation_audit'

def read(name):
    with (SOURCE / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def rule(r):
    c, p, s, i = (float(r[k]) for k in ('C3', 'P3', 'S3', 'I3'))
    return int((c >= 5 and (p == 0 or c >= 2*p)) or s >= 2 or i >= 1)

def metrics(rows):
    counts = Counter((int(r['Y12']), rule(r)) for r in rows)
    tn, fp, fn, tp = (counts[k] for k in ((0,0),(0,1),(1,0),(1,1)))
    return dict(rows=len(rows), tp=tp, fp=fp, fn=fn, tn=tn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                false_positive_rate=fp/(fp+tn) if fp+tn else None,
                cost_units_fp1_fn10=fp+10*fn)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read('monthly_panel.csv')
    events = read('recall_detection_12m.csv')
    end = max(r['MONTH'] for r in rows)
    # Scenario only: panel end is NOT proof of outcome-feed completeness.
    cutoff = f'{int(end[:4])-1:04d}{end[4:]}'
    test = [r for r in rows if r['MONTH'] >= '2025-01-01']
    mature = [r for r in test if r['MONTH'] <= cutoff]
    immature = [r for r in test if r['MONTH'] > cutoff]
    keys = [(r['BRAND'],r['MODEL'],r['YEAR'],r['CAT'],r['MONTH']) for r in rows]
    campaigns = Counter(r['캠페인'] for r in events)
    campaign_detected = {r['캠페인'] for r in events if r['12개월판정'] == '탐지'}
    campaign_all_detected = {c for c in campaigns if all(r['12개월판정'] == '탐지' for r in events if r['캠페인'] == c)}
    result = {
        'status':'RETROSPECTIVE_AUDIT_NOT_NEW_HOLDOUT',
        'sha256':{n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() for n in ('monthly_panel.csv','recall_detection_12m.csv','dataset_summary.json')},
        'rule':'C3>=5 and (P3=0 or C3>=2*P3), or S3>=2, or I3>=1',
        'panel_rows':len(rows),'panel_end':end,
        'duplicate_group_month_rows':len(keys)-len(set(keys)),
        'stored_alert_rule_mismatches':sum(rule(r)!=int(r['ALERT']) for r in rows),
        'full_existing_test':metrics(test),
        'maturity_scenario':{'assumption':'outcome coverage ends at panel end; not verified',
            'last_eligible_month':cutoff,'eligible_test':metrics(mature),
            'excluded_test':metrics(immature)},
        'by_test_year':{y:metrics([r for r in test if r['MONTH'].startswith(y)]) for y in sorted({r['MONTH'][:4] for r in test})},
        'recall_table':{'rows':len(events),'unique_campaign_ids':len(campaigns),
                        'any_row_detected_campaigns':len(campaign_detected),
                        'all_rows_detected_campaigns':len(campaign_all_detected),
                        'any_row_detection_rate':len(campaign_detected)/len(campaigns) if campaigns else None,
                        'campaign_metric_note':'Descriptive regrouping of stored verdicts, not new backtest; any-row detection does not mean every vehicle is detected.',
                        'campaigns_with_multiple_rows':sum(v>1 for v in campaigns.values()),
                        'verdict_counts':dict(Counter(r['12개월판정'] for r in events))},
        'limitations':[
            'All supplied periods were already used in reported evaluation; no independent new holdout.',
            'Raw publication timestamps and outcome coverage date are not supplied in these aggregate tables.',
            'C3/P3/S3/I3 availability at prediction time is not established by rule reproduction.',
            '12-month training labels may overlap validation; historical fit dates and label maturity require audit.',
            'Recall table rows are campaign/model/year/category records, not unique campaigns or vehicles.',
            'Maturity scenario results use stored Y12 labels and are not an independently reconstructed ground truth.'
        ]
    }
    (OUT/'audit_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
