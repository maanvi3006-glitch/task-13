"""
validation_checks.py
Decision-grade data quality and verification layer:
  - duplicate detection
  - null validation
  - timestamp freshness checks
  - event integrity checks
  - offer tamper-evidence verification (signed offers must be independently verifiable)

These are the checks that catch a broken pipe before the founder does.
"""

import sqlite3
import hashlib
import logging
from datetime import datetime, timedelta

import pandas as pd

import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("validation_checks")


def _connect():
    return sqlite3.connect(config.DB_PATH)


def check_duplicate_offers() -> pd.DataFrame:
    """Flags candidates with more than one offer record (possible retry/double-create bug)."""
    query = """
        SELECT candidate_id, COUNT(*) AS offer_count
        FROM offers
        GROUP BY candidate_id
        HAVING COUNT(*) > 1
        ORDER BY offer_count DESC;
    """
    conn = _connect()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    return df


def check_null_fields() -> pd.DataFrame:
    """Flags Signed/Accepted offers missing their tamper-evidence hash - a pipeline gap."""
    query = """
        SELECT offer_id, candidate_id, offer_status, offer_hash, signed_timestamp
        FROM offers
        WHERE offer_status IN ('Signed', 'Accepted') AND offer_hash IS NULL;
    """
    conn = _connect()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    return df


def check_freshness(sla_hours: int = None) -> dict:
    """
    Confirms events are still landing recently. If the most recent event in the
    whole pipeline is older than the SLA, the pipe is likely broken and this
    must be caught here, not reported by the founder.
    """
    sla_hours = sla_hours or config.FRESHNESS_SLA_HOURS
    query = "SELECT MAX(timestamp) AS last_event_time, COUNT(*) AS total_events FROM events;"
    conn = _connect()
    try:
        row = pd.read_sql_query(query, conn).iloc[0]
    finally:
        conn.close()

    if row["last_event_time"] is None:
        return {"status": "FAIL", "reason": "No events found in pipeline.", "last_event_time": None}

    last_event_dt = datetime.fromisoformat(row["last_event_time"])
    age_hours = (datetime.now() - last_event_dt).total_seconds() / 3600
    is_fresh = age_hours <= sla_hours

    return {
        "status": "PASS" if is_fresh else "STALE",
        "last_event_time": row["last_event_time"],
        "age_hours": round(age_hours, 2),
        "sla_hours": sla_hours,
        "total_events": int(row["total_events"]),
    }


def check_event_integrity() -> dict:
    """
    Confirms events reference real candidates/offers (no orphaned events), and
    that funnel stage ordering is internally consistent (e.g. no 'Accepted'
    offer that skipped 'Signed').
    """
    conn = _connect()
    try:
        orphan_query = """
            SELECT COUNT(*) AS orphan_count FROM events e
            LEFT JOIN candidates c ON e.candidate_id = c.candidate_id
            WHERE c.candidate_id IS NULL;
        """
        orphan_count = pd.read_sql_query(orphan_query, conn).iloc[0]["orphan_count"]

        inconsistent_query = """
            SELECT COUNT(*) AS bad_count FROM offers
            WHERE accepted_timestamp IS NOT NULL AND signed_timestamp IS NULL;
        """
        bad_count = pd.read_sql_query(inconsistent_query, conn).iloc[0]["bad_count"]
    finally:
        conn.close()

    return {
        "orphan_events": int(orphan_count),
        "stage_order_violations": int(bad_count),
        "status": "PASS" if orphan_count == 0 and bad_count == 0 else "FAIL",
    }


def verify_offer_integrity(offer_id: str) -> dict:
    """
    Independent tamper-evidence check for a single offer: recomputes the
    SHA-256 hash from the offer's original created fields and compares it to
    the stored offer_hash. This is what answers "if a candidate disputes an
    offer, can we independently verify it's authentic?"
    """
    conn = _connect()
    try:
        query = "SELECT * FROM offers WHERE offer_id = ?;"
        df = pd.read_sql_query(query, conn, params=(offer_id,))
    finally:
        conn.close()

    if df.empty:
        return {"offer_id": offer_id, "status": "NOT_FOUND"}

    row = df.iloc[0]
    if pd.isna(row["offer_hash"]) or row["offer_hash"] is None:
        return {"offer_id": offer_id, "status": "UNSIGNED", "reason": "Offer was never signed."}

    expected_hash = hashlib.sha256(
        f"{row['candidate_id']}|{row['offer_id']}|{row['created_timestamp']}|PLACEMUX_OFFER_V1".encode(
            "utf-8"
        )
    ).hexdigest()

    is_valid = expected_hash == row["offer_hash"]
    return {
        "offer_id": offer_id,
        "status": "VERIFIED" if is_valid else "TAMPERED",
        "stored_hash": row["offer_hash"],
        "recomputed_hash": expected_hash,
    }


def run_all_checks() -> dict:
    """Runs the full verification suite and returns a single summary dict."""
    dupes = check_duplicate_offers()
    nulls = check_null_fields()
    freshness = check_freshness()
    integrity = check_event_integrity()

    summary = {
        "duplicate_candidates_flagged": len(dupes),
        "null_hash_signed_offers_flagged": len(nulls),
        "freshness": freshness,
        "event_integrity": integrity,
        "overall_status": "PASS"
        if (len(dupes) == 0 and len(nulls) == 0 and freshness["status"] == "PASS" and integrity["status"] == "PASS")
        else "ATTENTION_NEEDED",
    }
    logger.info("Validation summary: %s", summary)
    return summary


if __name__ == "__main__":
    summary = run_all_checks()
    print("=== Validation Summary ===")
    for k, v in summary.items():
        print(f"{k}: {v}")
