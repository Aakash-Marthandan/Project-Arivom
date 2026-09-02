"""Search data.gov.in for candidate datasets, and read their shape (D-043).

Finding a usable source was the slow part of every data milestone so far:
UDISE, NFHS and JJM each cost an afternoon of clicking before a line of
importer code was written. data.gov.in catalogues 279,554 resources and its
`lists` endpoint is searchable, so that work is a command rather than an
afternoon.

    uv run discover-data "rainfall"          # search titles
    uv run discover-data --show <resource_id>  # fields, freshness, a sample row

What this prints, deliberately, is the freshness of each candidate. The
recurring lesson from probing Indian open data (docs/DATA-SOURCES.md) is that
almost everything accessible without an approval is a historical snapshot
rather than a live feed. That is still useful — "the last published figure is
X, for year Y" grounds a claim perfectly well — but only if the year travels
with the number everywhere it is shown. A source whose `updated` date is old
is not disqualified; it is disclosed.

This tool only reads. Choosing a source, writing the importer and recording
the provenance stay human decisions.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from .common import datagovin_key, http_session

LISTS = "https://api.data.gov.in/lists"
RESOURCE = "https://api.data.gov.in/resource"


def search(session: Any, term: str, limit: int = 15) -> list[dict[str, Any]]:
    resp = session.get(
        LISTS,
        params={
            "api-key": datagovin_key(), "format": "json",
            "limit": limit, "filters[title]": term,
        },
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()
    print(f"catalogue matches for {term!r}: {payload.get('total', 0)}\n")
    return payload.get("records", [])


def describe(session: Any, resource_id: str) -> None:
    resp = session.get(
        f"{RESOURCE}/{resource_id}",
        params={"api-key": datagovin_key(), "format": "json", "limit": 2},
        timeout=60,
    )
    resp.raise_for_status()
    d = resp.json()
    print(f"  title    : {d.get('title')}")
    print(f"  org      : {' / '.join(d.get('org') or []) or '—'}")
    print(f"  rows     : {d.get('total')}")
    print(f"  updated  : {d.get('updated_date') or '—'}")
    fields = [f.get("name") for f in (d.get("field") or [])]
    print(f"  fields   : {len(fields)}")
    for name in fields[:16]:
        print(f"      - {name}")
    if len(fields) > 16:
        print(f"      ... {len(fields) - 16} more")
    records = d.get("records") or []
    if records:
        print(f"  sample   : {json.dumps(records[0], ensure_ascii=False)[:400]}")
    # Freshness is the thing that decides whether a source can ground today's
    # news or only supply a baseline, so say it rather than leaving it in a field.
    updated = str(d.get("updated_date") or "")
    if updated[:4].isdigit():
        year = int(updated[:4])
        print(
            f"\n  NOTE: last updated {year}. "
            + (
                "Recent enough to read as current."
                if year >= 2025
                else "This is a historical snapshot. Usable as a baseline only, "
                "and the year must travel with the number wherever it is shown."
            )
        )


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(
            "usage:\n"
            '  discover-data "<title search>"     find candidate datasets\n'
            "  discover-data --show <resource_id>  fields, freshness, sample row"
        )
    session = http_session()
    if args[0] == "--show":
        if len(args) < 2:
            sys.exit("--show needs a resource id")
        describe(session, args[1])
        return

    term = " ".join(args)
    for record in search(session, term):
        print(f"  {str(record.get('title'))[:82]}")
        print(f"    id      : {record.get('index_name')}")
        org = record.get("org")
        if org:
            print(f"    org     : {' / '.join(org)[:76]}")
        print()


if __name__ == "__main__":
    main()
