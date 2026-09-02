"""공개 리콜·선행신호 CSV를 출처가 추적되는 표준 증거자료로 변환한다.

공개자료에는 기업의 LOT·VIN 연결키가 없으므로 내부 생산자료와 임의 결합하지 않는다.
대신 브랜드·모델·연식·부품계통·월 단위의 외부 신호로 정규화하고 품질을 검사한다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from enterprise_data_validator import read_csv_safely


PANEL_FILE = "monthly_panel.csv"
RECALL_FILE = "recall_detection_12m.csv"
PANEL_REQUIRED = ["BRAND", "MODEL", "YEAR", "CAT", "MONTH", "COMPLAINTS", "SERIOUS", "INVESTIGATIONS", "ALERT"]
RECALL_REQUIRED = ["캠페인", "브랜드", "모델", "연식", "부품계통", "리콜월", "12개월판정", "잠재대상대수"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def _number(value: str, *, integer: bool = False, minimum: float = 0) -> float | int:
    number = float(value.replace(",", "").strip())
    if number != number or number in (float("inf"), float("-inf")) or number < minimum:
        raise ValueError(f"{minimum} 이상의 유한한 숫자가 아닙니다")
    if integer:
        if not number.is_integer():
            raise ValueError("정수가 아닙니다")
        return int(number)
    return number


def _month(value: str) -> str:
    cleaned = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m")
        except ValueError:
            pass
    raise ValueError("월 형식은 YYYY-MM 또는 YYYY-MM-DD여야 합니다")


def _check_headers(filename: str, headers: list[str], required: list[str], issues: list[dict]) -> bool:
    missing = [name for name in required if name not in headers]
    for name in missing:
        issues.append({"file": filename, "row": 1, "column": name, "code": "COLUMN_MISSING", "message": "필수 열이 없습니다"})
    return not missing


def adapt_public_data(input_dir: Path, output_dir: Path) -> dict:
    input_dir, output_dir = input_dir.resolve(), output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[dict] = []
    signals: list[dict] = []
    manifest = {
        "adapter_version": "1.0", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir), "linkage_policy": "AGGREGATE_ONLY_NO_LOT_VIN_JOIN", "files": {},
    }

    for filename, required in ((PANEL_FILE, PANEL_REQUIRED), (RECALL_FILE, RECALL_REQUIRED)):
        path = input_dir / filename
        if not path.exists():
            issues.append({"file": filename, "row": None, "column": None, "code": "FILE_MISSING", "message": "필수 공개자료가 없습니다"})
            continue
        try:
            rows, headers, encoding = read_csv_safely(path)
        except Exception as exc:
            issues.append({"file": filename, "row": None, "column": None, "code": "READ_ERROR", "message": str(exc)})
            continue
        manifest["files"][filename] = {"rows": len(rows), "encoding": encoding, "sha256": _sha256(path)}
        if not _check_headers(filename, headers, required, issues):
            continue
        for line, row in enumerate(rows, 2):
            try:
                if filename == PANEL_FILE:
                    signals.append({
                        "source_type": "MONTHLY_EARLY_SIGNAL", "brand": row["BRAND"].strip().upper(),
                        "model": row["MODEL"].strip().upper(), "model_year": _number(row["YEAR"], integer=True, minimum=1900),
                        "component_category": row["CAT"].strip().upper(), "event_month": _month(row["MONTH"]),
                        "complaints": _number(row["COMPLAINTS"]), "serious_cases": _number(row["SERIOUS"]),
                        "investigations": _number(row["INVESTIGATIONS"]), "alert": _number(row["ALERT"], integer=True),
                        "campaign_id": "", "recall_detected_12m": "", "potential_units": "",
                    })
                else:
                    detected = row["12개월판정"].strip()
                    if detected not in {"탐지", "미탐지"}:
                        raise ValueError("12개월판정은 탐지 또는 미탐지여야 합니다")
                    signals.append({
                        "source_type": "RECALL_OUTCOME", "brand": row["브랜드"].strip().upper(),
                        "model": row["모델"].strip().upper(), "model_year": _number(row["연식"], integer=True, minimum=1900),
                        "component_category": row["부품계통"].strip().upper(), "event_month": _month(row["리콜월"]),
                        "complaints": "", "serious_cases": "", "investigations": "", "alert": "",
                        "campaign_id": row["캠페인"].strip().upper(), "recall_detected_12m": detected,
                        "potential_units": _number(row["잠재대상대수"], integer=True),
                    })
            except (ValueError, KeyError) as exc:
                issues.append({"file": filename, "row": line, "column": None, "code": "INVALID_VALUE", "message": str(exc)})

    keys: set[tuple] = set()
    unique_signals = []
    for row in signals:
        key = (row["source_type"], row["brand"], row["model"], row["model_year"], row["component_category"], row["event_month"], row["campaign_id"])
        if key in keys:
            issues.append({"file": "normalized_public_signals.csv", "row": None, "column": None, "code": "DUPLICATE_SIGNAL", "message": "동일한 공개 신호 키가 중복됐습니다"})
        else:
            keys.add(key)
            unique_signals.append(row)

    fields = ["source_type", "brand", "model", "model_year", "component_category", "event_month", "complaints", "serious_cases", "investigations", "alert", "campaign_id", "recall_detected_12m", "potential_units"]
    if not issues:
        with (output_dir / "normalized_public_signals.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader(); writer.writerows(unique_signals)
    with (output_dir / "public_data_issues.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "row", "column", "code", "message"])
        writer.writeheader(); writer.writerows(issues)
    manifest.update(status="BLOCKED" if issues else "READY", error_count=len(issues), normalized_rows=len(unique_signals) if not issues else 0)
    (output_dir / "public_data_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="공개 리콜·선행신호 표준화 및 오류검사")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("results/public_adapter"))
    args = parser.parse_args()
    result = adapt_public_data(args.input_dir, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
