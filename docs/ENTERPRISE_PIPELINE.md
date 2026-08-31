# 기업 데이터 통합 실행 파이프라인

기업 원본 데이터를 지정하면 다음 순서가 자동으로 실행됩니다.

1. 기업 형식에서 표준 형식으로 변환하고 오류 검사
2. LOT 위험도·영향 VIN·예상 손익 분석
3. 검색 가능한 SQLite 데이터베이스 구축
4. 고위험 데이터 시험 조회

중간 단계가 실패하면 이후 단계는 `NOT_RUN` 상태로 남고 실행되지 않습니다. 실패 실행은 `runs`에 별도로 보존되며, 마지막 정상 결과인 `current`를 덮어쓰지 않습니다.

`status=READY`는 프로그램 실행이 정상이라는 뜻입니다. `decision_gate_passed=false`이면 표본 부족 상태이므로 실제 출고보류·리콜 판단 근거로 사용하면 안 됩니다.

실행 파일: `기업데이터_전체통합실행.cmd`

주요 결과:

- `results/enterprise_pipeline/current/pipeline_summary.json`
- `results/enterprise_pipeline/current/03_database/automotive_quality.db`
- `results/enterprise_pipeline/current/04_smoke_search.json`
