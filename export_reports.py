"""
export_reports.py
Generates the acceptance report and dashboard export CSVs used for sharing
metrics outside the live dashboard (founder/board reporting, spreadsheet hand-off).
"""

import logging

import pandas as pd

import config
import metrics_engine
import funnel_analysis
import validation_checks

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("export_reports")


def export_acceptance_report():
    """One row per candidate with funnel stage + verification status, for sharing."""
    df = funnel_analysis.get_candidate_funnel_table(limit=100000)
    df.to_csv(config.ACCEPTANCE_REPORT_CSV, index=False)
    logger.info("Acceptance report exported to %s (%d rows)", config.ACCEPTANCE_REPORT_CSV, len(df))
    return config.ACCEPTANCE_REPORT_CSV


def export_dashboard_summary():
    """Single-row summary of every headline metric, for board/founder snapshots."""
    fc = metrics_engine.get_funnel_counts()
    rates = metrics_engine.get_acceptance_rate(fc)
    interviews = metrics_engine.get_interview_counts()
    validation = validation_checks.run_all_checks()

    summary = {
        **fc,
        **rates,
        "interviews_scheduled": interviews.get("Scheduled", 0),
        "interviews_completed": interviews.get("Completed", 0),
        "interviews_cancelled": interviews.get("Cancelled", 0),
        "interviews_no_show": interviews.get("No-Show", 0),
        "data_quality_status": validation["overall_status"],
        "freshness_status": validation["freshness"]["status"],
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    pd.DataFrame([summary]).to_csv(config.DASHBOARD_EXPORT_CSV, index=False)
    logger.info("Dashboard summary exported to %s", config.DASHBOARD_EXPORT_CSV)
    return config.DASHBOARD_EXPORT_CSV


if __name__ == "__main__":
    path1 = export_acceptance_report()
    path2 = export_dashboard_summary()
    print(f"Exported: {path1}")
    print(f"Exported: {path2}")
