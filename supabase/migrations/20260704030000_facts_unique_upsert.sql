-- Fact identity: one row per (subject, key, source). Makes fact upserts a
-- single INSERT ... ON CONFLICT statement (halves round trips for pipeline
-- runs over the WAN pooler) and guards against duplicate facts structurally.

CREATE UNIQUE INDEX uq_facts_subject_key_source
  ON facts (subject_type, subject_id, key, source_id);
