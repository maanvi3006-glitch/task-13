-- funnel_queries.sql
-- Reference analytics queries used by metrics_engine.py / funnel_analysis.py
-- These are run via sqlite3 connection in Python; kept here as the source of truth
-- so every number in the dashboard can be traced back to an explicit query.

-- 1. Total offers created
-- SELECT COUNT(*) FROM offers;

-- 2. Funnel stage counts (offer lifecycle)
SELECT
    COUNT(*) AS total_offers,
    SUM(CASE WHEN sent_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS sent,
    SUM(CASE WHEN viewed_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS viewed,
    SUM(CASE WHEN signed_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS signed,
    SUM(CASE WHEN accepted_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS accepted
FROM offers;

-- 3. Acceptance rate = accepted / signed
-- SELECT
--   CAST(SUM(CASE WHEN accepted_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS FLOAT)
--   / NULLIF(SUM(CASE WHEN signed_timestamp IS NOT NULL THEN 1 ELSE 0 END), 0) AS acceptance_rate
-- FROM offers;

-- 4. Daily conversion (offers created vs accepted per day)
SELECT
    DATE(created_timestamp) AS day,
    COUNT(*) AS offers_created,
    SUM(CASE WHEN accepted_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS offers_accepted
FROM offers
GROUP BY DATE(created_timestamp)
ORDER BY day;

-- 5. Candidate-level funnel (one row per candidate, furthest stage reached)
SELECT
    c.candidate_id,
    c.full_name,
    o.offer_status,
    o.signed_timestamp,
    o.accepted_timestamp
FROM candidates c
JOIN offers o ON c.candidate_id = o.candidate_id;

-- 6. Interview success metrics
SELECT
    interview_status,
    COUNT(*) AS count
FROM interviews
GROUP BY interview_status;

-- 7. Drop-off between each funnel stage
-- computed in Python from query #2 since SQLite lacks easy step math inline

-- 8. Duplicate offer_id / candidate_id detection
SELECT candidate_id, COUNT(*) AS cnt
FROM offers
GROUP BY candidate_id
HAVING COUNT(*) > 1;

-- 9. Freshness check: most recent event per offer
SELECT offer_id, MAX(timestamp) AS last_event_time
FROM events
GROUP BY offer_id;
