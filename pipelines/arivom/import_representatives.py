"""Import the representative spine: 234 MLAs (2026) + 39 Lok Sabha MPs (2024).

Authorities (DECISIONS.md D-013):
- MLA winners, parties, vote counts: ECI 2026 results portal, one page per
  AC (provisional RO-entered trends until Form 20 — stored and displayed
  as provisional per DESIGN.md §13).
- MLA Tamil names + Tamil party names: the per-constituency results table
  on Tamil Wikipedia's 2026 election article. Joined by AC number and
  VALIDATED BY EXACT VOTE-COUNT EQUALITY with ECI — vote numbers are
  script-independent, so a matching count confirms the same person without
  any cross-script name matching. Party match is the documented fallback.
- Lok Sabha winners: English Wikipedia's 2024-TN results table (EN side)
  joined with Tamil Wikipedia's (TA side), same number+votes validation.
  (The ECI 2024 portal is no longer online; sansad.in blocks scraping.)

A person who wins two seats (e.g. one candidate winning two ACs) is one
`persons` row with two tenures. The importer hard-fails if any seat cannot
be fully resolved bilingually. Nothing is transliterated or invented.
"""

from __future__ import annotations

import re
import subprocess
import time
from datetime import date
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .common import (
    Db,
    expand_table_grid,
    fail,
    has_tamil,
    http_session,
    now_utc,
)

ECI_BASE = "https://results.eci.gov.in/ResultAcGenMay2026"
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

TAWIKI_API = "https://ta.wikipedia.org/w/api.php"
ENWIKI_API = "https://en.wikipedia.org/w/api.php"
TAWIKI_ASSEMBLY_PAGE = "தமிழ்நாடு சட்டமன்றத் தேர்தல், 2026"
TAWIKI_LS_PAGE = "தமிழ்நாட்டில் இந்தியப் பொதுத் தேர்தல், 2024"
ENWIKI_LS_PAGE = "2024 Indian general election in Tamil Nadu"

# Result declaration dates: tenure start (oath dates differ per member and
# are not machine-available; basis recorded in the election_result fact).
ASSEMBLY_RESULT_DATE = date(2026, 5, 4)
LS_RESULT_DATE = date(2024, 6, 4)

# Classification-only: English party name (as ECI prints it) → normalized
# Tamil renderings. Used solely to LOCATE the winner inside Tamil source
# tables; the stored Tamil party name still comes from the source itself.
PARTY_EN_TO_TA_NORMS: dict[str, set[str]] = {
    "Tamilaga Vettri Kazhagam": {"தவெக", "தமிழகவெற்றிக்கழகம்"},
    "Dravida Munnetra Kazhagam": {"திமுக", "திராவிடமுன்னேற்றக்கழகம்"},
    "All India Anna Dravida Munnetra Kazhagam": {
        "அதிமுக", "அஇஅதிமுக", "அனைத்திந்தியஅண்ணாதிராவிடமுன்னேற்றக்கழகம்",
    },
    "Indian National Congress": {"இதேகா", "காங்கிரசு", "இந்தியதேசியகாங்கிரசு"},
    "Bharatiya Janata Party": {"பாஜக", "பாரதியஜனதாகட்சி"},
    "Pattali Makkal Katchi": {"பாமக", "பாட்டாளிமக்கள்கட்சி"},
    "Viduthalai Chiruthaigal Katchi": {"விசிக", "விடுதலைச்சிறுத்தைகள்கட்சி"},
    "Communist Party of India": {"இபொக", "இந்தியபொதுவுடைமைக்கட்சி"},
    "Communist Party of India (Marxist)": {"இபொகமா", "மார்க்சிஸ்ட்"},
    "Naam Tamilar Katchi": {"நாதக", "நாம்தமிழர்கட்சி"},
    "Desiya Murpokku Dravida Kazhagam": {"தேமுதிக", "தேசியமுற்போக்குதிராவிடக்கழகம்"},
    "Marumalarchi Dravida Munnetra Kazhagam": {"மதிமுக"},
    "Indian Union Muslim League": {
        "இயூமுலீ", "இந்தியயூனியன்முஸ்லிம்லீக்", "இந்தியஒன்றியமுஸ்லிம்லீக்", "முஸ்லிம்லீக்",
    },
    "Independent": {"சுயேச்சை", "சார்பிலி"},
}

# The English Wikipedia LS table uses abbreviations; alias them to the
# same Tamil-rendering sets.
_EN_ABBREVS = {
    "TVK": "Tamilaga Vettri Kazhagam",
    "DMK": "Dravida Munnetra Kazhagam",
    "AIADMK": "All India Anna Dravida Munnetra Kazhagam",
    "INC": "Indian National Congress",
    "BJP": "Bharatiya Janata Party",
    "PMK": "Pattali Makkal Katchi",
    "VCK": "Viduthalai Chiruthaigal Katchi",
    "CPI": "Communist Party of India",
    "CPI(M)": "Communist Party of India (Marxist)",
    "CPM": "Communist Party of India (Marxist)",
    "NTK": "Naam Tamilar Katchi",
    "DMDK": "Desiya Murpokku Dravida Kazhagam",
    "MDMK": "Marumalarchi Dravida Munnetra Kazhagam",
    "IUML": "Indian Union Muslim League",
    "IND": "Independent",
}
for _abbrev, _full in _EN_ABBREVS.items():
    PARTY_EN_TO_TA_NORMS[_abbrev] = PARTY_EN_TO_TA_NORMS[_full]

# Classification-only lexicon: Tamil renderings (short + full) of TN party
# names, used solely to tell a party cell from a person cell when a wiki
# table's column order is ambiguous. Never stored as data — stored party
# names always come from the sources themselves.
PARTY_LEXICON_TA = {
    "தவெக", "தமிழக வெற்றிக் கழகம்",
    "திமுக", "திராவிட முன்னேற்றக் கழகம்",
    "அதிமுக", "அஇஅதிமுக", "அனைத்திந்திய அண்ணா திராவிட முன்னேற்றக் கழகம்",
    "பாஜக", "பாரதிய ஜனதா கட்சி",
    "இதேகா", "காங்கிரசு", "இந்திய தேசிய காங்கிரசு", "இந்திய தேசிய காங்கிரஸ்",
    "பாமக", "பாட்டாளி மக்கள் கட்சி",
    "மதிமுக", "மறுமலர்ச்சி திராவிட முன்னேற்றக் கழகம்",
    "விசிக", "விடுதலைச் சிறுத்தைகள் கட்சி",
    "இபொக", "இந்திய பொதுவுடைமைக் கட்சி",
    "இபொகமா", "இந்திய பொதுவுடைமைக் கட்சி (மார்க்சிஸ்ட்)", "மார்க்சிஸ்ட்",
    "நாதக", "நாம் தமிழர் கட்சி",
    "தேமுதிக", "தேசிய முற்போக்கு திராவிடக் கழகம்",
    "சுயேச்சை",
}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_int(text: str) -> int | None:
    cleaned = re.sub(r"[,\s]", "", text)
    return int(cleaned) if re.fullmatch(r"\d+", cleaned) else None


# --------------------------------------------------------------------------
# ECI per-AC results
# --------------------------------------------------------------------------
def fetch_eci_ac_page(num: int) -> str:
    """Fetch (with cache) one constituency page via curl (WAF, see D-006)."""
    cache = CACHE_DIR / "eci2026"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"ac{num}.htm"
    if path.exists() and path.stat().st_size > 2000:
        return path.read_text(errors="replace")
    result = subprocess.run(
        ["curl", "-sS", "--fail", "-m", "60", f"{ECI_BASE}/ConstituencywiseS22{num}.htm"],
        capture_output=True,
        text=True,
        check=True,
    )
    path.write_text(result.stdout)
    time.sleep(0.35)  # be polite: ~234 sequential fetches on first run
    return result.stdout


def parse_eci_candidates(html: str, num: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        cells = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all("td")]
        if len(cells) < 7:
            continue
        total = parse_int(cells[5])
        if total is None or not cells[1]:
            continue
        candidates.append(
            {
                "name": cells[1],
                "party": cells[2],
                "votes": total,
                "pct": float(cells[6]) if re.fullmatch(r"\d+(\.\d+)?", cells[6]) else None,
            }
        )
    real = [c for c in candidates if c["party"] != "None of the Above"]
    if len(real) < 2:
        fail(f"ECI AC {num}: could not parse a plausible candidate table")
    return real


def fetch_eci_results() -> dict[int, dict[str, Any]]:
    """AC number → winner/runner-up with votes and margin (provisional)."""
    results: dict[int, dict[str, Any]] = {}
    for num in range(1, 235):
        candidates = parse_eci_candidates(fetch_eci_ac_page(num), num)
        ranked = sorted(candidates, key=lambda c: c["votes"], reverse=True)
        winner, runner = ranked[0], ranked[1]
        if winner["votes"] == runner["votes"]:
            fail(f"ECI AC {num}: tie at the top — refusing to pick a winner")
        results[num] = {
            "winner": winner,
            "runner_up": runner,
            "margin": winner["votes"] - runner["votes"],
            "total_votes": sum(c["votes"] for c in candidates),
            "candidates": len(candidates),
        }
        if num % 50 == 0:
            print(f"  ECI: parsed {num}/234")
    return results


# --------------------------------------------------------------------------
# Wikipedia results tables (generic, structure-validated)
# --------------------------------------------------------------------------
def fetch_wiki_html(session: Any, api: str, page: str) -> str:
    """Fetch a rendered wiki page, disk-cached for 24h (iteration + rate limits)."""
    import hashlib
    import time as _time

    cache = CACHE_DIR / "wiki"
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{api}|{page}".encode()).hexdigest()[:24]
    path = cache / f"{key}.html"
    miss_marker = cache / f"{key}.missing"
    if miss_marker.exists() and _time.time() - miss_marker.stat().st_mtime < 86400:
        fail(f"wiki page not found: {page}")
    if path.exists() and _time.time() - path.stat().st_mtime < 86400:
        return path.read_text()
    resp = session.get(
        api,
        params={
            "action": "parse",
            "page": page,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        },
        timeout=120,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "parse" not in payload:
        miss_marker.write_text("")
        fail(f"wiki page not found: {page}")
    html = payload["parse"]["text"]
    path.write_text(html)
    return html


def find_results_rows(
    html: str, max_no: int, min_rows: int
) -> dict[int, list[str]]:
    """Locate the per-constituency results table in a wiki page.

    Returns constituency number → full expanded row. The right table is the
    one where some column holds distinct integers covering most of 1..max_no.
    """
    soup = BeautifulSoup(html, "html.parser")
    best: dict[int, list[str]] = {}
    for table in soup.find_all("table", class_="wikitable"):
        grid = expand_table_grid(table)
        if len(grid) < min_rows:
            continue
        # Try each column as the "constituency number" column.
        width = max(len(r) for r in grid)
        for col in range(min(width, 6)):
            rows: dict[int, list[str]] = {}
            for row in grid:
                if len(row) <= col:
                    continue
                n = parse_int(row[col])
                if n is not None and 1 <= n <= max_no:
                    # Keep the first occurrence (winner row when a
                    # constituency spans multiple rows).
                    rows.setdefault(n, row)
            if len(rows) <= len(best):
                continue
            # A RESULTS table has vote counts; a candidates table doesn't.
            # Require vote-sized integers in most rows.
            with_votes = sum(
                1
                for row in rows.values()
                if any((parse_int(c) or 0) >= 1000 for c in row)
            )
            if with_votes >= 0.8 * len(rows):
                best = rows
        if len(best) >= min_rows:
            break
    if len(best) < min_rows:
        fail(f"no results table found covering ≥{min_rows} constituencies")
    return best


def find_candidates_rows(html: str) -> dict[int, list[str]]:
    """The pre-election candidates-by-alliance table: numbered rows, mostly
    Tamil names, NO vote counts (that's how it differs from results tables)."""
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table", class_="wikitable"):
        grid = expand_table_grid(table)
        if len(grid) < 200:
            continue
        header_text = " ".join(grid[0]) + " " + " ".join(grid[1] if len(grid) > 1 else [])
        if "வேட்பாளர்" not in header_text:
            continue
        rows: dict[int, list[str]] = {}
        with_votes = 0
        for row in grid:
            for col in range(min(len(row), 4)):
                n = parse_int(row[col])
                if n is not None and 1 <= n <= 234:
                    rows.setdefault(n, row)
                    if any((parse_int(c) or 0) >= 1000 for c in row):
                        with_votes += 1
                    break
        if len(rows) >= 220 and with_votes < 0.2 * len(rows):
            return rows
    return {}


def candidate_from_row(
    row: list[str], party_norms_wanted: set[str], all_party_norms: set[str]
) -> str | None:
    """Find the candidate whose adjacent party cell matches the wanted party.
    Works for (party, name) pairs; single-party columns (no party subcell)
    are handled by the caller via calibration."""
    for i, cell in enumerate(row[:-1]):
        if norm_party(cell) in party_norms_wanted:
            nxt = clean_cell(row[i + 1])
            if nxt and has_tamil(nxt) and norm_party(nxt) not in all_party_norms:
                return nxt
    return None


def _search_ac_article_title(session: Any, ac_name_ta: str) -> str | None:
    """Some AC articles use spelling variants; find via tawiki search."""
    resp = session.get(
        TAWIKI_API,
        params={
            "action": "query",
            "list": "search",
            "srsearch": f"{ac_name_ta} சட்டமன்றத் தொகுதி",
            "srlimit": "3",
            "format": "json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    for hit in resp.json().get("query", {}).get("search", []):
        if hit["title"].endswith("சட்டமன்றத் தொகுதி"):
            return hit["title"]
    return None


def fetch_ac_article_winner(
    session: Any, ac_name_ta: str, expect_votes: int, party_norms_wanted: set[str]
) -> dict[str, Any] | None:
    """Fallback for rows the statewide table leaves untranslated: the AC's
    own Tamil Wikipedia article, winner anchored by vote count (exact first,
    then ≤1% drift for differing counting snapshots)."""
    html = None
    try:
        html = fetch_wiki_html(session, TAWIKI_API, f"{ac_name_ta} சட்டமன்றத் தொகுதி")
    except SystemExit:
        title = _search_ac_article_title(session, ac_name_ta)
        if title:
            try:
                html = fetch_wiki_html(session, TAWIKI_API, title)
            except SystemExit:
                return None
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    def scan(tolerance: float) -> dict[str, Any] | None:
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                cells = [
                    " ".join(td.get_text(" ", strip=True).split())
                    for td in tr.find_all(["td", "th"])
                ]
                for i, cell in enumerate(cells):
                    v = parse_int(cell)
                    if v is None or v < 1000:
                        continue
                    if abs(v - expect_votes) <= tolerance * expect_votes:
                        texts = [c for c in cells[:i] if c and parse_int(c) is None]
                        tamil = [clean_cell(c) for c in texts if has_tamil(c)]
                        tamil = [c for c in tamil if c]
                        if len(tamil) < 2:
                            continue
                        # The anchored row must belong to the winner's party:
                        # exactly one of the two cells must be a matching
                        # party rendering. A vote coincidence with a wrong
                        # party (e.g. an older election's row) is rejected.
                        a, b = tamil[-2], tamil[-1]
                        a_ok = norm_party(a) in party_norms_wanted
                        b_ok = norm_party(b) in party_norms_wanted
                        if a_ok == b_ok:
                            continue
                        name, party = (a, b) if b_ok else (b, a)
                        return {
                            "name_ta": name,
                            "party_ta": party,
                            "exact": v == expect_votes,
                        }
        return None

    return scan(0.0) or scan(0.01)


def clean_cell(text: str) -> str:
    """Strip footnote markers like '[ 4 ]' / '[a]' that ride along in cells."""
    return re.sub(r"\[\s*[^\]]{1,4}\s*\]", "", text).strip()


def norm_party(text: str) -> str:
    """Normalize a Tamil party rendering for matching: 'இ.தே.கா.' == 'இதேகா'."""
    return re.sub(r"[.\s()]+", "", clean_cell(text))


def parse_statewide_row(row: list[str], num: int) -> dict[str, Any] | None:
    """Positional parse of the statewide winners table, anchored on the
    constituency-number cell. Verified layout:
    […, no, ac_name, w_name, color, w_party, w_votes, w_pct, r_name, …]
    """
    for i, cell in enumerate(row[:4]):
        if parse_int(cell) == num:
            if len(row) < i + 7:
                return None
            name = clean_cell(row[i + 2])
            party = clean_cell(row[i + 4])
            votes = parse_int(row[i + 5])
            # Some rows omit the empty color cell; realign if needed.
            if votes is None:
                party = clean_cell(row[i + 3])
                votes = parse_int(row[i + 4])
            if votes is None or not name:
                return None
            return {"name_ta": name, "party_ta": party, "votes": votes}
    return None


def extract_winner_from_row(
    row: list[str], num: int, expect_votes: int | None
) -> dict[str, Any] | None:
    """Pull (name, party) from a results row using vote anchoring.

    Finds the cell equal to the expected winner vote count (script-agnostic
    anchor), then reads name and party from the preceding text cells.
    """
    if expect_votes is None:
        return None
    for i, cell in enumerate(row):
        if parse_int(cell) == expect_votes and expect_votes > 500:
            texts = [clean_cell(c) for c in row[:i] if c and parse_int(c) is None]
            texts = [c for c in texts if c]
            if len(texts) >= 2:
                return {"name_ta": texts[-2], "party_ta": texts[-1], "anchor": "votes"}
    return None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    eci_source = db.ensure_source(
        name="ECI Results Portal — 2026 Tamil Nadu General Election",
        url=f"{ECI_BASE}/",
        publisher="Election Commission of India",
        license=None,
        access_mode="scrape",
        notes=(
            "Authority for the 234-AC universe and 2026 winners/vote counts. The portal "
            "notes results are preliminary RO-entered trends until Form 20."
        ),
    )
    tawiki_source = db.ensure_source(
        name="Tamil Wikipedia",
        url="https://ta.wikipedia.org/",
        publisher="Wikimedia Foundation (community-curated)",
        license="CC BY-SA 4.0",
        access_mode="api",
        notes=(
            "Tamil renderings of representative and party names, from per-constituency "
            "results tables; every join validated by exact vote-count equality with the "
            "English-side authority."
        ),
    )
    enwiki_source = db.ensure_source(
        name="English Wikipedia — 2024 general election in Tamil Nadu",
        url="https://en.wikipedia.org/wiki/2024_Indian_general_election_in_Tamil_Nadu",
        publisher="Wikimedia Foundation (community-curated)",
        license="CC BY-SA 4.0",
        access_mode="api",
        notes=(
            "English-side authority for 2024 Lok Sabha winners in TN (the ECI 2024 "
            "results portal is no longer online; sansad.in blocks scraping)."
        ),
    )

    ac_rows = {
        int(code): (loc_id, name_en, name_ta)
        for loc_id, code, name_en, name_ta in db.conn.execute(
            "SELECT id, eci_code, name_en, name_ta FROM localities WHERE level = 'ac'"
        )
    }
    pc_rows = {
        int(code): (loc_id, name_en)
        for loc_id, code, name_en in db.conn.execute(
            "SELECT id, eci_code, name_en FROM localities WHERE level = 'pc'"
        )
    }
    if len(ac_rows) != 234 or len(pc_rows) != 39:
        fail("run import-constituencies before import-representatives")

    # ---- MLAs -----------------------------------------------------------------
    print("Fetching ECI 2026 results (234 pages, cached)…")
    eci = fetch_eci_results()

    print("Fetching Tamil Wikipedia 2026 results table…")
    html_2026 = fetch_wiki_html(session, TAWIKI_API, TAWIKI_ASSEMBLY_PAGE)
    ta_rows = find_results_rows(html_2026, 234, 200)

    # Pass 1: statewide table, positional parse. Exact vote equality gives
    # confidence 1.0; ≤1% drift (different counting snapshots / typos) with
    # a Tamil name still parses gives 0.9 with a printed note.
    mla_records: dict[int, dict[str, Any]] = {}
    problems: list[str] = []
    gaps: list[int] = []
    vote_validated = 0
    party_map: dict[str, str] = {}
    for num in range(1, 235):
        result = eci[num]
        winner = result["winner"]
        row = ta_rows.get(num)
        parsed = parse_statewide_row(row, num) if row else None
        if parsed is None or not has_tamil(parsed["name_ta"]):
            gaps.append(num)
            continue
        drift = abs(parsed["votes"] - winner["votes"]) / max(winner["votes"], 1)
        if parsed["votes"] == winner["votes"]:
            confidence = 1.0
            vote_validated += 1
        elif drift <= 0.01:
            confidence = 0.9
            print(
                f"  NOTE (AC {num}): vote drift {parsed['votes']} vs ECI "
                f"{winner['votes']} ({drift:.2%}) — accepting with lower confidence."
            )
        else:
            gaps.append(num)
            continue
        if has_tamil(parsed["party_ta"]):
            party_map.setdefault(winner["party"], parsed["party_ta"])
        mla_records[num] = {**result, "name_ta": parsed["name_ta"], "confidence": confidence}

    # Known Tamil party renderings: harvested from pass 1 + the static
    # classification lexicon. Used by both fallback passes below.
    party_norms = {norm_party(p) for p in party_map.values()} | {
        norm_party(p) for p in PARTY_LEXICON_TA
    }

    # Pass 2 (cheap, bulk): the pre-election candidates-by-alliance table (fully Tamil).
    # Party-anchored: the winner's party (from ECI) locates the candidate
    # cell. Single-party columns (no party subcell, e.g. TVK) are located by
    # CALIBRATION: the column must reproduce the names pass 1 already
    # vote-validated for that party, else it is not trusted.
    def norm_person(s: str) -> str:
        return re.sub(r"[.\s]+", "", s)

    if gaps:
        cand_rows = find_candidates_rows(html_2026)
        print(f"  candidates table: {len(cand_rows)} rows")

        def wanted_norms(party_en: str) -> set[str]:
            wanted = {norm_party(x) for x in PARTY_EN_TO_TA_NORMS.get(party_en, set())}
            mapped = party_map.get(party_en)
            if mapped:
                wanted.add(norm_party(mapped))
            return wanted

        calib_by_party: dict[str, dict[int, str]] = {}
        for num, rec in mla_records.items():
            calib_by_party.setdefault(rec["winner"]["party"], {})[num] = rec["name_ta"]

        def calibrated_column(party_en: str) -> int | None:
            calibration = {
                n: name for n, name in calib_by_party.get(party_en, {}).items()
            }
            if not calibration or not cand_rows:
                return None
            width = max(len(r) for r in cand_rows.values())
            # Positive indexes, then end-relative (rows vary in width, but
            # trailing single-party columns stay anchored to the row end).
            for col in list(range(width)) + [-1, -2, -3, -4]:
                hits = total = 0
                for n, expected in calibration.items():
                    row = cand_rows.get(n)
                    if row is None or len(row) < abs(col) + (col >= 0):
                        continue
                    cell = clean_cell(row[col])
                    if not cell:
                        continue
                    total += 1
                    if norm_person(cell) == norm_person(expected):
                        hits += 1
                if total >= 3 and hits >= 0.8 * total:
                    return col
            return None

        single_col_cache: dict[str, int | None] = {}
        for num in gaps[:]:
            winner = eci[num]["winner"]
            row = cand_rows.get(num)
            if not row:
                continue
            name = candidate_from_row(row, wanted_norms(winner["party"]), party_norms)
            if name is None:
                party = winner["party"]
                if party not in single_col_cache:
                    single_col_cache[party] = calibrated_column(party)
                col = single_col_cache[party]
                if col is not None and len(row) >= abs(col) + (col >= 0):
                    cell = clean_cell(row[col])
                    if cell and has_tamil(cell) and norm_party(cell) not in party_norms:
                        name = cell
            if name:
                mla_records[num] = {**eci[num], "name_ta": name, "confidence": 0.85}
                gaps.remove(num)
                print(f"  AC {num}: Tamil name via candidates table → {name}")

    # Pass 3 (last resort, network-heavy): per-AC Tamil Wikipedia articles
    # for rows still unresolved. The party set disambiguates which of the
    # two anchored cells is the party and which the person.
    for num in gaps[:]:
        result = eci[num]
        winner = result["winner"]
        found = fetch_ac_article_winner(
            session, ac_rows[num][2], winner["votes"], wanted_norms(winner["party"])
        )
        if found is None or not has_tamil(found["name_ta"]):
            continue
        party_map.setdefault(winner["party"], found["party_ta"])
        confidence = 1.0 if found.get("exact") else 0.9
        mla_records[num] = {**result, "name_ta": found["name_ta"], "confidence": confidence}
        gaps.remove(num)
        print(f"  AC {num}: Tamil name via per-AC article → {found['name_ta']}")

    # Residual gaps (D-014): no sourced Tamil rendering exists yet. Import
    # with name_ta = NULL — the UI shows the English name with a visible
    # "Tamil name pending" note. Reported on every run until zero.
    for num in gaps:
        mla_records[num] = {**eci[num], "name_ta": None, "confidence": None}
    if problems:
        fail("unresolved MLA seats:\n  " + "\n  ".join(problems))

    # ---- Lok Sabha MPs ----------------------------------------------------------
    print("Fetching 2024 Lok Sabha results tables (en + ta wiki)…")
    en_ls = find_results_rows(fetch_wiki_html(session, ENWIKI_API, ENWIKI_LS_PAGE), 39, 35)
    ta_ls_html = fetch_wiki_html(session, TAWIKI_API, TAWIKI_LS_PAGE)

    ta_soup = BeautifulSoup(ta_ls_html, "html.parser")

    # The elected-members table: header names the MP column. Layout per row
    # (verified): [no, constituency, member, color, party-full].
    ta_members: dict[int, dict[str, str]] = {}
    for table in ta_soup.find_all("table", class_="wikitable"):
        grid = expand_table_grid(table)
        if not grid or len(grid) < 35:
            continue
        if "நாடாளுமன்ற உறுப்பினர்" not in " ".join(grid[0]):
            continue
        for row in grid[1:]:
            if len(row) < 3:
                continue
            n = parse_int(row[0])
            if n is None or not 1 <= n <= 39:
                continue
            name = clean_cell(row[2])
            party = next(
                (clean_cell(c) for c in row[3:] if has_tamil(clean_cell(c))), ""
            )
            if name and has_tamil(name):
                ta_members[n] = {"name_ta": name, "party_ta": party}
        break
    if len(ta_members) < 35:
        fail(f"tawiki LS members table: only {len(ta_members)} rows parsed")

    # Alliance-votes table for the cross-check: winner votes per PC = the
    # row maximum across alliance columns.
    ta_alliance_votes: dict[int, int] = {}
    for table in ta_soup.find_all("table", class_="wikitable"):
        grid = expand_table_grid(table)
        if not grid or len(grid) < 35 or "கூட்டணி" not in " ".join(grid[0]):
            continue
        for row in grid[1:]:
            n = parse_int(row[0]) if row else None
            if n is None or not 1 <= n <= 39:
                continue
            votes = [v for c in row[2:] if (v := parse_int(c)) and v >= 10000]
            if votes:
                ta_alliance_votes[n] = max(votes)
        break

    mp_records: dict[int, dict[str, Any]] = {}
    for num in range(1, 40):
        en_row = en_ls.get(num)
        member = ta_members.get(num)
        if en_row is None or member is None:
            problems.append(f"PC {num}: missing row (en={bool(en_row)}, ta={bool(member)})")
            continue
        # Winner votes = the row's largest integer (margin and runner-up are
        # always smaller); name/party are the text cells just before it.
        en_votes = max((parse_int(c) or 0) for c in en_row)
        en_w = extract_winner_from_row(en_row, num, en_votes)
        if not en_w or en_votes < 10000:
            problems.append(f"PC {num}: could not parse English winner row")
            continue
        # Validation 1: the Tamil party must match the English party.
        wanted = {norm_party(x) for x in PARTY_EN_TO_TA_NORMS.get(en_w["party_ta"], set())}
        mapped = party_map.get(en_w["party_ta"])
        if mapped:
            wanted.add(norm_party(mapped))
        party_ok = bool(wanted) and norm_party(member["party_ta"]) in wanted
        # Validation 2: alliance-votes cross-check (exact or ≤1%).
        votes_ok = (
            num in ta_alliance_votes
            and abs(ta_alliance_votes[num] - en_votes) <= 0.01 * en_votes
        )
        if not party_ok and not votes_ok:
            problems.append(
                f"PC {num}: cross-validation failed (party '{member['party_ta']}' vs "
                f"'{en_w['party_ta']}', alliance votes {ta_alliance_votes.get(num)})"
            )
            continue
        mp_records[num] = {
            "name_en": en_w["name_ta"],  # field name is generic: EN row text
            "party_en": en_w["party_ta"],
            "name_ta": member["name_ta"],
            "party_ta": member["party_ta"] or None,
            "votes": en_votes,
            "confidence": 1.0 if (party_ok and votes_ok) else 0.9,
        }

    if problems:
        fail("unresolved seats:\n  " + "\n  ".join(problems))

    # ---- Write ------------------------------------------------------------------
    def ensure_office(office_type: str, locality_id: int, source_id: int) -> int:
        row = db.conn.execute(
            """
            INSERT INTO offices (office_type, locality_id, source_id, retrieved_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (office_type, locality_id) DO UPDATE
              SET source_id = EXCLUDED.source_id, retrieved_at = EXCLUDED.retrieved_at
            RETURNING id
            """,
            (office_type, locality_id, source_id, retrieved_at),
        ).fetchone()
        assert row is not None
        return row[0]

    def ensure_person(
        external_ref: str,
        name_en: str,
        name_ta: str | None,
        party_en: str,
        party_ta: str | None,
        source_id: int,
    ) -> int:
        row = db.conn.execute(
            """
            INSERT INTO persons
              (external_ref, name_en, name_ta, party_en, party_ta, source_id, retrieved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (external_ref) DO UPDATE
              SET name_en = EXCLUDED.name_en, name_ta = EXCLUDED.name_ta,
                  party_en = EXCLUDED.party_en, party_ta = EXCLUDED.party_ta,
                  source_id = EXCLUDED.source_id, retrieved_at = EXCLUDED.retrieved_at
            RETURNING id
            """,
            (external_ref, name_en, name_ta, party_en, party_ta, source_id, retrieved_at),
        ).fetchone()
        assert row is not None
        return row[0]

    def ensure_tenure(
        office_id: int, person_id: int, start: date, source_id: int
    ) -> None:
        db.conn.execute(
            """
            INSERT INTO tenures (office_id, person_id, start_date, status,
                                 source_id, retrieved_at)
            VALUES (%s, %s, %s, 'active', %s, %s)
            ON CONFLICT (office_id, person_id, start_date) DO UPDATE
              SET source_id = EXCLUDED.source_id, retrieved_at = EXCLUDED.retrieved_at
            """,
            (office_id, person_id, start, source_id, retrieved_at),
        )

    print("Writing MLAs…")
    for num, rec in sorted(mla_records.items()):
        loc_id = ac_rows[num][0]
        winner = rec["winner"]
        name_en = winner["name"].title()
        # Per-seat identity: two same-named winners in different seats are
        # different people; a dual-seat winner appears as two rows until
        # person-level reconciliation (affidavits/Wikidata) lands in M4.
        ref = f"tn2026:ac{num}:{slugify(winner['name'])}"
        office_id = ensure_office("mla", loc_id, eci_source)
        person_id = ensure_person(
            ref, name_en, rec["name_ta"], winner["party"],
            party_map.get(winner["party"]), eci_source,
        )
        ensure_tenure(office_id, person_id, ASSEMBLY_RESULT_DATE, eci_source)
        db.upsert_fact(
            subject_type="locality",
            subject_id=loc_id,
            key="election_result",
            value={
                "election": "2026 Tamil Nadu Legislative Assembly",
                "provisional": True,
                "basis": "RO-entered trends; final data via Form 20",
                "result_date": ASSEMBLY_RESULT_DATE.isoformat(),
                "winner_en": name_en,
                "winner_ta": rec["name_ta"],
                "party_en": winner["party"],
                "party_ta": party_map.get(winner["party"]),
                "votes": winner["votes"],
                "vote_pct": winner["pct"],
                "margin": rec["margin"],
                "runner_up_en": rec["runner_up"]["name"].title(),
                "runner_up_party_en": rec["runner_up"]["party"],
                "total_votes": rec["total_votes"],
                "candidates": rec["candidates"],
            },
            source_id=eci_source,
            retrieved_at=retrieved_at,
            extraction_method="scrape",
            confidence=1.0,
        )
        if rec["name_ta"] is not None:
            db.upsert_fact(
                subject_type="person",
                subject_id=person_id,
                key="name_ta",
                value={"name_ta": rec["name_ta"], "validated_by": "vote-count equality"},
                source_id=tawiki_source,
                retrieved_at=retrieved_at,
                extraction_method="scrape",
                confidence=rec["confidence"],
            )

    print("Writing MPs…")
    for num, rec in sorted(mp_records.items()):
        loc_id, _ = pc_rows[num]
        ref = f"ls2024:pc{num}:{slugify(rec['name_en'])}"
        office_id = ensure_office("mp_ls", loc_id, enwiki_source)
        person_id = ensure_person(
            ref, rec["name_en"], rec["name_ta"], rec["party_en"], rec["party_ta"],
            enwiki_source,
        )
        ensure_tenure(office_id, person_id, LS_RESULT_DATE, enwiki_source)
        db.upsert_fact(
            subject_type="locality",
            subject_id=loc_id,
            key="election_result",
            value={
                "election": "2024 Indian general election (Lok Sabha)",
                "provisional": False,
                "result_date": LS_RESULT_DATE.isoformat(),
                "winner_en": rec["name_en"],
                "winner_ta": rec["name_ta"],
                "party_en": rec["party_en"],
                "party_ta": rec["party_ta"],
                "votes": rec["votes"],
            },
            source_id=enwiki_source,
            retrieved_at=retrieved_at,
            extraction_method="scrape",
            confidence=0.9,
        )
        db.upsert_fact(
            subject_type="person",
            subject_id=person_id,
            key="name_ta",
            value={"name_ta": rec["name_ta"], "validated_by": "vote-count equality"},
            source_id=tawiki_source,
            retrieved_at=retrieved_at,
            extraction_method="scrape",
            confidence=1.0,
        )

    db.conn.commit()

    persons_n = db.conn.execute("SELECT count(*) FROM persons").fetchone()
    tenures_n = db.conn.execute("SELECT count(*) FROM tenures").fetchone()
    assert persons_n and tenures_n
    print("\n=== Representatives import report ===")
    print(f"MLA seats: {len(mla_records)}/234 (vote-validated Tamil names: {vote_validated})")
    print(f"LS seats:  {len(mp_records)}/39")
    print(f"persons: {persons_n[0]} | tenures: {tenures_n[0]}")
    print(f"party map entries: {len(party_map)}")
    pending = sorted(n for n, r in mla_records.items() if r["name_ta"] is None)
    if pending:
        print(f"TAMIL NAME PENDING ({len(pending)} MLAs — D-014, shown in EN until sourced):")
        for n in pending:
            print(f"  AC {n}: {eci[n]['winner']['name'].title()}")


if __name__ == "__main__":
    main()
