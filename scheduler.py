"""
scheduler.py
Interview scheduling logic: auto-schedules interviews for newly accepted
candidates who don't yet have one, and exposes status-tracking queries
for the dashboard's "Interview Scheduling" page.
"""

import sqlite3
import uuid
import random
import logging
from datetime import datetime, timedelta

import pandas as pd

import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("scheduler")


def _connect():
    return sqlite3.connect(config.DB_PATH)


def find_unscheduled_accepted_candidates() -> pd.DataFrame:
    """Candidates who accepted an offer but have no interview record yet."""
    query = """
        SELECT o.candidate_id, o.offer_id, o.accepted_timestamp
        FROM offers o
        LEFT JOIN interviews i ON o.candidate_id = i.candidate_id
        WHERE o.accepted_timestamp IS NOT NULL AND i.interview_id IS NULL;
    """
    conn = _connect()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    return df


def auto_schedule_interviews() -> int:
    """
    Auto-schedule logic: for every accepted candidate without an interview,
    create one 2-5 business days out. Returns number of interviews created.
    """
    pending = find_unscheduled_accepted_candidates()
    if pending.empty:
        logger.info("No unscheduled accepted candidates found.")
        return 0

    conn = _connect()
    try:
        cursor = conn.cursor()
        created = 0
        for _, row in pending.iterrows():
            accepted_dt = datetime.fromisoformat(row["accepted_timestamp"])
            schedule_dt = accepted_dt + timedelta(days=random.randint(2, 5), hours=random.uniform(0, 8))
            cursor.execute(
                """
                INSERT INTO interviews (interview_id, candidate_id, schedule_time, interview_status)
                VALUES (?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), row["candidate_id"], schedule_dt.isoformat(timespec="seconds"), "Scheduled"),
            )
            created += 1
        conn.commit()
        logger.info("Auto-scheduled %d new interviews.", created)
    finally:
        conn.close()
    return created


def get_upcoming_interviews(limit: int = 100) -> pd.DataFrame:
    """Interviews scheduled in the future, soonest first - the live ops view."""
    query = """
        SELECT i.interview_id, c.full_name, c.email, i.schedule_time, i.interview_status
        FROM interviews i
        JOIN candidates c ON i.candidate_id = c.candidate_id
        WHERE i.interview_status = 'Scheduled'
        ORDER BY i.schedule_time ASC
        LIMIT ?;
    """
    conn = _connect()
    try:
        df = pd.read_sql_query(query, conn, params=(limit,))
    finally:
        conn.close()
    return df


def get_interview_status_breakdown() -> pd.DataFrame:
    query = "SELECT interview_status, COUNT(*) AS count FROM interviews GROUP BY interview_status;"
    conn = _connect()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    return df


if __name__ == "__main__":
    n = auto_schedule_interviews()
    print(f"Auto-scheduled {n} interviews.")
    print(get_interview_status_breakdown())
