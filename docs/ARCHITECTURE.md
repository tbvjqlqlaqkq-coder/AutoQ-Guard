# AutoQ-Guard 시스템 아키텍처

AutoQ-Guard는 부품 생산단위인 LOT에서 시작해 공정검사, 차량 VIN 장착이력, 보증수리·리콜 신호를 연결하고 위험도와 경제성을 함께 보여주는 자동차 품질 조기대응 PoC입니다.

## 전체 구조

```mermaid
flowchart TB
    subgraph INPUT[입력 데이터 계층]
        A1[공개 불만·조사·리콜]
        A2[부품 LOT·협력사]
        A3[공정 검사·재검·설비]
        A4[LOT–VIN 장착이력]
        A5[DTC·보증수리·클레임]
        A6[부품비·수리비·보상비]
    end

    subgraph GATE[기업 데이터 반입·품질 게이트]
        B1[CSV 열 매핑]
        B2[형식·필수값·중복 검사]
        B3[LOT·VIN 참조관계 검사]
        B4[격리 적재·승인 토큰]
        B5[오류 시 전체 ROLLBACK]
    end

    subgraph CORE[Python 분석·업무 계층]
        C1[고정 경보규칙]
        C2[시간순 백테스트]
        C3[위험 LOT 산출]
        C4[영향 VIN 특정]
        C5[대응 우선순위]
        C6[손실·비용·ROI 계산]
    end

    subgraph DB[데이터 계층]
        D1[(PostgreSQL\n기업형 12개 업무 테이블)]
        D2[(SQLite\n로컬 데모·회귀시험)]
    end

    subgraph API[서비스·보안 계층]
        E1[Python HTTP API]
        E2[세션·CSRF·입력 제한]
        E3[RBAC 권한 분리]
        E4[감사기록·HMAC 가명처리]
    end

    subgraph UI[사용자 화면]
        F1[종합 현황]
        F2[위험 분석]
        F3[LOT·VIN 상세 검색]
        F4[손익·ROI 시뮬레이터]
        F5[데이터 반입·관리자]
    end

    subgraph RUN[실행·검증·배포]
        G1[Docker Compose]
        G2[unittest 26개]
        G3[pgbench 동시조회]
        G4[GitHub Actions CI]
        G5[GitHub Pages 공개 데모]
    end

    A1 --> C2
    A2 & A3 & A4 & A5 & A6 --> B1
    B1 --> B2 --> B3 --> B4
    B2 -.실패.-> B5
    B3 -.실패.-> B5
    B4 --> D1
    B4 --> D2
    C2 --> C1
    D1 & D2 --> C1
    C1 --> C3 --> C4 --> C5 --> C6
    C3 & C4 & C6 --> D1
    D1 & D2 --> E1
    E2 & E3 & E4 --> E1
    E1 --> F1 & F2 & F3 & F4 & F5
    G1 --> D1
    G2 & G3 --> G4
    G4 --> G5
```

## 권한 구조

```mermaid
flowchart LR
    ADMIN[관리자] -->|계정·권한 관리| USERS[사용자 관리]
    ADMIN -->|로그인·검색·변경 확인| AUDIT[감사기록]
    QUALITY[품질담당자] -->|위험 LOT·VIN 조회| SEARCH[품질 검색]
    QUALITY -->|파일 사전검사| PREVIEW[반입 미리보기]
    VIEWER[조회자] -->|읽기 전용| DASH[대시보드]
    APPROVER[승인책임자] -->|승인 토큰| IMPORT[운영 데이터 반영]
    PREVIEW --> IMPORT
    IMPORT --> DASH
```

| 역할 | 허용 범위 | 허용하지 않는 범위 |
|---|---|---|
| 관리자 | 계정·권한·감사기록 관리 | 품질·리콜 최종 판단 자동화 |
| 품질담당자 | 위험조회, 검색, 데이터 사전검사 | 계정관리, 단독 운영반영 |
| 조회자 | 대시보드와 검색 | 데이터 반입·변경 |
| 승인책임자 | 검증 완료 데이터의 운영반영 승인 | 검사 실패 데이터 승인 |

## 공개 데모와 기업용 실행본의 경계

```mermaid
flowchart LR
    subgraph PUBLIC[GitHub Pages 공개 데모]
        P1[합성데이터]
        P2[위험 그래프]
        P3[읽기 전용 LOT 검색]
        P4[ROI 시뮬레이션]
    end

    subgraph ENTERPRISE[기업용 실행본]
        E1[로그인·세션]
        E2[역할별 권한]
        E3[기업 데이터 반입]
        E4[PostgreSQL]
        E5[감사기록]
    end

    PUBLIC -.화면·계산 구조 검증.-> ENTERPRISE
    ENTERPRISE --> NEED[기업 SSO·KMS·망분리·보안관제 추가 필요]
```

공개 데모에는 실제 개인정보, 기업 내부 데이터, 로그인 정보와 관리자 기능을 포함하지 않습니다. 기업 적용 시에는 데이터 항목 매핑과 시간순 재검증을 거쳐 실제 탐지율·오탐 비용·ROI를 다시 측정해야 합니다.

## 사용 기술과 역할

| 영역 | 기술 | 역할 |
|---|---|---|
| 분석·백엔드 | Python | 데이터 검증, 위험 산출, 영향 VIN 검색, ROI 계산, API |
| 운영 데이터베이스 | PostgreSQL | 12개 업무 테이블, 대량 적재, 인덱스 조회, 트랜잭션 |
| 로컬 시험 | SQLite | 데모 실행과 빠른 회귀시험 |
| 화면 | HTML, CSS, JavaScript | 대시보드, 그래프, 검색, ROI 조절, 관리자 화면 |
| 실행환경 | Docker Compose | Python·PostgreSQL 동일 실행환경 구성 |
| 보안 | PBKDF2, CSRF, 세션, RBAC, HMAC | 인증, 최소권한, 요청보호, 감사 식별자 가명처리 |
| 검증 | unittest, pgbench | 기능·보안·롤백·동시조회 검사 |
| 배포 | GitHub Actions, GitHub Pages | 자동 테스트와 읽기 전용 공개 데모 |

## 검증된 범위와 남은 범위

**검증 완료**

- LOT–검사–VIN–클레임 연결 구조
- 위험 LOT과 영향 차량 검색
- 잘못된 데이터의 반입 차단과 전체 롤백
- 20명·15초 동시조회 442,833건, 실패 0건
- Python 3.10·3.12 자동검사 26개 통과

**기업 데이터로 추가 검증 필요**

- 실제 생산라인 탐지율과 오탐 비용
- 실제 예방 차량 수와 절감액
- 기업 확정 ROI
- SSO·KMS·망 분리·보안관제·백업복구 연동

