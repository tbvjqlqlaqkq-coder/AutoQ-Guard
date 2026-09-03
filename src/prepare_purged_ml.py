"""Prepare frozen temporal splits before model fitting; no ML dependency."""
import csv
import hashlib
import json
from datetime import date
from pathlib import Path
from mature_public_backtest import classify, label_end, month_end

ROOT=Path(__file__).resolve().parents[1]
FIT_AT=date(2023,1,1)
FREEZE_AT=date(2025,1,1)
OUTCOME_END=date(2026,6,30)

def split_rows(rows):
    tagged=classify(rows,OUTCOME_END)
    splits={'train':[],'validation':[],'test':[]}
    for r in tagged:
        if r['evaluation_status']!='EVALUABLE':continue
        if label_end(r['MONTH'])<FIT_AT:
            splits['train'].append(r)
        elif '2023-01-01'<=r['MONTH']<='2023-12-01' and label_end(r['MONTH'])<FREEZE_AT:
            splits['validation'].append(r)
        elif '2025-01-01'<=r['MONTH']<='2025-06-01':
            splits['test'].append(r)
    assert all(label_end(r['MONTH'])<FIT_AT for r in splits['train'])
    assert all(month_end(r['MONTH'])>=FIT_AT and label_end(r['MONTH'])<FREEZE_AT for r in splits['validation'])
    assert all(month_end(r['MONTH'])>=FREEZE_AT and label_end(r['MONTH'])<=OUTCOME_END for r in splits['test'])
    return splits

def main():
    source=ROOT/'data/public/monthly_panel.csv'
    with source.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    splits=split_rows(rows)
    out=ROOT/'results/purged_ml';out.mkdir(parents=True,exist_ok=True)
    report={'status':'SPLITS_VERIFIED_MODELS_NOT_TRAINED','fit_at':str(FIT_AT),
        'threshold_freeze_at':str(FREEZE_AT),'outcome_end':str(OUTCOME_END),
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'protocol':['Train model and preprocessing on train only; no refit before test.',
          'Select threshold using 2023 validation labels mature by end of 2024.',
          'Test only January-June 2025; do not tune from test results.',
          '2022 and 2024 feature rows excluded as temporal gaps.',
          'Keep same fixed-rule comparator and restricted first-signal cohort.',
          'Retrospective reanalysis: periods previously inspected, no new independent holdout.',
          'Historical publication content and I3 availability remain unverified.'], 'splits':{}}
    for name,rs in splits.items():
        if not rs:raise ValueError(f'Empty {name}')
        with (out/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
        report['splits'][name]={'rows':len(rs),'positive_rows':sum(int(r['Y12']) for r in rs),
          'first_month':min(r['MONTH'] for r in rs),'last_month':max(r['MONTH'] for r in rs),
          'last_label_end':str(max(label_end(r['MONTH']) for r in rs))}
    (out/'protocol.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
