from pathlib import Path
import sqlite3

from src.enterprise_security import SecurityStore


def test_audit_does_not_store_raw_client_address(tmp_path: Path):
    store = SecurityStore(tmp_path / "security.db")
    store.audit("quality01", "LOGIN", "SUCCESS", "192.168.10.25")
    with sqlite3.connect(store.database) as db:
        saved = db.execute("SELECT client_ip FROM security_audit ORDER BY audit_id DESC LIMIT 1").fetchone()[0]
    assert saved.startswith("net_")
    assert "192.168.10.25" not in saved


def test_audit_api_pseudonymizes_username(tmp_path: Path):
    store = SecurityStore(tmp_path / "security.db")
    store.audit("quality01", "SEARCH", "SUCCESS", "127.0.0.1")
    row = store.audit_rows(1)[0]
    assert row["username"].startswith("usr_")
    assert row["username"] != "quality01"
    assert row["client_ip"].startswith("net_")
