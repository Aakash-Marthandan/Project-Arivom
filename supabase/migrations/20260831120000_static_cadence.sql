-- A cadence for datasets that are final (D-041).
--
-- /freshness compares each source's last retrieval against how often we say
-- we check it. Several sources are not periodic at all: a completed election's
-- results, a finished survey round, a published handbook edition, boundaries
-- fixed at the last delimitation. Holding those to a monthly SLA marked them
-- overdue every month forever, which is not true — nothing was missed — and a
-- transparency page that is permanently red teaches readers to ignore it.
--
-- 'static' says the honest thing: this dataset is final as published, and we
-- re-check it only if the publisher issues a revision.

ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_cadence_check;
ALTER TABLE sources ADD CONSTRAINT sources_cadence_check
  CHECK (cadence IN ('half-hourly', 'hourly', 'daily', 'monthly', 'static', 'manual'));

COMMENT ON COLUMN sources.cadence IS
  'How often pipelines check this source (cron cadence); manual = run on '
  'demand; static = the dataset is final as published and is re-checked only '
  'on a publisher revision. Drives the /freshness SLA colours.';

-- Only datasets that are genuinely closed. Anything that still receives
-- updates (UDISE+, JJM, LGD, Wikidata, Wikipedia) stays on its real cadence.
UPDATE sources SET cadence = 'static'
WHERE name IN (
  'ECI Results Portal — 2026 Tamil Nadu General Election',
  'NFHS-5 district factsheets (2019-21)',
  'TN Statistical Handbook 2020 — Lok Sabha constituencies (data.gov.in)',
  'DataMeet India AC boundaries (ECI-derived)'
);
