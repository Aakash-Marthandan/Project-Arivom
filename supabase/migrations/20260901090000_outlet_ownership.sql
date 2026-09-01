-- Outlets as first-class subjects, so we can hold sourced facts about them (D-042).
--
-- The registry has lived in pipelines/data/outlets.json since M6, which is fine
-- for a poller but cannot carry provenance per claim. Ownership is exactly the
-- kind of assertion that must: "this outlet's parent is controlled by a sitting
-- MP" is a claim about a real person, and it does not enter the database
-- without a citation (pillar 1).
--
-- Ownership claims are stored as rows in `facts`, not as columns here. That
-- gets them the provenance columns the whole platform already enforces, lets
-- two sources corroborate or disagree on the same key, and makes them render
-- through the existing provenance chip with no new UI concept.

CREATE TABLE outlets (
  id           BIGSERIAL PRIMARY KEY,
  slug         TEXT NOT NULL UNIQUE,
  name         TEXT NOT NULL,
  lang         TEXT NOT NULL CHECK (lang IN ('ta', 'en')),
  role         TEXT NOT NULL,
  status       TEXT NOT NULL,
  homepage     TEXT,
  -- The sources row this outlet publishes through, when it is polled. Null for
  -- registry entries with no machine-readable feed yet.
  source_id    BIGINT REFERENCES sources(id),
  retrieved_at TIMESTAMPTZ NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE outlets IS
  'The tracked outlet registry, promoted from pipelines/data/outlets.json so '
  'that ownership and other claims about an outlet can carry provenance.';

CREATE INDEX outlets_status_idx ON outlets (status, lang);

-- Ownership claims live in facts, keyed by these:
--   owner            the parent company, trust or group that publishes it
--   owner_group      the controlling group, where one owner runs several outlets
--   ownership_type   Ground News's published eight-category taxonomy, attributed
--   political_affiliation  documented links only, one citation per claim
ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_subject_type_check;
ALTER TABLE facts ADD CONSTRAINT facts_subject_type_check
  CHECK (subject_type IN ('person', 'locality', 'office', 'outlet'));

ALTER TABLE outlets ENABLE ROW LEVEL SECURITY;
CREATE POLICY outlets_public_read ON outlets FOR SELECT USING (true);
