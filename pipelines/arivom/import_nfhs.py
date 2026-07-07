"""Import NFHS-5 district health indicators for Tamil Nadu (M12, first slice).

Source: the data.gov.in mirror of the NFHS-5 (2019-21) India district
factsheets. NFHS is a sample survey run by the Union health ministry with
IIPS; district figures are estimates from a household sample and the UI
frames them as survey data, never as counts.

Scope (D-030): twelve indicators whose values are clean across every TN
row ship verbatim. Vaccination coverage (negative-mangled in the mirror,
likely the factsheets' parenthesised low-sample convention) and sex ratio
at birth (high sampling variance, easy to misread) are deliberately
withheld until verified against the official factsheet PDFs.

The 2019-21 survey used the pre-2019 district list (32 districts). The
six districts created since were surveyed inside their parents and have
no separate factsheet; they are reported every run, never guessed.
"""

from __future__ import annotations

from .common import Db, fail, fetch_datagovin_resource, http_session, norm_name, now_utc

RESOURCE_ID = "cf80173e-fece-439d-a0b1-6e9cb510593d"
RESOURCE_URL = (
    "https://www.data.gov.in/catalog/"
    "national-family-health-survey-5-nfhs-5-india-districts-factsheet-data"
)

# Factsheet field → our indicator key. All values are percentages 0–100.
INDICATOR_FIELDS = {
    "Household_Electricity": "electricity",
    "Improved_Drinking-Water_Source": "improvedDrinkingWater",
    "Household_Using_Improved_Sanitation": "improvedSanitation",
    "Households_Using_Clean_Fuel": "cleanFuel",
    "Health_Insurance_Scheme_Coverage": "healthInsurance",
    "Institutional_Birth": "institutionalBirth",
    "Mothers_Four_ANC_Visits": "ancFourVisits",
    "Stunted_Children_Under_Five": "stunted",
    "Wasted_Children_Under_Five": "wasted",
    "Underweight_Children_Under_Five": "underweight",
    "Anaemic_Children_6-59_Months": "anaemicChildren",
    "Anaemic_All_Women_15-49": "anaemicWomen",
}

# NFHS spellings that differ from our LGD names (normalized comparison).
NFHS_NAME_ALIASES = {
    "nilgiris": "the nilgiris",
    "tuticorin": "thoothukkudi",
    "virudunagar": "virudhunagar",
}


def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    source_id = db.ensure_source(
        name="NFHS-5 district factsheets (2019-21)",
        url=RESOURCE_URL,
        publisher=(
            "Ministry of Health & Family Welfare / IIPS, via data.gov.in"
        ),
        license="Government Open Data License - India (GODL)",
        access_mode="api",
        notes=(
            "National Family Health Survey round 5 (2019-21) district"
            " factsheet indicators. Sample-survey estimates, displayed as"
            " survey data. Twelve clean indicators only (D-030);"
            " vaccination coverage and sex ratio at birth are withheld"
            " until verified against the official factsheet PDFs."
        ),
    )

    districts = db.conn.execute(
        "SELECT id, name_en FROM localities WHERE level = 'district'"
    ).fetchall()
    by_norm = {norm_name(name): (loc_id, name) for loc_id, name in districts}

    print("Fetching NFHS-5 factsheet rows for Tamil Nadu…")
    rows = fetch_datagovin_resource(
        session,
        RESOURCE_ID,
        filters={"State_UT": "Tamil Nadu"},
        page_size=10,  # the public sample key caps pages at 10 records
    )
    if len(rows) < 30:
        fail(f"expected ~32 NFHS-5 rows for TN, got {len(rows)}")

    written: list[str] = []
    unmatched: list[str] = []
    for row in rows:
        nfhs_name = str(row["District_Names"]).strip()
        norm = norm_name(nfhs_name)
        hit = by_norm.get(NFHS_NAME_ALIASES.get(norm, norm))
        if hit is None:
            unmatched.append(nfhs_name)
            continue
        loc_id, lgd_name = hit

        indicators: dict[str, float] = {}
        for field, key in INDICATOR_FIELDS.items():
            value = float(str(row[field]))
            if not 0 <= value <= 100:
                fail(f"{nfhs_name}: {field}={row[field]} outside 0–100 — "
                     "mirror artifact reached a shipped indicator?")
            indicators[key] = value

        db.upsert_fact(
            subject_type="locality",
            subject_id=loc_id,
            key="health.nfhs5",
            value={
                "survey": "NFHS-5",
                "period": "2019-21",
                "indicators": indicators,
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
    not_surveyed = sorted(
        name for _loc_id, name in districts if name not in covered
    )
    print("\n=== NFHS-5 import report ===")
    print(f"Factsheet rows: {len(rows)}; district facts written: {len(written)}")
    if unmatched:
        print("PENDING — NFHS districts with no LGD match (skipped, fix "
              f"NFHS_NAME_ALIASES): {sorted(unmatched)}")
    if not_surveyed:
        print(
            "Districts without a separate NFHS-5 factsheet (created after "
            f"the survey was designed; expected): {not_surveyed}"
        )
    if len(written) < 30:
        fail(f"only {len(written)} districts matched — mapping broke?")


if __name__ == "__main__":
    main()
