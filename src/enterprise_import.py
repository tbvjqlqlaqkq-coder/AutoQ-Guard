"""기업별 원본 CSV를 프로젝트 표준형식으로 변환한 뒤 즉시 검증한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from enterprise_data_validator import Issue, SCHEMAS, read_csv_safely, validate_directory


TRANSFORMS = {"strip", "upper", "number", "integer", "percent_to_rate", "datetime"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_source_path(input_dir: Path, filename: str) -> Path:
    candidate = (input_dir / filename).resolve()
    base = input_dir.resolve()
    if candidate.parent != base:
        raise ValueError("source_file은 입력 폴더 바로 아래의 파일명만 사용할 수 있습니다")
    return candidate


def apply_transform(value: str, transform: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if transform == "strip":
        return cleaned
    if transform == "upper":
        return cleaned.upper()
    if transform == "number":
        return cleaned.replace(",", "")
    if transform == "integer":
        number = float(cleaned.replace(",", ""))
        if not number.is_integer():
            raise ValueError("정수로 변환할 수 없습니다")
        return str(int(number))
    if transform == "percent_to_rate":
        if cleaned.endswith("%"):
            number = float(cleaned[:-1].replace(",", "")) / 100
        else:
            number = float(cleaned.replace(",", ""))
        return f"{number:.10g}"
    if transform == "datetime":
        formats = (
            "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d", "%Y.%m.%d %H:%M:%S",
            "%Y/%m/%d", "%Y/%m/%d %H:%M:%S", "%Y%m%d", "%Y%m%d%H%M%S",
        )
        for fmt in formats:
            try:
                parsed = datetime.strptime(cleaned, fmt)
                return parsed.strftime("%Y-%m-%d" if parsed.hour == parsed.minute == parsed.second == 0 else "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        raise ValueError("지원되는 날짜형식으로 변환할 수 없습니다")
    raise ValueError(f"지원하지 않는 변환규칙입니다: {transform}")


def add_issue(issues: list[Issue], file: str, row: int | None, column: str | None,
              code: str, value: object, message: str) -> None:
    issues.append(Issue("ERROR", file, row, column, code, str(value)[:200], message))


def write_import_reports(output_dir: Path, issues: list[Issue], manifest: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir = output_dir.parent / "import_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    with (report_dir / "import_issues.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = ["severity", "file", "row", "column", "code", "value", "message"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(item) for item in issues)
    manifest["status"] = "BLOCKED" if issues else "CONVERTED"
    manifest["error_count"] = len(issues)
    (report_dir / "import_summary.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8-sig"
    )


def convert_table(input_dir: Path, output_dir: Path, standard_file: str, config: dict,
                  issues: list[Issue], manifest: dict) -> None:
    if standard_file not in SCHEMAS:
        add_issue(issues, standard_file, None, None, "UNKNOWN_STANDARD_TABLE", standard_file,
                  "지원하지 않는 표준 파일입니다")
        return
    source_name = config.get("source_file", "")
    if not source_name:
        add_issue(issues, standard_file, None, None, "SOURCE_FILE_UNSET", "", "source_file이 없습니다")
        return
    try:
        source = safe_source_path(input_dir, source_name)
    except ValueError as exc:
        add_issue(issues, standard_file, None, None, "UNSAFE_SOURCE_PATH", source_name, str(exc))
        return
    if not source.exists():
        add_issue(issues, source_name, None, None, "SOURCE_FILE_MISSING", "", "기업 원본 파일이 없습니다")
        return
    try:
        rows, headers, encoding = read_csv_safely(source)
    except Exception as exc:
        add_issue(issues, source_name, None, None, "SOURCE_READ_ERROR", "", str(exc))
        return

    column_map = config.get("columns", {})
    transforms = config.get("transforms", {})
    for canonical in SCHEMAS[standard_file]["required"]:
        source_column = column_map.get(canonical)
        if not source_column:
            add_issue(issues, source_name, 1, canonical, "MAPPING_MISSING", "", "표준 열에 연결된 기업 열이 없습니다")
        elif source_column not in headers:
            add_issue(issues, source_name, 1, canonical, "SOURCE_COLUMN_MISSING", source_column,
                      "매핑에 지정된 기업 열을 원본 파일에서 찾을 수 없습니다")
    for canonical, transform in transforms.items():
        if canonical not in SCHEMAS[standard_file]["required"] or transform not in TRANSFORMS:
            add_issue(issues, source_name, 1, canonical, "INVALID_TRANSFORM", transform, "변환규칙 설정이 올바르지 않습니다")
    if issues:
        return

    converted = []
    for index, row in enumerate(rows, start=2):
        target = {}
        for canonical in SCHEMAS[standard_file]["required"]:
            source_column = column_map[canonical]
            value = row.get(source_column, "")
            transform = transforms.get(canonical, "strip")
            try:
                target[canonical] = apply_transform(value, transform)
            except (ValueError, TypeError) as exc:
                add_issue(issues, source_name, index, source_column, "TRANSFORM_FAILED", value,
                          f"{canonical} 변환 실패: {exc}")
                target[canonical] = ""
        converted.append(target)
    if any(item.file == source_name for item in issues):
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / standard_file
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCHEMAS[standard_file]["required"])
        writer.writeheader()
        writer.writerows(converted)
    manifest["tables"][standard_file] = {
        "source_file": source_name,
        "source_sha256": sha256(source),
        "source_encoding": encoding,
        "input_rows": len(rows),
        "output_rows": len(converted),
    }


def import_and_validate(input_dir: Path, mapping_file: Path, work_dir: Path) -> dict:
    issues: list[Issue] = []
    manifest = {"mapping_file": str(mapping_file.resolve()), "tables": {}}
    standardized = work_dir / "standardized"
    validation = work_dir / "validation"
    if standardized.exists():
        shutil.rmtree(standardized)
    try:
        mapping = json.loads(mapping_file.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        add_issue(issues, mapping_file.name, None, None, "MAPPING_READ_ERROR", "", str(exc))
        write_import_reports(standardized, issues, manifest)
        return {"status": "BLOCKED", "stage": "IMPORT", "errors": len(issues)}

    tables = mapping.get("tables", {})
    for standard_file in SCHEMAS:
        config = tables.get(standard_file)
        if config is None:
            add_issue(issues, mapping_file.name, None, standard_file, "TABLE_MAPPING_MISSING", "",
                      "필수 표준파일의 매핑 설정이 없습니다")
            continue
        before = len(issues)
        convert_table(input_dir, standardized, standard_file, config, issues, manifest)
        if len(issues) > before:
            continue
    write_import_reports(standardized, issues, manifest)
    if issues:
        return {"status": "BLOCKED", "stage": "IMPORT", "errors": len(issues)}

    result = validate_directory(standardized, validation)
    return {"status": result["status"], "stage": "VALIDATION", "errors": result["errors"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="기업 원본데이터 표준변환 + 오류검사")
    parser.add_argument("input_dir", type=Path, help="기업 원본 CSV 폴더")
    parser.add_argument("mapping_file", type=Path, help="기업별 파일·열 매핑 JSON")
    parser.add_argument("--work-dir", type=Path, default=Path("results/enterprise_import"))
    args = parser.parse_args()
    result = import_and_validate(args.input_dir.resolve(), args.mapping_file.resolve(), args.work_dir.resolve())
    print(f"처리결과: {result['status']} / 단계: {result['stage']} / 오류: {result['errors']}건")
    print(f"결과폴더: {args.work_dir.resolve()}")
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
