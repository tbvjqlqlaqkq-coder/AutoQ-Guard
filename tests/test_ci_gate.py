import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1]/'.github/workflows/ci.yml'


class DeploymentGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding='utf-8')

    def test_deploy_requires_test(self):
        deploy = self.text.split('\n  deploy:', 1)[1]
        self.assertIn('\n    needs: test', deploy)

    def test_deploy_only_main_push(self):
        deploy = self.text.split('\n  deploy:', 1)[1]
        self.assertIn("github.event_name == 'push'", deploy)
        self.assertIn("github.ref == 'refs/heads/main'", deploy)

    def test_verified_artifact_is_deployed(self):
        deploy = self.text.split('\n  deploy:', 1)[1]
        self.assertLess(deploy.index('actions/upload-pages-artifact@v3'), deploy.index('actions/deploy-pages@v4'))
        self.assertIn('path: docs', deploy)

    def test_test_job_contains_artifact_check(self):
        test = self.text.split('\n  test:', 1)[1].split('\n  deploy:', 1)[0]
        self.assertIn('python src/verify_alert_artifact.py', test)

    def test_permissions_declared(self):
        self.assertIn('pages: write', self.text)
        self.assertIn('id-token: write', self.text)
