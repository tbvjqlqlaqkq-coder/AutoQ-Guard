"""Frozen, mature-label retrospective model comparison; never deploys models."""
import csv, hashlib, json, platform
from pathlib import Path
import numpy as np
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from prepare_purged_ml import split_rows
from public_validation_audit import rule
from time_split_model_comparison import metric

ROOT=Path(__file__).resolve().parents[1]
NUM=['YEAR','COMPLAINTS','SERIOUS','INVESTIGATIONS','C3','P3','S3','I3']
CAT=['BRAND','CAT']
SEED=20260805

def xy(rs):
    return [[float(r[k]) for k in NUM]+[r[k] for k in CAT] for r in rs],np.array([int(r['Y12']) for r in rs])

def choose_threshold(y,prob,min_recall):
    candidates=[]
    for n in range(5,96):
        t=n/100
        m=metric(y,(prob>=t).astype(int))
        if m['recall']>=min_recall:
            candidates.append(((m['cost_units_fp1_fn10'],-m['recall'],-m['precision'],t),t))
    return min(candidates)[1] if candidates else None

def preprocessing():
    return ColumnTransformer([
      ('num',Pipeline([('impute',SimpleImputer(strategy='median')),('scale',StandardScaler())]),list(range(len(NUM)))),
      ('cat',Pipeline([('impute',SimpleImputer(strategy='most_frequent')),('onehot',OneHotEncoder(handle_unknown='ignore'))]),list(range(len(NUM),len(NUM)+len(CAT))))])

def main():
    source=ROOT/'data/public/monthly_panel.csv'
    with source.open(encoding='utf-8-sig',newline='') as f:splits=split_rows(list(csv.DictReader(f)))
    tr,va,te=[splits[k] for k in ('train','validation','test')]
    Xtr,ytr=xy(tr);Xv,yv=xy(va);Xt,yt=xy(te)
    if any(len(np.unique(y))<2 for y in (ytr,yv,yt)):raise ValueError('Each split needs both classes')
    fixed_v=metric(yv,np.array([rule(r) for r in va]));fixed_t=metric(yt,np.array([rule(r) for r in te]))
    out=ROOT/'results/purged_ml';out.mkdir(parents=True,exist_ok=True)
    result={'status':'MATURE_LABEL_RETROSPECTIVE_COMPARISON','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'python':platform.python_version(),'sklearn':sklearn.__version__,'numpy':np.__version__,'seed':SEED,
      'features':NUM+CAT,'split_sizes':{k:len(v) for k,v in splits.items()},
      'threshold_policy':'Validation only: grid 0.05..0.95 step 0.01; FP+10*FN minimum subject to recall >= fixed rule; no feasible threshold means rejected.',
      'test_reused_period':True,'publication_history_verified':False,'model_refit_after_validation':False,
      'models':{'fixed_rule':{'validation':fixed_v,'test':fixed_t}},
      'cautions':['Restricted first-observed surveillance cohort, not entire fleet.',
        'Stored signal content and investigation publication dates remain unverified.',
        'Cost units are not KRW; no prevention or ROI established.',
        'Historical periods already examined; not an independent new holdout.']}
    models={
      'logistic_regression':LogisticRegression(max_iter=2000,class_weight='balanced',random_state=SEED),
      'random_forest':RandomForestClassifier(n_estimators=300,min_samples_leaf=5,class_weight='balanced_subsample',random_state=SEED,n_jobs=1)}
    preds={'fixed_rule':[rule(r) for r in te]}
    for name,est in models.items():
        print('Training '+name,flush=True)
        model=Pipeline([('prep',preprocessing()),('model',est)])
        model.fit(Xtr,ytr)
        pv=model.predict_proba(Xv)[:,1]
        threshold=choose_threshold(yv,pv,fixed_v['recall'])
        if threshold is None:
            result['models'][name]={'status':'REJECTED_NO_VALIDATION_THRESHOLD'};continue
        pt=model.predict_proba(Xt)[:,1];pred=(pt>=threshold).astype(int)
        preds[name]=pred
        result['models'][name]={'threshold':threshold,'validation':metric(yv,(pv>=threshold).astype(int),pv),
                               'test':metric(yt,pred,pt)}
    (out/'model_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'test_predictions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['BRAND','MODEL','YEAR','CAT','MONTH','Y12']
        w=csv.DictWriter(f,fieldnames=fields+list(preds));w.writeheader()
        for j,r in enumerate(te):w.writerow({**{k:r[k] for k in fields},**{k:int(v[j]) for k,v in preds.items()}})
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
