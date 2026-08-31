"""AutoQ-Guard 로컬 PoC 인증·권한·감사기록."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROLE_PERMISSIONS = {
    "ADMIN": {"VIEW_DASHBOARD", "SEARCH", "IMPORT_PREVIEW", "IMPORT_APPROVE", "MANAGE_USERS", "VIEW_AUDIT"},
    "QUALITY": {"VIEW_DASHBOARD", "SEARCH", "IMPORT_PREVIEW"},
    "VIEWER": {"VIEW_DASHBOARD", "SEARCH"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 10:
        raise ValueError("비밀번호는 10자 이상이어야 합니다.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        _, iterations, salt_hex, expected_hex = encoded.split("$", 3)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


class SecurityStore:
    def __init__(self, database: Path, bootstrap_file: Path | None = None):
        self.database = database
        self.bootstrap_file = bootstrap_file or database.with_name("초기_관리자_계정.txt")
        # 운영 환경에서는 AUTOQ_AUDIT_HMAC_KEY를 Secret Manager/KMS에서 주입한다.
        # 로컬 PoC에서는 서버 실행마다 임시 키를 생성해 원본 접속주소 저장을 방지한다.
        self._audit_hmac_key = (os.environ.get("AUTOQ_AUDIT_HMAC_KEY") or secrets.token_urlsafe(32)).encode("utf-8")
        database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _protected_reference(self, value: str, prefix: str) -> str:
        if not value:
            return ""
        digest = hmac.new(self._audit_hmac_key, value.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        return f"{prefix}_{digest}"

    def _protect_client_identifier(self, value: str) -> str:
        return value if not value or value.startswith("net_") else self._protected_reference(value, "net")

    def connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS security_user(
                    username TEXT PRIMARY KEY, display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT, created_at TEXT NOT NULL, last_login_at TEXT
                );
                CREATE TABLE IF NOT EXISTS security_session(
                    token_hash TEXT PRIMARY KEY, username TEXT NOT NULL REFERENCES security_user(username),
                    csrf_token TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS security_audit(
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
                    username TEXT, action TEXT NOT NULL, outcome TEXT NOT NULL,
                    client_ip TEXT, details TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_security_audit_time ON security_audit(occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_security_session_expiry ON security_session(expires_at);
            """)
            count = db.execute("SELECT COUNT(*) FROM security_user").fetchone()[0]
            if not count:
                username = os.environ.get("AUTOQ_ADMIN_USER", "admin").strip().lower()
                password = os.environ.get("AUTOQ_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
                self.create_user(username, "초기 관리자", password, "ADMIN", actor="SYSTEM", connection=db)
                self.bootstrap_file.write_text(
                    f"AutoQ-Guard 초기 관리자\n아이디: {username}\n임시 비밀번호: {password}\n\n첫 로그인 후 별도 안전한 장소에 보관하고 이 파일을 삭제하세요.\n",
                    encoding="utf-8-sig",
                )
            # 과거 PoC 버전이 저장한 원본 접속주소를 즉시 가명 참조값으로 전환한다.
            for row in db.execute("SELECT audit_id,client_ip FROM security_audit WHERE client_ip IS NOT NULL AND client_ip<>''"):
                protected = self._protect_client_identifier(row["client_ip"])
                if protected != row["client_ip"]:
                    db.execute("UPDATE security_audit SET client_ip=? WHERE audit_id=?", (protected, row["audit_id"]))
            cutoff = (_now() - timedelta(days=90)).isoformat()
            db.execute("DELETE FROM security_audit WHERE occurred_at < ?", (cutoff,))

    def audit(self, username: str | None, action: str, outcome: str, client_ip: str = "", details: dict | None = None, connection=None):
        own = connection is None
        db = connection or self.connect()
        try:
            db.execute("INSERT INTO security_audit(occurred_at,username,action,outcome,client_ip,details) VALUES(?,?,?,?,?,?)",
                       (_now().isoformat(), username, action[:80], outcome[:20], self._protect_client_identifier(client_ip), json.dumps(details or {}, ensure_ascii=False)[:2000]))
            db.execute("DELETE FROM security_audit WHERE occurred_at < ?", ((_now() - timedelta(days=90)).isoformat(),))
            if own:
                db.commit()
        finally:
            if own:
                db.close()

    def create_user(self, username: str, display_name: str, password: str, role: str, actor: str, connection=None):
        username = username.strip().lower()
        role = role.strip().upper()
        if not username or len(username) > 50 or not all(c.isalnum() or c in "._-" for c in username):
            raise ValueError("아이디는 영문·숫자·점·밑줄·하이픈으로 1~50자만 사용할 수 있습니다.")
        if role not in ROLE_PERMISSIONS:
            raise ValueError("지원하지 않는 역할입니다.")
        if not display_name.strip() or len(display_name) > 50:
            raise ValueError("표시 이름은 1~50자여야 합니다.")
        own = connection is None
        db = connection or self.connect()
        try:
            db.execute("INSERT INTO security_user(username,display_name,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                       (username, display_name.strip(), _hash_password(password), role, _now().isoformat()))
            self.audit(actor, "USER_CREATE", "SUCCESS", details={"target": username, "role": role}, connection=db)
            if own:
                db.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("이미 존재하는 아이디입니다.") from exc
        finally:
            if own:
                db.close()

    def login(self, username: str, password: str, client_ip: str = "") -> dict | None:
        username = username.strip().lower()
        with closing(self.connect()) as db, db:
            row = db.execute("SELECT * FROM security_user WHERE username=?", (username,)).fetchone()
            now = _now()
            locked = row and row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > now
            if not row or not row["active"] or locked or not _verify_password(password, row["password_hash"]):
                if row and not locked:
                    failed = row["failed_attempts"] + 1
                    until = (now + timedelta(minutes=15)).isoformat() if failed >= 5 else None
                    db.execute("UPDATE security_user SET failed_attempts=?,locked_until=? WHERE username=?", (0 if until else failed, until, username))
                self.audit(username or None, "LOGIN", "DENIED", client_ip, connection=db)
                return None
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
            db.execute("DELETE FROM security_session WHERE expires_at < ?", (now.isoformat(),))
            db.execute("INSERT INTO security_session VALUES(?,?,?,?,?)",
                       (hashlib.sha256(token.encode()).hexdigest(), username, csrf, now.isoformat(), (now + timedelta(hours=8)).isoformat()))
            db.execute("UPDATE security_user SET failed_attempts=0,locked_until=NULL,last_login_at=? WHERE username=?", (now.isoformat(), username))
            self.audit(username, "LOGIN", "SUCCESS", client_ip, connection=db)
            return {"token": token, "csrf_token": csrf, "username": username, "display_name": row["display_name"], "role": row["role"]}

    def session(self, token: str | None) -> dict | None:
        if not token:
            return None
        with closing(self.connect()) as db, db:
            row = db.execute("""SELECT s.*,u.display_name,u.role,u.active FROM security_session s
                               JOIN security_user u ON u.username=s.username WHERE s.token_hash=?""",
                             (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            if not row or not row["active"] or datetime.fromisoformat(row["expires_at"]) <= _now():
                return None
            return {"username": row["username"], "display_name": row["display_name"], "role": row["role"],
                    "csrf_token": row["csrf_token"], "permissions": sorted(ROLE_PERMISSIONS[row["role"]])}

    def logout(self, token: str | None, client_ip: str = ""):
        user = self.session(token)
        if token:
            with closing(self.connect()) as db, db:
                db.execute("DELETE FROM security_session WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        self.audit(user["username"] if user else None, "LOGOUT", "SUCCESS", client_ip)

    def list_users(self) -> list[dict]:
        with closing(self.connect()) as db, db:
            return [dict(row) for row in db.execute("SELECT username,display_name,role,active,created_at,last_login_at FROM security_user ORDER BY username")]

    def set_active(self, username: str, active: bool, actor: str):
        if username == actor and not active:
            raise ValueError("현재 로그인한 관리자 계정은 비활성화할 수 없습니다.")
        with closing(self.connect()) as db, db:
            changed = db.execute("UPDATE security_user SET active=? WHERE username=?", (1 if active else 0, username.lower())).rowcount
            if not changed:
                raise ValueError("사용자를 찾을 수 없습니다.")
            if not active:
                db.execute("DELETE FROM security_session WHERE username=?", (username.lower(),))
            self.audit(actor, "USER_STATUS", "SUCCESS", details={"target": username.lower(), "active": active}, connection=db)

    def audit_rows(self, limit: int = 100) -> list[dict]:
        with closing(self.connect()) as db, db:
            rows = db.execute("SELECT occurred_at,username,action,outcome,client_ip,details FROM security_audit ORDER BY audit_id DESC LIMIT ?", (min(max(limit, 1), 500),))
            result = []
            for row in rows:
                item = dict(row)
                if item["username"]:
                    item["username"] = self._protected_reference(item["username"], "usr")
                item["client_ip"] = self._protect_client_identifier(item["client_ip"] or "")
                result.append(item)
            return result
