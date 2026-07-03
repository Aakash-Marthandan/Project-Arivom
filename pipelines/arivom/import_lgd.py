"""Import the LGD locality hierarchy for Tamil Nadu (state 33).

Scope (M1): state, districts, taluks (sub-districts). Villages and local
bodies are deferred to the milestone that consumes them (DECISIONS.md D-007).

Sources:
- LGD via the data.gov.in mirror (DECISIONS.md D-004) — authority for the
  hierarchy and English names.
- Wikidata — Tamil names where LGD's `*_name_local` is missing or not
  actually Tamil (DECISIONS.md D-005); each such name is recorded as a fact.
"""

from __future__ import annotations

from difflib import get_close_matches

from .common import (
    Db,
    fail,
    fetch_datagovin_resource,
    has_tamil,
    http_session,
    norm_name,
    now_utc,
    sparql,
)

TN_STATE_CODE = "33"
EXPECTED_DISTRICTS = 38

RES_DISTRICTS = "37231365-78ba-44d5-ac22-3deec40b9197"
RES_SUBDISTRICTS = "6be51a29-876a-403a-a6da-42fde795e751"

WIKIDATA_TN = "Q1445"
# District of India, located in (P131) Tamil Nadu.
DISTRICTS_SPARQL = f"""
SELECT ?item ?en ?ta WHERE {{
  ?item wdt:P31 wd:Q1149652 ; wdt:P131 wd:{WIKIDATA_TN} .
  OPTIONAL {{ ?item rdfs:label ?en FILTER(LANG(?en)='en') }}
  OPTIONAL {{ ?item rdfs:label ?ta FILTER(LANG(?ta)='ta') }}
}}
"""
# Taluk of Tamil Nadu.
TALUKS_SPARQL = """
SELECT ?item ?en ?ta WHERE {
  ?item wdt:P31 wd:Q122987736 .
  OPTIONAL { ?item rdfs:label ?en FILTER(LANG(?en)='en') }
  OPTIONAL { ?item rdfs:label ?ta FILTER(LANG(?ta)='ta') }
}
"""

DISTRICT_TA_SUFFIX = " மாவட்டம்"
TALUK_TA_SUFFIX = " வட்டம்"
TALUK_EN_SUFFIX = " taluk"
STATE_TA_SPARQL = f"""
SELECT ?ta WHERE {{
  wd:{WIKIDATA_TN} rdfs:label ?ta FILTER(LANG(?ta)='ta')
}}
"""


def wd_district_name(label: str) -> str:
    label = label.removesuffix(" district").removesuffix(" District")
    return label


def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    lgd_source = db.ensure_source(
        name="Local Government Directory (data.gov.in mirror)",
        url="https://www.data.gov.in/catalog/local-government-directory-lgd",
        publisher="Ministry of Panchayati Raj, Government of India",
        license="Government Open Data License – India (GODL)",
        access_mode="api",
        notes=(
            "Authoritative administrative hierarchy codes for Tamil Nadu (state 33). "
            "Mirrored on data.gov.in; the LGD portal itself requires a captcha for bulk "
            "download. Local-language names are inconsistently populated upstream."
        ),
    )
    wikidata_source = db.ensure_source(
        name="Wikidata",
        url="https://www.wikidata.org/",
        publisher="Wikimedia Foundation",
        license="CC0 1.0",
        access_mode="api",
        notes="Tamil names for entities whose LGD local-language field is missing or not Tamil.",
    )

    print("Fetching LGD districts…")
    districts = fetch_datagovin_resource(
        session, RES_DISTRICTS, filters={"state_code": TN_STATE_CODE}
    )
    if len(districts) != EXPECTED_DISTRICTS:
        fail(f"expected {EXPECTED_DISTRICTS} TN districts from LGD, got {len(districts)}")

    print("Fetching Wikidata TN district labels…")
    wd_rows = sparql(session, DISTRICTS_SPARQL)
    wd_by_name: dict[str, dict[str, str]] = {}
    for row in wd_rows:
        en = row.get("en", {}).get("value")
        ta = row.get("ta", {}).get("value")
        if en and ta and has_tamil(ta):
            # Bare place name, consistent with LGD's convention.
            ta = ta.removesuffix(DISTRICT_TA_SUFFIX).strip()
            wd_by_name[norm_name(wd_district_name(en))] = {"en": en, "ta": ta}

    # --- State row -----------------------------------------------------------
    state_en = districts[0]["state_name_english"].strip()
    state_ta_lgd = (districts[0].get("state_name_local") or "").strip()
    if has_tamil(state_ta_lgd):
        state_ta, state_ta_from_wd = state_ta_lgd, False
    else:
        wd_state = sparql(session, STATE_TA_SPARQL)
        state_ta = wd_state[0]["ta"]["value"] if wd_state else ""
        state_ta_from_wd = True
    if not has_tamil(state_ta):
        fail("could not obtain a Tamil name for the state row from LGD or Wikidata")

    state_id = db.upsert_locality_by_lgd(
        lgd_code=TN_STATE_CODE,
        name_en=state_en,
        name_ta=state_ta,
        level="state",
        parent_id=None,
        source_id=lgd_source,
        retrieved_at=retrieved_at,
    )
    if state_ta_from_wd:
        db.upsert_fact(
            subject_type="locality",
            subject_id=state_id,
            key="name_ta",
            value={"name_ta": state_ta},
            source_id=wikidata_source,
            retrieved_at=retrieved_at,
            extraction_method="api",
            confidence=1.0,
        )

    # --- Districts -----------------------------------------------------------
    district_ids: dict[str, int] = {}
    ta_from_lgd = 0
    ta_from_wd = 0
    unmatched: list[str] = []

    for row in sorted(districts, key=lambda r: r["district_name_english"]):
        code = str(row["district_code"])
        name_en = row["district_name_english"].strip()
        local = (row.get("district_name_local") or "").strip()

        if has_tamil(local):
            name_ta, from_wd = local, False
            ta_from_lgd += 1
        else:
            key = norm_name(name_en)
            wd = wd_by_name.get(key)
            if wd is None:
                candidates = get_close_matches(key, list(wd_by_name), n=1, cutoff=0.75)
                if candidates:
                    print(f"  FUZZY MATCH (district): LGD '{name_en}' → Wikidata '{candidates[0]}'")
                    wd = wd_by_name[candidates[0]]
            if wd is None:
                unmatched.append(name_en)
                continue
            name_ta, from_wd = wd["ta"], True
            ta_from_wd += 1

        district_id = db.upsert_locality_by_lgd(
            lgd_code=code,
            name_en=name_en,
            name_ta=name_ta,
            level="district",
            parent_id=state_id,
            source_id=lgd_source,
            retrieved_at=retrieved_at,
        )
        district_ids[code] = district_id
        if from_wd:
            db.upsert_fact(
                subject_type="locality",
                subject_id=district_id,
                key="name_ta",
                value={"name_ta": name_ta},
                source_id=wikidata_source,
                retrieved_at=retrieved_at,
                extraction_method="api",
                confidence=1.0,
            )

    if unmatched:
        fail(
            "no Tamil name from LGD or Wikidata for districts: "
            + ", ".join(unmatched)
            + " — fix the matching; do NOT fill by hand without a source."
        )

    # --- Taluks (sub-districts) ----------------------------------------------
    print("Fetching LGD sub-districts…")
    taluks = fetch_datagovin_resource(
        session, RES_SUBDISTRICTS, filters={"state_code": TN_STATE_CODE}
    )
    print("Fetching Wikidata TN taluk labels…")
    wd_taluks: dict[str, str] = {}
    for row in sparql(session, TALUKS_SPARQL):
        en = row.get("en", {}).get("value")
        ta = row.get("ta", {}).get("value")
        if en and ta and has_tamil(ta):
            key = norm_name(en.removesuffix(TALUK_EN_SUFFIX).removesuffix(" Taluk"))
            wd_taluks[key] = ta.removesuffix(TALUK_TA_SUFFIX).strip()

    taluk_from_lgd = 0
    taluk_from_wd = 0
    taluk_gap: list[str] = []
    for row in taluks:
        code = str(row["subdistrict_code"])
        name_en = (row.get("subdistrict_name_english") or "").strip()
        local = (row.get("subdistrict_name_local") or "").strip()
        district_id = district_ids.get(str(row["district_code"]))
        if not name_en or district_id is None:
            taluk_gap.append(f"{code} (incomplete row)")
            continue

        from_wd = False
        if has_tamil(local):
            name_ta = local
        else:
            name_ta = wd_taluks.get(norm_name(name_en), "")
            from_wd = bool(name_ta)
            if not name_ta:
                taluk_gap.append(name_en)
                continue

        taluk_id = db.upsert_locality_by_lgd(
            lgd_code=code,
            name_en=name_en,
            name_ta=name_ta,
            level="taluk",
            parent_id=district_id,
            source_id=lgd_source,
            retrieved_at=retrieved_at,
        )
        if from_wd:
            taluk_from_wd += 1
            db.upsert_fact(
                subject_type="locality",
                subject_id=taluk_id,
                key="name_ta",
                value={"name_ta": name_ta},
                source_id=wikidata_source,
                retrieved_at=retrieved_at,
                extraction_method="api",
                confidence=1.0,
            )
        else:
            taluk_from_lgd += 1
    taluk_ok = taluk_from_lgd + taluk_from_wd

    db.conn.commit()

    print("\n=== LGD import report ===")
    state_ta_origin = "Wikidata" if state_ta_from_wd else "LGD"
    print(f"state:      1 (Tamil name from {state_ta_origin})")
    print(
        f"districts:  {len(district_ids)} "
        f"(Tamil from LGD: {ta_from_lgd}, from Wikidata: {ta_from_wd})"
    )
    print(
        f"taluks:     {taluk_ok} imported "
        f"(Tamil from LGD: {taluk_from_lgd}, from Wikidata: {taluk_from_wd}), "
        f"{len(taluk_gap)} skipped (no Tamil name in LGD or Wikidata)"
    )
    if taluk_gap:
        shown = ", ".join(sorted(taluk_gap)[:20])
        print(f"  skipped taluks: {shown}" + (" …" if len(taluk_gap) > 20 else ""))
        print("  (Skipped rows are a data gap, reported honestly — never filled with English.)")


if __name__ == "__main__":
    main()
