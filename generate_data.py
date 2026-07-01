"""
generate_data.py
Generates realistic synthetic data for candidates, offers, interviews and events,
simulating a real Offer -> Acceptance funnel with believable drop-off at each stage.

Also computes a tamper-evidence hash for each signed offer (SHA-256 over the
offer's immutable fields) so that "is this offer authentic / unmodified" can be
verified independently later (see validation_checks.py:verify_offer_integrity).

Run:
    python generate_data.py
"""

import sqlite3
import uuid
import random
import hashlib
import logging
from datetime import datetime, timedelta

import pandas as pd
from faker import Faker

import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("generate_data")

fake = Faker()
Faker.seed(config.RANDOM_SEED)
random.seed(config.RANDOM_SEED)

WINDOW_DAYS = 45  # offers spread across the last 45 days, for daily-trend charts


def _ts(base: datetime, max_extra_hours: int) -> datetime:
    """Advance a timestamp forward by a random amount, simulating real-world delay."""
    return base + timedelta(hours=random.uniform(0.1, max_extra_hours))


def compute_offer_hash(candidate_id: str, offer_id: str, created_timestamp: str) -> str:
    """
    Tamper-evidence hash. Any change to the offer's core identity fields after
    signing will change this hash, which is how a disputed offer can be
    independently verified as authentic (or flagged as altered).
    """
    payload = f"{candidate_id}|{offer_id}|{created_timestamp}|PLACEMUX_OFFER_V1"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_candidates(n):
    candidates = []
    start = datetime.now() - timedelta(days=WINDOW_DAYS)
    for _ in range(n):
        cid = str(uuid.uuid4())
        created_at = start + timedelta(
            days=random.uniform(0, WINDOW_DAYS - 1),
            hours=random.uniform(0, 23),
        )
        candidates.append(
            {
                "candidate_id": cid,
                "full_name": fake.name(),
                "email": fake.unique.email(),
                "status": "Active",
                "created_at": created_at.isoformat(timespec="seconds"),
            }
        )
    return pd.DataFrame(candidates)


def generate_offers_events_interviews(candidates_df):
    offers = []
    events = []
    interviews = []

    def add_event(candidate_id, offer_id, event_name, ts):
        events.append(
            {
                "event_id": str(uuid.uuid4()),
                "candidate_id": candidate_id,
                "offer_id": offer_id,
                "event_name": event_name,
                "timestamp": ts.isoformat(timespec="seconds"),
            }
        )

    probs = config.STAGE_PROGRESSION_PROBABILITY

    for _, cand in candidates_df.iterrows():
        candidate_id = cand["candidate_id"]
        offer_id = str(uuid.uuid4())
        created_dt = datetime.fromisoformat(cand["created_at"]) + timedelta(
            hours=random.uniform(1, 12)
        )

        offer_status = "Created"
        sent_ts = viewed_ts = signed_ts = accepted_ts = None
        offer_hash = None

        add_event(candidate_id, offer_id, "Offer Created", created_dt)

        # Offer Sent
        if random.random() <= probs["Offer Sent"]:
            sent_dt = _ts(created_dt, 6)
            sent_ts = sent_dt.isoformat(timespec="seconds")
            offer_status = "Sent"
            add_event(candidate_id, offer_id, "Offer Sent", sent_dt)

            # Offer Viewed
            if random.random() <= probs["Offer Viewed"]:
                viewed_dt = _ts(sent_dt, 48)
                viewed_ts = viewed_dt.isoformat(timespec="seconds")
                offer_status = "Viewed"
                add_event(candidate_id, offer_id, "Offer Viewed", viewed_dt)

                # Offer Signed
                if random.random() <= probs["Offer Signed"]:
                    signed_dt = _ts(viewed_dt, 72)
                    signed_ts = signed_dt.isoformat(timespec="seconds")
                    offer_status = "Signed"
                    offer_hash = compute_offer_hash(candidate_id, offer_id, created_dt.isoformat(timespec="seconds"))
                    add_event(candidate_id, offer_id, "Offer Signed", signed_dt)

                    # Offer Accepted
                    if random.random() <= probs["Offer Accepted"]:
                        accepted_dt = _ts(signed_dt, 4)
                        accepted_ts = accepted_dt.isoformat(timespec="seconds")
                        offer_status = "Accepted"
                        add_event(candidate_id, offer_id, "Offer Accepted", accepted_dt)

                        # Interview Scheduled
                        if random.random() <= probs["Interview Scheduled"]:
                            interview_dt = _ts(accepted_dt, 96)
                            add_event(
                                candidate_id, offer_id, "Interview Scheduled", interview_dt
                            )
                            interviews.append(
                                {
                                    "interview_id": str(uuid.uuid4()),
                                    "candidate_id": candidate_id,
                                    "schedule_time": interview_dt.isoformat(
                                        timespec="seconds"
                                    ),
                                    "interview_status": random.choices(
                                        ["Scheduled", "Completed", "Cancelled", "No-Show"],
                                        weights=[0.45, 0.40, 0.10, 0.05],
                                    )[0],
                                }
                            )
                    else:
                        offer_status = "Declined"
                else:
                    offer_status = "Expired"
            # else: stuck at Sent (never viewed) -> realistic drop-off

        offers.append(
            {
                "offer_id": offer_id,
                "candidate_id": candidate_id,
                "offer_status": offer_status,
                "offer_hash": offer_hash,
                "created_timestamp": created_dt.isoformat(timespec="seconds"),
                "sent_timestamp": sent_ts,
                "viewed_timestamp": viewed_ts,
                "signed_timestamp": signed_ts,
                "accepted_timestamp": accepted_ts,
            }
        )

    # Inject a small, known number of intentional data-quality issues so the
    # verification layer has real things to catch (this is what "decision-grade"
    # checks are tested against, not a toy happy path).
    offers_df = pd.DataFrame(offers)
    events_df = pd.DataFrame(events)
    interviews_df = pd.DataFrame(interviews)

    offers_df = _inject_quality_issues(offers_df)

    return offers_df, events_df, interviews_df


def _inject_quality_issues(offers_df, n_dupes=8, n_nulls=5):
    """Intentionally seed a handful of duplicate and null-field rows so the
    validation layer can be demonstrated catching real problems."""
    rng = random.Random(config.RANDOM_SEED)

    # Duplicate candidate offers (simulates a retry bug double-creating offers)
    dupe_rows = offers_df.sample(n=n_dupes, random_state=config.RANDOM_SEED).copy()
    for _, row in dupe_rows.iterrows():
        new_row = row.copy()
        new_row["offer_id"] = str(uuid.uuid4())
        offers_df = pd.concat([offers_df, pd.DataFrame([new_row])], ignore_index=True)

    # Null timestamps on otherwise "Signed" offers (simulates pipeline gap)
    signed_mask = offers_df["offer_status"].isin(["Signed", "Accepted"])
    if signed_mask.sum() > 0:
        idxs = offers_df[signed_mask].sample(
            n=min(n_nulls, signed_mask.sum()), random_state=config.RANDOM_SEED
        ).index
        offers_df.loc[idxs, "offer_hash"] = None

    logger.info(
        "Injected %d duplicate offers and nulled offer_hash on %d signed offers for QA testing.",
        n_dupes,
        n_nulls,
    )
    return offers_df


def persist_to_db(candidates_df, offers_df, events_df, interviews_df):
    conn = sqlite3.connect(config.DB_PATH)
    try:
        candidates_df.to_sql("candidates", conn, if_exists="replace", index=False)
        offers_df.to_sql("offers", conn, if_exists="replace", index=False)
        events_df.to_sql("events", conn, if_exists="replace", index=False)
        interviews_df.to_sql("interviews", conn, if_exists="replace", index=False)
        conn.commit()
        logger.info("Data persisted to SQLite database at %s", config.DB_PATH)
    finally:
        conn.close()


def persist_to_csv(candidates_df, offers_df, events_df):
    candidates_df.to_csv(config.CANDIDATES_CSV, index=False)
    offers_df.to_csv(config.OFFERS_CSV, index=False)
    events_df.to_csv(config.ACCEPTANCE_EVENTS_CSV, index=False)
    logger.info("CSV exports written to %s", config.DATA_DIR)


def main():
    logger.info("Generating %d candidates...", config.NUM_CANDIDATES)
    candidates_df = generate_candidates(config.NUM_CANDIDATES)

    logger.info("Simulating offer lifecycle and events...")
    offers_df, events_df, interviews_df = generate_offers_events_interviews(candidates_df)

    logger.info(
        "Generated: %d candidates, %d offers, %d events, %d interviews",
        len(candidates_df),
        len(offers_df),
        len(events_df),
        len(interviews_df),
    )

    persist_to_db(candidates_df, offers_df, events_df, interviews_df)
    persist_to_csv(candidates_df, offers_df, events_df)

    print("Data generation complete.")
    print(f"  Candidates: {len(candidates_df)}")
    print(f"  Offers:     {len(offers_df)}")
    print(f"  Events:     {len(events_df)}")
    print(f"  Interviews: {len(interviews_df)}")


if __name__ == "__main__":
    main()
