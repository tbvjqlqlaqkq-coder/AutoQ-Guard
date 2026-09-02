# 공개자료·기업자료 통합 설계

## 목적

공개 리콜·불만·조사 자료와 기업의 LOT·공정검사·VIN·보증수리 자료를 한 실행 흐름에서 검사한다. 다만 공개자료에는 기업 내부 LOT·VIN 연결키가 없으므로 임의로 결합하지 않는다.

## 증거 경계

| 자료 | 단위 | 역할 |
|---|---|---|
| 공개자료 | 브랜드·모델·연식·부품계통·월 | 외부 선행신호와 과거 리콜 결과 검증 |
| 기업자료 | LOT·검사·VIN·보증수리·비용 | 위험 LOT, 영향 차량, 예상 손익 산출 |

`public_data_adapter.py`는 두 공개 CSV의 필수 열, 날짜, 숫자, 판정값, 중복을 검사하고 SHA-256과 입력 행 수를 기록한다. 정상일 때만 `normalized_public_signals.csv`를 발행한다.

## 실행

```bash
python src/enterprise_pipeline.py enterprise_data/demo_company_raw enterprise_data/demo_company_mapping.json --public-dir data/public
```

실행 결과의 `00_public_evidence`는 공개 증거, `01_import` 이후는 기업자료 처리 결과다. 어느 한쪽에서 오류가 발생하면 뒤 단계가 중단되고 기존 `current` 정상본은 보존된다.

## 기업 실증 시 추가할 연결표

실제 기업 적용에서는 품질 담당자가 승인한 `모델·연식·부품번호 → 공개 부품계통` 매핑표가 필요하다. 자동 문자열 유사도로 LOT와 리콜을 직접 연결하지 않으며, 매핑 버전·승인자·유효기간을 기록해야 한다.
