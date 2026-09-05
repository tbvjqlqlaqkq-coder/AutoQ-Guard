from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "demo" / "enterprise-flow.html"


class EnterpriseFlowDemoTests(unittest.TestCase):
    def test_page_is_linked_from_public_demo(self):
        self.assertIn('href="enterprise-flow.html"', (ROOT / "docs" / "demo" / "index.html").read_text(encoding="utf-8"))

    def test_page_has_all_five_stages(self):
        text = PAGE.read_text(encoding="utf-8")
        for label in ("데이터 선택", "형식 검증", "위험도 계산", "담당자 검토", "감사기록"):
            self.assertIn(label, text)

    def test_human_review_is_required_before_audit(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn('id="approve" disabled', text)
        self.assertIn("$('approve').disabled=false", text)
        self.assertIn("reviewer_id", text)
        self.assertIn("결함 확정 또는 리콜 자동결정 아님", text)

    def test_file_handling_is_documented_as_local_only(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("서버로 전송하지 않고", text)
        self.assertIn("현재 브라우저 메모리", text)
