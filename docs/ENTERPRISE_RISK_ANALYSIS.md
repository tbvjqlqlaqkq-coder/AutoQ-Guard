# 3단계: 위험 LOT·대상 VIN·손익 분석

## 실행 조건

표준 데이터 5개를 다시 검사하며, 오류가 1건이라도 있으면 분석을 중단합니다. 이전 검증결과만 믿지 않고 분석 직전에 다시 검사합니다.

## 위험도 근거

- 공정편차: 2σ, 3σ 기준
- 재검률: 7%, 10% 기준
- 보증수리 건수와 LOT 장착차량 대비 수리율
- 안전 핵심부품과 주행 영향부품 가중치

규칙은 `enterprise_data/enterprise_analysis_rules.json`에 버전과 함께 저장됩니다. 기업 적용 시 품질부서가 기준을 승인해야 하며 임의로 바꾸면 재검증해야 합니다.

## 결과파일

- `lot_risk_results.csv`: LOT별 위험점수·근거·공정지표·수리율·대응방법·예상 손익
- `affected_vehicles.csv`: 고위험·관찰 LOT가 장착된 VIN과 출고상태
- `enterprise_analysis_summary.json`: 전체 고위험 LOT, 영향차량, 예상 예방대수와 프로그램 ROI
- `preanalysis_validation/`: 분석 직전 재검사 결과

## 해석 제한

위험점수는 조치 우선순위를 정하는 규칙 기반 지표입니다. 결함 확정이나 법적 리콜 결정을 자동으로 내리지 않습니다. ROI는 기업이 제공한 비용과 조치 성공률 가정에 따라 달라집니다.

LOT 10개, LOT-VIN 연결 100건, 보증수리 10건보다 적으면 `data_sufficiency`를 `INSUFFICIENT`로 표시하고 운영·리콜 의사결정 사용을 금지합니다. 이 기준은 기능 시연용 최소 Gate이며 기업 파일럿에서는 데이터 분포와 기간을 검토해 다시 승인해야 합니다.

## 실행

```text
python src/enterprise_risk_analyzer.py results/enterprise_import/standardized --output-dir results/enterprise_analysis
```
