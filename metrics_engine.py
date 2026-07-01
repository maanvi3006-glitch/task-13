"""
metrics_engine.py
Computes every decision-grade metric shown on the dashboard, each one traceable
back to an explicit SQL query against the SQLite database. No metric here is
computed without a defined source - see DOCSTRINGS for "source" and "decision".
"""

import sqlite3
import logging

import pandas as pd

import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("metrics_engine")


def _connect():
    return sqlite3.connect(config.DB_PATH)


def get_funnel_counts() -> dict:
    """
    Source: offers table, timestamp columns presence per stage.
    Decision: identifies exactly which funnel stage is leaking candidates,
    so the team knows whether to fix offer delivery, offer content/clarity,
    or signing friction.
    """
    query = """
        SELECT
            COUNT(*) AS total_offers,
            SUM(CASE WHEN sent_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS sent,
            SUM(CASE WHEN viewed_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS viewed,
            SUM(CASE WHEN signed_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS signed,
            SUM(CASE WHEN accepted_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS accepted
        FROM offers;
    """
    conn = _connect()
    try:
        row = pd.read_sql_query(query, conn).iloc[0].to_dict()
    finally:
        conn.close()
    return {k: int(v) for k, v in row.items()}


def get_interview_counts() -> dict:
    """
    Source: interviews table, grouped by interview_status.
    Decision: tells ops whether scheduled interviews are converting to
    completions, or whether no-shows/cancellations need follow-up automation.
    """
    query = "SELECT interview_status, COUNT(*) AS cnt FROM interviews GROUP BY interview_status;"
    conn = _connect()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    return dict(zip(df["interview_status"], df["cnt"]))


def get_daily_conversion() -> pd.DataFrame:
    """
    Source: offers.created_timestamp / offers.accepted_timestamp, grouped by day.
    Decision: a sudden multi-day drop in acceptance rate signals a live problem
    (e.g. broken e-sign link) that needs same-day investigation, not a vanity trend line.
    """
    query = """
        SELECT
            DATE(created_timestamp) AS day,
            COUNT(*) AS offers_created,
            SUM(CASE WHEN accepted_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS offers_accepted
        FROM offers
        GROUP BY DATE(created_timestamp)
        ORDER BY day;
    """
    conn = _connect()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    df["acceptance_rate_pct"] = (
        (df["offers_accepted"] / df["offers_created"].replace(0, pd.NA)) * 100
    ).round(2)
    return df


def get_acceptance_rate(funnel_counts: dict = None) -> dict:
    """
    Source: derived from get_funnel_counts().
    Decision: THE headline number the founder checks. Below threshold (set by
    business, e.g. 70%) triggers candidate-experience review of the offer flow.
    """
    fc = funnel_counts or get_funnel_counts()
    acceptance_rate = (fc["accepted"] / fc["signed"] * 100) if fc["signed"] else 0.0
    sign_rate = (fc["signed"] / fc["viewed"] * 100) if fc["viewed"] else 0.0
    view_rate = (fc["viewed"] / fc["sent"] * 100) if fc["sent"] else 0.0
    send_rate = (fc["sent"] / fc["total_offers"] * 100) if fc["total_offers"] else 0.0
    overall_conversion = (
        (fc["accepted"] / fc["total_offers"] * 100) if fc["total_offers"] else 0.0
    )
    return {
        "send_rate_pct": round(send_rate, 2),
        "view_rate_pct": round(view_rate, 2),
        "sign_rate_pct": round(sign_rate, 2),
        "acceptance_rate_pct": round(acceptance_rate, 2),
        "overall_offer_to_acceptance_pct": round(overall_conversion, 2),
    }


def get_dropoff_breakdown(funnel_counts: dict = None) -> pd.DataFrame:
    """
    Source: derived from get_funnel_counts(), stage-over-stage deltas.
    Decision: pinpoints the single worst-leaking stage to prioritize fixing first.
    """
    fc = funnel_counts or get_funnel_counts()
    stages = ["total_offers", "sent", "viewed", "signed", "accepted"]
    labels = ["Created", "Sent", "Viewed", "Signed", "Accepted"]
    rows = []
    prev = None
    for label, key in zip(labels, stages):
        count = fc[key]
        dropoff = None if prev is None else prev - count
        dropoff_pct = None if prev in (None, 0) else round((dropoff / prev) * 100, 2)
        rows.append(
            {"stage": label, "count": count, "dropoff_from_prev": dropoff, "dropoff_pct": dropoff_pct}
        )
        prev = count
    return pd.DataFrame(rows)


def get_metric_dictionary() -> pd.DataFrame:
    """
    The metric dictionary: every number on the dashboard, its source table/column,
    and the decision it informs. This is what makes the dashboard 'decision-grade'
    rather than a wall of unexplained numbers.
    """
    rows = [
        {
            "metric": "Total Offers",
            "source": "offers (COUNT *)",
            "decision": "Volume baseline; denominator for every other rate.",
        },
        {
            "metric": "Send Rate %",
            "source": "offers.sent_timestamp NOT NULL / total_offers",
            "decision": "Low value -> offer-issuance pipeline is broken, fix delivery first.",
        },
        {
            "metric": "View Rate %",
            "source": "offers.viewed_timestamp NOT NULL / sent",
            "decision": "Low value -> candidates aren't opening offers; check email/notification copy.",
        },
        {
            "metric": "Sign Rate %",
            "source": "offers.signed_timestamp NOT NULL / viewed",
            "decision": "Low value -> offer content/terms causing hesitation; review with recruiting.",
        },
        {
            "metric": "Acceptance Rate %",
            "source": "offers.accepted_timestamp NOT NULL / signed",
            "decision": "Headline KPI; below SLA threshold triggers candidate-experience review.",
        },
        {
            "metric": "Overall Offer->Acceptance %",
            "source": "accepted / total_offers",
            "decision": "End-to-end funnel health for founder-level reporting.",
        },
        {
            "metric": "Interview Scheduled Count",
            "source": "interviews (COUNT *)",
            "decision": "Confirms hand-off from acceptance into scheduling actually fired.",
        },
        {
            "metric": "Interview Completion Rate",
            "source": "interviews.interview_status = 'Completed' / total interviews",
            "decision": "Low value -> scheduling friction or no-show problem needing reminders.",
        },
    ]
    return pd.DataFrame(rows)


if __name__ == "__main__":
    fc = get_funnel_counts()
    logger.info("Funnel counts: %s", fc)
    print("Funnel counts:", fc)
    print("Acceptance metrics:", get_acceptance_rate(fc))
    print("Interview counts:", get_interview_counts())
