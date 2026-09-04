# 검증 후 배포 구조

2026-09-04. 공개 데모의 코드 업로드와 검증·배포 순서를 하나의 워크플로로 연결했다.

## 실행 순서

1. main 또는 pull request 변경에서 Python 3.10·3.12 시험을 각각 실행한다.
2. 두 환경 모두 전체 테스트와 공개 경보 화면 산출물 일치 검사를 실행한다.
3. pull request에서는 배포하지 않는다.
4. main push에서 두 테스트 작업이 모두 성공했을 때만 `deploy` 작업이 시작된다.
5. 저장소의 `docs` 폴더를 별도 Pages 산출물로 만들고 배포한다.

`deploy.needs: test`가 배포 의존성을 만든다. 어느 하나라도 실패하면 deploy 작업은 건너뛰며 마지막으로 성공한 공개 화면은 유지된다. 같은 브랜치에서 새 실행이 시작되면 이전 진행 중 실행은 취소한다.

## 활성화 조건

저장소 Settings → Pages → Build and deployment의 Source가 **GitHub Actions**여야 이 워크플로가 배포 주체가 된다. 기존 `Deploy from a branch`가 남아 있으면 GitHub의 별도 `pages-build-deployment`가 CI와 무관하게 실행될 수 있으므로 아직 차단 구조가 완성된 것이 아니다.

워크플로 파일을 먼저 커밋한 뒤 Pages Source를 GitHub Actions로 바꾸고, 이 커밋의 test와 deploy가 모두 성공하는지 확인해야 활성화 완료로 판단한다.

## 한계

- GitHub Actions 공급망 자체와 관리자에 의한 수동 설정 변경까지 막지는 않는다.
- `docs` 안의 정적 파일을 배포하므로 서버 로그인·PostgreSQL은 공개 데모에 포함되지 않는다.
- 브랜치 보호나 승인 환경은 별도 보안 강화 항목이다.
- 배포 성공은 화면 전달 성공이지 실제 기업 성능·리콜 예방·ROI 입증이 아니다.
