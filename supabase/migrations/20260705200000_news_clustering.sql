-- M7 news clustering: cluster provenance, bilingual titles, citations,
-- moderation lock category, and per-item extraction state.
--
-- news_clusters rows are pipeline-derived displayed facts (summaries are
-- shown to users), so they carry source_id + retrieved_at per the D-003
-- pattern. Both tables are empty of these fields' consumers pre-M7, and
-- news_clusters itself has never been written to, so NOT NULL is safe.

ALTER TABLE news_clusters
  ADD COLUMN source_id BIGINT NOT NULL REFERENCES sources(id),
  ADD COLUMN retrieved_at TIMESTAMPTZ NOT NULL,
  ADD COLUMN title_en TEXT,
  ADD COLUMN title_ta TEXT,
  ADD COLUMN citations JSONB,
  ADD COLUMN lock_category TEXT
    CHECK (lock_category IN ('communal', 'sub_judice', 'allegations')),
  ADD COLUMN content_hash TEXT,
  ADD COLUMN review_status TEXT NOT NULL DEFAULT 'unreviewed'
    CHECK (review_status IN ('unreviewed', 'llm_checked', 'human_verified')),
  ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

COMMENT ON COLUMN news_clusters.summary_en IS
  'Neutral own-words summary with inline [n] citation markers; drafted by a '
  'cheap model, spot-checked by a frontier model (DESIGN §7). Never article text.';
COMMENT ON COLUMN news_clusters.citations IS
  'Array of news_items ids; position n-1 resolves citation marker [n] in the summaries.';
COMMENT ON COLUMN news_clusters.lock_category IS
  'Why discussion_locked was set by the moderation classifier (escalation '
  'protocol, DESIGN §9). The pipeline only ever sets the lock, never clears it.';
COMMENT ON COLUMN news_clusters.content_hash IS
  'Hash of member items; summaries are regenerated only when membership changes.';

-- Per-item entity extraction state (clustering features, never article text).
ALTER TABLE news_items
  ADD COLUMN entities JSONB,
  ADD COLUMN fetch_status TEXT
    CHECK (fetch_status IN ('fetched', 'failed', 'skipped'));

COMMENT ON COLUMN news_items.entities IS
  'Extracted entities for clustering: matched person/district ids, names, '
  'places, organizations, a short own-words gist. Derived metadata only — '
  'article text is read transiently and never stored (D-022).';
COMMENT ON COLUMN news_items.fetch_status IS
  'Whether the transient article fetch for entity extraction succeeded.';
