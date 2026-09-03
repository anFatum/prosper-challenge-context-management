-- ── Extensions ────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── Core catalog tables ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS locations (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    address      TEXT,
    city         TEXT,
    phone        TEXT,
    hours        TEXT,
    capabilities TEXT[] DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_loc_capabilities ON locations USING gin (capabilities);

CREATE TABLE IF NOT EXISTS providers (
    id                   TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    title                TEXT,
    specialty            TEXT,
    languages            TEXT[] DEFAULT '{}',
    accepting_new        BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS appointment_types (
    id                   TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    specialty            TEXT,
    duration_min         INTEGER NOT NULL,
    required_capability  TEXT,
    requires_referral    BOOLEAN DEFAULT FALSE,
    new_patients_allowed BOOLEAN DEFAULT TRUE
);

-- ── Junction tables ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS provider_locations (
    provider_id  TEXT REFERENCES providers(id) ON DELETE CASCADE,
    location_id  TEXT REFERENCES locations(id) ON DELETE CASCADE,
    PRIMARY KEY  (provider_id, location_id)
);
CREATE INDEX IF NOT EXISTS idx_prov_loc_loc ON provider_locations (location_id, provider_id);

CREATE TABLE IF NOT EXISTS provider_appointment_types (
    provider_id   TEXT REFERENCES providers(id) ON DELETE CASCADE,
    appt_type_id  TEXT REFERENCES appointment_types(id) ON DELETE CASCADE,
    PRIMARY KEY   (provider_id, appt_type_id)
);
CREATE INDEX IF NOT EXISTS idx_prov_appt_appt ON provider_appointment_types (appt_type_id, provider_id);

-- ── Name lookup indexes ────────────────────────────────────────────────────
-- Exact case-insensitive match
CREATE INDEX IF NOT EXISTS idx_loc_name_lower  ON locations         (lower(name));
CREATE INDEX IF NOT EXISTS idx_prov_name_lower ON providers         (lower(name));
CREATE INDEX IF NOT EXISTS idx_appt_name_lower ON appointment_types (lower(name));

-- Fuzzy / partial match via trigrams
CREATE INDEX IF NOT EXISTS idx_loc_name_trgm  ON locations         USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_prov_name_trgm ON providers         USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_appt_name_trgm ON appointment_types USING gin (name gin_trgm_ops);

-- Specialty filter
CREATE INDEX IF NOT EXISTS idx_prov_specialty ON providers         (specialty);
CREATE INDEX IF NOT EXISTS idx_appt_specialty ON appointment_types (specialty);

-- ── Calendar slots (partitioned by date) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS calendar_slots (
    id           UUID DEFAULT gen_random_uuid(),
    provider_id  TEXT NOT NULL,
    location_id  TEXT NOT NULL,
    date         DATE NOT NULL,
    start_time   TIME NOT NULL,
    end_time     TIME NOT NULL,
    duration_min SMALLINT GENERATED ALWAYS AS (
                     (EXTRACT(EPOCH FROM (end_time - start_time)) / 60)::SMALLINT
                 ) STORED,
    available    BOOLEAN DEFAULT TRUE,
    booked_at    TIMESTAMPTZ,
    session_id   TEXT,
    PRIMARY KEY  (id, date)
) PARTITION BY RANGE (date);

CREATE INDEX IF NOT EXISTS idx_slots_date_avail
    ON calendar_slots (date, available) WHERE available = TRUE;
CREATE INDEX IF NOT EXISTS idx_slots_prov_loc_date
    ON calendar_slots (provider_id, location_id, date) WHERE available = TRUE;
CREATE INDEX IF NOT EXISTS idx_slots_duration
    ON calendar_slots (duration_min) WHERE available = TRUE;

-- ── Eligible pairs (materialized view) ────────────────────────────────────
-- Pre-joins provider × location × capability. Refresh on any catalog write.
CREATE MATERIALIZED VIEW IF NOT EXISTS eligible_pairs AS
SELECT
    pat.appt_type_id,
    p.id          AS provider_id,
    pl.location_id,
    p.accepting_new,
    at.duration_min,
    at.requires_referral,
    at.new_patients_allowed
FROM providers p
JOIN provider_appointment_types pat ON pat.provider_id  = p.id
JOIN provider_locations         pl  ON pl.provider_id   = p.id
JOIN appointment_types          at  ON at.id = pat.appt_type_id
JOIN locations                  l   ON l.id  = pl.location_id
WHERE
    at.required_capability IS NULL
    OR at.required_capability = ANY(l.capabilities);

CREATE UNIQUE INDEX IF NOT EXISTS idx_eligible_pairs
    ON eligible_pairs (appt_type_id, provider_id, location_id);