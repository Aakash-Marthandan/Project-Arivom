"""Import Jal Jeevan Mission rural tap-water coverage for TN districts (M12).

Source: the JJM public dashboard's own JSON endpoint (the WebMethod the
dashboard map calls). Figures are administrative data reported by the
implementing agencies into the mission's IMIS — the UI labels them
"mission-reported", never survey or census data.

Scope is rural by mission design: Chennai (fully urban) has no JJM row
and renders an honest note instead of data; it is reported every run.

The endpoint encodes parameters with the page's own public scheme
(character codes shifted by encN=1, suffixed with "1") — presentation
obfuscation shipped in the page source, not authentication.
"""

from __future__ import annotations

import json
from typing import Any

from .common import Db, fail, http_session, norm_name, now_utc

ENDPOINT = "https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx/BindDistrictMap"
DASHBOARD_URL = "https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx"
TN_CENSUS_CODE = "33"

JJM_NAME_ALIASES: dict[str, str] = {
    # JJM spellings that differ from our LGD names (normalized comparison).
    "villupuram": "viluppuram",
    "tuticorin": "thoothukkudi",
    "nilgiris": "the nilgiris",
}


def encode_param(value: str) -> str:
    """The dashboard's encodeTxt with encN = 1."""
    return "".join(chr(ord(ch) + 1) for ch in value) + "1"


def fetch_districts(session: Any) -> list[dict[str, Any]]:
    payload = {
        "StCode11": encode_param(TN_CENSUS_CODE),
        "Cat": encode_param("0"),
        "SubCat": encode_param("0"),
        "Param": encode_param("0"),
    }
    resp = session.post(
        ENDPOINT,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=60,
    )
    resp.raise_for_status()
    rows = resp.json()["d"]
    if not isinstance(rows, list):
        fail("JJM endpoint shape changed: 'd' is not a list")
    return rows


def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    source_id = db.ensure_source(
        name="Jal Jeevan Mission dashboard — district coverage",
        url=DASHBOARD_URL,
        publisher=(
            "Department of Drinking Water & Sanitation,"
            " Ministry of Jal Shakti"
        ),
        license=None,
        access_mode="api",
        cadence="monthly",
        notes=(
            "District-wise rural household tap-connection coverage from"
            " the public JJM dashboard's JSON endpoint. Administrative"
            " data reported by implementing agencies into the mission"
            " IMIS; cumulative as on the retrieval date. Labelled"
            " mission-reported in the UI (D-031)."
        ),
    )

    districts = db.conn.execute(
        "SELECT id, name_en FROM localities WHERE level = 'district'"
    ).fetchall()
    by_norm = {norm_name(name): (loc_id, name) for loc_id, name in districts}

    print("Fetching JJM district coverage for Tamil Nadu…")
    rows = fetch_districts(session)
    if len(rows) < 35:
        fail(f"expected ~37 JJM rows for TN, got {len(rows)}")

    written: list[str] = []
    unmatched: list[str] = []
    for row in rows:
        jjm_name = str(row["Name"]).strip()
        norm = norm_name(jjm_name)
        hit = by_norm.get(JJM_NAME_ALIASES.get(norm, norm))
        if hit is None:
            unmatched.append(jjm_name)
            continue
        loc_id, lgd_name = hit

        with_tap = int(row["Value"])
        total = int(row["Total"])
        published_pct = float(row["Per"])
        if total <= 0 or not 0 <= with_tap <= total:
            fail(f"{jjm_name}: counts out of range ({with_tap}/{total})")
        # Integrity gate (D-028 posture): their published percentage must
        # match their own counts.
        if abs(published_pct - with_tap / total * 100) > 0.1:
            fail(
                f"{jjm_name}: published {published_pct}% disagrees with"
                f" counts {with_tap}/{total}"
            )

        db.upsert_fact(
            subject_type="locality",
            subject_id=loc_id,
            key="water.jjm",
            value={
                "mission": "Jal Jeevan Mission",
                "scope": "rural",
                "asOn": retrieved_at.date().isoformat(),
                "ruralHouseholds": total,
                "withTapConnection": with_tap,
                "coveragePercent": published_pct,
                "harGharJalReported": row.get("ISHGJReported") == "1",
                "harGharJalCertified": row.get("IsHGJCertified") == "1",
            },
            source_id=source_id,
            retrieved_at=retrieved_at,
            extraction_method="api",
            confidence=1.0,
            review_status="unreviewed",
        )
        written.append(lgd_name)

    db.conn.commit()

    covered = set(written)
    missing = sorted(name for _loc_id, name in districts if name not in covered)
    print("\n=== JJM import report ===")
    print(f"Dashboard rows: {len(rows)}; district facts written: {len(written)}")
    if unmatched:
        print(
            "PENDING — JJM districts with no LGD match (skipped, fix"
            f" JJM_NAME_ALIASES): {sorted(unmatched)}"
        )
    if missing:
        print(
            "Districts with no JJM row (rural mission; fully urban"
            f" districts expected here): {missing}"
        )
    if len(written) < 35:
        fail(f"only {len(written)} districts matched — mapping broke?")


if __name__ == "__main__":
    main()
