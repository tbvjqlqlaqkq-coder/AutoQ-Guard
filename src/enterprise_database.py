"""검증된 기업 데이터를 SQLite에 안전하게 적재하고 조회한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from enterprise_data_validator import read_csv_safely, validate_directory


SCHEMA_VERSION = "1.0"
SOURCE_TABLES = {
    "part_lot.csv": ("part_lot", ["lot_id", "supplier_id", "part_number", "safety_class", "received_at", "quantity"]),
    "process_inspection.csv": ("process_inspection", ["inspection_id", "lot_id", "process_id", "measured_at", "process_z", "recheck_rate"]),
    "vehicle_build.csv": ("vehicle_build", ["vin", "lot_id", "model", "production_at", "shipment_status"]),
    "warranty_claim.csv": ("warranty_claim", ["claim_id", "vin", "claim_at", "failure_code", "repair_cost_krw"]),
    "cost_master.csv": ("cost_master", ["part_number", "early_action_cost_krw", "field_repair_cost_krw", "customer_compensation_krw"]),
}
RISK_COLUMNS = [
    "lot_id", "supplier_id", "part_number", "safety_class", "risk_score", "risk_level",
    "risk_reasons", "max_process_z", "max_recheck_rate", "vehicle_count",
    "warranty_claim_count", "warranty_claim_rate", "action_code", "recommended_action",
    "economic_status", "estimated_prevented_vehicles", "estimated_avoided_loss_krw",
    "estimated_early_action_cost_krw", "estimated_net_benefit_krw", "estimated_direct_roi",
]
AFFECTED_COLUMNS = ["vin", "lot_id", "model", "shipment_status", "risk_level", "action_code"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE part_lot (
            lot_id TEXT PRIMARY KEY, supplier_id TEXT NOT NULL, part_number TEXT NOT NULL,
            safety_class TEXT NOT NULL, received_at TEXT NOT NULL, quantity INTEGER NOT NULL
        );
        CREATE TABLE process_inspection (
            inspection_id TEXT PRIMARY KEY, lot_id TEXT NOT NULL, process_id TEXT NOT NULL,
            measured_at TEXT NOT NULL, process_z REAL NOT NULL, recheck_rate REAL NOT NULL,
            FOREIGN KEY(lot_id) REFERENCES part_lot(lot_id)
        );
        CREATE TABLE vehicle_build (
            vin TEXT NOT NULL, lot_id TEXT NOT NULL, model TEXT NOT NULL,
            production_at TEXT NOT NULL, shipment_status TEXT NOT NULL,
            PRIMARY KEY(vin, lot_id), FOREIGN KEY(lot_id) REFERENCES part_lot(lot_id)
        );
        CREATE TABLE warranty_claim (
            claim_id TEXT PRIMARY KEY, vin TEXT NOT NULL, claim_at TEXT NOT NULL,
            failure_code TEXT NOT NULL, repair_cost_krw REAL NOT NULL
        );
        CREATE TABLE cost_master (
            part_number TEXT PRIMARY KEY, early_action_cost_krw REAL NOT NULL,
            field_repair_cost_krw REAL NOT NULL, customer_compensation_krw REAL NOT NULL
        );
        CREATE TABLE lot_risk_result (
            lot_id TEXT PRIMARY KEY, supplier_id TEXT, part_number TEXT, safety_class TEXT,
            risk_score REAL, risk_level TEXT, risk_reasons TEXT, max_process_z REAL,
            max_recheck_rate REAL, vehicle_count INTEGER, warranty_claim_count INTEGER,
            warranty_claim_rate REAL, action_code TEXT, recommended_action TEXT,
            economic_status TEXT, estimated_prevented_vehicles REAL,
            estimated_avoided_loss_krw REAL, estimated_early_action_cost_krw REAL,
            estimated_net_benefit_krw REAL, estimated_direct_roi REAL,
            FOREIGN KEY(lot_id) REFERENCES part_lot(lot_id)
        );
        CREATE TABLE affected_vehicle (
            vin TEXT NOT NULL, lot_id TEXT NOT NULL, model TEXT, shipment_status TEXT,
            risk_level TEXT, action_code TEXT, PRIMARY KEY(vin, lot_id),
            FOREIGN KEY(lot_id) REFERENCES part_lot(lot_id)
        );
        CREATE INDEX idx_lot_supplier ON part_lot(supplier_id);
        CREATE INDEX idx_lot_part ON part_lot(part_number);
        CREATE INDEX idx_inspection_lot ON process_inspection(lot_id);
        CREATE INDEX idx_vehicle_vin ON vehicle_build(vin);
        CREATE INDEX idx_vehicle_lot ON vehicle_build(lot_id);
        CREATE INDEX idx_claim_vin ON warranty_claim(vin);
        CREATE INDEX idx_risk_level ON lot_risk_result(risk_level);
        CREATE INDEX idx_affected_vin ON affected_vehicle(vin);
    """)


def _insert_csv(connection: sqlite3.Connection, path: Path, table: str, columns: list[str]) -> int:
    rows, _, _ = read_csv_safely(path)
    placeholders = ",".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
    connection.executemany(sql, [[row.get(column, "") for column in columns] for row in rows])
    return len(rows)


def build_database(standardized_dir: Path, analysis_dir: Path, database_path: Path,
                   report_dir: Path) -> dict:
    standardized_dir = standardized_dir.resolve()
    analysis_dir = analysis_dir.resolve()
    database_path = database_path.resolve()
    report_dir = report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    validation = validate_directory(standardized_dir, report_dir / "predatabase_validation")
    if validation["status"] != "READY":
        result = {"status": "BLOCKED", "database_replaced": False, "reason": "입력 데이터 검증 실패"}
        (report_dir / "database_build_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
        return result

    required_analysis = [analysis_dir / "lot_risk_results.csv", analysis_dir / "affected_vehicles.csv"]
    missing = [str(path) for path in required_analysis if not path.exists()]
    if missing:
        result = {"status": "BLOCKED", "database_replaced": False, "reason": "위험분석 결과 없음", "missing": missing}
        (report_dir / "database_build_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
        return result

    database_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = database_path.with_suffix(database_path.suffix + ".building")
    if temp_path.exists():
        temp_path.unlink()
    counts: dict[str, int] = {}
    try:
        connection = sqlite3.connect(temp_path)
        try:
            _create_schema(connection)
            connection.execute("BEGIN")
            for filename, (table, columns) in SOURCE_TABLES.items():
                counts[table] = _insert_csv(connection, standardized_dir / filename, table, columns)
            counts["lot_risk_result"] = _insert_csv(connection, required_analysis[0], "lot_risk_result", RISK_COLUMNS)
            counts["affected_vehicle"] = _insert_csv(connection, required_analysis[1], "affected_vehicle", AFFECTED_COLUMNS)
            metadata = {
                "schema_version": SCHEMA_VERSION,
                "built_at_utc": datetime.now(timezone.utc).isoformat(),
                "standardized_dir": str(standardized_dir),
            }
            for filename in SOURCE_TABLES:
                metadata[f"sha256:{filename}"] = sha256(standardized_dir / filename)
            connection.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", metadata.items())
            connection.commit()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok" or foreign_keys:
                raise RuntimeError(f"데이터베이스 무결성 실패: {integrity}, FK={len(foreign_keys)}")
        finally:
            connection.close()
        os.replace(temp_path, database_path)
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink()
        result = {"status": "BLOCKED", "database_replaced": False, "reason": str(exc)}
        (report_dir / "database_build_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
        return result

    result = {
        "status": "READY", "database_replaced": True, "database": str(database_path),
        "schema_version": SCHEMA_VERSION, "row_counts": counts,
    }
    (report_dir / "database_build_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result


def search_database(database_path: Path, *, lot_id: str | None = None, vin: str | None = None,
                    supplier_id: str | None = None, part_number: str | None = None,
                    risk_level: str | None = None) -> list[dict]:
    conditions, params = [], []
    for expression, value in [
        ("p.lot_id = ?", lot_id), ("v.vin = ?", vin), ("p.supplier_id = ?", supplier_id),
        ("p.part_number = ?", part_number), ("r.risk_level = ?", risk_level),
    ]:
        if value:
            conditions.append(expression)
            params.append(value.strip().upper())
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    sql = """
        SELECT p.lot_id, p.supplier_id, p.part_number, p.safety_class,
               v.vin, v.model, v.shipment_status, r.risk_score, r.risk_level,
               r.action_code, r.recommended_action, r.estimated_net_benefit_krw,
               r.estimated_direct_roi
        FROM part_lot p
        LEFT JOIN vehicle_build v ON v.lot_id=p.lot_id
        LEFT JOIN lot_risk_result r ON r.lot_id=p.lot_id
    """ + where + " ORDER BY COALESCE(r.risk_score, 0) DESC, p.lot_id, v.vin LIMIT 1000"
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="기업 품질 데이터베이스 구축 및 안전 조회")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("standardized_dir", type=Path)
    build.add_argument("analysis_dir", type=Path)
    build.add_argument("database", type=Path)
    build.add_argument("--report-dir", type=Path, default=Path("results/enterprise_database"))
    search = sub.add_parser("search")
    search.add_argument("database", type=Path)
    for name in ("lot_id", "vin", "supplier_id", "part_number", "risk_level"):
        search.add_argument(f"--{name.replace('_', '-')}")
    search.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        result = build_database(args.standardized_dir, args.analysis_dir, args.database, args.report_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "READY" else 2
    rows = search_database(args.database, lot_id=args.lot_id, vin=args.vin, supplier_id=args.supplier_id,
                           part_number=args.part_number, risk_level=args.risk_level)
    text = json.dumps({"count": len(rows), "results": rows}, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8-sig")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
