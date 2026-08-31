# 1단계: 기업 데이터 오류검사 시스템

## 목적

기업 원본 데이터를 분석하기 전에 누락, 잘못된 형식, 중복, 연결 실패를 찾아 잘못된 결과가 생성되는 것을 차단합니다. 원본 파일은 수정하지 않습니다.

## 입력 파일

`enterprise_data/templates`에 있는 5개 CSV 형식을 기준으로 합니다.

1. `part_lot.csv`: 협력사·부품 LOT·입고정보
2. `process_inspection.csv`: 공정검사·편차·재검률
3. `vehicle_build.csv`: VIN과 장착 LOT 연결
4. `warranty_claim.csv`: 보증수리·고장코드·수리비
5. `cost_master.csv`: 출고 전후 조치비와 고객보상비

## 실행

프로젝트 폴더에서 다음 명령을 실행합니다.

```text
python src/enterprise_data_validator.py enterprise_data/templates --output-dir results/enterprise_validation
```

## 결과

- `validation_summary.json`: 분석 가능 여부, 오류·경고 건수, 파일별 행 수와 인코딩
- `validation_issues.csv`: 파일명, 행 번호, 열 이름, 오류코드, 입력값, 수정 설명

`status`가 `READY`일 때만 다음 분석 단계로 넘깁니다. `BLOCKED`이면 오류를 수정하기 전까지 분석을 실행하면 안 됩니다.

## 현재 검사 항목

- 필수 파일·필수 열·필수값
- UTF-8 또는 CP949 인코딩
- 날짜 형식과 미래 날짜
- 숫자, 양수, 비율 0~1
- VIN 17자리 형식
- 기본키 중복
- LOT가 부품 LOT 원장에 존재하는지
- 보증수리 VIN이 차량 조립이력에 존재하는지
- 부품별 비용정보가 존재하는지

## 다음 단계

기업마다 다른 열 이름을 이 표준 열 이름으로 연결하는 매핑 기능을 추가합니다. 예를 들어 기업의 `부품LOT번호`를 표준 `lot_id`로 변환합니다. 검증을 통과한 데이터만 위험도 분석과 화면에 전달합니다.
