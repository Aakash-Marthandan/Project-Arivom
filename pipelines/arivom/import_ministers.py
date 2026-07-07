"""Import the council of ministers of the 17th Tamil Nadu assembly.

Sources: the ministers tables on the Tamil and English Wikipedia articles
for the 17th assembly. Rows are matched to persons through their
CONSTITUENCY (Tamil table by our name_ta, English table by our name_en),
which avoids any cross-script name matching; the two sides are then merged
per person, giving bilingual portfolios. A member present on only one side
is imported with what that side provides and reported.

Facts: key='minister' on the person, carrying position and portfolios in
both languages. Ministers who leave the council disappear from the tables
and their fact is removed on the next run (the report says so).
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from .common import Db, expand_table_grid, fail, http_session, norm_name, now_utc
from .import_representatives import ENWIKI_API, TAWIKI_API, fetch_wiki_html

TAWIKI_PAGE = "பதினேழாவது தமிழ்நாடு சட்டமன்றம்"
ENWIKI_PAGE = "17th Tamil Nadu Assembly"

CM_MARKERS = re.compile(r"முதலமைச்சர்|முதல்வர்|chief minister", re.IGNORECASE)

# Spelling variants between the wiki tables and our stored names.
# Classification aid only.
TA_SEAT_ALIASES = {
    "திருவரங்கம்": "ஸ்ரீரங்கம்",       # Srirangam: temple-name variant
    "திருவாடானை": "திருவாடாணை",     # ன/ண variant
}
EN_SEAT_ALIASES = {
    "r k nagar": "radhakrishnan nagar",
}


def split_plain_departments(text: str) -> list[str]:
    """Comma-split a PLAIN portfolio cell (no list markup in the source).

    Only used when the source itself gave no item structure; a cell that
    had <li>/<br> items keeps each item whole, commas and all (D-032)."""
    parts = [" ".join(p.split()) for p in text.split(",")]
    return [p for p in parts if len(p) > 1]


def parse_ministers_table(
    html: str, name_col_marker: str, seat_col_marker: str, extra_cols: dict[str, str]
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table", class_="wikitable"):
        grid = expand_table_grid(table, segments=True)
        if not (10 < len(grid) < 80):
            continue
        header = [" ".join(h).lower() for h in grid[0]]
        joined = " ".join(header)
        if name_col_marker.lower() not in joined or seat_col_marker.lower() not in joined:
            continue

        def col(marker: str, hdr: list[str] = header) -> int | None:
            for i, h in enumerate(hdr):
                if marker.lower() in h:
                    return i
            return None

        name_i = col(name_col_marker)
        seat_i = col(seat_col_marker)
        extras = {key: col(marker) for key, marker in extra_cols.items()}
        if name_i is None or seat_i is None:
            continue
        rows = []
        for row in grid[1:]:
            if len(row) <= max(name_i, seat_i):
                continue
            name = " ".join(row[name_i]).strip()
            seat = " ".join(row[seat_i]).strip()
            if not name or not seat or name.lower() == header[name_i]:
                continue
            entry: dict[str, Any] = {"name": name, "seat": seat}
            for key, idx in extras.items():
                segments = row[idx] if idx is not None and len(row) > idx else []
                if key == "portfolio":
                    # One department per source item; a lone plain segment
                    # falls back to comma-splitting (the source's own
                    # convention when it uses no list markup).
                    if len(segments) == 1:
                        entry[key] = split_plain_departments(segments[0])
                    else:
                        entry[key] = [s for s in segments if len(s) > 1]
                else:
                    entry[key] = " ".join(segments).strip()
            rows.append(entry)
        if len(rows) >= 10:
            return rows
    fail(f"no ministers table found (markers: {name_col_marker}/{seat_col_marker})")
    return []


def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    source_id = db.ensure_source(
        name="17th Tamil Nadu Assembly — council of ministers (Wikipedia ta+en)",
        url="https://ta.wikipedia.org/wiki/பதினேழாவது_தமிழ்நாடு_சட்டமன்றம்",
        publisher="Wikimedia Foundation (community-curated)",
        license="CC BY-SA 4.0",
        access_mode="api",
        notes=(
            "Ministers and portfolios from the Tamil and English 17th-assembly "
            "articles, matched to members through their constituency and merged "
            "bilingually. Preferred replacement: the official tn.gov.in ministers "
            "directory once reachable (geo-blocked outside India, D-017)."
        ),
    )

    # Person lookup via the member's seat (active tenure).
    rows = db.conn.execute(
        """
        SELECT l.name_en, l.name_ta, l.eci_code, p.id
        FROM localities l
        JOIN offices o ON o.locality_id = l.id AND o.office_type = 'mla'
        JOIN tenures t ON t.office_id = o.id AND t.end_date IS NULL AND t.status = 'active'
        JOIN persons p ON p.id = t.person_id
        WHERE l.level = 'ac'
        """
    ).fetchall()
    by_en = {norm_name(en): (pid, code) for en, ta, code, pid in rows}
    by_ta = {ta.strip(): (pid, code) for en, ta, code, pid in rows}

    print("Fetching ministers tables…")
    ta_rows = parse_ministers_table(
        fetch_wiki_html(session, TAWIKI_API, TAWIKI_PAGE),
        name_col_marker="பெயர்",
        seat_col_marker="தொகுதி",
        extra_cols={"position": "பதவி", "portfolio": "துறை"},
    )
    en_rows = parse_ministers_table(
        fetch_wiki_html(session, ENWIKI_API, ENWIKI_PAGE),
        name_col_marker="name",
        seat_col_marker="constituency",
        extra_cols={"portfolio": "portfolio", "party": "party"},
    )
    print(f"  tawiki rows: {len(ta_rows)}, enwiki rows: {len(en_rows)}")

    merged: dict[int, dict[str, Any]] = {}
    problems: list[str] = []

    for row in ta_rows:
        seat = row["seat"].replace("சட்டமன்றத் தொகுதி", "").strip()
        seat = TA_SEAT_ALIASES.get(seat, seat)
        hit = by_ta.get(seat)
        if hit is None:
            candidates = [k for k in by_ta if k in seat or seat in k]
            hit = by_ta[candidates[0]] if len(candidates) == 1 else None
        if hit is None:
            problems.append(f"tawiki minister '{row['name']}' seat '{row['seat']}' unmatched")
            continue
        pid, code = hit
        merged[pid] = {
            "ac": code,
            "position_ta": row.get("position", ""),
            "portfolios_ta": row.get("portfolio", []),
            "is_cm": bool(CM_MARKERS.search(row.get("position", ""))),
        }

    from difflib import get_close_matches

    for row in en_rows:
        key = norm_name(row["seat"])
        key = EN_SEAT_ALIASES.get(key, key)
        hit = by_en.get(key)
        if hit is None:
            close = get_close_matches(key, list(by_en), n=1, cutoff=0.8)
            hit = by_en[close[0]] if close else None
        if hit is None:
            problems.append(f"enwiki minister '{row['name']}' seat '{row['seat']}' unmatched")
            continue
        pid, code = hit
        entry = merged.setdefault(pid, {"ac": code, "is_cm": False})
        entry["portfolios_en"] = row.get("portfolio", [])
        if CM_MARKERS.search(" ".join(row.get("portfolio", []))):
            entry["is_cm"] = True

    only_ta = sum(1 for v in merged.values() if "portfolios_en" not in v)
    only_en = sum(1 for v in merged.values() if "portfolios_ta" not in v)

    # Remove ministers no longer in the tables, then upsert current ones.
    current_ids = list(merged.keys())
    removed = db.conn.execute(
        "DELETE FROM facts WHERE key = 'minister' AND source_id = %s "
        "AND NOT (subject_id = ANY(%s))",
        (source_id, current_ids),
    ).rowcount

    for pid, entry in merged.items():
        db.upsert_fact(
            subject_type="person",
            subject_id=pid,
            key="minister",
            value={
                "position_ta": entry.get("position_ta", ""),
                # One entry per department as the source lists them (D-032).
                "portfolios_ta": entry.get("portfolios_ta", []),
                "portfolios_en": entry.get("portfolios_en", []),
                "is_chief_minister": entry["is_cm"],
                "assembly": "17th Tamil Nadu Legislative Assembly",
            },
            source_id=source_id,
            retrieved_at=retrieved_at,
            extraction_method="scrape",
            confidence=1.0 if "portfolios_ta" in entry and "portfolios_en" in entry else 0.9,
        )

    db.conn.commit()

    cm = [pid for pid, v in merged.items() if v["is_cm"]]
    dep_ta = sum(len(v.get("portfolios_ta", [])) for v in merged.values())
    dep_en = sum(len(v.get("portfolios_en", [])) for v in merged.values())
    print("\n=== Ministers import report ===")
    print(f"ministers: {len(merged)} (chief minister rows: {len(cm)})")
    print(f"department entries: ta {dep_ta}, en {dep_en}")
    print(f"bilingual: {len(merged) - only_ta - only_en}, ta-only: {only_ta}, en-only: {only_en}")
    print(f"stale minister facts removed: {removed}")
    for line in problems:
        print(f"  UNMATCHED: {line}")
    if len(cm) != 1:
        fail(f"expected exactly one chief minister, found {len(cm)} — inspect the tables")
    if not 15 <= len(merged) <= 60:
        fail(f"minister count {len(merged)} outside sane range — inspect the tables")


if __name__ == "__main__":
    main()
