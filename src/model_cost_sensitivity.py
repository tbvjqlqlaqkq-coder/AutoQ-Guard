"""Descriptive cost sensitivity of frozen predictions, not ROI or retuning."""
import hashlib, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def cost(m,ratio):
    if not math.isfinite(ratio) or ratio<0:raise ValueError('Nonnegative finite ratio required')
    return m['fp']+ratio*m['fn']

def crossing(a,b):
    d=a['fn']-b['fn']
    if d==0:return None
    r=(b['fp']-a['fp'])/d
    return r if r>=0 else None

def analyze(data):
    models={k:v for k,v in data['models'].items() if 'test' in v and 'validation' in v}
    for split in ('validation','test'):
        sizes={(v[split]['rows'],v[split]['positives']) for v in models.values()}
        if len(sizes)!=1:raise ValueError('Models must share evaluation population')
        for v in models.values():
            m=v[split]
            if sum(m[k] for k in ('tp','fp','fn','tn'))!=m['rows'] or m['tp']+m['fn']!=m['positives']:
                raise ValueError('Invalid confusion matrix')
    baselines={}
    for split in ('validation','test'):
        m=models['fixed_rule'][split]
        baselines[split]={'no_alert_reference':{'fp':0,'fn':m['positives']},
                          'all_alert_reference':{'fp':m['rows']-m['positives'],'fn':0}}
    scenarios=[]
    for ratio in (1,5,10,20,25,50,100):
        cv={k:cost(v['validation'],ratio) for k,v in models.items()}
        ct={k:cost(v['test'],ratio) for k,v in models.items()}
        selected=min(cv,key=cv.get)
        scenarios.append({'fn_to_fp_cost_ratio':ratio,'validation_costs':cv,'test_costs':ct,
          'validation_selected_model':selected,'selected_model_test_cost':ct[selected],
          'test_lowest_for_description_only':min(ct,key=ct.get),
          'reference_test_costs':{k:cost(v,ratio) for k,v in baselines['test'].items()}})
    return {'status':'DESCRIPTIVE_FROZEN_PREDICTION_COST_SENSITIVITY',
      'formula':'FP + ratio * FN; FP unit cost=1',
      'thresholds_reoptimized':False,'models_retrained':False,
      'crossings_fixed_vs_logistic':{s:crossing(models['fixed_rule'][s],models['logistic_regression'][s]) for s in ('validation','test')},
      'scenarios':scenarios,
      'limitations':['Unit is a group-month, not a recall campaign or vehicle.',
        'No cost for true-alert review, residual defects, implementation, recurring duplicate alerts, or compensation.',
        'Test crossings are descriptive and must not be used to claim independently selected optimal policy.',
        'No/all-alert references are mathematical controls, not operational safety recommendations.',
        'Ratios are hypothetical; no KRW savings or ROI demonstrated.']}

def main():
    source=ROOT/'docs/model_validation/purged_ml_results.json'
    result=analyze(json.loads(source.read_text(encoding='utf-8-sig')))
    result['source_result_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    out=ROOT/'results/model_cost_sensitivity';out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
