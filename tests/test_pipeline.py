"""
tests/test_pipeline.py
End-to-end pipeline tests: builds the real schema, generates a small synthetic
dataset, and asserts the full pipeline (data gen -> validation -> scheduling ->
export) runs and produces internally consistent, real (non-mocked) results.

Run:
    python -m pytest tests/test_pipeline.py -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestPipelineEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Redirect all paths to a temp directory so this test never touches
        # the real project database/data.
        cls.tmp_dir = tempfile.mkdtemp()
        cls.original = {
            "DB_PATH": config.DB_PATH,
            "DATA_DIR": config.DATA_DIR,
            "CANDIDATES_CSV": config.CANDIDATES_CSV,
            "OFFERS_CSV": config.OFFERS_CSV,
            "ACCEPTANCE_EVENTS_CSV": config.ACCEPTANCE_EVENTS_CSV,
            "REPORTS_DIR": config.REPORTS_DIR,
            "ACCEPTANCE_REPORT_CSV": config.ACCEPTANCE_REPORT_CSV,
            "DASHBOARD_EXPORT_CSV": config.DASHBOARD_EXPORT_CSV,
            "NUM_CANDIDATES": config.NUM_CANDIDATES,
        }

        config.DB_PATH = os.path.join(cls.tmp_dir, "test_placemux.db")
        config.DATA_DIR = cls.tmp_dir
        config.CANDIDATES_CSV = os.path.join(cls.tmp_dir, "candidates.csv")
        config.OFFERS_CSV = os.path.join(cls.tmp_dir, "offers.csv")
        config.ACCEPTANCE_EVENTS_CSV = os.path.join(cls.tmp_dir, "acceptance_events.csv")
        config.REPORTS_DIR = cls.tmp_dir
        config.ACCEPTANCE_REPORT_CSV = os.path.join(cls.tmp_dir, "acceptance_report.csv")
        config.DASHBOARD_EXPORT_CSV = os.path.join(cls.tmp_dir, "dashboard_export.csv")
        config.NUM_CANDIDATES = 300  # small but real, not a single happy-path row

        import create_database
        create_database.create_database()

        import generate_data
        generate_data.main()

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.original.items():
            setattr(config, key, value)

    def test_database_created_with_tables(self):
        import sqlite3
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        self.assertTrue({"candidates", "offers", "interviews", "events"}.issubset(tables))

    def test_data_actually_flowing(self):
        import metrics_engine
        fc = metrics_engine.get_funnel_counts()
        self.assertEqual(fc["total_offers"], config.NUM_CANDIDATES + 8)  # +8 injected dupes
        self.assertGreater(fc["sent"], 0)
        self.assertGreater(fc["accepted"], 0)

    def test_validation_checks_catch_injected_issues(self):
        import validation_checks
        dupes = validation_checks.check_duplicate_offers()
        nulls = validation_checks.check_null_fields()
        # We intentionally injected 8 duplicates and 5 null-hash signed offers in generate_data.py
        self.assertGreaterEqual(len(dupes), 1)
        self.assertGreaterEqual(len(nulls), 1)

    def test_freshness_check_passes_on_fresh_data(self):
        import validation_checks
        freshness = validation_checks.check_freshness()
        self.assertEqual(freshness["status"], "PASS")
        self.assertGreater(freshness["total_events"], 0)

    def test_offer_integrity_verification(self):
        import sqlite3
        import validation_checks
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT offer_id FROM offers WHERE offer_hash IS NOT NULL LIMIT 1;")
        row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(row, "Expected at least one signed offer with a hash")
        result = validation_checks.verify_offer_integrity(row[0])
        self.assertEqual(result["status"], "VERIFIED")

    def test_auto_scheduling_runs(self):
        import scheduler
        created = scheduler.auto_schedule_interviews()
        self.assertGreaterEqual(created, 0)
        pending_after = scheduler.find_unscheduled_accepted_candidates()
        self.assertEqual(len(pending_after), 0)

    def test_export_reports_generate_files(self):
        import export_reports
        path1 = export_reports.export_acceptance_report()
        path2 = export_reports.export_dashboard_summary()
        self.assertTrue(os.path.exists(path1))
        self.assertTrue(os.path.exists(path2))
        self.assertGreater(os.path.getsize(path1), 0)
        self.assertGreater(os.path.getsize(path2), 0)


if __name__ == "__main__":
    unittest.main()
