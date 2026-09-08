"""AutoQ-Guard의 선택형 제조 도메인 프로필.

프로필은 표시 용어와 연동 설명만 바꾼다. 핵심 위험분석, 승인 게이트,
데이터베이스 스키마는 자동차 기본 프로필과 동일하게 유지한다.
"""

from __future__ import annotations

import os


PROFILES = {
    "automotive": {
        "id": "automotive",
        "name": "자동차 제조",
        "eyebrow": "AUTOMOTIVE QUALITY INTELLIGENCE",
        "headline": "자동차 품질 조기대응",
        "description": "부품 LOT과 차량 VIN을 연결해 위험을 조기에 찾고 대응 우선순위와 예상 손익을 확인합니다.",
        "trace_label": "영향 VIN",
        "trace_help": "장착 차량 추적",
        "entity_label": "차량",
        "claim_label": "보증수리",
        "process_examples": ["부품 입고", "조립", "공정검사", "출고"],
        "disclaimer": "공개·합성 자동차 데이터 기반 PoC",
    },
    "medical_device": {
        "id": "medical_device",
        "name": "의료기기 제조",
        "eyebrow": "MEDICAL DEVICE QUALITY INTELLIGENCE",
        "headline": "의료기기 LOT 품질 조기대응",
        "description": "원자재·튜브 LOT과 완제품 배치를 연결해 검사 이상과 영향 범위를 조기에 확인합니다.",
        "trace_label": "영향 배치",
        "trace_help": "완제품 제조배치 추적",
        "entity_label": "완제품 배치",
        "claim_label": "반품·고객불만",
        "process_examples": ["원자재 입고", "압출·조립", "누설·외관검사", "포장·출하"],
        "disclaimer": "공개 기업정보를 참고한 합성 의료기기 데이터 기반 PoC · 실제 기업 내부 데이터 미사용",
    },
    "general_manufacturing": {
        "id": "general_manufacturing",
        "name": "일반 제조",
        "eyebrow": "MANUFACTURING QUALITY INTELLIGENCE",
        "headline": "제조 품질 조기대응",
        "description": "자재 LOT과 생산 배치를 연결해 공정 이상, 영향 제품과 예상 손실을 조기에 확인합니다.",
        "trace_label": "영향 제품",
        "trace_help": "생산 배치 추적",
        "entity_label": "생산 배치",
        "claim_label": "반품·품질비용",
        "process_examples": ["자재 입고", "생산", "품질검사", "출하"],
        "disclaimer": "합성 일반 제조 데이터 기반 PoC · 적용 전 기업 데이터와 공정 기준으로 재검증 필요",
    },
}


def profile_catalog(default_profile: str | None = None, n8n_enabled: bool | None = None) -> dict:
    """허용된 프로필과 선택형 n8n 연동 상태를 반환한다."""
    selected = default_profile or os.getenv("AUTOQ_DEFAULT_PROFILE", "automotive")
    if selected not in PROFILES:
        selected = "automotive"
    enabled = n8n_enabled
    if enabled is None:
        enabled = os.getenv("AUTOQ_N8N_INTEGRATION", "false").strip().lower() in {"1", "true", "yes", "on"}
    return {
        "status": "READY",
        "default_profile": selected,
        "n8n_integration": bool(enabled),
        "integration_mode": "N8N_OPTIONAL" if enabled else "STANDALONE",
        "profiles": list(PROFILES.values()),
        "notice": "프로필은 표시·매핑 계층만 전환하며 핵심 분석과 승인 안전장치는 그대로 유지됩니다.",
    }
