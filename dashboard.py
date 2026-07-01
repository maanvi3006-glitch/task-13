"""
dashboard.py
Streamlit live dashboard for PlaceMux Task 13: Offer -> Acceptance funnel.

Pages:
  - Executive Overview
  - Funnel Analytics
  - Verification Monitoring
  - Interview Scheduling
  - Export Center

Run:
    streamlit run dashboard.py
"""

import os
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
import metrics_engine
import funnel_analysis
import validation_checks
import scheduler
import export_reports

st.set_page_config(page_title="PlaceMux | Offer -> Acceptance", layout="wide")


def _db_ready() -> bool:
    return os.path.exists(config.DB_PATH)


def _has_data() -> bool:
    if not _db_ready():
        return False
    conn = sqlite3.connect(config.DB_PATH)
    try:
        count = pd.read_sql_query("SELECT COUNT(*) AS c FROM offers;", conn).iloc[0]["c"]
    except Exception:
        return False
    finally:
        conn.close()
    return count > 0


def page_executive_overview():
    st.title("Executive Overview")
    st.caption("Task 13 - Verification & Interview Scheduling | Focus: Track offer -> acceptance")

    fc = metrics_engine.get_funnel_counts()
    rates = metrics_engine.get_acceptance_rate(fc)
    validation = validation_checks.run_all_checks()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Offers", f"{fc['total_offers']:,}")
    c2.metric("Signed Offers", f"{fc['signed']:,}")
    c3.metric("Accepted Offers", f"{fc['accepted']:,}")
    c4.metric("Acceptance Rate (Accepted/Signed)", f"{rates['acceptance_rate_pct']}%")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Send Rate", f"{rates['send_rate_pct']}%")
    c6.metric("View Rate", f"{rates['view_rate_pct']}%")
    c7.metric("Sign Rate", f"{rates['sign_rate_pct']}%")
    c8.metric("Overall Offer->Acceptance", f"{rates['overall_offer_to_acceptance_pct']}%")

    st.divider()
    status_color = "green" if validation["overall_status"] == "PASS" else "orange"
    st.markdown(f"**Data Quality Status:** :{status_color}[{validation['overall_status']}]")
    fcol1, fcol2, fcol3 = st.columns(3)
    fcol1.metric("Freshness", validation["freshness"]["status"], f"{validation['freshness']['age_hours']}h old")
    fcol2.metric("Duplicate Candidates Flagged", validation["duplicate_candidates_flagged"])
    fcol3.metric("Null-Hash Signed Offers Flagged", validation["null_hash_signed_offers_flagged"])

    st.divider()
    st.subheader("Daily Conversion Trend")
    daily = metrics_engine.get_daily_conversion()
    fig = px.line(
        daily, x="day", y=["offers_created", "offers_accepted"],
        markers=True, title="Offers Created vs Accepted, Daily"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Metric Dictionary - where every number above comes from")
    st.dataframe(metrics_engine.get_metric_dictionary(), use_container_width=True, hide_index=True)


def page_funnel_analytics():
    st.title("Funnel Analytics")

    chart_df = funnel_analysis.get_funnel_chart_data()
    fig = go.Figure(
        go.Funnel(
            y=chart_df["stage"],
            x=chart_df["count"],
            textinfo="value+percent initial",
        )
    )
    fig.update_layout(title="Offer -> Acceptance Funnel")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Stage-over-Stage Drop-off")
    dropoff = metrics_engine.get_dropoff_breakdown()
    st.dataframe(dropoff, use_container_width=True, hide_index=True)

    st.subheader("Weekly Cohort Acceptance")
    cohort = funnel_analysis.get_weekly_cohort_acceptance()
    fig2 = px.bar(cohort, x="cohort_week", y="acceptance_rate_pct", title="Acceptance Rate by Cohort Week")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Candidate-Level Funnel (most recent 200)")
    st.dataframe(funnel_analysis.get_candidate_funnel_table(200), use_container_width=True, hide_index=True)


def page_verification_monitoring():
    st.title("Verification Monitoring")
    st.caption("Trust layer: duplicates, nulls, freshness, event integrity, and tamper-evidence checks.")

    summary = validation_checks.run_all_checks()
    status_color = "green" if summary["overall_status"] == "PASS" else "orange"
    st.markdown(f"### Overall Status: :{status_color}[{summary['overall_status']}]")

    st.subheader("Freshness Check")
    st.json(summary["freshness"])

    st.subheader("Event Integrity Check")
    st.json(summary["event_integrity"])

    st.subheader("Duplicate Offers (candidates with >1 offer)")
    dupes = validation_checks.check_duplicate_offers()
    st.dataframe(dupes, use_container_width=True, hide_index=True)
    if dupes.empty:
        st.success("No duplicate offers detected.")
    else:
        st.warning(f"{len(dupes)} candidates have duplicate offers - investigate offer-creation retries.")

    st.subheader("Signed Offers Missing Tamper-Evidence Hash")
    nulls = validation_checks.check_null_fields()
    st.dataframe(nulls, use_container_width=True, hide_index=True)
    if nulls.empty:
        st.success("All signed offers have a valid hash.")
    else:
        st.warning(f"{len(nulls)} signed offers are missing their integrity hash - pipeline gap.")

    st.divider()
    st.subheader("Verify a Specific Offer (tamper-evidence check)")
    st.caption("Proves a disputed offer is authentic and hasn't been quietly altered.")
    conn = sqlite3.connect(config.DB_PATH)
    sample_signed = pd.read_sql_query(
        "SELECT offer_id FROM offers WHERE offer_hash IS NOT NULL LIMIT 1;", conn
    )
    conn.close()
    default_id = sample_signed.iloc[0]["offer_id"] if not sample_signed.empty else ""
    offer_id_input = st.text_input("Offer ID", value=default_id)
    if st.button("Verify Offer Authenticity"):
        result = validation_checks.verify_offer_integrity(offer_id_input)
        if result["status"] == "VERIFIED":
            st.success(f"Offer {offer_id_input} is VERIFIED - hash matches, not tampered.")
        elif result["status"] == "TAMPERED":
            st.error(f"Offer {offer_id_input} hash MISMATCH - possible tampering.")
        else:
            st.info(f"Status: {result['status']}")
        st.json(result)


def page_interview_scheduling():
    st.title("Interview Scheduling")

    if st.button("Run Auto-Schedule for Newly Accepted Candidates"):
        n = scheduler.auto_schedule_interviews()
        st.success(f"Auto-scheduled {n} new interview(s).")

    st.subheader("Interview Status Breakdown")
    breakdown = scheduler.get_interview_status_breakdown()
    fig = px.pie(breakdown, names="interview_status", values="count", title="Interview Status Distribution")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Upcoming Scheduled Interviews")
    upcoming = scheduler.get_upcoming_interviews()
    st.dataframe(upcoming, use_container_width=True, hide_index=True)

    st.subheader("Candidates Awaiting Scheduling (Accepted, no interview yet)")
    pending = scheduler.find_unscheduled_accepted_candidates()
    st.dataframe(pending, use_container_width=True, hide_index=True)
    if not pending.empty:
        st.info(f"{len(pending)} accepted candidates do not yet have an interview scheduled.")


def page_export_center():
    st.title("Export Center")

    if st.button("Generate Acceptance Report (CSV)"):
        path = export_reports.export_acceptance_report()
        st.success(f"Report generated: {path}")

    if st.button("Generate Dashboard Summary (CSV)"):
        path = export_reports.export_dashboard_summary()
        st.success(f"Summary generated: {path}")

    st.divider()
    if os.path.exists(config.ACCEPTANCE_REPORT_CSV):
        with open(config.ACCEPTANCE_REPORT_CSV, "rb") as f:
            st.download_button("Download Acceptance Report", f, file_name="acceptance_report.csv")

    if os.path.exists(config.DASHBOARD_EXPORT_CSV):
        with open(config.DASHBOARD_EXPORT_CSV, "rb") as f:
            st.download_button("Download Dashboard Summary", f, file_name="dashboard_export.csv")


def main():
    st.sidebar.title("PlaceMux")
    st.sidebar.caption("Task 13 - Data Analyst - Phase 2")

    if not _has_data():
        st.error(
            "No data found. Run the setup pipeline first:\n\n"
            "1. python create_database.py\n"
            "2. python generate_data.py\n\n"
            "Then restart this dashboard."
        )
        return

    pages = {
        "Executive Overview": page_executive_overview,
        "Funnel Analytics": page_funnel_analytics,
        "Verification Monitoring": page_verification_monitoring,
        "Interview Scheduling": page_interview_scheduling,
        "Export Center": page_export_center,
    }
    selection = st.sidebar.radio("Navigate", list(pages.keys()))
    pages[selection]()


if __name__ == "__main__":
    main()
