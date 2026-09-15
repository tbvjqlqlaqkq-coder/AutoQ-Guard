import sqlite3,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from quality_case_workflow import QualityCaseWorkflow

class QualityCaseWorkflowTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.workflow=QualityCaseWorkflow(Path(self.temp.name)/"workflow.db");self.case=self.workflow.open_case("LOT-1","SAFETY","quality1","QUALITY","WATCH 우선검토")
    def tearDown(self):self.temp.cleanup()
    def test_approved_flow_and_hash_chain(self):
        self.workflow.transition(self.case,"INVESTIGATING","quality1","QUALITY","검사 시작");self.workflow.transition(self.case,"ACTION_PROPOSED","quality1","QUALITY","이상 확인","INSP-1");result=self.workflow.transition(self.case,"ACTION_APPROVED","admin1","ADMIN","조치 승인","APR-1")
        self.assertEqual(result["case"]["status"],"ACTION_APPROVED");self.assertTrue(self.workflow.verify_chain(self.case));self.assertFalse(result["automatic_recall"])
    def test_viewer_and_invalid_jump_are_blocked(self):
        with self.assertRaises(PermissionError):self.workflow.transition(self.case,"INVESTIGATING","viewer1","VIEWER","시도")
        with self.assertRaises(ValueError):self.workflow.transition(self.case,"ACTION_APPROVED","admin1","ADMIN","건너뛰기","APR-1")
    def test_action_requires_evidence(self):
        self.workflow.transition(self.case,"INVESTIGATING","quality1","QUALITY","검사 시작")
        with self.assertRaises(ValueError):self.workflow.transition(self.case,"ACTION_PROPOSED","quality1","QUALITY","근거 없음")
    def test_audit_event_cannot_be_modified(self):
        db=sqlite3.connect(self.workflow.path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE quality_case_event SET reason='changed'")
        finally:
            db.close()
if __name__=="__main__":unittest.main()
