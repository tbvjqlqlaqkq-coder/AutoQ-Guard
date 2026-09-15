"""WATCH LOT의 조사·조치승인 상태와 변경 이력을 SQLite에 보존한다."""
from __future__ import annotations
import argparse,hashlib,json,sqlite3
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path

TRANSITIONS={
    "WATCH":{"INVESTIGATING"},
    "INVESTIGATING":{"ACTION_PROPOSED","CLEARED"},
    "ACTION_PROPOSED":{"ACTION_APPROVED","ACTION_REJECTED"},
    "ACTION_REJECTED":{"INVESTIGATING"},
    "ACTION_APPROVED":{"CLOSED"},
    "CLEARED":{"CLOSED"},
    "CLOSED":set(),
}
ROLE_TARGETS={"QUALITY":{"INVESTIGATING","ACTION_PROPOSED","CLEARED","CLOSED"},"ADMIN":{"INVESTIGATING","ACTION_APPROVED","ACTION_REJECTED","CLOSED"},"VIEWER":set()}

def _now()->str:return datetime.now(timezone.utc).isoformat()

class QualityCaseWorkflow:
    def __init__(self,path:Path):
        self.path=path;path.parent.mkdir(parents=True,exist_ok=True);self._init()
    @contextmanager
    def _db(self):
        db=sqlite3.connect(self.path);db.row_factory=sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    def _init(self):
        with self._db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS quality_case(case_id INTEGER PRIMARY KEY AUTOINCREMENT,lot_id TEXT NOT NULL UNIQUE,safety_class TEXT NOT NULL,status TEXT NOT NULL,opened_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS quality_case_event(event_id INTEGER PRIMARY KEY AUTOINCREMENT,case_id INTEGER NOT NULL,occurred_at TEXT NOT NULL,actor TEXT NOT NULL,actor_role TEXT NOT NULL,from_status TEXT,to_status TEXT NOT NULL,reason TEXT NOT NULL,evidence_ref TEXT NOT NULL,previous_hash TEXT NOT NULL,event_hash TEXT NOT NULL,FOREIGN KEY(case_id) REFERENCES quality_case(case_id));
            CREATE TRIGGER IF NOT EXISTS quality_event_no_update BEFORE UPDATE ON quality_case_event BEGIN SELECT RAISE(ABORT,'audit events are immutable');END;
            CREATE TRIGGER IF NOT EXISTS quality_event_no_delete BEFORE DELETE ON quality_case_event BEGIN SELECT RAISE(ABORT,'audit events are immutable');END;
            """)
    @staticmethod
    def _hash(case_id:int,occurred_at:str,actor:str,role:str,from_status:str,to_status:str,reason:str,evidence_ref:str,previous_hash:str)->str:
        raw="|".join(map(str,(case_id,occurred_at,actor,role,from_status,to_status,reason,evidence_ref,previous_hash)))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    def open_case(self,lot_id:str,safety_class:str,actor:str,role:str,reason:str)->int:
        role=role.upper();reason=reason.strip()
        if role not in {"QUALITY","ADMIN"}:raise PermissionError("QUALITY 또는 ADMIN만 사건을 열 수 있습니다")
        if not lot_id.strip() or not reason:raise ValueError("LOT와 개설 사유가 필요합니다")
        occurred=_now()
        with self._db() as db:
            cur=db.execute("INSERT INTO quality_case(lot_id,safety_class,status,opened_at,updated_at) VALUES(?,?,?,?,?)",(lot_id.strip().upper(),safety_class.strip().upper(),"WATCH",occurred,occurred));case_id=cur.lastrowid
            digest=self._hash(case_id,occurred,actor,role,"","WATCH",reason,"","")
            db.execute("INSERT INTO quality_case_event(case_id,occurred_at,actor,actor_role,from_status,to_status,reason,evidence_ref,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",(case_id,occurred,actor,role,"","WATCH",reason,"","",digest));return case_id
    def transition(self,case_id:int,to_status:str,actor:str,role:str,reason:str,evidence_ref:str="")->dict:
        role=role.upper();to_status=to_status.upper();reason=reason.strip();evidence_ref=evidence_ref.strip()
        if not reason:raise ValueError("상태 변경 사유가 필요합니다")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE");case=db.execute("SELECT * FROM quality_case WHERE case_id=?",(case_id,)).fetchone()
            if not case:raise KeyError("사건을 찾을 수 없습니다")
            current=case["status"]
            if to_status not in TRANSITIONS[current]:raise ValueError(f"허용되지 않은 상태 변경: {current} -> {to_status}")
            if to_status not in ROLE_TARGETS.get(role,set()):raise PermissionError(f"{role} 역할은 {to_status} 변경 권한이 없습니다")
            if to_status in {"ACTION_PROPOSED","ACTION_APPROVED","CLEARED"} and not evidence_ref:raise ValueError("조치·해제 판단에는 증거 참조가 필요합니다")
            occurred=_now();previous=db.execute("SELECT event_hash FROM quality_case_event WHERE case_id=? ORDER BY event_id DESC LIMIT 1",(case_id,)).fetchone()[0]
            digest=self._hash(case_id,occurred,actor,role,current,to_status,reason,evidence_ref,previous)
            db.execute("UPDATE quality_case SET status=?,updated_at=? WHERE case_id=?",(to_status,occurred,case_id));db.execute("INSERT INTO quality_case_event(case_id,occurred_at,actor,actor_role,from_status,to_status,reason,evidence_ref,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",(case_id,occurred,actor,role,current,to_status,reason,evidence_ref,previous,digest))
        return self.case(case_id)
    def case(self,case_id:int)->dict:
        with self._db() as db:
            case=db.execute("SELECT * FROM quality_case WHERE case_id=?",(case_id,)).fetchone();events=db.execute("SELECT * FROM quality_case_event WHERE case_id=? ORDER BY event_id",(case_id,)).fetchall()
            if not case:raise KeyError("사건을 찾을 수 없습니다")
            return {"case":dict(case),"events":[dict(r) for r in events],"automatic_recall":False}
    def verify_chain(self,case_id:int)->bool:
        data=self.case(case_id);previous=""
        for event in data["events"]:
            expected=self._hash(case_id,event["occurred_at"],event["actor"],event["actor_role"],event["from_status"],event["to_status"],event["reason"],event["evidence_ref"],previous)
            if event["previous_hash"]!=previous or event["event_hash"]!=expected:return False
            previous=event["event_hash"]
        return True

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--db",type=Path,default=Path("results/quality_workflow.db"));a=p.parse_args();w=QualityCaseWorkflow(a.db);case=w.open_case("LOT-DEMO-WATCH","SAFETY","quality.demo","QUALITY","검토 큐 상위 LOT");w.transition(case,"INVESTIGATING","quality.demo","QUALITY","검사 시작");w.transition(case,"ACTION_PROPOSED","quality.demo","QUALITY","반복 이상 확인","INSP-DEMO-001");w.transition(case,"ACTION_APPROVED","admin.demo","ADMIN","출고보류 및 추가검사 승인","APPROVAL-DEMO-001");print(json.dumps(w.case(case),ensure_ascii=False,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
