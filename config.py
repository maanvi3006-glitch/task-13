"""
config.py
Centralized configuration for the PlaceMux Offer->Acceptance analytics project.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Paths ---
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DATA_DIR = os.path.join(BASE_DIR, "data")
SQL_DIR = os.path.join(BASE_DIR, "sql")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

DB_PATH = os.path.join(DATABASE_DIR, "placemux.db")

CANDIDATES_CSV = os.path.join(DATA_DIR, "candidates.csv")
OFFERS_CSV = os.path.join(DATA_DIR, "offers.csv")
ACCEPTANCE_EVENTS_CSV = os.path.join(DATA_DIR, "acceptance_events.csv")

ACCEPTANCE_REPORT_CSV = os.path.join(REPORTS_DIR, "acceptance_report.csv")
DASHBOARD_EXPORT_CSV = os.path.join(REPORTS_DIR, "dashboard_export.csv")

CREATE_TABLES_SQL = os.path.join(SQL_DIR, "create_tables.sql")
FUNNEL_QUERIES_SQL = os.path.join(SQL_DIR, "funnel_queries.sql")

# --- Data generation ---
NUM_CANDIDATES = 10000
RANDOM_SEED = 42

# Offer lifecycle stage names (used for events + funnel ordering)
FUNNEL_STAGES = [
    "Offer Created",
    "Offer Sent",
    "Offer Viewed",
    "Offer Signed",
    "Offer Accepted",
    "Interview Scheduled",
]

# Probabilities that a candidate progresses to the NEXT stage, given they
# reached the current one. Used to simulate realistic drop-off.
STAGE_PROGRESSION_PROBABILITY = {
    "Offer Created": 1.00,      # baseline: every offer record reaches "created"
    "Offer Sent": 0.97,         # 97% of created offers actually get sent
    "Offer Viewed": 0.85,       # 85% of sent offers get viewed
    "Offer Signed": 0.62,       # 62% of viewed offers get signed
    "Offer Accepted": 0.93,     # 93% of signed offers are marked accepted
    "Interview Scheduled": 0.88 # 88% of accepted candidates get an interview slot
}

# --- Verification / data quality thresholds ---
FRESHNESS_SLA_HOURS = 24       # events older than this without newer activity => stale
DUPLICATE_KEY_FIELDS = ["candidate_id", "offer_id"]

# --- Logging ---
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "pipeline.log")
LOG_LEVEL = "INFO"

for d in (DATABASE_DIR, DATA_DIR, SQL_DIR, REPORTS_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)
