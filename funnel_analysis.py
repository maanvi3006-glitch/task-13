"""
funnel_analysis.py
Higher-level funnel and cohort analysis built on top of metrics_engine.
Produces the candidate-level funnel table and per-stage conversion summary
used by the dashboard's "Funnel Analytics" page.
"""

import sqlite3
import logging

import pandas as pd

import config
import metrics_engine

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("funnel_analysis")


def _connect():
    return sqlite3.connect(config.DB_PATH)


def get_candidate_funnel_table(limit: int = 200) -> pd.DataFrame:
    """One row per candidate showing their furthest funnel stage and key timestamps."""
    query = """
        SELECT
            c.candidate_id,
            c.full_name,
            c.email,
            o.offer_status,
            o.created_timestamp,
            o.sent_timestamp,
            o.viewed_timestamp,
            o.signed_timestamp,
            o.accepted_timestamp
        FROM candidates c
        JOIN offers o ON c.candidate_id = o.candidate_id
        ORDER BY o.created_timestamp DESC
        LIMIT ?;
    """
    conn = _connect()
    try:
        df = pd.read_sql_query(query, conn, params=(limit,))
    finally:
        conn.close()
    return df


def get_funnel_chart_data() -> pd.DataFrame:
    """Stage labels + counts, shaped for a Plotly funnel chart."""
    fc = metrics_engine.get_funnel_counts()
    return pd.DataFrame(
        {
            "stage": ["Offer Created", "Offer Sent", "Offer Viewed", "Offer Signed", "Offer Accepted"],
            "count": [fc["total_offers"], fc["sent"], fc["viewed"], fc["signed"], fc["accepted"]],
        }
    )


def get_weekly_cohort_acceptance() -> pd.DataFrame:
    """
    Cohorts candidates by the week their offer was created, tracks acceptance
    rate per cohort. Useful for spotting whether a recent process change
    improved or hurt acceptance.
    """
    query = """
        SELECT
            strftime('%Y-W%W', created_timestamp) AS cohort_week,
            COUNT(*) AS total_offers,
            SUM(CASE WHEN accepted_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS accepted
        FROM offers
        GROUP BY cohort_week
        ORDER BY cohort_week;
    """
    conn = _connect()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    df["acceptance_rate_pct"] = (
        (df["accepted"] / df["total_offers"].replace(0, pd.NA)) * 100
    ).round(2)
    return df


if __name__ == "__main__":
    print(get_funnel_chart_data())
    print(get_weekly_cohort_acceptance().tail())
