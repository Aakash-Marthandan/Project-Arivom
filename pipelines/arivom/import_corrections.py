"""Import the public corrections log from the curated seed (M10).

The log records accepted corrections to facts or framing Arivom
DISPLAYED: what was shown, what it became, when, and why — original
values retained (pillar 1). The seed (pipelines/data/corrections.json)
is human-curated and every entry cites its public record; this importer
only validates and applies. User-filed reports start feeding the same
log once M9's moderation queue exists.

Append-only in practice: a key that disappears from the seed is
reported loudly and left in the database, never deleted.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .common import Db, fail, now_utc

SEED = Path(__file__).resolve().parent.parent / "data" / "corrections.json"

REQUIRED = [
    "key", "corrected_on", "subject_en", "subject_ta", "field",
    "old_value_en", "old_value_ta", "new_value_en", "new_value_ta",
    "note_en", "note_ta",
]


def main() -> None:
    db = Db.connect()
    retrieved_at = now_utc()

    source_id = db.ensure_source(
        name="Arivom corrections log (curated, cited)",
        url="https://github.com/Aakash-Marthandan/Project-Arivom/blob/main/pipelines/data/corrections.json",
        publisher="Arivom",
        license=None,
        access_mode="manual",
        cadence="manual",
        notes=(
            "Human-curated log of accepted corrections to displayed facts"
            " or framing; every entry cites its public record"
            " (docs/DECISIONS.md). Original values retained (pillar 1)."
        ),
    )

    entries = json.loads(SEED.read_text())["corrections"]
    if not entries:
        fail("corrections seed is empty — the table already has entries?")

    keys: set[str] = set()
    for entry in entries:
        missing = [f for f in REQUIRED if not str(entry.get(f, "")).strip()]
        if missing:
            fail(f"correction '{entry.get('key', '?')}' missing {missing}")
        if entry["key"] in keys:
            fail(f"duplicate correction key '{entry['key']}'")
        keys.add(entry["key"])
        date.fromisoformat(entry["corrected_on"])  # validates
        for field in ("subject_en", "subject_ta", "note_en", "note_ta"):
            if "—" in entry[field]:
                fail(f"correction '{entry['key']}': em dash in {field} (copy rule)")

    for entry in entries:
        db.conn.execute(
            """
            INSERT INTO corrections
              (key, corrected_on, subject_en, subject_ta, field,
               old_value_en, old_value_ta, new_value_en, new_value_ta,
               note_en, note_ta, reference, source_id, retrieved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (key) DO UPDATE
              SET corrected_on = EXCLUDED.corrected_on,
                  subject_en = EXCLUDED.subject_en,
                  subject_ta = EXCLUDED.subject_ta,
                  field = EXCLUDED.field,
                  old_value_en = EXCLUDED.old_value_en,
                  old_value_ta = EXCLUDED.old_value_ta,
                  new_value_en = EXCLUDED.new_value_en,
                  new_value_ta = EXCLUDED.new_value_ta,
                  note_en = EXCLUDED.note_en,
                  note_ta = EXCLUDED.note_ta,
                  reference = EXCLUDED.reference,
                  source_id = EXCLUDED.source_id,
                  retrieved_at = EXCLUDED.retrieved_at
            """,
            (
                entry["key"], entry["corrected_on"], entry["subject_en"],
                entry["subject_ta"], entry["field"], entry["old_value_en"],
                entry["old_value_ta"], entry["new_value_en"],
                entry["new_value_ta"], entry["note_en"], entry["note_ta"],
                entry.get("reference"), source_id, retrieved_at,
            ),
        )

    orphans = [
        row[0]
        for row in db.conn.execute(
            "SELECT key FROM corrections WHERE NOT (key = ANY(%s))",
            (sorted(keys),),
        ).fetchall()
    ]
    db.conn.commit()

    print("\n=== Corrections import report ===")
    print(f"seed entries applied: {len(entries)}")
    if orphans:
        print(
            "IN DATABASE BUT NOT IN SEED (log is append-only; restore them"
            f" to the seed): {orphans}"
        )


if __name__ == "__main__":
    main()
