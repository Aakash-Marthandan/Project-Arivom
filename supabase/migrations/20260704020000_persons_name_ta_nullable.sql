-- M3 (D-014): a small set of newly elected MLAs have no Tamil rendering of
-- their name in any machine-checkable source yet. Our rules forbid both
-- transliteration (invented text) and English strings in Tamil fields, so
-- the honest state is NULL: the UI shows the sourced English name with a
-- visible "Tamil name pending verification" note, and importers report the
-- outstanding list on every run until it reaches zero.

ALTER TABLE persons ALTER COLUMN name_ta DROP NOT NULL;

COMMENT ON COLUMN persons.name_ta IS
  'NULL = no sourced Tamil rendering yet (never transliterated; see DECISIONS.md D-014).';
