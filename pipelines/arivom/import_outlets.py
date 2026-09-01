"""Outlet registry and sourced ownership claims (D-042).

Two jobs, both idempotent:

1. Promote pipelines/data/outlets.json into the `outlets` table, so an outlet
   is a subject we can hold facts about rather than a line in a poller config.

2. Apply the curated, cited ownership claims in outlets_ownership.json as rows
   in `facts` with subject_type='outlet'. Ownership is an assertion about real
   companies and real people, so it gets the same provenance treatment as every
   other fact: source, retrieval date, extraction method, review status.

What this importer will NOT do, by design: infer an owner's politics from an
outlet's coverage. A political affiliation is recorded only when a named source
documents it. Deriving one from what an outlet publishes is the bias labelling
pillar 2 forbids, and the D-040 investigation showed how badly a home-grown
proxy misfires on Tamil outlets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import Db, now_utc

DATA = Path(__file__).resolve().parent.parent / "data"
REGISTRY = DATA / "outlets.json"
OWNERSHIP = DATA / "outlet_ownership.json"

# Ground News researched and hand-coded ownership across 2,276 outlets and
# published this taxonomy. Adopting it (with attribution) beats inventing a
# ninth scheme, and it makes our data comparable with theirs.
OWNERSHIP_TYPES = {
    "media_conglomerate", "private_equity", "individual", "government",
    "telecom", "corporation", "independent", "other",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def upsert_outlets(db: Db, registry: dict[str, Any], retrieved_at: Any) -> int:
    """Registry rows -> outlets table, linked to their sources row when polled."""
    count = 0
    for entry in registry["outlets"]:
        row = db.conn.execute(
            "SELECT id FROM sources WHERE name = %s",
            (f"News outlet: {entry['name']}",),
        ).fetchone()
        db.conn.execute(
            """
            INSERT INTO outlets (slug, name, lang, role, status, homepage,
                                 source_id, retrieved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
              name = EXCLUDED.name, lang = EXCLUDED.lang, role = EXCLUDED.role,
              status = EXCLUDED.status, homepage = EXCLUDED.homepage,
              source_id = COALESCE(EXCLUDED.source_id, outlets.source_id),
              retrieved_at = EXCLUDED.retrieved_at
            """,
            (entry["slug"], entry["name"], entry["lang"], entry["role"],
             entry["status"], entry.get("homepage"), row[0] if row else None,
             retrieved_at),
        )
        count += 1
    db.conn.commit()
    return count


def ensure_sources(db: Db, defs: dict[str, Any]) -> dict[str, int]:
    """One sources row per citation used by the ownership seed."""
    ids: dict[str, int] = {}
    for key, meta in defs.items():
        ids[key] = db.ensure_source(
            name=meta["name"], url=meta.get("url"), publisher=meta["publisher"],
            license=None, access_mode="manual", cadence="manual",
            notes=meta.get("note"),
        )
    return ids


def write_fact(
    db: Db, outlet_id: int, key: str, value: Any, source_id: int, retrieved_at: Any
) -> None:
    db.conn.execute(
        """
        INSERT INTO facts (subject_type, subject_id, key, value, source_id,
                           retrieved_at, extraction_method, review_status)
        VALUES ('outlet', %s, %s, %s, %s, %s, 'manual', 'human_verified')
        ON CONFLICT (subject_type, subject_id, key, source_id)
        DO UPDATE SET value = EXCLUDED.value, retrieved_at = EXCLUDED.retrieved_at
        """,
        (outlet_id, key, json.dumps(value, ensure_ascii=False), source_id, retrieved_at),
    )


def main() -> None:
    db = Db.connect()
    retrieved_at = now_utc()
    registry = load(REGISTRY)
    ownership = load(OWNERSHIP)

    n_outlets = upsert_outlets(db, registry, retrieved_at)
    source_ids = ensure_sources(db, ownership["sources"])
    ids = {r[0]: r[1] for r in db.conn.execute("SELECT slug, id FROM outlets").fetchall()}

    report = {"outlets": n_outlets, "owner": 0, "group": 0, "type": 0,
              "affiliation": 0, "unknown_owner": [], "bad_type": []}

    for slug, claim in ownership["outlets"].items():
        outlet_id = ids.get(slug)
        if outlet_id is None:
            report["unknown_owner"].append(f"{slug} (not in registry)")
            continue
        src = source_ids[claim["source"]]
        write_fact(db, outlet_id, "owner", {"name": claim["owner"],
                   "note": claim.get("note")}, src, retrieved_at)
        report["owner"] += 1
        if claim.get("owner_group"):
            write_fact(db, outlet_id, "owner_group", {"name": claim["owner_group"]},
                       src, retrieved_at)
            report["group"] += 1
        otype = claim.get("ownership_type")
        if otype:
            if otype not in OWNERSHIP_TYPES:
                report["bad_type"].append(f"{slug}: {otype}")
                continue
            write_fact(db, outlet_id, "ownership_type", {
                "type": otype,
                "taxonomy": "Ground News ownership categories",
            }, src, retrieved_at)
            report["type"] += 1

    # Affiliation is stated against the controlling group, so it applies to every
    # outlet that group runs without being restated per outlet.
    for entry in ownership.get("political_affiliation", []):
        group = entry["owner_group"]
        src = source_ids[entry["source"]]
        members = db.conn.execute(
            """
            SELECT o.id FROM outlets o
            JOIN facts f ON f.subject_type = 'outlet' AND f.subject_id = o.id
             AND f.key = 'owner_group' AND f.value ->> 'name' = %s
            """,
            (group,),
        ).fetchall()
        if not members:
            report["unknown_owner"].append(f"affiliation for unknown group {group!r}")
            continue
        for (outlet_id,) in members:
            write_fact(db, outlet_id, "political_affiliation", {
                "group": group, "claim": entry["claim"],
                "claim_ta": entry.get("claim_ta"), "note": entry.get("note"),
            }, src, retrieved_at)
            report["affiliation"] += 1

    db.conn.commit()

    print("\n=== Outlet ownership import ===")
    for key in ("outlets", "owner", "group", "type", "affiliation"):
        print(f"  {key}: {report[key]}")
    for problem in report["unknown_owner"] + report["bad_type"]:
        print(f"  PROBLEM: {problem}")

    # Coverage concentration is the point of owner_group, so report it here
    # where a human reads the run, not only in the product.
    rows = db.conn.execute(
        """
        SELECT f.value ->> 'name' AS grp, count(*) AS n,
               string_agg(o.slug, ', ' ORDER BY o.slug)
        FROM facts f JOIN outlets o ON o.id = f.subject_id
        WHERE f.subject_type = 'outlet' AND f.key = 'owner_group'
        GROUP BY 1 HAVING count(*) > 1 ORDER BY 2 DESC
        """
    ).fetchall()
    print("\n  Owners running more than one tracked outlet:")
    for grp, n, slugs in rows:
        print(f"    {grp}: {n} — {slugs}")

    missing = db.conn.execute(
        """
        SELECT count(*) FROM outlets o WHERE NOT EXISTS (
          SELECT 1 FROM facts f WHERE f.subject_type='outlet'
            AND f.subject_id = o.id AND f.key = 'owner')
        """
    ).fetchone()
    print(f"\n  Outlets with no recorded owner: {missing[0]}")


if __name__ == "__main__":
    main()
