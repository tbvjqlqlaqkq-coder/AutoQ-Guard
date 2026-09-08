"""선택형 n8n MES 이벤트 수신과 단건 위험 미리보기."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from enterprise_risk_analyzer import risk_score
from manufacturing_profiles import PROFILES


def integration_enabled() -> bool:
    return os.getenv("AUTOQ_N8N_INTEGRATION", "false").strip().lower() in {"1", "true", "yes", "on"}


def integration_token() -> str:
    return os.getenv("AUTOQ_INTEGRATION_TOKEN", "")


def validate_token(supplied: str) -> bool:
    expected = integration_token()
    return len(expected) >= 16 and supplied == expected


def assess_quality_event(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("이벤트는 JSON 객체여야 합니다.")
    profile_id = str(payload.get("profile", "general_manufacturing")).strip()
    if profile_id not in PROFILES:
        raise ValueError("지원하지 않는 제조 프로필입니다.")
    lot_id = str(payload.get("lot_id", "")).strip().upper()
    process_id = str(payload.get("process_id", "")).strip().upper()
    if not lot_id or len(lot_id) > 100:
        raise ValueError("lot_id는 1~100자 필수값입니다.")
    if not process_id or len(process_id) > 100:
        raise ValueError("process_id는 1~100자 필수값입니다.")
    try:
        process_z = float(payload.get("process_z", 0))
        recheck_rate = float(payload.get("recheck_rate", 0))
        claim_count = int(payload.get("claim_count", 0))
        affected_count = int(payload.get("affected_count", 0))
        unit_loss_krw = float(payload.get("unit_loss_krw", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("수치 항목 형식이 올바르지 않습니다.") from exc
    if not (0 <= recheck_rate <= 1) or claim_count < 0 or affected_count < 0 or unit_loss_krw < 0:
        raise ValueError("비율·건수·비용은 허용 범위를 벗어날 수 없습니다.")
    safety_class = str(payload.get("safety_class", "SAFETY")).strip().upper()
    if safety_class not in {"SAFETY", "POWERTRAIN", "CONVENIENCE", "SOFTWARE"}:
        safety_class = "SAFETY"
    claim_rate = claim_count / affected_count if affected_count else 0
    score, reasons = risk_score(process_z, recheck_rate, claim_count, claim_rate, 0.02, safety_class)
    level = "HIGH" if score >= 55 else "WATCH" if score >= 25 else "NORMAL"
    actions = {
        "automotive": {"HIGH": "LOT 격리·영향 VIN 긴급 확인", "WATCH": "공정 재검·출고 전 확인", "NORMAL": "정상 추세 모니터링"},
        "medical_device": {"HIGH": "원자재 LOT 격리·영향 완제품 배치 누설검사", "WATCH": "공정조건 확인·표본 확대검사", "NORMAL": "정상 추세 모니터링"},
        "general_manufacturing": {"HIGH": "자재 LOT 격리·영향 생산배치 전수검토", "WATCH": "추가 품질검사·출하 전 확인", "NORMAL": "정상 추세 모니터링"},
    }
    estimated_loss = round(affected_count * unit_loss_krw)
    return {
        "status": "ANALYZED_PREVIEW",
        "mode": "OPTIONAL_N8N",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile_id,
        "profile_name": PROFILES[profile_id]["name"],
        "lot_id": lot_id,
        "process_id": process_id,
        "risk_score": score,
        "risk_level": level,
        "risk_reasons": reasons or ["경보기준 미만"],
        "affected_count": affected_count,
        "estimated_loss_krw": estimated_loss,
        "recommended_action": actions[profile_id][level],
        "decision_allowed": False,
        "notice": "단건 합성 이벤트의 규칙 기반 미리보기이며 실제 품질·리콜 의사결정에 사용할 수 없습니다.",
    }


def save_last_event(result: dict, status_file: Path) -> None:
    status_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = status_file.with_suffix(".next.json")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, status_file)


def integration_status(status_file: Path, enabled_override: bool | None = None) -> dict:
    enabled = integration_enabled() if enabled_override is None else bool(enabled_override)
    last = None
    if status_file.exists():
        try:
            last = json.loads(status_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            last = None
    return {
        "status": "READY" if enabled else "DISABLED",
        "enabled": enabled,
        "configured": len(integration_token()) >= 16,
        "last_event": last,
    }
