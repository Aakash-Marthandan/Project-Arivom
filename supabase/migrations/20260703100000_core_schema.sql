-- Arivom core schema (Milestone 1).
-- Implements docs/DESIGN.md §5 with provenance hardened per pillar 1:
-- a fact that cannot carry a source cannot be inserted.
--
-- Conventions:
--  * Never edit this file after it is merged; add a new migration instead.
--  * Works against plain Postgres+PostGIS (local/CI) and hosted Supabase.

CREATE EXTENSION IF NOT EXISTS postgis;

-- Supabase provides these roles; plain Postgres (local dev/CI) does not.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN BYPASSRLS;
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- sources: registry of every place data comes from. Everything else points
-- here — created first because provenance columns depend on it.
-- ---------------------------------------------------------------------------
CREATE TABLE sources (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  url TEXT,
  publisher TEXT NOT NULL,
  license TEXT,
  access_mode TEXT NOT NULL
    CHECK (access_mode IN ('api', 'scrape', 'pdf', 'bulk', 'rti', 'manual')),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE sources IS
  'Registry of data origins. Every stored fact references a row here (pillar 1).';

-- ---------------------------------------------------------------------------
-- localities: LGD/ECI-coded hierarchy with geometry.
-- parent_id follows the primary hierarchy (admin chain, or ac→pc→state for
-- the electoral overlay); district_id links electoral rows to their district.
-- ---------------------------------------------------------------------------
CREATE TABLE localities (
  id BIGSERIAL PRIMARY KEY,
  lgd_code TEXT UNIQUE,            -- Local Government Directory code (TN = 33)
  eci_code TEXT,                   -- ECI constituency number for ac/pc rows
  name_en TEXT NOT NULL,
  name_ta TEXT NOT NULL,
  level TEXT NOT NULL
    CHECK (level IN ('state', 'district', 'taluk', 'block', 'ulb',
                     'panchayat', 'ward', 'ac', 'pc')),
  parent_id BIGINT REFERENCES localities(id),
  district_id BIGINT REFERENCES localities(id),
  geom GEOMETRY(MultiPolygon, 4326),
  source_id BIGINT NOT NULL REFERENCES sources(id),
  retrieved_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_localities_geom ON localities USING GIST (geom);
CREATE INDEX idx_localities_parent ON localities (parent_id);
CREATE INDEX idx_localities_district ON localities (district_id);
CREATE INDEX idx_localities_level ON localities (level);
CREATE UNIQUE INDEX uq_localities_level_eci
  ON localities (level, eci_code) WHERE eci_code IS NOT NULL;
COMMENT ON COLUMN localities.district_id IS
  'For ac/pc rows: the district the constituency is administratively assigned to.';

-- ---------------------------------------------------------------------------
-- Representative spine: offices, persons, tenures.
-- ---------------------------------------------------------------------------
CREATE TABLE offices (
  id BIGSERIAL PRIMARY KEY,
  office_type TEXT NOT NULL
    CHECK (office_type IN ('mla', 'mp_ls', 'mp_rs', 'councillor')),
  locality_id BIGINT NOT NULL REFERENCES localities(id),
  title_en TEXT,
  title_ta TEXT,
  source_id BIGINT NOT NULL REFERENCES sources(id),
  retrieved_at TIMESTAMPTZ NOT NULL,
  UNIQUE (office_type, locality_id)
);

CREATE TABLE persons (
  id BIGSERIAL PRIMARY KEY,
  name_en TEXT NOT NULL,
  name_ta TEXT NOT NULL,
  photo_url TEXT,
  party_en TEXT,
  party_ta TEXT,
  source_id BIGINT NOT NULL REFERENCES sources(id),
  retrieved_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE tenures (
  id BIGSERIAL PRIMARY KEY,
  office_id BIGINT NOT NULL REFERENCES offices(id),
  person_id BIGINT NOT NULL REFERENCES persons(id),
  start_date DATE,
  end_date DATE,                   -- NULL = current
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'vacant', 'resigned', 'deceased', 'disqualified')),
  source_id BIGINT NOT NULL REFERENCES sources(id),
  retrieved_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_tenures_office ON tenures (office_id);
CREATE INDEX idx_tenures_person ON tenures (person_id);

-- Vacancy tracker: offices with no active current tenure (DESIGN.md §5).
CREATE VIEW vacancies AS
  SELECT o.*
  FROM offices o
  LEFT JOIN tenures t
    ON t.office_id = o.id AND t.end_date IS NULL AND t.status = 'active'
  WHERE t.id IS NULL;

-- ---------------------------------------------------------------------------
-- facts: polymorphic sourced facts. The provenance NOT NULLs are the
-- software enforcement of pillar 1.
-- ---------------------------------------------------------------------------
CREATE TABLE facts (
  id BIGSERIAL PRIMARY KEY,
  subject_type TEXT NOT NULL
    CHECK (subject_type IN ('person', 'locality', 'office')),
  subject_id BIGINT NOT NULL,
  key TEXT NOT NULL,               -- e.g. 'declared_assets', 'criminal_cases'
  value JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES sources(id),
  retrieved_at TIMESTAMPTZ NOT NULL,
  extraction_method TEXT NOT NULL
    CHECK (extraction_method IN ('manual', 'llm_bulk', 'parser', 'api', 'scrape', 'bulk', 'pdf')),
  confidence NUMERIC CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  review_status TEXT NOT NULL DEFAULT 'unreviewed'
    CHECK (review_status IN ('unreviewed', 'llm_checked', 'human_verified')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_facts_subject ON facts (subject_type, subject_id, key);

-- ---------------------------------------------------------------------------
-- News layer. Aggregation policy (hard): headline + link + own-words summary
-- only; full article text is never stored.
-- ---------------------------------------------------------------------------
CREATE TABLE news_items (
  id BIGSERIAL PRIMARY KEY,
  outlet TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  headline_orig TEXT NOT NULL,
  lang TEXT NOT NULL CHECK (lang IN ('ta', 'en')),
  published_at TIMESTAMPTZ,
  locality_id BIGINT REFERENCES localities(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_news_items_locality ON news_items (locality_id, published_at DESC);

CREATE TABLE news_clusters (
  id BIGSERIAL PRIMARY KEY,
  summary_en TEXT,                 -- neutral AI summary with citations
  summary_ta TEXT,
  locality_id BIGINT REFERENCES localities(id),
  event_time TIMESTAMPTZ,
  discussion_locked BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_news_clusters_locality ON news_clusters (locality_id, event_time DESC);

CREATE TABLE cluster_coverage (
  cluster_id BIGINT NOT NULL REFERENCES news_clusters(id),
  news_item_id BIGINT NOT NULL REFERENCES news_items(id),
  PRIMARY KEY (cluster_id, news_item_id)
);

-- ---------------------------------------------------------------------------
-- Community: users, contributions, ratings, moderation audit log.
-- ---------------------------------------------------------------------------
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  phone_hash TEXT NOT NULL UNIQUE, -- never store a raw phone number
  identity_tier INT NOT NULL DEFAULT 0
    CHECK (identity_tier BETWEEN 0 AND 3),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE contributions (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  type TEXT NOT NULL
    CHECK (type IN ('correction', 'issue_confirm', 'rating', 'comment')),
  rung_required INT NOT NULL DEFAULT 1 CHECK (rung_required BETWEEN 0 AND 3),
  payload JSONB NOT NULL,
  moderation_state TEXT NOT NULL DEFAULT 'pending'
    CHECK (moderation_state IN ('pending', 'approved', 'rejected')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_contributions_state ON contributions (moderation_state, created_at);

CREATE TABLE ratings (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  locality_id BIGINT NOT NULL REFERENCES localities(id),
  sector TEXT NOT NULL
    CHECK (sector IN ('education', 'health', 'water_sanitation')),
  score INT NOT NULL CHECK (score BETWEEN 1 AND 5),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, locality_id, sector)  -- one live rating per user/locality/sector
);

CREATE TABLE moderation_events (   -- append-only audit log
  id BIGSERIAL PRIMARY KEY,
  contribution_id BIGINT NOT NULL REFERENCES contributions(id),
  actor TEXT NOT NULL,             -- 'llm_classifier' | moderator identifier
  action TEXT NOT NULL,
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Append-only: no UPDATE/DELETE for anyone but superuser; RLS has no policies.
REVOKE UPDATE, DELETE ON moderation_events FROM PUBLIC;

-- ---------------------------------------------------------------------------
-- Row-Level Security (DESIGN.md §5): public read on civic data; community
-- tables are closed until the auth milestone adds scoped policies.
-- ---------------------------------------------------------------------------
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE localities ENABLE ROW LEVEL SECURITY;
ALTER TABLE offices ENABLE ROW LEVEL SECURITY;
ALTER TABLE persons ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenures ENABLE ROW LEVEL SECURITY;
ALTER TABLE facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE news_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE news_clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE cluster_coverage ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE contributions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ratings ENABLE ROW LEVEL SECURITY;
ALTER TABLE moderation_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY public_read_sources ON sources
  FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read_localities ON localities
  FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read_offices ON offices
  FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read_persons ON persons
  FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read_tenures ON tenures
  FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read_facts ON facts
  FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read_news_items ON news_items
  FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read_news_clusters ON news_clusters
  FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read_cluster_coverage ON cluster_coverage
  FOR SELECT TO anon, authenticated USING (true);

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON sources, localities, offices, persons, tenures, facts,
  news_items, news_clusters, cluster_coverage, vacancies
  TO anon, authenticated;
