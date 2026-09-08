# 선택형 제조 프로필과 n8n 연동

AutoQ-Guard의 위험분석·후보 DB·운영 반영 게이트는 자동차 기본 구조 그대로 유지한다.
프로필은 화면 용어와 외부 데이터 매핑만 바꾸며 분석 결과를 과장하지 않는다.

## 실행 모드

- `AUTOQ_N8N_INTEGRATION=false`: 기존 독립 실행. CSV 반입과 대시보드가 종전과 동일하게 동작한다.
- `AUTOQ_N8N_INTEGRATION=true`: n8n을 선택형 오케스트레이션 계층으로 표시한다.
- `AUTOQ_DEFAULT_PROFILE`: `automotive`, `medical_device`, `general_manufacturing` 중 하나를 기본값으로 지정한다.

화면에서도 프로필을 바꿀 수 있다. 선택값은 해당 브라우저에만 저장되며 DB 스키마나 분석 결과를 변경하지 않는다.

## 의료기기 시연의 한계

의료기기 프로필은 공개 기업정보를 참고한 합성 데이터용이다. 특정 기업의 실제 MES·ERP,
원자재 규격, 공정 조건 또는 품질 성능을 재현한다고 주장하지 않는다.

## n8n 가져오기

`n8n/autoq-guard-optional-integration.json`을 n8n에서 Import from File로 불러온다.
워크플로는 기본적으로 비활성 상태이며, 면접 시연에서는 테스트 Webhook으로만 실행한다.
현재 파일은 LOT 필수값 검증, 프로필 정규화, AutoQ-Guard 단건 위험 미리보기 API 호출까지 담당한다.
HTTP Request 노드에는 Header Auth credential을 만들고 이름은 `AutoQ Integration Token`,
헤더 이름은 `X-AutoQ-Integration-Token`, 값은 서버의 `AUTOQ_INTEGRATION_TOKEN`과 같게 설정한다.

로컬 n8n은 기본 API 주소 `http://127.0.0.1:8878`을 사용할 수 있다. Docker에서 실행하면
주소를 `http://host.docker.internal:8878`로 바꿔야 하며, n8n Cloud에서는 로컬 주소에 직접
접근할 수 없으므로 별도 보안 배포 전까지 이 시연은 로컬 n8n 사용을 권장한다.

운영 시스템 연결 전에는 허용 IP, 재시도, 중복 이벤트 방지, 상세 감사로그와 사람의 최종 승인을 추가해야 한다.

## 대시보드 시작·중지 버튼

관리자는 대시보드의 `시작`과 `중지` 버튼으로 AutoQ-Guard의 n8n 이벤트 수신을 제어할 수 있다.
중지를 누르면 외부 품질 이벤트 API는 즉시 503으로 차단되지만 기존 대시보드와 핵심 분석은 계속 동작한다.
버튼은 n8n 프로그램 프로세스를 설치하거나 종료하지 않으며, 연동 통로만 안전하게 열고 닫는다.
서버를 다시 시작하면 `.env`의 `AUTOQ_N8N_INTEGRATION` 기본값으로 복원된다.
