"""기업 자동차 품질데이터 입력 전용 검증기.

원본 파일을 수정하지 않고 스키마, 자료형, 범위, 중복, 참조관계를 검사한다.
ERROR가 한 건이라도 있으면 분석 단계로 넘기지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


SCHEMAS = {
    "part_lot.csv": {
        "required": ["lot_id", "supplier_id", "part_number", "safety_class", "received_at", "quantity"],
        "primary_key": ["lot_id"],
        "types": {"safety_class": "safety_class", "received_at": "datetime", "quantity": "positive_int"},
    },
    "process_inspection.csv": {
        "required": ["inspection_id", "lot_id", "process_id", "measured_at", "process_z", "recheck_rate"],
        "primary_key": ["inspection_id"],
        "types": {
            "measured_at": "datetime",
            "process_z": "finite_number",
            "recheck_rate": "rate",
        },
    },
    "vehicle_build.csv": {
        "required": ["vin", "lot_id", "model", "production_at", "shipment_status"],
        "primary_key": ["vin", "lot_id"],
        "types": {"vin": "vin", "production_at": "datetime", "shipment_status": "shipment_status"},
    },
    "warranty_claim.csv": {
        "required": ["claim_id", "vin", "claim_at", "failure_code", "repair_cost_krw"],
        "primary_key": ["claim_id"],
        "types": {"vin": "vin", "claim_at": "datetime", "repair_cost_krw": "nonnegative_number"},
    },
    "cost_master.csv": {
        "required": [
            "part_number", "early_action_cost_krw", "field_repair_cost_krw", "customer_compensation_krw"
        ],
        "primary_key": ["part_number"],
        "types": {
            "early_action_cost_krw": "nonnegative_number",
            "field_repair_cost_krw": "nonnegative_number",
            "customer_compensation_krw": "nonnegative_number",
        },
    },
}


@dataclass
class Issue:
    severity: str
    file: str
    row: int | None
    column: str | None
    code: str
    value: str
    message: str


def parse_datetime(value: str) -> datetime:
    cleaned = value.strip().replace("Z", "")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            pass
    raise ValueError("지원 날짜형식: YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, YYYY-MM-DDTHH:MM:SS")


def finite_number(value: str) -> float:
    number = float(value.replace(",", "").strip())
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError("유한한 숫자가 아닙니다")
    return number


def validate_value(kind: str, value: str) -> None:
    if kind == "datetime":
        parsed = parse_datetime(value)
        if parsed.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            raise ValueError("미래 날짜는 입력할 수 없습니다")
    elif kind == "positive_int":
        number = finite_number(value)
        if not number.is_integer() or number <= 0:
            raise ValueError("0보다 큰 정수여야 합니다")
    elif kind == "finite_number":
        finite_number(value)
    elif kind == "nonnegative_number":
        if finite_number(value) < 0:
            raise ValueError("0 이상의 숫자여야 합니다")
    elif kind == "rate":
        number = finite_number(value)
        if number < 0 or number > 1:
            raise ValueError("0~1 사이의 비율이어야 합니다. 8%는 0.08로 입력합니다")
    elif kind == "vin":
        if not VIN_PATTERN.fullmatch(value.strip().upper()):
            raise ValueError("VIN은 I, O, Q를 제외한 영문·숫자 17자리여야 합니다")
    elif kind == "safety_class":
        if value.strip().upper() not in {"SAFETY", "POWERTRAIN", "CONVENIENCE", "SOFTWARE"}:
            raise ValueError("SAFETY, POWERTRAIN, CONVENIENCE, SOFTWARE 중 하나여야 합니다")
    elif kind == "shipment_status":
        if value.strip().upper() not in {"BEFORE_SHIPMENT", "SHIPPED", "FIELD"}:
            raise ValueError("BEFORE_SHIPMENT, SHIPPED, FIELD 중 하나여야 합니다")
    else:
        raise ValueError(f"알 수 없는 검증 형식: {kind}")


def read_csv_safely(path: Path) -> tuple[list[dict[str, str]], list[str], str]:
    raw = path.read_bytes()
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(encoding)
            sample = text[:4096]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(text.splitlines(), dialect=dialect)
            headers = [header.strip() if header else "" for header in (reader.fieldnames or [])]
            rows = []
            for source in reader:
                rows.append({(key or "").strip(): (value or "").strip() for key, value in source.items()})
            return rows, headers, encoding
        except (UnicodeDecodeError, csv.Error) as exc:
            last_error = exc
    raise ValueError(f"UTF-8 또는 CP949 CSV로 읽을 수 없습니다: {last_error}")


def issue(issues: list[Issue], severity: str, file: str, row: int | None, column: str | None,
          code: str, value: object, message: str) -> None:
    issues.append(Issue(severity, file, row, column, code, str(value)[:200], message))


def validate_file(input_dir: Path, filename: str, issues: list[Issue]) -> tuple[list[dict[str, str]], str | None]:
    path = input_dir / filename
    schema = SCHEMAS[filename]
    if not path.exists():
        issue(issues, "ERROR", filename, None, None, "FILE_MISSING", "", "필수 파일이 없습니다")
        return [], None
    try:
        rows, headers, encoding = read_csv_safely(path)
    except Exception as exc:
        issue(issues, "ERROR", filename, None, None, "FILE_READ_ERROR", "", str(exc))
        return [], None

    duplicates = sorted({header for header in headers if headers.count(header) > 1 and header})
    for column in duplicates:
        issue(issues, "ERROR", filename, 1, column, "DUPLICATE_COLUMN", column, "동일한 열 이름이 중복됐습니다")
    missing_columns = [column for column in schema["required"] if column not in headers]
    for column in missing_columns:
        issue(issues, "ERROR", filename, 1, column, "COLUMN_MISSING", "", "필수 열이 없습니다")
    if missing_columns:
        return rows, encoding
    if not rows:
        issue(issues, "ERROR", filename, None, None, "FILE_EMPTY", "", "데이터 행이 없습니다")
        return rows, encoding

    seen_keys: dict[tuple[str, ...], int] = {}
    for index, row in enumerate(rows, start=2):
        for column in schema["required"]:
            if not row.get(column, "").strip():
                issue(issues, "ERROR", filename, index, column, "VALUE_MISSING", "", "필수값이 비어 있습니다")
        for column, kind in schema["types"].items():
            value = row.get(column, "").strip()
            if not value:
                continue
            try:
                validate_value(kind, value)
            except (ValueError, TypeError) as exc:
                issue(issues, "ERROR", filename, index, column, "INVALID_VALUE", value, str(exc))
        key = tuple(row.get(column, "").strip().upper() for column in schema["primary_key"])
        if all(key):
            if key in seen_keys:
                issue(issues, "ERROR", filename, index, ",".join(schema["primary_key"]), "DUPLICATE_KEY",
                      "|".join(key), f"{seen_keys[key]}번째 행과 기본키가 중복됐습니다")
            else:
                seen_keys[key] = index
    return rows, encoding


def validate_relationships(data: dict[str, list[dict[str, str]]], issues: list[Issue]) -> None:
    lot_ids = {row.get("lot_id", "").upper() for row in data.get("part_lot.csv", []) if row.get("lot_id")}
    vins = {row.get("vin", "").upper() for row in data.get("vehicle_build.csv", []) if row.get("vin")}
    parts = {row.get("part_number", "").upper() for row in data.get("cost_master.csv", []) if row.get("part_number")}

    for filename in ("process_inspection.csv", "vehicle_build.csv"):
        for index, row in enumerate(data.get(filename, []), start=2):
            lot_id = row.get("lot_id", "").upper()
            if lot_id and lot_id not in lot_ids:
                issue(issues, "ERROR", filename, index, "lot_id", "FK_LOT_NOT_FOUND", lot_id,
                      "part_lot.csv에서 해당 LOT를 찾을 수 없습니다")
    for index, row in enumerate(data.get("warranty_claim.csv", []), start=2):
        vin = row.get("vin", "").upper()
        if vin and vin not in vins:
            issue(issues, "ERROR", "warranty_claim.csv", index, "vin", "FK_VIN_NOT_FOUND", vin,
                  "vehicle_build.csv에서 해당 VIN을 찾을 수 없습니다")
    for index, row in enumerate(data.get("part_lot.csv", []), start=2):
        part = row.get("part_number", "").upper()
        if part and part not in parts:
            issue(issues, "WARNING", "part_lot.csv", index, "part_number", "COST_NOT_FOUND", part,
                  "cost_master.csv에 비용정보가 없어 ROI 계산에서 제외됩니다")


def write_reports(output_dir: Path, issues: list[Issue], file_stats: dict[str, dict[str, object]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "validation_issues.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(Issue("", "", None, None, "", "", "")).keys()))
        writer.writeheader()
        writer.writerows(asdict(item) for item in issues)
    errors = sum(item.severity == "ERROR" for item in issues)
    warnings = sum(item.severity == "WARNING" for item in issues)
    summary = {
        "status": "BLOCKED" if errors else "READY",
        "analysis_allowed": errors == 0,
        "error_count": errors,
        "warning_count": warnings,
        "files": file_stats,
        "message": "오류를 수정하기 전에는 분석을 실행할 수 없습니다" if errors else "필수 검사를 통과해 분석 단계로 전달할 수 있습니다",
    }
    (output_dir / "validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8-sig"
    )


def validate_directory(input_dir: Path, output_dir: Path) -> dict[str, object]:
    issues: list[Issue] = []
    data: dict[str, list[dict[str, str]]] = {}
    file_stats: dict[str, dict[str, object]] = {}
    for filename in SCHEMAS:
        rows, encoding = validate_file(input_dir, filename, issues)
        data[filename] = rows
        file_stats[filename] = {"rows": len(rows), "encoding": encoding}
    validate_relationships(data, issues)
    write_reports(output_dir, issues, file_stats)
    errors = sum(item.severity == "ERROR" for item in issues)
    return {"status": "BLOCKED" if errors else "READY", "errors": errors, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="기업 자동차 품질데이터 사전 오류검사")
    parser.add_argument("input_dir", type=Path, help="표준 CSV 5개가 들어 있는 폴더")
    parser.add_argument("--output-dir", type=Path, default=Path("results/enterprise_validation"))
    args = parser.parse_args()
    result = validate_directory(args.input_dir.resolve(), args.output_dir.resolve())
    print(f"검증결과: {result['status']} / 오류 {result['errors']}건")
    print(f"보고서: {(args.output_dir.resolve() / 'validation_summary.json')}")
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
