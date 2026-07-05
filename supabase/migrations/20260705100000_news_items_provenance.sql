-- M6 news ingestion: provenance columns on news_items.
--
-- DESIGN.md §5 puts provenance on `facts` only, but pillar 1 requires every
-- *displayed* fact to carry provenance, and news headlines are displayed
-- facts once feeds ship. This extends D-003 (localities/offices/persons/
-- tenures already carry source_id + retrieved_at) to news_items: source_id
-- points at the outlet's row in `sources` (the §4E outlet registry).
--
-- news_items has never been written to (news ingestion starts with this
-- milestone), so the columns can be NOT NULL from the start.

ALTER TABLE news_items
  ADD COLUMN source_id BIGINT NOT NULL REFERENCES sources(id),
  ADD COLUMN retrieved_at TIMESTAMPTZ NOT NULL;

COMMENT ON COLUMN news_items.source_id IS
  'The outlet''s registry row in sources (D-003 extension: provenance beyond facts).';
COMMENT ON COLUMN news_items.retrieved_at IS
  'When the poller last observed this item in the outlet''s feed.';
COMMENT ON COLUMN news_items.outlet IS
  'Outlet slug from the curated registry (pipelines/data/outlets.json).';
COMMENT ON COLUMN news_items.headline_orig IS
  'Headline as published, plus link metadata only — never article text (DESIGN.md §4E aggregation policy).';

-- The M7 statewide feed reads newest-first without a locality filter;
-- idx_news_items_locality only serves the per-locality path.
CREATE INDEX idx_news_items_published ON news_items (published_at DESC);
