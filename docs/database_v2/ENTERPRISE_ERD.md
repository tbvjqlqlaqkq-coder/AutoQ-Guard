# AutoQ-Guard Enterprise Data Model v2

현재 PoC의 7개 테이블을 기업 파일럿에 필요한 12개 업무 테이블로 정규화한 설계다. 기존 SQLite 실행본은 그대로 유지하고, 이 모델은 PostgreSQL 전환과 기업 데이터 매핑의 기준으로 사용한다.

```mermaid
erDiagram
    SUPPLIER ||--o{ PART_LOT : supplies
    PART ||--o{ PART_LOT : identifies
    PART_LOT ||--o{ PROCESS_INSPECTION : inspected
    PROCESS ||--o{ PROCESS_INSPECTION : measures
    VEHICLE ||--o{ VEHICLE_PART_INSTALLATION : contains
    PART_LOT ||--o{ VEHICLE_PART_INSTALLATION : installed_in
    VEHICLE ||--o{ WARRANTY_CLAIM : generates
    PART ||--o{ WARRANTY_CLAIM : concerns
    PART_LOT ||--o{ RISK_ASSESSMENT : evaluated
    RISK_ASSESSMENT ||--o{ AFFECTED_VEHICLE : scopes
    VEHICLE ||--o{ AFFECTED_VEHICLE : affected
    PART ||--o{ COST_POLICY : priced
    DATA_LOAD_BATCH ||--o{ PART_LOT : loaded_by
    DATA_LOAD_BATCH ||--o{ PROCESS_INSPECTION : loaded_by
    DATA_LOAD_BATCH ||--o{ VEHICLE_PART_INSTALLATION : loaded_by
    DATA_LOAD_BATCH ||--o{ WARRANTY_CLAIM : loaded_by

    SUPPLIER {
      text supplier_id PK
      text supplier_name
      boolean active
    }
    PART {
      text part_number PK
      text part_name
      text safety_class
      text commodity_group
    }
    PART_LOT {
      text lot_id PK
      text supplier_id FK
      text part_number FK
      timestamptz received_at
      integer quantity
      text batch_id FK
    }
    PROCESS {
      text process_id PK
      text process_name
      text plant_code
      text line_code
    }
    PROCESS_INSPECTION {
      text inspection_id PK
      text lot_id FK
      text process_id FK
      timestamptz measured_at
      numeric process_z
      numeric recheck_rate
      text batch_id FK
    }
    VEHICLE {
      text vehicle_key PK
      text model
      timestamptz production_at
      text shipment_status
    }
    VEHICLE_PART_INSTALLATION {
      text vehicle_key FK
      text lot_id FK
      timestamptz installed_at
      text station_code
      text batch_id FK
    }
    WARRANTY_CLAIM {
      text claim_id PK
      text vehicle_key FK
      text part_number FK
      timestamptz claim_at
      text failure_code
      numeric repair_cost_krw
      text batch_id FK
    }
    RISK_ASSESSMENT {
      bigint assessment_id PK
      text lot_id FK
      timestamptz assessed_at
      text model_version
      numeric risk_score
      text risk_level
      text action_code
      numeric estimated_direct_roi
    }
    AFFECTED_VEHICLE {
      bigint assessment_id FK
      text vehicle_key FK
      text lot_id FK
      text action_code
    }
    COST_POLICY {
      text part_number FK
      date effective_from
      numeric early_action_cost_krw
      numeric field_repair_cost_krw
      numeric customer_compensation_krw
    }
    DATA_LOAD_BATCH {
      text batch_id PK
      text source_system
      timestamptz loaded_at
      text source_hash
      text load_status
    }
```

## 기존 구조보다 개선된 점

- 공급사·부품·공정·차량을 별도 기준정보로 분리해 중복을 줄였다.
- VIN 원문 대신 가명화된 `vehicle_key` 사용을 기본으로 한다.
- 한 차량에 여러 LOT이 장착되는 현실을 설치이력 테이블로 표현한다.
- 위험평가 결과를 실행 시점과 모델 버전별로 누적해 재현할 수 있다.
- 비용 기준에 적용 시작일을 두어 과거 백테스트 당시 비용을 복원할 수 있다.
- 모든 원천 데이터에 적재 배치를 연결해 출처·해시·상태를 추적한다.

## 적용 원칙

1. 기존 SQLite v1은 포트폴리오 시연과 회귀시험용으로 보존한다.
2. PostgreSQL v2는 기업 파일럿용 목표 구조로 사용한다.
3. 실제 회사 컬럼은 표준 컬럼으로 매핑한 뒤 원천값을 변경하지 않고 별도 보존한다.
4. 위험평가는 원천 테이블을 수정하지 않고 새 평가 이력으로 적재한다.
