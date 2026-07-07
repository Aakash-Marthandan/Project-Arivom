-- M10: per-source checking cadence, the basis of the /freshness SLA
-- table. This is how often WE check the source (cron reality), not how
-- often the source publishes — the distinction the page spells out.
ALTER TABLE sources ADD COLUMN cadence TEXT
  CHECK (cadence IN ('half-hourly', 'hourly', 'daily', 'monthly', 'manual'));

COMMENT ON COLUMN sources.cadence IS
  'How often pipelines check this source (cron cadence); manual = run on demand. Drives the /freshness SLA colours.';
