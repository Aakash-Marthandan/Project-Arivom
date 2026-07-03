-- M2: facts can now be derived spatially (e.g. an AC's current district
-- assigned by majority polygon overlap). Never edit a merged migration —
-- this extends the M1 CHECK by replacement.

ALTER TABLE facts DROP CONSTRAINT facts_extraction_method_check;
ALTER TABLE facts ADD CONSTRAINT facts_extraction_method_check
  CHECK (extraction_method IN
    ('manual', 'llm_bulk', 'parser', 'api', 'scrape', 'bulk', 'pdf', 'spatial'));
