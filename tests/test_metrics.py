"""
tests/test_metrics.py
Unit tests for metrics_engine.py. Builds a small isolated in-memory-style SQLite
DB (via a temp file) with known data so expected metric values can be asserted exactly.

Run:
    python -m pytest tests/test_metrics.py -v
"""

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import metrics_engine


class TestMetricsEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.tmp_db.close()
        cls.original_db_path = config.DB_PATH
        config.DB_PATH = cls.tmp_db.name

        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE offers (
                offer_id TEXT PRIMARY KEY,
                candidate_id TEXT,
                offer_status TEXT,
                offer_hash TEXT,
                created_timestamp TEXT,
                sent_timestamp TEXT,
                viewed_timestamp TEXT,
                signed_timestamp TEXT,
                accepted_timestamp TEXT
            );
            CREATE TABLE interviews (
                interview_id TEXT PRIMARY KEY,
                candidate_id TEXT,
                schedule_time TEXT,
                interview_status TEXT
            );
            """
        )
        # 4 offers: 1 created only, 1 sent only, 1 signed only, 1 fully accepted
        rows = [
            ("o1", "c1", "Created", None, "2026-01-01T00:00:00", None, None, None, None),
            ("o2", "c2", "Sent", None, "2026-01-01T00:00:00", "2026-01-01T01:00:00", None, None, None),
            ("o3", "c3", "Signed", "hash3", "2026-01-01T00:00:00", "2026-01-01T01:00:00", "2026-01-01T02:00:00", "2026-01-01T03:00:00", None),
            ("o4", "c4", "Accepted", "hash4", "2026-01-01T00:00:00", "2026-01-01T01:00:00", "2026-01-01T02:00:00", "2026-01-01T03:00:00", "2026-01-01T04:00:00"),
        ]
        cursor.executemany(
            "INSERT INTO offers VALUES (?,?,?,?,?,?,?,?,?)", rows
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        config.DB_PATH = cls.original_db_path
        os.unlink(cls.tmp_db.name)

    def test_funnel_counts(self):
        fc = metrics_engine.get_funnel_counts()
        self.assertEqual(fc["total_offers"], 4)
        self.assertEqual(fc["sent"], 3)
        self.assertEqual(fc["viewed"], 2)
        self.assertEqual(fc["signed"], 2)
        self.assertEqual(fc["accepted"], 1)

    def test_acceptance_rate(self):
        fc = metrics_engine.get_funnel_counts()
        rates = metrics_engine.get_acceptance_rate(fc)
        # accepted / signed = 1/2 = 50%
        self.assertAlmostEqual(rates["acceptance_rate_pct"], 50.0)

    def test_dropoff_breakdown_shape(self):
        df = metrics_engine.get_dropoff_breakdown()
        self.assertEqual(list(df["stage"]), ["Created", "Sent", "Viewed", "Signed", "Accepted"])
        self.assertEqual(df.iloc[0]["count"], 4)
        self.assertEqual(df.iloc[-1]["count"], 1)

    def test_metric_dictionary_not_empty(self):
        df = metrics_engine.get_metric_dictionary()
        self.assertGreater(len(df), 0)
        self.assertIn("metric", df.columns)
        self.assertIn("source", df.columns)
        self.assertIn("decision", df.columns)


if __name__ == "__main__":
    unittest.main()
