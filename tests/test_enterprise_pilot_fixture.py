import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from enterprise_pipeline import run_pipeline
from generate_enterprise_pilot_fixture import generate


class EnterprisePilotFixtureTests(unittest.TestCase):
    def test_scale_fixture_runs_through_existing_pipeline(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            raw = temp_path / "raw"
            manifest = generate(raw, lots=1_000, vehicles=10_000, claims=300)
            result = run_pipeline(raw, root / "enterprise_data" / "demo_company_mapping.json",
                                  root / "enterprise_data" / "enterprise_analysis_rules.json",
                                  temp_path / "output")
            self.assertEqual(manifest["lots"], 1_000)
            self.assertEqual(result["status"], "READY")
            self.assertTrue(result["decision_gate_passed"])
            analysis = next(x["result"] for x in result["stages"] if x["name"] == "RISK_ANALYSIS")
            self.assertEqual(analysis["lot_count"], 1_000)
            self.assertGreater(analysis["high_risk_lots"], 0)
            affected_path = Path(result["run_dir"]) / "02_analysis" / "affected_vehicles.csv"
            with affected_path.open(encoding="utf-8-sig", newline="") as handle:
                self.assertGreater(len(list(csv.DictReader(handle))), 0)


if __name__ == "__main__":
    unittest.main()
