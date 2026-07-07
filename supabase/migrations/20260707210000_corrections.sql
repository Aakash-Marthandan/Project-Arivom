-- M10: the public corrections log (pillar 1). Accepted corrections to
-- displayed facts, timestamps and the original value retained. Entries
-- come from the curated, cited seed (pipelines/data/corrections.json);
-- user-filed reports join this log through M9's moderation queue.
CREATE TABLE corrections (
  id BIGSERIAL PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,          -- stable id from the seed
  corrected_on DATE NOT NULL,
  subject_en TEXT NOT NULL,
  subject_ta TEXT NOT NULL,
  field TEXT NOT NULL,               -- the changed field, in plain words
  old_value_en TEXT NOT NULL,        -- the original value, retained
  old_value_ta TEXT NOT NULL,
  new_value_en TEXT NOT NULL,
  new_value_ta TEXT NOT NULL,
  note_en TEXT NOT NULL,             -- why, in plain words
  note_ta TEXT NOT NULL,
  reference TEXT,                    -- public record, e.g. DECISIONS.md anchor
  source_id BIGINT NOT NULL REFERENCES sources(id),
  retrieved_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE corrections IS
  'Public corrections log: what was displayed, what it became, and why. Original values are retained (pillar 1).';

ALTER TABLE corrections ENABLE ROW LEVEL SECURITY;
CREATE POLICY public_read_corrections ON corrections
  FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON corrections TO anon, authenticated;
