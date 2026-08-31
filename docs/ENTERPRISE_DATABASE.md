# 기업 데이터베이스 구축·조회

검증을 통과한 5개 표준 CSV와 위험분석 결과를 하나의 SQLite 파일로 묶는 단계입니다.

## 안전장치

- 적재 직전에 표준 데이터를 다시 검사합니다.
- 임시 데이터베이스에서 전체 적재와 무결성 검사를 끝낸 뒤 정상일 때만 운영 파일을 교체합니다.
- 실패하면 기존 정상 데이터베이스를 보존합니다.
- 원본 파일별 SHA-256과 스키마 버전을 기록합니다.
- 검색값은 매개변수 방식으로 전달해 SQL 삽입 공격과 특수문자 오류를 막습니다.
- 조회 결과는 최대 1,000건으로 제한합니다.

## 구축 결과

- 데이터베이스: `results/enterprise_database/automotive_quality.db`
- 구축 보고서: `results/enterprise_database/database_build_summary.json`
- 조회 예시: `results/enterprise_database/search_result.json`

이 단계는 검색 가능한 데이터 기반을 만든 것이며, 기업의 보안·권한·실시간 연계까지 완료했다는 뜻은 아닙니다.
