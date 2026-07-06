-- M7.5 polish round (D-024): story images and Ground-style detail content.
--
-- image_url is a LINK to the outlet's own published asset (from the feed's
-- media metadata or the article's og:image). We store the URL as item
-- metadata and hotlink it in the UI; the image itself is never copied,
-- stored, or re-served — same posture as headlines + links (§4E).

ALTER TABLE news_items
  ADD COLUMN image_url TEXT;
COMMENT ON COLUMN news_items.image_url IS
  'Outlet''s own story image URL (feed media/og:image). Hotlinked, never copied (D-024).';

-- Detail-page content: a longer checked summary plus per-outlet coverage
-- notes — neutral, content-descriptive one-liners on what each outlet''s
-- reporting adds ("carries the minister''s statement", "adds casualty
-- figures"). Never quality or slant judgments (pillar 2); verified by the
-- frontier spot-check like the summaries themselves.
ALTER TABLE news_clusters
  ADD COLUMN summary_long_en TEXT,
  ADD COLUMN summary_long_ta TEXT,
  ADD COLUMN coverage_notes JSONB;
COMMENT ON COLUMN news_clusters.coverage_notes IS
  'Array of {news_item_id, note_en, note_ta}: what that outlet''s coverage adds. Content-descriptive only (D-024).';
