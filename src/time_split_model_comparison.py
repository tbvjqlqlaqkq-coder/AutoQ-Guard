"""고정 경보규칙과 ML 모델을 시간순 분할로 비교한다."""
from __future__ import annotations
import csv, json, sys
from pathlib import Path
from datetime import datetime
import numpy as np

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"model_libs"))
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score,recall_score,f1_score,average_precision_score,roc_auc_score,confusion_matrix

NUM=["YEAR","COMPLAINTS","SERIOUS","INVESTIGATIONS","C3","P3","S3","I3"]
CAT=["BRAND","CAT"]

def load(path):
 rows=[]
 with path.open(encoding="utf-8-sig",newline="") as f:
  for r in csv.DictReader(f):
   month=datetime.strptime(r["MONTH"],"%Y-%m-%d")
   rows.append({**{k:float(r[k]) for k in NUM},**{k:r[k] for k in CAT},"month":month,"y":int(r["Y12"]),"rule":int(float(r["ALERT"]))})
 return rows

def xy(rows):
 return [[r[k] for k in NUM+CAT] for r in rows],np.array([r["y"] for r in rows])

def metric(y,pred,prob=None):
 tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
 out={"rows":len(y),"positives":int(y.sum()),"alerts":int(pred.sum()),"tp":int(tp),"fp":int(fp),"fn":int(fn),"tn":int(tn),
      "precision":precision_score(y,pred,zero_division=0),"recall":recall_score(y,pred,zero_division=0),"f1":f1_score(y,pred,zero_division=0),
      "cost_units_fp1_fn10":int(fp+10*fn)}
 if prob is not None:
  out["pr_auc"]=average_precision_score(y,prob); out["roc_auc"]=roc_auc_score(y,prob)
 return out

def threshold(y,prob,min_recall):
 candidates=np.arange(.05,.951,.01); best=None
 for t in candidates:
  m=metric(y,(prob>=t).astype(int))
  if m["recall"] < min_recall: continue
  key=(m["cost_units_fp1_fn10"],-m["recall"],-m["precision"])
  if best is None or key<best[0]: best=(key,float(round(t,2)),m)
 return best[1] if best else 0.05

def main():
 rows=load(ROOT/"monthly_panel.csv")
 train=[r for r in rows if r["month"]<datetime(2024,1,1)]
 valid=[r for r in rows if datetime(2024,1,1)<=r["month"]<datetime(2025,1,1)]
 test=[r for r in rows if r["month"]>=datetime(2025,1,1)]
 Xtr,ytr=xy(train); Xv,yv=xy(valid); Xt,yt=xy(test)
 numeric=Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler())])
 categorical=Pipeline([("impute",SimpleImputer(strategy="most_frequent")),("onehot",OneHotEncoder(handle_unknown="ignore"))])
 prep=ColumnTransformer([("num",numeric,list(range(len(NUM)))),("cat",categorical,list(range(len(NUM),len(NUM)+len(CAT))))])
 models={
  "logistic_regression":Pipeline([("prep",prep),("model",LogisticRegression(max_iter=2000,class_weight="balanced",random_state=20260805))]),
  "random_forest":Pipeline([("prep",prep),("model",RandomForestClassifier(n_estimators=300,min_samples_leaf=5,class_weight="balanced_subsample",random_state=20260805,n_jobs=-1))])}
 result={"method":"time_ordered_holdout","target":"recall within next 12 months (Y12)","split":{"train":"2020-01~2023-12","validation":"2024-01~2024-12","test":"2025-01~2026-06"},
         "threshold_policy":"validation cost minimum (FP=1, FN=10), subject to recall >= fixed-rule validation recall","features":NUM+CAT,"models":{}}
 rule_valid=metric(yv,np.array([r["rule"] for r in valid])); rule_test=metric(yt,np.array([r["rule"] for r in test]))
 result["models"]["fixed_rule"]={"threshold":"predefined ALERT rule","validation":rule_valid,"test":rule_test}
 for name,model in models.items():
  model.fit(Xtr,ytr); pv=model.predict_proba(Xv)[:,1]; t=threshold(yv,pv,rule_valid["recall"]); pt=model.predict_proba(Xt)[:,1]
  result["models"][name]={"threshold":t,"validation":metric(yv,(pv>=t).astype(int),pv),"test":metric(yt,(pt>=t).astype(int),pt)}
 result["dataset"]={"total":len(rows),"train":len(train),"validation":len(valid),"test":len(test),"test_positive_rate":float(yt.mean())}
 out=Path(__file__).resolve().parent/"results"; out.mkdir(exist_ok=True)
 (out/"model_comparison.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8-sig")
 with (out/"model_comparison.csv").open("w",encoding="utf-8-sig",newline="") as f:
  fields=["model","threshold","rows","positives","alerts","tp","fp","fn","tn","precision","recall","f1","pr_auc","roc_auc","cost_units_fp1_fn10"]
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for name,v in result["models"].items(): w.writerow({"model":name,"threshold":v["threshold"],**v["test"]})
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
