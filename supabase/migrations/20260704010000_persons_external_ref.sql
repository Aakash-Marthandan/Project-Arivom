-- M3: idempotency keys for the representative spine.
-- persons.external_ref: stable cross-run identity for imported people
-- (e.g. 'tn2026:<name-party-slug>' or 'wikidata:Q...'). One person can hold
-- multiple tenures (a candidate can win two seats), so identity must not be
-- keyed to a constituency.

ALTER TABLE persons ADD COLUMN external_ref TEXT UNIQUE;

-- Tenure idempotency: one row per office/person/start.
CREATE UNIQUE INDEX uq_tenures_office_person_start
  ON tenures (office_id, person_id, start_date);
