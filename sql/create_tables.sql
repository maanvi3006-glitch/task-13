-- create_tables.sql
-- PlaceMux Offer -> Acceptance trust layer schema

DROP TABLE IF EXISTS candidates;
DROP TABLE IF EXISTS offers;
DROP TABLE IF EXISTS interviews;
DROP TABLE IF EXISTS events;

CREATE TABLE candidates (
    candidate_id   TEXT PRIMARY KEY,
    full_name      TEXT NOT NULL,
    email          TEXT NOT NULL,
    status         TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE offers (
    offer_id            TEXT PRIMARY KEY,
    candidate_id        TEXT NOT NULL,
    offer_status        TEXT NOT NULL,   -- Created, Sent, Viewed, Signed, Accepted, Declined, Expired
    offer_hash          TEXT,            -- tamper-evidence hash of offer content
    created_timestamp   TEXT,
    sent_timestamp       TEXT,
    viewed_timestamp     TEXT,
    signed_timestamp     TEXT,
    accepted_timestamp   TEXT,
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
);

CREATE TABLE interviews (
    interview_id     TEXT PRIMARY KEY,
    candidate_id      TEXT NOT NULL,
    schedule_time     TEXT,
    interview_status  TEXT NOT NULL,  -- Scheduled, Completed, Cancelled, No-Show
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
);

CREATE TABLE events (
    event_id     TEXT PRIMARY KEY,
    candidate_id TEXT,
    offer_id     TEXT,
    event_name   TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id),
    FOREIGN KEY (offer_id) REFERENCES offers(offer_id)
);

CREATE INDEX idx_offers_candidate ON offers(candidate_id);
CREATE INDEX idx_events_offer ON events(offer_id);
CREATE INDEX idx_events_name ON events(event_name);
CREATE INDEX idx_interviews_candidate ON interviews(candidate_id);
