"""AutoQ-Guard SQLite v1 데이터를 정규화된 v2 호환 DB로 이전하고 동등성을 검사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE data_load_batch(batch_id TEXT PRIMARY KEY, source_system TEXT NOT NULL,
 loaded_at TEXT NOT NULL, source_hash TEXT NOT NULL, load_status TEXT NOT NULL,
 row_count INTEGER NOT NULL, error_count INTEGER NOT NULL);
CREATE TABLE supplier(supplier_id TEXT PRIMARY KEY, supplier_name TEXT, active INTEGER NOT NULL);
CREATE TABLE part(part_number TEXT PRIMARY KEY, part_name TEXT, safety_class TEXT NOT NULL, commodity_group TEXT);
CREATE TABLE process(process_id TEXT PRIMARY KEY, process_name TEXT, plant_code TEXT, line_code TEXT);
CREATE TABLE vehicle(vehicle_key TEXT PRIMARY KEY, model TEXT NOT NULL, production_at TEXT NOT NULL,
 shipment_status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE part_lot(lot_id TEXT PRIMARY KEY, supplier_id TEXT NOT NULL REFERENCES supplier,
 part_number TEXT NOT NULL REFERENCES part, received_at TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0),
 batch_id TEXT NOT NULL REFERENCES data_load_batch);
CREATE TABLE process_inspection(inspection_id TEXT PRIMARY KEY, lot_id TEXT NOT NULL REFERENCES part_lot,
 process_id TEXT NOT NULL REFERENCES process, measured_at TEXT NOT NULL, process_z REAL NOT NULL,
 recheck_rate REAL NOT NULL CHECK(recheck_rate BETWEEN 0 AND 1), batch_id TEXT NOT NULL REFERENCES data_load_batch);
CREATE TABLE vehicle_part_installation(vehicle_key TEXT NOT NULL REFERENCES vehicle,
 lot_id TEXT NOT NULL REFERENCES part_lot, installed_at TEXT, station_code TEXT,
 batch_id TEXT NOT NULL REFERENCES data_load_batch, PRIMARY KEY(vehicle_key,lot_id));
CREATE TABLE warranty_claim(claim_id TEXT PRIMARY KEY, vehicle_key TEXT NOT NULL REFERENCES vehicle,
 part_number TEXT REFERENCES part, claim_at TEXT NOT NULL, failure_code TEXT NOT NULL,
 repair_cost_krw REAL NOT NULL CHECK(repair_cost_krw>=0), batch_id TEXT NOT NULL REFERENCES data_load_batch);
CREATE TABLE cost_policy(part_number TEXT NOT NULL REFERENCES part, effective_from TEXT NOT NULL,
 effective_to TEXT, early_action_cost_krw REAL NOT NULL, field_repair_cost_krw REAL NOT NULL,
 customer_compensation_krw REAL NOT NULL, PRIMARY KEY(part_number,effective_from));
CREATE TABLE risk_assessment(assessment_id INTEGER PRIMARY KEY AUTOINCREMENT, lot_id TEXT NOT NULL REFERENCES part_lot,
 assessed_at TEXT NOT NULL, model_version TEXT NOT NULL, risk_score REAL NOT NULL CHECK(risk_score BETWEEN 0 AND 1),
 risk_level TEXT NOT NULL, risk_reasons TEXT NOT NULL, action_code TEXT NOT NULL,
 estimated_prevented_vehicles REAL, estimated_avoided_loss_krw REAL,
 estimated_early_action_cost_krw REAL, estimated_net_benefit_krw REAL, estimated_direct_roi REAL,
 UNIQUE(lot_id,assessed_at,model_version));
CREATE TABLE affected_vehicle(assessment_id INTEGER NOT NULL REFERENCES risk_assessment ON DELETE CASCADE,
 vehicle_key TEXT NOT NULL REFERENCES vehicle, lot_id TEXT NOT NULL REFERENCES part_lot,
 action_code TEXT NOT NULL, PRIMARY KEY(assessment_id,vehicle_key,lot_id));
CREATE INDEX idx_part_lot_supplier_part ON part_lot(supplier_id,part_number);
CREATE INDEX idx_inspection_lot_time ON process_inspection(lot_id,measured_at DESC);
CREATE INDEX idx_installation_lot ON vehicle_part_installation(lot_id,vehicle_key);
CREATE INDEX idx_claim_vehicle_time ON warranty_claim(vehicle_key,claim_at DESC);
CREATE INDEX idx_risk_level_time ON risk_assessment(risk_level,assessed_at DESC);
"""


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def migrate(source: Path, target: Path, report: Path) -> dict:
    source, target, report = source.resolve(), target.resolve(), report.resolve()
    if target.exists():
        target.unlink()
    old = sqlite3.connect(source)
    old.row_factory = sqlite3.Row
    new = sqlite3.connect(target)
    new.execute("PRAGMA foreign_keys=ON")
    batch_id = "MIGRATION_V1_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    assessed_at = datetime.now(timezone.utc).isoformat()
    try:
        new.executescript(DDL)
        source_total = sum(old.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in
                           ("part_lot","process_inspection","vehicle_build","warranty_claim"))
        new.execute("INSERT INTO data_load_batch VALUES(?,?,?,?,?,?,?)",
                    (batch_id,"SQLITE_V1",assessed_at,digest(source),"READY",source_total,0))
        lots = list(old.execute("SELECT * FROM part_lot"))
        new.executemany("INSERT OR IGNORE INTO supplier VALUES(?,NULL,1)", [(r["supplier_id"],) for r in lots])
        new.executemany("INSERT OR IGNORE INTO part VALUES(?,NULL,?,NULL)",
                        [(r["part_number"],r["safety_class"]) for r in lots])
        new.executemany("INSERT INTO part_lot VALUES(?,?,?,?,?,?)",
                        [(r["lot_id"],r["supplier_id"],r["part_number"],r["received_at"],r["quantity"],batch_id) for r in lots])
        inspections = list(old.execute("SELECT * FROM process_inspection"))
        new.executemany("INSERT OR IGNORE INTO process VALUES(?,NULL,NULL,NULL)", [(r["process_id"],) for r in inspections])
        new.executemany("INSERT INTO process_inspection VALUES(?,?,?,?,?,?,?)",
                        [(r["inspection_id"],r["lot_id"],r["process_id"],r["measured_at"],r["process_z"],r["recheck_rate"],batch_id) for r in inspections])
        builds = list(old.execute("SELECT * FROM vehicle_build"))
        for r in builds:
            new.execute("INSERT OR IGNORE INTO vehicle VALUES(?,?,?,?,?)",
                        (r["vin"],r["model"],r["production_at"],r["shipment_status"],assessed_at))
            new.execute("INSERT INTO vehicle_part_installation VALUES(?,?,?,?,?)",
                        (r["vin"],r["lot_id"],r["production_at"],None,batch_id))
        part_by_vehicle = {r["vin"]: r["part_number"] for r in old.execute(
            "SELECT vb.vin,pl.part_number FROM vehicle_build vb JOIN part_lot pl ON pl.lot_id=vb.lot_id")}
        claims = list(old.execute("SELECT * FROM warranty_claim"))
        new.executemany("INSERT INTO warranty_claim VALUES(?,?,?,?,?,?,?)",
                        [(r["claim_id"],r["vin"],part_by_vehicle.get(r["vin"]),r["claim_at"],r["failure_code"],r["repair_cost_krw"],batch_id) for r in claims])
        for r in old.execute("SELECT * FROM cost_master"):
            new.execute("INSERT INTO cost_policy VALUES(?,?,?,?,?,?)",
                        (r["part_number"],"1970-01-01",None,r["early_action_cost_krw"],r["field_repair_cost_krw"],r["customer_compensation_krw"]))
        assessment_by_lot = {}
        for r in old.execute("SELECT * FROM lot_risk_result"):
            score = r["risk_score"] / 100.0 if r["risk_score"] > 1 else r["risk_score"]
            cur = new.execute("""INSERT INTO risk_assessment
              (lot_id,assessed_at,model_version,risk_score,risk_level,risk_reasons,action_code,
               estimated_prevented_vehicles,estimated_avoided_loss_krw,estimated_early_action_cost_krw,
               estimated_net_benefit_krw,estimated_direct_roi) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
              (r["lot_id"],assessed_at,"rule_v1_migrated",score,r["risk_level"],json.dumps(r["risk_reasons"],ensure_ascii=False),
               r["action_code"],r["estimated_prevented_vehicles"],r["estimated_avoided_loss_krw"],
               r["estimated_early_action_cost_krw"],r["estimated_net_benefit_krw"],r["estimated_direct_roi"]))
            assessment_by_lot[r["lot_id"]] = cur.lastrowid
        for r in old.execute("SELECT * FROM affected_vehicle"):
            new.execute("INSERT INTO affected_vehicle VALUES(?,?,?,?)",
                        (assessment_by_lot[r["lot_id"]],r["vin"],r["lot_id"],r["action_code"]))
        new.commit()
        fk_errors = new.execute("PRAGMA foreign_key_check").fetchall()
        integrity = new.execute("PRAGMA integrity_check").fetchone()[0]
        parity = {
            "part_lot": [old.execute("SELECT count(*) FROM part_lot").fetchone()[0], new.execute("SELECT count(*) FROM part_lot").fetchone()[0]],
            "inspection": [old.execute("SELECT count(*) FROM process_inspection").fetchone()[0], new.execute("SELECT count(*) FROM process_inspection").fetchone()[0]],
            "installation": [old.execute("SELECT count(*) FROM vehicle_build").fetchone()[0], new.execute("SELECT count(*) FROM vehicle_part_installation").fetchone()[0]],
            "claim": [old.execute("SELECT count(*) FROM warranty_claim").fetchone()[0], new.execute("SELECT count(*) FROM warranty_claim").fetchone()[0]],
            "risk": [old.execute("SELECT count(*) FROM lot_risk_result").fetchone()[0], new.execute("SELECT count(*) FROM risk_assessment").fetchone()[0]],
            "affected_vehicle": [old.execute("SELECT count(*) FROM affected_vehicle").fetchone()[0], new.execute("SELECT count(*) FROM affected_vehicle").fetchone()[0]],
        }
        result = {"status":"PASS" if integrity == "ok" and not fk_errors and all(a==b for a,b in parity.values()) else "FAIL",
                  "source":str(source),"target":str(target),"integrity":integrity,
                  "foreign_key_errors":len(fk_errors),"row_count_parity":parity,
                  "source_sha256":digest(source),"target_sha256":digest(target)}
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8-sig")
        return result
    finally:
        old.close(); new.close()


if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("source",type=Path); p.add_argument("target",type=Path); p.add_argument("report",type=Path)
    a=p.parse_args(); result=migrate(a.source,a.target,a.report); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result["status"]=="PASS" else 2)
