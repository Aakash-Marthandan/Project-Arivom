"""Import the ECI constituency universe for Tamil Nadu: 234 ACs + 39 PCs.

Authorities (DECISIONS.md D-006):
- AC universe (numbers + English names): ECI 2026 results portal (S22).
- PC universe (numbers + English names + reservation): TN Statistical
  Handbook 2020 Lok Sabha dataset on data.gov.in (PC numbering is fixed by
  the 2008 delimitation).
- AC → PC linkage (+ AC reservation): DataMeet's ECI-derived AC shapefile
  attribute table — numeric AC_NO → PC_NO, no name matching. Cross-checked
  against the SHB PC names.
- AC → current district: enwiki constituency table (clean rows only), then
  Wikidata P131, then DataMeet's delimitation-era district as last resort
  (a handful of districts were split after 2008; enwiki reflects current
  boundaries).
- Tamil names: Wikidata labels; each recorded as a sourced fact (D-005).

The importer fails loudly if any AC/PC cannot be fully resolved. It never
invents a name.
"""

from __future__ import annotations

import re
import subprocess
from difflib import get_close_matches
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from bs4 import BeautifulSoup
from dbfread import DBF

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

ECI_AC_LIST_URL = "https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm"
RES_SHB_PC = "5bba3266-4f8a-45cb-91b7-dc4adf59d03e"
DATAMEET_AC_DBF_URL = (
    "https://raw.githubusercontent.com/datameet/maps/master/assembly-constituencies/India_AC.dbf"
)
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
ENWIKI_AC_PAGE = "List of constituencies of the Tamil Nadu Legislative Assembly"
ENWIKI_API = "https://en.wikipedia.org/w/api.php"

AC_SPARQL = """
SELECT ?item ?en ?ta ?ord ?distLabel ?taArticle WHERE {
  ?item wdt:P31 wd:Q54375510 .
  OPTIONAL { ?item rdfs:label ?en FILTER(LANG(?en)='en') }
  OPTIONAL { ?item rdfs:label ?ta FILTER(LANG(?ta)='ta') }
  OPTIONAL { ?item wdt:P1545 ?ord }
  OPTIONAL { ?item wdt:P131 ?dist .
             ?dist wdt:P31 wd:Q1149652 .
             ?dist rdfs:label ?distLabel FILTER(LANG(?distLabel)='en') }
  OPTIONAL { ?taArticle schema:about ?item ;
             schema:isPartOf <https://ta.wikipedia.org/> }
}
"""
PC_SPARQL = """
SELECT ?item ?en ?ta ?part WHERE {
  ?item wdt:P31 wd:Q47481352 ; wdt:P131 wd:Q1445 .
  OPTIONAL { ?item rdfs:label ?en FILTER(LANG(?en)='en') }
  OPTIONAL { ?item rdfs:label ?ta FILTER(LANG(?ta)='ta') }
  OPTIONAL { ?item wdt:P527 ?part }
}
"""

# Districts split after the 2008 delimitation (Tiruppur 2009; Ranipet,
# Tirupathur, Chengalpattu, Kallakurichi, Tenkasi 2019; Mayiladuthurai 2020).
# When the ONLY district signal for an AC is DataMeet's delimitation-era
# value and that value is one of these split parents, the current district
# is uncertain — we withhold it rather than risk showing a stale one.
# M2's boundary import resolves these spatially (AC ∩ current districts).
SPLIT_PARENT_DISTRICTS = {
    "vellore",
    "kancheepuram",
    "kanchipuram",
    "viluppuram",
    "villupuram",
    "tirunelveli",
    "nagapattinam",
    "coimbatore",
}

AC_EN_SUFFIX = " Assembly constituency"
AC_TA_SUFFIX = " சட்டமன்றத் தொகுதி"
PC_EN_SUFFIX = " Lok Sabha constituency"
PC_TA_SUFFIX = " மக்களவைத் தொகுதி"


def strip_suffix(label: str, suffix: str) -> str:
    """Strip a trailing suffix, case-insensitively."""
    if label.lower().endswith(suffix.lower()):
        return label[: len(label) - len(suffix)].strip()
    return label.strip()


def token_sorted(name: str) -> str:
    return " ".join(sorted(norm_name(name).split()))


def fetch_eci_acs(session: Any) -> dict[int, str]:
    """The constituency dropdown on the ECI results portal: value S22{n}.

    The portal's WAF rejects Python HTTP clients at the TLS layer while
    serving the same public page to curl, so this fetch shells out to curl.
    """
    del session
    result = subprocess.run(
        ["curl", "-sS", "--fail", "-m", "60", ECI_AC_LIST_URL],
        capture_output=True,
        text=True,
        check=True,
    )
    options = re.findall(r'<option value="S22(\d+)">([^<]+)</option>', result.stdout)
    acs: dict[int, str] = {}
    for num_str, label in options:
        name = label.rsplit(" - ", 1)[0].strip()
        acs[int(num_str)] = name
    if len(acs) != 234 or set(acs) != set(range(1, 235)):
        fail(f"ECI AC universe unexpected: {len(acs)} entries — refusing to import")
    return acs


def fetch_shb_pcs(session: Any) -> dict[int, dict[str, Any]]:
    records = fetch_datagovin_resource(session, RES_SHB_PC)
    pcs: dict[int, dict[str, Any]] = {}
    for row in records:
        try:
            num = int(str(row.get("_s_no_", "")).strip())
        except ValueError:
            continue
        raw = (row.get("name_of_the_parliamentary_constituency") or "").strip()
        if not raw or raw.lower() == "total" or not 1 <= num <= 39:
            continue
        match = re.search(r"\((SC|ST)\)\s*$", raw)
        pcs[num] = {
            "name_en": re.sub(r"\s*\((SC|ST)\)\s*$", "", raw).strip(),
            "reservation": match.group(1) if match else "GEN",
        }
    if len(pcs) != 39 or set(pcs) != set(range(1, 40)):
        fail(f"SHB PC universe unexpected: {sorted(pcs)} — refusing to import")
    return pcs


def fetch_datameet_acs(session: Any) -> dict[int, dict[str, Any]]:
    """AC_NO → PC_NO, delimitation-era district, reservation from DataMeet."""
    CACHE_DIR.mkdir(exist_ok=True)
    dbf_path = CACHE_DIR / "India_AC.dbf"
    if not dbf_path.exists():
        resp = session.get(DATAMEET_AC_DBF_URL, timeout=300)
        resp.raise_for_status()
        dbf_path.write_bytes(resp.content)

    result: dict[int, dict[str, Any]] = {}
    for row in DBF(dbf_path, encoding="latin-1"):
        if (row.get("ST_NAME") or "").strip().upper() != "TAMIL NADU":
            continue
        ac_no = int(row["AC_NO"])
        name = (row.get("AC_NAME") or "").strip()
        match = re.search(r"\((SC|ST)\)\s*$", name)
        result[ac_no] = {
            "pc_no": int(row["PC_NO"]),
            "pc_name": re.sub(r"\s*\((SC|ST)\)\s*$", "", (row.get("PC_NAME") or "").strip()),
            "district": (row.get("DIST_NAME") or "").strip().title(),
            "reserved": match.group(1) if match else None,
        }
    if len(result) != 234 or set(result) != set(range(1, 235)):
        fail(f"DataMeet TN AC universe unexpected: {len(result)} rows — refusing to import")
    return result


def _expand_table_grid(table: Any) -> list[list[str]]:
    """Expand an HTML table into a dense grid, resolving row/colspans."""
    grid: list[list[str]] = []
    pending: dict[int, tuple[str, int]] = {}  # col index -> (text, remaining rows)
    for tr in table.find_all("tr"):
        row: list[str] = []
        col = 0
        cells = tr.find_all(["td", "th"])
        cell_iter = iter(cells)
        while True:
            if col in pending:
                text, remaining = pending[col]
                row.append(text)
                if remaining > 1:
                    pending[col] = (text, remaining - 1)
                else:
                    del pending[col]
                col += 1
                continue
            cell = next(cell_iter, None)
            if cell is None:
                # Flush any trailing pending cells.
                if any(c >= col for c in pending):
                    max_col = max(c for c in pending if c >= col)
                    while col <= max_col:
                        if col in pending:
                            text, remaining = pending[col]
                            row.append(text)
                            if remaining > 1:
                                pending[col] = (text, remaining - 1)
                            else:
                                del pending[col]
                        else:
                            row.append("")
                        col += 1
                break
            text = " ".join(cell.get_text(" ", strip=True).split())
            rowspan = int(cell.get("rowspan", 1) or 1)
            colspan = int(cell.get("colspan", 1) or 1)
            for _ in range(colspan):
                row.append(text)
                if rowspan > 1:
                    pending[col] = (text, rowspan - 1)
                col += 1
        grid.append(row)
    return grid


def fetch_enwiki_ac_links(session: Any) -> dict[int, dict[str, str | None]]:
    """AC number → district, PC name, reservation from the enwiki list table."""
    resp = session.get(
        ENWIKI_API,
        params={
            "action": "parse",
            "page": ENWIKI_AC_PAGE,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        },
        timeout=60,
    )
    resp.raise_for_status()
    html = resp.json()["parse"]["text"]
    soup = BeautifulSoup(html, "html.parser")

    result: dict[int, dict[str, str | None]] = {}
    for table in soup.find_all("table", class_="wikitable"):
        grid = _expand_table_grid(table)
        if not grid:
            continue
        header = [h.lower() for h in grid[0]]
        if "constituency" not in " ".join(header) or "district" not in " ".join(header):
            continue
        col_num = 0
        col_name = next(i for i, h in enumerate(header) if "constituency" in h)
        col_reserved = next((i for i, h in enumerate(header) if "reserved" in h), None)
        col_district = next(i for i, h in enumerate(header) if "district" in h)
        col_pc = next(i for i, h in enumerate(header) if "lok sabha" in h)
        width = len(grid[0])
        for row in grid[1:]:
            # The page has hand-edited rows with stray pipes that shift
            # cells; accept only structurally clean rows. Gaps are fine —
            # Wikidata is the primary linkage source and this table only
            # fills its holes (with cross-validation).
            if len(row) != width or any("|" in cell for cell in row):
                continue
            try:
                num = int(row[col_num].strip())
            except ValueError:
                continue
            if not 1 <= num <= 234:
                continue
            reserved = None
            if col_reserved is not None:
                raw = row[col_reserved].strip().upper()
                reserved = raw if raw in ("SC", "ST") else None
            result[num] = {
                "name": row[col_name].strip(),
                "district": row[col_district].strip(),
                "pc": row[col_pc].strip(),
                "reserved": reserved,
            }
        if result:
            break

    # Only a sanity floor: this table is a secondary source for gap-filling
    # and cross-checks; the real completeness guarantee is the per-AC
    # resolution step, which hard-fails on any unresolved constituency.
    if len(result) < 150:
        fail(f"enwiki AC table parsed only {len(result)} clean rows — page structure changed?")
    print(f"  enwiki table: {len(result)} clean rows (of 234); rest resolved via Wikidata only")
    return result


def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    eci_source = db.ensure_source(
        name="ECI Results Portal — 2026 Tamil Nadu General Election",
        url="https://results.eci.gov.in/ResultAcGenMay2026/",
        publisher="Election Commission of India",
        license=None,
        access_mode="scrape",
        notes=(
            "Authority for the 234-AC universe (numbers + English names). The portal "
            "notes results are preliminary RO-entered trends until Form 20."
        ),
    )
    shb_source = db.ensure_source(
        name="TN Statistical Handbook 2020 — Lok Sabha constituencies (data.gov.in)",
        url="https://www.data.gov.in/catalog/statistical-hand-book-tamil-nadu",
        publisher="Department of Economics and Statistics, Government of Tamil Nadu",
        license="Government Open Data License – India (GODL)",
        access_mode="api",
        notes="Authority for the 39-PC universe: numbers, English names, reservation status.",
    )
    datameet_source = db.ensure_source(
        name="DataMeet India AC boundaries (ECI-derived)",
        url="https://github.com/datameet/maps",
        publisher="DataMeet community",
        license="CC BY 2.5 IN",
        access_mode="bulk",
        notes=(
            "Assembly-constituency attribute table scraped from ECI delimitation data. "
            "Authority for AC→PC linkage (numeric) and AC reservation; district names "
            "are delimitation-era (pre-2019 splits)."
        ),
    )
    db.ensure_source(
        name="English Wikipedia — List of TN Legislative Assembly constituencies",
        url="https://en.wikipedia.org/wiki/List_of_constituencies_of_the_Tamil_Nadu_Legislative_Assembly",
        publisher="Wikimedia Foundation (community-curated)",
        license="CC BY-SA 4.0",
        access_mode="api",
        notes=(
            "AC→district and AC→PC linkage plus AC reservation status. Community-curated; "
            "cross-checked against the ECI universe on every import."
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

    state_row = db.conn.execute(
        "SELECT id FROM localities WHERE level = 'state' AND lgd_code = '33'"
    ).fetchone()
    if state_row is None:
        fail("state row missing — run import-lgd first")
        return
    state_id = state_row[0]

    district_rows = db.conn.execute(
        "SELECT id, name_en FROM localities WHERE level = 'district'"
    ).fetchall()
    if not district_rows:
        fail("no districts in DB — run import-lgd first")
    districts_by_norm = {norm_name(name): loc_id for loc_id, name in district_rows}

    print("Fetching ECI AC list…")
    eci_acs = fetch_eci_acs(session)
    print("Fetching SHB PC list…")
    shb_pcs = fetch_shb_pcs(session)
    print("Fetching DataMeet AC attributes…")
    datameet = fetch_datameet_acs(session)
    print("Fetching enwiki AC table…")
    enwiki = fetch_enwiki_ac_links(session)
    print("Fetching Wikidata labels…")
    wd_ac_rows = sparql(session, AC_SPARQL)
    wd_pc_rows = sparql(session, PC_SPARQL)

    # --- Wikidata AC records: only items with a Tamil name are usable ---------
    wd_acs: dict[str, dict[str, Any]] = {}
    for row in wd_ac_rows:
        qid = row["item"]["value"].rsplit("/", 1)[1]
        rec = wd_acs.setdefault(qid, {"qid": qid, "districts": set(), "ords": set()})
        if "en" in row:
            rec["en"] = strip_suffix(row["en"]["value"], AC_EN_SUFFIX)
        if "ta" in row:
            rec["ta_label"] = row["ta"]["value"]
        if "taArticle" in row:
            rec["ta_article"] = row["taArticle"]["value"]
        if "ord" in row:
            try:
                rec["ords"].add(int(row["ord"]["value"]))
            except ValueError:
                pass
        if "distLabel" in row:
            rec["districts"].add(row["distLabel"]["value"])

    for rec in wd_acs.values():
        # Tamil name: the ta label if it is actually Tamil script; otherwise
        # the Tamil Wikipedia article title (some items carry English text
        # in the ta label slot).
        ta = rec.get("ta_label", "")
        if not has_tamil(ta) and rec.get("ta_article"):
            title = unquote(rec["ta_article"].rsplit("/", 1)[1]).replace("_", " ")
            ta = title
        if has_tamil(ta):
            rec["ta"] = strip_suffix(ta, AC_TA_SUFFIX)

    usable = [rec for rec in wd_acs.values() if has_tamil(rec.get("ta", ""))]
    # An ordinal is only trustworthy when the item claims exactly one and no
    # other item claims the same value (duplicate/stale P1545 exist for TN).
    ord_counts: dict[int, int] = {}
    for rec in usable:
        for o in rec["ords"]:
            ord_counts[o] = ord_counts.get(o, 0) + 1
    by_ord = {
        next(iter(rec["ords"])): rec
        for rec in usable
        if len(rec["ords"]) == 1 and ord_counts[next(iter(rec["ords"]))] == 1
    }
    by_name: dict[str, dict[str, Any]] = {}
    by_base_name: dict[str, list[dict[str, Any]]] = {}
    for rec in usable:
        if not rec.get("en"):
            continue
        by_name[norm_name(rec["en"])] = rec
        # "Tiruppattur, Sivaganga" → base "tiruppattur" (district-qualified
        # labels disambiguated later by district).
        base = norm_name(rec["en"].split(",")[0])
        by_base_name.setdefault(base, []).append(rec)

    # --- Wikidata PC records and P527 AC→PC linkage ----------------------------
    wd_pcs: dict[str, dict[str, Any]] = {}
    pc_qid_of_ac_qid: dict[str, str] = {}
    for row in wd_pc_rows:
        qid = row["item"]["value"].rsplit("/", 1)[1]
        rec = wd_pcs.setdefault(qid, {"qid": qid})
        if "en" in row:
            rec["en"] = strip_suffix(row["en"]["value"], PC_EN_SUFFIX)
        if "ta" in row:
            rec["ta"] = strip_suffix(row["ta"]["value"], PC_TA_SUFFIX)
        if "part" in row:
            pc_qid_of_ac_qid[row["part"]["value"].rsplit("/", 1)[1]] = qid

    usable_pcs = [rec for rec in wd_pcs.values() if has_tamil(rec.get("ta", "")) and rec.get("en")]
    wd_pc_by_norm = {norm_name(rec["en"]): rec for rec in usable_pcs}
    wd_pc_by_tokens = {token_sorted(rec["en"]): rec for rec in usable_pcs}

    def match_pc_name(name: str, context: str) -> dict[str, Any] | None:
        rec = wd_pc_by_norm.get(norm_name(name)) or wd_pc_by_tokens.get(token_sorted(name))
        if rec is None:
            candidates = get_close_matches(norm_name(name), list(wd_pc_by_norm), n=1, cutoff=0.75)
            if candidates:
                print(f"  FUZZY MATCH (PC, {context}): '{name}' → Wikidata '{candidates[0]}'")
                rec = wd_pc_by_norm[candidates[0]]
        return rec

    pc_problems: list[str] = []
    pc_num_by_norm: dict[str, int] = {}
    pc_num_by_tokens: dict[str, int] = {}
    pc_num_by_qid: dict[str, int] = {}
    for num, shb in sorted(shb_pcs.items()):
        rec = match_pc_name(shb["name_en"], f"SHB {num}")
        if rec is None:
            pc_problems.append(shb["name_en"])
            continue
        shb["ta"] = rec["ta"]
        shb["qid"] = rec["qid"]
        pc_num_by_norm[norm_name(shb["name_en"])] = num
        pc_num_by_norm[norm_name(rec["en"])] = num
        pc_num_by_tokens[token_sorted(shb["name_en"])] = num
        pc_num_by_tokens[token_sorted(rec["en"])] = num
        pc_num_by_qid[rec["qid"]] = num
    if pc_problems:
        fail("PCs without a resolvable Tamil name: " + ", ".join(pc_problems))

    # --- Resolve every ECI AC --------------------------------------------------
    # Layered: Wikidata is primary for district (P131) and PC (P527); clean
    # enwiki rows fill gaps. Where both sources speak, they must agree —
    # disagreement is a hard failure, never a silent choice.
    def lookup_district(label: str, context: str) -> int | None:
        key = norm_name(label.removesuffix(" district").removesuffix(" District"))
        found = districts_by_norm.get(key)
        if found is None:
            candidates = get_close_matches(key, list(districts_by_norm), n=1, cutoff=0.75)
            if candidates:
                print(f"  FUZZY MATCH (district, {context}): '{label}' → '{candidates[0]}'")
                found = districts_by_norm[candidates[0]]
        return found

    def lookup_pc_num(label: str, context: str) -> int | None:
        found = pc_num_by_norm.get(norm_name(label)) or pc_num_by_tokens.get(token_sorted(label))
        if found is None:
            candidates = get_close_matches(norm_name(label), list(pc_num_by_norm), n=1, cutoff=0.75)
            if candidates:
                print(f"  FUZZY MATCH (PC, {context}): '{label}' → '{candidates[0]}'")
                found = pc_num_by_norm[candidates[0]]
        return found

    resolved: dict[int, dict[str, Any]] = {}
    problems: list[str] = []
    district_gaps: list[str] = []
    used_qids: set[str] = set()
    for num, eci_name in sorted(eci_acs.items()):
        links = enwiki.get(num) or {}
        dm = datameet[num]

        # Which districts could this AC be in? (Used to disambiguate
        # same-named constituencies.) Union of the current (enwiki) and
        # delimitation-era (DataMeet) assignments.
        allowed_districts: set[int] = set()
        for label, ctx in ((links.get("district"), "enwiki"), (dm["district"], "datameet")):
            if label:
                found = lookup_district(str(label), f"AC {num} {ctx}")
                if found is not None:
                    allowed_districts.add(found)

        def district_compatible(cand: dict[str, Any], allowed: set[int]) -> bool:
            if not cand["districts"] or not allowed:
                return True  # nothing to check against
            cand_ids = {lookup_district(lbl, "cand") for lbl in cand["districts"]}
            return bool(cand_ids & allowed)

        # Wikidata item selection: exact name → district-disambiguated base
        # name → unique ordinal → fuzzy. Name+district beats a bare ordinal
        # because stale/duplicated P1545 values exist for TN.
        rec = by_name.get(norm_name(eci_name)) or by_name.get(
            norm_name(str(links.get("name") or ""))
        )
        if rec is None:
            base_cands = [
                c
                for c in by_base_name.get(norm_name(eci_name), [])
                if c["qid"] not in used_qids and district_compatible(c, allowed_districts)
            ]
            if len(base_cands) == 1:
                rec = base_cands[0]
        if rec is None:
            rec = by_ord.get(num)
            if rec is not None and not district_compatible(rec, allowed_districts):
                print(
                    f"  NOTE (AC {num}): ordinal match {rec['qid']} rejected — "
                    "district incompatible."
                )
                rec = None
        if rec is None:
            all_keys = list(by_name) + list(by_base_name)
            candidates = get_close_matches(norm_name(eci_name), all_keys, n=3, cutoff=0.75)
            for key in candidates:
                cands = [by_name[key]] if key in by_name else by_base_name[key]
                cands = [
                    c
                    for c in cands
                    if c["qid"] not in used_qids and district_compatible(c, allowed_districts)
                ]
                if len(cands) == 1:
                    print(f"  FUZZY MATCH (AC {num}): ECI '{eci_name}' → Wikidata '{key}'")
                    rec = cands[0]
                    break
        if rec is None:
            problems.append(f"AC {num} {eci_name}: no Tamil name found via Wikidata")
            continue
        if rec["qid"] in used_qids:
            problems.append(f"AC {num} {eci_name}: Wikidata item {rec['qid']} matched twice")
            continue
        used_qids.add(rec["qid"])

        # Current district: enwiki (current boundaries) → Wikidata P131 →
        # DataMeet's delimitation-era district. Vintage differences between
        # the first two are expected (post-2019 district splits); the newer
        # assignment wins, with a note for the audit trail.
        enwiki_district_id = (
            lookup_district(str(links["district"]), f"AC {num} enwiki")
            if links.get("district")
            else None
        )
        wd_district_ids = {
            d for d in (lookup_district(lbl, f"AC {num} wd") for lbl in rec["districts"]) if d
        }
        district_id: int | None
        if enwiki_district_id is not None:
            district_id = enwiki_district_id
            if wd_district_ids and enwiki_district_id not in wd_district_ids:
                print(
                    f"  NOTE (AC {num}): district differs — enwiki "
                    f"'{links.get('district')}' vs Wikidata {sorted(rec['districts'])}; "
                    "using enwiki (current boundaries)."
                )
        elif len(wd_district_ids) == 1:
            district_id = next(iter(wd_district_ids))
        elif norm_name(dm["district"]) in SPLIT_PARENT_DISTRICTS:
            # Delimitation-era district was later split: current assignment
            # uncertain. Withhold rather than display a possibly stale value.
            district_id = None
            district_gaps.append(f"AC {num} {eci_name} (was '{dm['district']}')")
        else:
            district_id = lookup_district(dm["district"], f"AC {num} datameet")
            if district_id is not None:
                print(
                    f"  NOTE (AC {num}): district from DataMeet (delimitation-era) — "
                    f"'{dm['district']}'."
                )
            else:
                problems.append(f"AC {num} {eci_name}: no district via enwiki/Wikidata/DataMeet")
                continue

        # PC: DataMeet numeric AC_NO → PC_NO, sanity-checked by PC name.
        pc_num = dm["pc_no"]
        if pc_num not in shb_pcs:
            problems.append(f"AC {num} {eci_name}: DataMeet PC_NO {pc_num} not in SHB universe")
            continue
        name_check = lookup_pc_num(dm["pc_name"], f"AC {num} datameet")
        if name_check is not None and name_check != pc_num:
            problems.append(
                f"AC {num} {eci_name}: DataMeet PC_NO {pc_num} vs PC_NAME "
                f"'{dm['pc_name']}' (= {name_check}) disagree"
            )
            continue

        # Display names: strip Wikidata's ", District" disambiguation
        # qualifier — the district is separate structured data here.
        name_en = (rec.get("en") or links.get("name") or eci_name.title()).split(",")[0].strip()
        resolved[num] = {
            "name_en": name_en,
            "name_ta": rec["ta"].split(",")[0].strip(),
            "qid": rec["qid"],
            "pc_num": pc_num,
            "district_id": district_id,
            "reserved": dm["reserved"],
        }

    if problems:
        fail("unresolved ACs:\n  " + "\n  ".join(problems))

    # --- Write PCs, then ACs ----------------------------------------------------
    pc_ids: dict[int, int] = {}
    for num, shb in sorted(shb_pcs.items()):
        pc_id = db.upsert_locality_by_eci(
            eci_code=str(num),
            name_en=shb["name_en"],
            name_ta=shb["ta"],
            level="pc",
            parent_id=state_id,
            district_id=None,
            source_id=shb_source,
            retrieved_at=retrieved_at,
        )
        pc_ids[num] = pc_id
        db.upsert_fact(
            subject_type="locality",
            subject_id=pc_id,
            key="name_ta",
            value={"name_ta": shb["ta"], "wikidata": shb["qid"]},
            source_id=wikidata_source,
            retrieved_at=retrieved_at,
            extraction_method="api",
            confidence=1.0,
        )
        db.upsert_fact(
            subject_type="locality",
            subject_id=pc_id,
            key="reservation",
            value={"status": shb["reservation"]},
            source_id=shb_source,
            retrieved_at=retrieved_at,
            extraction_method="api",
            confidence=1.0,
        )

    for num, rec in sorted(resolved.items()):
        ac_id = db.upsert_locality_by_eci(
            eci_code=str(num),
            name_en=rec["name_en"],
            name_ta=rec["name_ta"],
            level="ac",
            parent_id=pc_ids[rec["pc_num"]],
            district_id=rec["district_id"],
            source_id=eci_source,
            retrieved_at=retrieved_at,
        )
        db.upsert_fact(
            subject_type="locality",
            subject_id=ac_id,
            key="name_ta",
            value={"name_ta": rec["name_ta"], "wikidata": rec["qid"]},
            source_id=wikidata_source,
            retrieved_at=retrieved_at,
            extraction_method="api",
            confidence=1.0,
        )
        if rec["reserved"]:
            db.upsert_fact(
                subject_type="locality",
                subject_id=ac_id,
                key="reservation",
                value={"status": rec["reserved"]},
                source_id=datameet_source,
                retrieved_at=retrieved_at,
                extraction_method="bulk",
                confidence=1.0,
            )

    db.conn.commit()

    print("\n=== Constituency import report ===")
    print(f"PCs: {len(pc_ids)} (expected 39)")
    print(f"ACs: {len(resolved)} (expected 234)")
    if district_gaps:
        print(
            f"district withheld for {len(district_gaps)} ACs "
            "(delimitation-era district later split; resolved spatially in M2):"
        )
        for gap in district_gaps:
            print(f"  {gap}")
    counts = db.conn.execute(
        "SELECT level, count(*) FROM localities WHERE level IN ('ac','pc') GROUP BY level"
    ).fetchall()
    print(f"DB now has: {dict(counts)}")


if __name__ == "__main__":
    main()
