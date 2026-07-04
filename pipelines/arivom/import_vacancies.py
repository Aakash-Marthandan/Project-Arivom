"""Apply researched vacancy records to the representative spine (pre-M5).

Reads pipelines/data/vacancies_2026.json — a curated, per-entry-cited record
of the seven seats vacated after the May 2026 election (researched
2026-07-04; owner-reviewed). For each entry it validates that the seated
member's name matches the record, then ends the tenure and writes a
`vacancy` fact on the constituency with the reason, date, previous member,
and citations. The `vacancies` view starts reflecting reality immediately.

M5 replaces this curation with the automated ECI press-release pipeline
(with human confirmation before status flips, per DESIGN.md §6); this seed
then becomes its regression fixture.
"""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

from .common import Db, fail, norm_name, now_utc

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "vacancies_2026.json"
NOTES_PATH = Path(__file__).resolve().parent.parent / "data" / "status_notes.json"


def main() -> None:
    db = Db.connect()
    retrieved_at = now_utc()
    seed = json.loads(DATA_PATH.read_text())

    source_id = db.ensure_source(
        name="17th Tamil Nadu Assembly — vacancy records (curated, cited)",
        url="https://en.wikipedia.org/wiki/17th_Tamil_Nadu_Assembly",
        publisher="Arivom curation over Wikipedia and news reports",
        license=None,
        access_mode="manual",
        notes=(
            "Seat-vacancy records researched from the 17th-assembly article and news "
            "reports, cited per entry in pipelines/data/vacancies_2026.json. "
            "Superseded by the automated ECI tracker pipeline in M5."
        ),
    )

    applied = 0
    already = 0
    for entry in seed["vacancies"]:
        row = db.conn.execute(
            """
            SELECT t.id, t.status, t.end_date, p.id, p.name_en, p.name_ta, l.id, l.name_en
            FROM localities l
            JOIN offices o ON o.locality_id = l.id AND o.office_type = 'mla'
            JOIN tenures t ON t.office_id = o.id
            JOIN persons p ON p.id = t.person_id
            WHERE l.level = 'ac' AND l.eci_code = %s
            ORDER BY t.start_date DESC
            LIMIT 1
            """,
            (entry["ac"],),
        ).fetchone()
        if row is None:
            fail(f"AC {entry['ac']}: no seated tenure found — run import-representatives")
            return
        tenure_id, status, end_date, person_id, name_en, name_ta, loc_id, ac_name = row

        # The record must name the person actually seated: no silent flips.
        sim = SequenceMatcher(
            None, norm_name(entry["member_hint"]), norm_name(name_en)
        ).ratio()
        if sim < 0.5:
            fail(
                f"AC {entry['ac']} ({ac_name}): seed names '{entry['member_hint']}' but "
                f"the seated member is '{name_en}' (sim {sim:.2f}) — refusing to flip"
            )

        if status == "resigned" and end_date is not None:
            already += 1
        else:
            db.conn.execute(
                """
                UPDATE tenures
                SET end_date = %s, status = 'resigned',
                    source_id = %s, retrieved_at = %s
                WHERE id = %s
                """,
                (entry["vacated_on"], source_id, retrieved_at, tenure_id),
            )
            applied += 1

        db.upsert_fact(
            subject_type="locality",
            subject_id=loc_id,
            key="vacancy",
            value={
                "reason": entry["reason"],
                "vacated_on": entry["vacated_on"],
                "previous_member_en": name_en,
                "previous_member_ta": name_ta,
                "by_election": "awaiting_notification",
                "note": entry.get("note"),
                "cited_sources": entry["sources"],
            },
            source_id=source_id,
            retrieved_at=retrieved_at,
            extraction_method="manual",
            confidence=1.0,
        )

    # Curated status notes (court disputes and similar, D-016): bilingual,
    # cited, applied to the constituency as a sourced fact.
    notes_applied = 0
    if NOTES_PATH.exists():
        notes_source = db.ensure_source(
            name="Seat status notes (curated, cited)",
            url=None,
            publisher="Arivom curation over news reports",
            license=None,
            access_mode="manual",
            notes=(
                "Civically important context about a seat's current situation (for "
                "example a pending election petition), curated with citations in "
                "pipelines/data/status_notes.json."
            ),
        )
        for note in json.loads(NOTES_PATH.read_text())["notes"]:
            loc = db.conn.execute(
                "SELECT id FROM localities WHERE level = 'ac' AND eci_code = %s",
                (note["ac"],),
            ).fetchone()
            if loc is None:
                fail(f"status note references unknown AC {note['ac']}")
                return
            db.upsert_fact(
                subject_type="locality",
                subject_id=loc[0],
                key="status_note",
                value={
                    "note_en": note["note_en"],
                    "note_ta": note["note_ta"],
                    "as_of": note["as_of"],
                    "cited_sources": note["sources"],
                },
                source_id=notes_source,
                retrieved_at=retrieved_at,
                extraction_method="manual",
                confidence=1.0,
            )
            notes_applied += 1

    db.conn.commit()

    vacant = db.conn.execute("SELECT count(*) FROM vacancies").fetchone()
    assert vacant is not None
    print("=== Vacancy import report ===")
    print(f"records applied: {applied} (already applied: {already})")
    print(f"vacancies view now shows: {vacant[0]} offices without an active tenure")
    print(f"status notes applied: {notes_applied}")
    if vacant[0] != len(seed["vacancies"]):
        fail(
            f"vacancies view count {vacant[0]} != seed count {len(seed['vacancies'])} — "
            "an unexpected tenure state exists; inspect before shipping"
        )


if __name__ == "__main__":
    main()
