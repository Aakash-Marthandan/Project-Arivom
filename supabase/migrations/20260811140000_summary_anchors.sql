-- Anchors: Arivom's own sourced records cited inside a summary (D-040).
--
-- Summaries may now cite our published facts as [A1], [A2] alongside the
-- outlet markers [1], [2] — "he said the seat was won narrowly [2]; the
-- recorded margin was 1,455 votes [A1]". A displayed citation has to resolve
-- to its source (pillar 1), so the records behind those markers are stored
-- with the summary rather than rebuilt at read time: the underlying facts can
-- change, and a summary must keep pointing at what it actually cited.

ALTER TABLE news_clusters ADD COLUMN anchors JSONB;

COMMENT ON COLUMN news_clusters.anchors IS
  'Ordered list of Arivom records cited by this summary as [A1], [A2], ... '
  'Each carries label, value, source_name and whether the fact is '
  'self-declared. Frozen at write time so the citation always resolves.';
