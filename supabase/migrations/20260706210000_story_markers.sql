-- D-026 story markers: facts, never judgments.
--
-- civic_priority: selection tier within displayed news (high = statewide
-- policy impact, elections, courts, safety affecting many), assigned
-- offline with a published rubric. sources_disagree: set by the summary
-- stage when tracked outlets report conflicting facts about the event;
-- the checked summary names the disagreement with citations. A
-- "controversy score" was considered and refused (pillar 2; D-026).

ALTER TABLE news_items
  ADD COLUMN civic_priority TEXT
    CHECK (civic_priority IN ('high', 'normal'));
COMMENT ON COLUMN news_items.civic_priority IS
  'D-026 civic priority tier (high/normal), rubric published on /methodology. Never engagement-based.';

ALTER TABLE news_clusters
  ADD COLUMN sources_disagree BOOLEAN NOT NULL DEFAULT false;
COMMENT ON COLUMN news_clusters.sources_disagree IS
  'True when member outlets report conflicting facts; the checked summary states the disagreement with citations (D-026).';
