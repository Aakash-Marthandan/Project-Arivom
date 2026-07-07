"""Import UDISE+ district education indicators for Tamil Nadu.

Source: the official UDISE+ open-services API (api.udiseplus.gov.in), the
same public API that renders the national UDISE+ dashboard
(dashboard.udiseplus.gov.in). District-wise rows come from the kpi report
endpoints with regionType 22 ("districts of a state") and regionCode 33
(Tamil Nadu); the pupil-teacher ratio state rollup uses regionType 21.
The client token below is the public one shipped in the dashboard's own
JS bundle; if it rotates this run fails loudly and the token needs
re-reading from the bundle (see docs/DECISIONS.md D-028).

Scope (D-028): counts and ratios whose semantics are unambiguous —
enrollment by level and gender, schools, teachers, pupil-teacher ratios,
and functional school infrastructure. Derived rates whose UDISE level
buckets we could not verify (GER/NER/dropout) are deliberately not
imported. UDISE+ data is voluntarily self-uploaded by schools (reference
date 30 September of the academic year); the UI labels it accordingly.

Facts: subject_type='locality' on each district (and the state row),
one fact per indicator, value = {"series": [{"year": "2021-22", ...}]}
ascending by academic year. A district that cannot be matched to an LGD
district is reported and skipped, never guessed.
"""

from __future__ import annotations

from typing import Any

import requests

from .common import Db, fail, http_session, norm_name, now_utc

BASE = "https://api.udiseplus.gov.in/open-services/v1.1/"

# Public client token embedded verbatim in the public dashboard bundle
# (https://dashboard.udiseplus.gov.in/report2025/static/js/main.*.js).
PUBLIC_DASHBOARD_TOKEN = (
    "df;lkjz8lke4lk345kljsdfkjdfgkljsf08994a/sdfljsdf879w4ra/sdflksdflksdf"
)

TN_STATE_CODE = "33"
REGION_STATE_WISE = 21  # rows = every state
REGION_DISTRICT_WISE = 22  # rows = districts of regionCode's state

# UDISE spellings that differ from our LGD names (normalized comparison).
UDISE_NAME_ALIASES = {
    "sivagangai": "sivaganga",
    "tiruvallur": "thiruvallur",
    "tiruvarur": "thiruvarur",
    "villupuram": "viluppuram",
}

# UDISE education districts that intentionally have no LGD counterpart.
# CHENNAI (EXT. GCC) covers Greater Chennai Corporation areas that lie in
# neighbouring revenue districts; it is counted in the state rollup only.
KNOWN_UNMATCHED = {"CHENNAI (EXT. GCC)"}

# Functional counts are the honest measure of a facility's presence.
INFRA_FIELDS = {
    "functionalElectricity": "totSchFuncElectricity",
    "functionalDrinkingWater": "totSchFuncDrinkingWater",
    "functionalGirlsToilet": "totSchFuncGirlsToilet",
    "functionalBoysToilet": "totSchFuncBoysToilet",
    "library": "totSchLibrary",
    "playground": "totSchPlayground",
    "functionalComputers": "totSchFuncCompAvail",
    "internet": "totSchInternet",
    "ramps": "totSchRamps",
    "medicalCheckup": "totSchMedicalCheckup",
}

# Level buckets are computed from the class-wise fields, NOT the API's
# totEnrPry/totEnrSec rollups: those follow school-category logic (verified
# numerically — "Sec" spans classes 9–12 and "PrePry"/"Pry" shift students
# across the class-1–5 boundary), while class-wise counts are unambiguous
# and sum exactly to totEnr. The computation is documented on /methodology.
ENROLLMENT_LEVELS = {
    "prePrimary": ["prePry1", "prePry2", "prePry3"],
    "primary": ["class1", "class2", "class3", "class4", "class5"],
    "upperPrimary": ["class6", "class7", "class8"],
    "secondary": ["class9", "class10"],
    "higherSecondary": ["class11", "class12"],
}

PTR_FIELDS = {
    "primary": "ptrPry",
    "upperPrimary": "ptrUPry",
    "secondary": "ptrSec",
    "higherSecondary": "ptrHSec",
}

FACT_KEYS = (
    "education.enrollment",
    "education.schools",
    "education.teachers",
    "education.ptr",
    "education.school_infrastructure",
)


def api_session() -> requests.Session:
    session = http_session()
    session.headers["Authorization"] = f"Bearer {PUBLIC_DASHBOARD_TOKEN}"
    session.headers["Identity"] = "test"  # fixed value the dashboard sends
    return session


def api_get(session: requests.Session, path: str) -> list[dict[str, Any]]:
    resp = session.get(BASE + path, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") is not True:
        fail(f"UDISE+ API refused GET {path}: {payload.get('errorDetails')}")
    return payload["data"]


def api_post(
    session: requests.Session, path: str, body: dict[str, Any]
) -> list[dict[str, Any]]:
    resp = session.post(BASE + path, json=body, timeout=120)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") is not True:
        fail(f"UDISE+ API refused {path} {body}: {payload.get('errorDetails')}")
    data = payload["data"]
    return data if isinstance(data, list) else []


def district_rows(
    session: requests.Session, path: str, year_id: int
) -> list[dict[str, Any]]:
    return api_post(
        session,
        path,
        {
            "yearId": year_id,
            "regionCode": TN_STATE_CODE,
            "regionType": REGION_DISTRICT_WISE,
            "valueType": 1,
        },
    )


def to_int(value: Any) -> int:
    return int(str(value or 0).strip() or 0)


def to_ratio(value: Any) -> float | None:
    """UDISE reports 0.0 where a level is absent; that is 'no data', not 0."""
    ratio = float(str(value).strip() or 0)
    return ratio if ratio > 0 else None


def enrollment_point(row: dict[str, Any], year_desc: str) -> dict[str, Any]:
    """Class-wise fields → level buckets (see ENROLLMENT_LEVELS note)."""
    point: dict[str, Any] = {
        "year": year_desc,
        "total": to_int(row["totEnr"]),
        "boys": to_int(row["totEnrB"]),
        "girls": to_int(row["totEnrG"]),
    }
    check_sum = 0
    for level, classes in ENROLLMENT_LEVELS.items():
        boys = sum(to_int(row.get(f"{c}B")) for c in classes)
        girls = sum(to_int(row.get(f"{c}G")) for c in classes)
        trans = sum(to_int(row.get(f"{c}Trans")) for c in classes)
        point[level] = boys + girls + trans
        point[f"{level}Boys"] = boys
        point[f"{level}Girls"] = girls
        check_sum += boys + girls + trans
    if check_sum != point["total"]:
        fail(
            f"{row.get('regionName')} {year_desc}: class-wise sum {check_sum} "
            f"!= published total {point['total']} — bucket semantics changed?"
        )
    return point


def main() -> None:
    session = api_session()
    db = Db.connect()
    retrieved_at = now_utc()

    source_id = db.ensure_source(
        name="UDISE+ (Unified District Information System for Education)",
        url="https://dashboard.udiseplus.gov.in/",
        publisher=(
            "Department of School Education & Literacy, Ministry of Education,"
            " Government of India"
        ),
        license=None,
        access_mode="api",
        notes=(
            "District-wise education statistics for Tamil Nadu from the public"
            " UDISE+ dashboard API (open-services v1.1). Data is voluntarily"
            " self-uploaded by schools; reference date 30 September of each"
            " academic year. Counts and ratios only (D-028); GER/NER/dropout"
            " rates are not imported until their level bucketing is verified."
        ),
    )

    # LGD districts (and the state row) we attach facts to.
    districts = db.conn.execute(
        "SELECT id, name_en FROM localities WHERE level = 'district'"
    ).fetchall()
    by_norm = {norm_name(name): loc_id for loc_id, name in districts}
    state_row = db.conn.execute(
        "SELECT id, name_en FROM localities WHERE level = 'state'"
    ).fetchall()
    if len(state_row) != 1:
        fail(f"expected exactly one state locality, found {len(state_row)}")
    state_id = state_row[0][0]

    def match_district(udise_name: str) -> int | None:
        norm = norm_name(udise_name)
        return by_norm.get(UDISE_NAME_ALIASES.get(norm, norm))

    years = api_get(session, "acad-year-master/public")
    years.sort(key=lambda y: y["yearId"])
    print(f"UDISE+ academic years advertised: "
          f"{', '.join(y['yearDesc'] for y in years)}")

    # series[locality_id][fact_key] -> list of per-year points
    series: dict[int, dict[str, list[dict[str, Any]]]] = {}
    unmatched: set[str] = set()
    covered_years: list[str] = []
    pending_years: list[str] = []

    def add_point(loc_id: int, fact_key: str, point: dict[str, Any]) -> None:
        series.setdefault(loc_id, {}).setdefault(fact_key, []).append(point)

    for year in years:
        year_id, year_desc = year["yearId"], year["yearDesc"]
        enrollment = [
            r
            for r in district_rows(session, "kpi/students-enrollment/public", year_id)
            if str(r.get("casteId")) == "0"
        ]
        infra = district_rows(session, "kpi/schools-basic-infra/public", year_id)
        ptr = district_rows(session, "kpi/ptr/public", year_id)
        teachers = district_rows(session, "kpi/teachers/public", year_id)

        if not (enrollment or infra or ptr or teachers):
            pending_years.append(year_desc)
            continue
        covered_years.append(year_desc)

        state_totals: dict[str, dict[str, int]] = {
            key: {} for key in FACT_KEYS if key != "education.ptr"
        }

        def accumulate(
            fact_key: str,
            point: dict[str, Any],
            totals_by_key: dict[str, dict[str, int]] = state_totals,
        ) -> None:
            totals = totals_by_key[fact_key]
            for field, value in point.items():
                if isinstance(value, int):
                    totals[field] = totals.get(field, 0) + value

        # State totals sum EVERY district-wise row, matched or not: UDISE
        # education districts partition the state, and one of them
        # (CHENNAI (EXT. GCC)) has no LGD counterpart by design.
        for row in enrollment:
            point = enrollment_point(row, year_desc)
            accumulate("education.enrollment", point)
            loc_id = match_district(row["regionName"])
            if loc_id is None:
                unmatched.add(row["regionName"])
                continue
            add_point(loc_id, "education.enrollment", point)

        for row in infra:
            schools_point: dict[str, Any] = {
                "year": year_desc,
                "total": to_int(row["totSch"]),
            }
            infra_point: dict[str, Any] = {
                "year": year_desc,
                "schools": to_int(row["totSch"]),
            }
            infra_point.update({k: to_int(row[f]) for k, f in INFRA_FIELDS.items()})
            accumulate("education.schools", schools_point)
            accumulate("education.school_infrastructure", infra_point)
            loc_id = match_district(row["regionName"])
            if loc_id is None:
                unmatched.add(row["regionName"])
                continue
            add_point(loc_id, "education.schools", schools_point)
            add_point(loc_id, "education.school_infrastructure", infra_point)

        for row in teachers:
            point = {
                "year": year_desc,
                "total": to_int(row["totTch"]),
                "female": to_int(row["totTchF"]),
                "male": to_int(row["totTchM"]),
            }
            accumulate("education.teachers", point)
            loc_id = match_district(row["regionName"])
            if loc_id is None:
                unmatched.add(row["regionName"])
                continue
            add_point(loc_id, "education.teachers", point)

        for row in ptr:
            loc_id = match_district(row["regionName"])
            if loc_id is None:
                unmatched.add(row["regionName"])
                continue
            point = {"year": year_desc}
            point.update({k: to_ratio(row[f]) for k, f in PTR_FIELDS.items()})
            add_point(loc_id, "education.ptr", point)

        # State rollup: sums of the district counts (documented on
        # /methodology); PTR cannot be summed, so read the state-wise row.
        for fact_key, totals in state_totals.items():
            if totals:
                add_point(state_id, fact_key, {"year": year_desc, **totals})
        state_ptr = [
            r
            for r in api_post(
                session,
                "kpi/ptr/public",
                {
                    "yearId": year_id,
                    "regionCode": "99",
                    "regionType": REGION_STATE_WISE,
                    "valueType": 1,
                },
            )
            if str(r.get("regionCode")) == TN_STATE_CODE
        ]
        if state_ptr:
            point = {"year": year_desc}
            point.update(
                {k: to_ratio(state_ptr[0][f]) for k, f in PTR_FIELDS.items()}
            )
            add_point(state_id, "education.ptr", point)

        matched = sum(1 for r in infra if match_district(r["regionName"]))
        print(
            f"  {year_desc}: {matched}/{len(infra)} districts matched, "
            f"{len(enrollment)} enrollment rows"
        )
        if infra and matched < 30:
            fail(f"{year_desc}: only {matched} districts matched — mapping broke?")

    if not covered_years:
        fail("UDISE+ returned no district data for any advertised year")

    # Plausibility gate on the latest statewide enrollment (TN is ~1.2 crore
    # students); a total outside this window means semantics changed.
    state_points = series.get(state_id, {}).get("education.enrollment", [])
    latest_total = state_points[-1]["total"] if state_points else 0
    if not 8_000_000 <= latest_total <= 20_000_000:
        fail(f"statewide enrollment {latest_total} implausible — check API semantics")

    # Cross-validation: our sum of district-wise rows must reproduce the
    # state figure UDISE+ publishes independently (summarised endpoint).
    for point in state_points:
        year_id = next(y["yearId"] for y in years if y["yearDesc"] == point["year"])
        published = [
            r
            for r in api_post(
                session,
                "students-summarised-stats/public",
                {"yearId": year_id, "regionCode": "99",
                 "regionType": REGION_STATE_WISE, "valueType": 1},
            )
            if str(r.get("regionCd")) == TN_STATE_CODE
        ]
        if not published:
            print(f"  cross-check {point['year']}: no published state row (skipped)")
            continue
        official = to_int(published[0]["totStudents"])
        drift = abs(official - point["total"]) / official
        status = "OK" if drift <= 0.01 else "MISMATCH"
        print(
            f"  cross-check {point['year']}: district sum {point['total']:,} "
            f"vs published state total {official:,} — {status}"
        )
        if drift > 0.01:
            fail(f"{point['year']}: district sum diverges {drift:.1%} from the "
                 "published state total — partition semantics changed?")

    written = 0
    for loc_id, facts in series.items():
        for fact_key, points in facts.items():
            db.upsert_fact(
                subject_type="locality",
                subject_id=loc_id,
                key=fact_key,
                value={"series": points},
                source_id=source_id,
                retrieved_at=retrieved_at,
                extraction_method="api",
                confidence=1.0,
                review_status="unreviewed",
            )
            written += 1
    db.conn.commit()

    print("\n=== UDISE+ import report ===")
    print(f"Academic years imported: {', '.join(covered_years)}")
    if pending_years:
        print(
            "Years advertised but not yet published district-wise "
            f"(pending, expected): {', '.join(pending_years)}"
        )
    print(f"Facts written: {written} "
          f"({len(series) - 1} districts + state rollup)")
    print(f"Statewide enrollment, latest year: {latest_total:,}")
    expected_unmatched = unmatched & KNOWN_UNMATCHED
    surprise_unmatched = unmatched - KNOWN_UNMATCHED
    if expected_unmatched:
        print(
            "Known UDISE-only education districts (state rollup only): "
            f"{sorted(expected_unmatched)}"
        )
    if surprise_unmatched:
        print("PENDING — UDISE districts with no LGD match (state rollup "
              f"only, fix UDISE_NAME_ALIASES): {sorted(surprise_unmatched)}")


if __name__ == "__main__":
    main()
