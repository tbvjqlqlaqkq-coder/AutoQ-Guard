# 기업 파일럿 규모 합성데이터 드라이런

## 결론

AutoQ-Guard의 기존 기업 데이터 반입 파이프라인에 합성 원본 5종을 넣어 `1,000 LOT·10,000 LOT–VIN 연결·300 보증수리`를 오류 없이 처리했다. 이는 **기업 파일럿 규모에서 데이터 연결과 시스템 흐름이 작동한다는 기능시험**이며 실제 탐지 성능이나 기업 ROI 증명이 아니다.

## 시험 조건

| 항목 | 값 |
|---|---:|
| 난수 시드 | 20260909 |
| 부품 LOT | 1,000 |
| 공정검사 | 1,000 |
| LOT–VIN 장착연결 | 10,000 |
| 보증수리 | 300 |
| 비용 기준 | 20 |
| 의도적으로 주입한 공정 위험 LOT | 20 |

생성기는 [`src/generate_enterprise_pilot_fixture.py`](../src/generate_enterprise_pilot_fixture.py)이며 실제 기업명·VIN·협력사·비용정보를 포함하지 않는다.

## 실행 결과

| 단계 | 결과 |
|---|---|
| 기업 원본 5종 생성 | PASS |
| 열 매핑·형식·필수값 검사 | PASS, 오류 0건 |
| 참조관계 검사 | PASS |
| 위험 LOT 분석 | PASS |
| SQLite 후보 DB 구축 | PASS |
| 고위험 LOT 검색 | PASS |
| 합성 정답표 대조 | TP 20, FP 0, FN 0, TN 980 |
| 전체 자동검사 | 105개 통과, 2개 제외 |

위험분석은 기존 고정 규칙으로 고위험 LOT 20개, 관찰 LOT 50개, 영향 차량 연결 700건을 산출했다. 합성 정답표 기준 정밀도·재현율·F1은 모두 1.0이지만, 경보규칙을 만족하도록 주입한 명확한 공정 이상을 다시 찾은 결과다. 따라서 **평가 코드와 LOT 대조 기능이 작동한다는 증거일 뿐 실제 성능 또는 일반화 성능이 아니다.** 산출된 예방차량·손실·ROI도 합성 비용과 사전 가정의 결과이므로 기업 효과로 인용하지 않는다.

## 시험 중 실제로 잡힌 오류

최초 합성 VIN 접두사에 VIN 금지문자 `Q`가 포함되어 검증기가 차량 10,000건과 연결된 보증수리 300건을 차단했다. 생성 규칙을 허용문자로 수정한 뒤 동일 시험을 재실행해 통과했다. 이 사례는 잘못된 기업 입력이 분석으로 넘어가지 않는 사전 차단 기능이 작동함을 보여준다.

## 재현 방법

```powershell
python src/generate_enterprise_pilot_fixture.py --output-dir results/enterprise_pilot_fixture/raw
python src/enterprise_pipeline.py results/enterprise_pilot_fixture/raw enterprise_data/demo_company_mapping.json --output-root results/enterprise_pilot_fixture/pipeline
python -m unittest discover -s tests -p "test_*.py"
```

## 아직 남은 검증

- 실제 기업에서 가명처리한 LOT–VIN·공정검사·보증수리 표본 반입
- 시간순 학습/평가 분리와 결함 라벨 정의
- 현재 품질 대응 방식과 정밀도·재현율·선행기간·VIN 축소율 비교
- 실제 부품비·공임·물류·보상비로 ROI 재산정
- 기업 SSO·KMS·망분리·보안관제 환경 연동

따라서 현재 판정은 **기업 실증을 시작할 기술적 준비가 됨**이며 **기업 효과가 확정됨**은 아니다.
