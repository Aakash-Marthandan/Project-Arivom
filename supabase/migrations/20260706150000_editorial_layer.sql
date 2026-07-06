-- D-025 editorial layer: civic classification and the Arivom headline.
--
-- civic_class: subject-based selection tier assigned offline by the
-- extraction stage (civic / adjacent / soft). Feeds render civic +
-- adjacent; soft never enters product surfaces but stays queryable.
-- title_clean_*: bilingual titles in Arivom's calm, informative voice,
-- spot-checked like summaries; the outlet's original headline remains in
-- headline_orig (displayed on story pages, provenance intact).

ALTER TABLE news_items
  ADD COLUMN civic_class TEXT
    CHECK (civic_class IN ('civic', 'adjacent', 'soft')),
  ADD COLUMN title_clean_en TEXT,
  ADD COLUMN title_clean_ta TEXT;

COMMENT ON COLUMN news_items.civic_class IS
  'D-025 selection tier: civic/adjacent shown in feeds, soft never displayed. Subject-based, actor-blind, criteria published.';
COMMENT ON COLUMN news_items.title_clean_en IS
  'Arivom-voice English title (pipeline-written, spot-checked). Original stays in headline_orig.';
COMMENT ON COLUMN news_items.title_clean_ta IS
  'Arivom-voice Tamil title (pipeline-written, spot-checked). Original stays in headline_orig.';
