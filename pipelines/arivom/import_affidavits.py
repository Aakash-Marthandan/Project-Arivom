"""Import self-declared affidavit profiles for winning MLAs and TN's MPs.

Source: MyNeta (ADR), which mirrors ECI's public-domain affidavit filings
(DESIGN.md §4.4, reliability high). Two elections are covered:
- TamilNadu2026: the 234 winning MLAs (ADR coverage: whatever it has
  analyzed; the gap is reported on every run).
- LokSabha2024: TN's 39 sitting MPs, filtered from the all-India winners
  list by constituency and validated by name similarity against the seated
  member.

Per candidate, the LISTING row provides the summary and the DETAIL page
provides age, self-declared profession, and an independently rendered copy
of the same figures. Every matched candidate is reconciled listing-vs-
detail (a full-population audit, stronger than the original 20-sample
spot-check): when the two surfaces disagree, the detail page (the
enumerated, fuller record) wins, the listing value is preserved inside the
fact, confidence drops to 0.9, and the discrepancy is printed.

Everything is stored per DESIGN.md's hard rule: SELF-DECLARED filings,
never verified ground truth, and framed as such in the UI.
"""

from __future__ import annotations

import re
import subprocess
import time
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .common import Db, fail, http_session, norm_name, now_utc

MYNETA_TN = "https://www.myneta.info/TamilNadu2026"
MYNETA_LS = "https://www.myneta.info/LokSabha2024"
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

EXPECTED_MLAS = 234
EXPECTED_MPS = 39
MIN_ANALYZED_MLAS = 180

# MyNeta constituency spelling → ours (normalized), for names whose
# spellings differ beyond fuzzy range. Classification aid only.
CONSTITUENCY_ALIASES = {
    "anaikattu": "anaicut",     # MyNeta uses the ECI spelling variant
    "sankari": "sangagiri",     # ours follows the Wikidata rendering
}


def fetch_cached(session: Any, url: str, key: str, ttl: int = 86400) -> str:
    cache = CACHE_DIR / "myneta"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{key}.html"
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        return path.read_text(errors="replace")
    # MyNeta intermittently serves table-less shells to Python HTTP clients
    # while serving curl consistently (TLS-fingerprint discrimination, same
    # as the ECI portal, see D-006). Fetch via curl.
    del session
    result = subprocess.run(
        ["curl", "-sS", "--fail", "-m", "60", "-A", "Mozilla/5.0", url],
        capture_output=True,
        text=True,
        check=True,
    )
    path.write_text(result.stdout)
    time.sleep(0.5)  # be polite to ADR's servers
    return result.stdout


def parse_rupees(text: str) -> tuple[int, str] | None:
    """'Rs 2,12,75,925 ~ 2 Crore+' → (21275925, '~2 Crore+')."""
    text = text.replace("\xa0", " ").strip()
    m = re.search(r"Rs\s*([\d,]+)", text)
    if not m:
        return None
    amount = int(m.group(1).replace(",", ""))
    approx = re.search(r"~\s*(.+)$", text)
    return amount, (approx.group(1).strip() if approx else "")


def parse_winner_rows(html: str) -> dict[int, dict[str, Any]]:
    """candidate_id → row fields from a winners-analyzed listing page."""
    soup = BeautifulSoup(html, "html.parser")
    out: dict[int, dict[str, Any]] = {}
    for tr in soup.find_all("tr"):
        link = tr.find("a", href=re.compile(r"candidate_id=\d+"))
        if link is None:
            continue
        cells = [
            " ".join(td.get_text(" ", strip=True).replace("\xa0", " ").split())
            for td in tr.find_all("td")
        ]
        if len(cells) < 8:
            continue
        cid = int(re.search(r"candidate_id=(\d+)", link["href"]).group(1))
        cases = cells[4].strip()
        out[cid] = {
            "candidate_id": cid,
            "name": cells[1],
            "constituency": cells[2],
            "party": cells[3],
            "criminal_cases": int(cases) if cases.isdigit() else 0,
            "education": cells[5],
            "assets": parse_rupees(cells[6]),
            "liabilities": parse_rupees(cells[7]),
        }
    return out


def fetch_winner_listing(
    session: Any, base_url: str, cache_prefix: str, min_rows: int
) -> dict[int, dict[str, Any]]:
    def page_url(page: int) -> str:
        return (
            f"{base_url}/index.php?action=summary&subAction=winner_analyzed"
            f"&sort=candidate&page={page}"
        )

    first_html = fetch_cached(session, page_url(1), f"{cache_prefix}-p1")
    m = re.search(
        r"Showing page\s+\d+\s+of\s+(\d+)\s+pages", re.sub(r"<[^>]+>", " ", first_html)
    )
    if not m:
        fail(f"MyNeta winners ({cache_prefix}): could not read pagination count")
    total_pages = int(m.group(1))

    winners: dict[int, dict[str, Any]] = {}
    for page in range(1, total_pages + 1):
        # The server intermittently returns a table-less shell; retry a thin
        # page up to three times with a pause before accepting it.
        rows: dict[int, dict[str, Any]] = {}
        for attempt in range(3):
            rows = parse_winner_rows(
                fetch_cached(session, page_url(page), f"{cache_prefix}-p{page}")
            )
            if len(rows) >= 12 or page == total_pages:
                break
            (CACHE_DIR / "myneta" / f"{cache_prefix}-p{page}.html").unlink(missing_ok=True)
            time.sleep(2 + attempt * 3)
        winners.update(rows)
    if len(winners) < min_rows:
        fail(
            f"MyNeta winners ({cache_prefix}): only {len(winners)} parsed across "
            f"{total_pages} pages (floor {min_rows}); page structure changed?"
        )
    return winners


def parse_detail_page(html: str) -> dict[str, Any]:
    """Age, profession, and the affidavit figures from a candidate detail
    page (the enumerated, fuller record; primary when surfaces disagree)."""
    text = re.sub(r"<[^>]+>", "|", html).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    out: dict[str, Any] = {}
    m = re.search(r"Number of Criminal Cases:\s*\|?\s*(\d+)", text)
    if m:
        out["criminal_cases"] = int(m.group(1))
    m = re.search(r"Assets:[\s|]*Rs\s*([\d,]+)", text)
    if m:
        out["assets"] = int(m.group(1).replace(",", ""))
    m = re.search(r"Liabilities:[\s|]*Rs\s*([\d,]+)", text)
    if m:
        out["liabilities"] = int(m.group(1).replace(",", ""))
    m = re.search(r"Age:\s*\|?\s*(\d{2,3})", text)
    if m:
        out["age"] = int(m.group(1))
    m = re.search(r"Self Profession:\s*\|?\s*([^|]{2,80})", text)
    if m:
        out["profession"] = m.group(1).strip()
    return out


def name_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_name(a), norm_name(b)).ratio()


def match_rows_to_seats(
    winners: dict[int, dict[str, Any]],
    person_by_seat: dict[str, list[tuple[int, str]]],
    label: str,
    require_sim: float = 0.45,
) -> tuple[dict[int, tuple[int, str, dict[str, Any]]], list[str]]:
    """Match listing rows to seated members by constituency name plus
    winner-name similarity (validates every attachment and disambiguates
    same-named seats). Non-matching constituencies are dropped silently,
    which filters the all-India Lok Sabha listing down to TN."""
    matched: dict[int, tuple[int, str, dict[str, Any]]] = {}
    skipped: list[str] = []
    for cid, row in winners.items():
        bare = re.sub(r"\s*\((SC|ST)\)\s*$", "", row["constituency"])
        key = norm_name(bare)
        key = CONSTITUENCY_ALIASES.get(key, key)
        candidates = (
            [key]
            if key in person_by_seat
            else get_close_matches(key, list(person_by_seat), n=3, cutoff=0.85)
        )
        if not candidates:
            continue
        scored = sorted(
            (
                (name_sim(row["name"], pname), k, pid, pname)
                for k in candidates
                for pid, pname in person_by_seat[k]
            ),
            reverse=True,
        )
        best_sim, best_key, best_pid, best_winner = scored[0]
        if best_sim < require_sim:
            skipped.append(
                f"{label} cid {cid} '{row['name']}' ({row['constituency']}): best seat "
                f"'{best_key}' holds '{best_winner}' (sim {best_sim:.2f}); skipped"
            )
            continue
        if row["assets"] is None:
            skipped.append(f"{label} cid {cid} ({row['name']}): unparseable assets; skipped")
            continue
        matched[cid] = (best_pid, best_key, row)
    return matched, skipped


def write_candidate_facts(
    db: Db,
    session: Any,
    base_url: str,
    cid: int,
    person_id: int,
    row: dict[str, Any],
    source_id: int,
    retrieved_at: Any,
    audits: list[str],
) -> None:
    detail = parse_detail_page(
        fetch_cached(session, f"{base_url}/candidate.php?candidate_id={cid}", f"cand-{cid}")
    )

    def reconciled(field: str, listing_value: int) -> tuple[int, float, dict[str, Any]]:
        det = detail.get(field)
        if det is None or det == listing_value:
            return listing_value, 1.0, {}
        audits.append(
            f"cid {cid} {row['name']}: {field} listing {listing_value} vs detail {det}; "
            "detail (enumerated record) kept"
        )
        return det, 0.9, {"listing_value": listing_value}

    common = dict(
        subject_type="person",
        subject_id=person_id,
        source_id=source_id,
        retrieved_at=retrieved_at,
        extraction_method="parser",
    )

    assets_amount, assets_approx = row["assets"]
    value, confidence, extra = reconciled("assets", assets_amount)
    db.upsert_fact(
        key="declared_assets",
        value={
            "self_declared": True,
            "amount_inr": value,
            "approx": assets_approx,
            "myneta_candidate_id": cid,
            **extra,
        },
        confidence=confidence,
        **common,
    )

    liab = row["liabilities"] or (0, "")
    value, confidence, extra = reconciled("liabilities", liab[0])
    db.upsert_fact(
        key="declared_liabilities",
        value={"self_declared": True, "amount_inr": value, "approx": liab[1], **extra},
        confidence=confidence,
        **common,
    )

    value, confidence, extra = reconciled("criminal_cases", row["criminal_cases"])
    db.upsert_fact(
        key="criminal_cases",
        value={"self_declared": True, "count": value, **extra},
        confidence=confidence,
        **common,
    )

    db.upsert_fact(
        key="education",
        value={"self_declared": True, "category": row["education"]},
        confidence=1.0,
        **common,
    )

    if detail.get("age"):
        db.upsert_fact(
            key="age",
            value={"self_declared": True, "years_at_nomination": detail["age"]},
            confidence=1.0,
            **common,
        )
    if detail.get("profession"):
        db.upsert_fact(
            key="profession",
            value={"self_declared": True, "profession": detail["profession"]},
            confidence=1.0,
            **common,
        )


def seated_members(db: Db, office_type: str) -> dict[str, list[tuple[int, str]]]:
    rows = db.conn.execute(
        """
        SELECT l.name_en, p.id, p.name_en
        FROM localities l
        JOIN offices o ON o.locality_id = l.id AND o.office_type = %s
        JOIN tenures t ON t.office_id = o.id AND t.end_date IS NULL AND t.status = 'active'
        JOIN persons p ON p.id = t.person_id
        """,
        (office_type,),
    ).fetchall()
    out: dict[str, list[tuple[int, str]]] = {}
    for seat, pid, pname in rows:
        out.setdefault(norm_name(seat), []).append((pid, pname))
    return out


def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    tn_source = db.ensure_source(
        name="MyNeta (ADR) — Tamil Nadu 2026 affidavit analysis",
        url=f"{MYNETA_TN}/",
        publisher="Association for Democratic Reforms",
        license=None,
        access_mode="scrape",
        notes=(
            "Structured analysis of candidates' self-declared ECI election affidavits "
            "(assets, liabilities, criminal cases, education, age, profession). MyNeta "
            "mirrors ECI public-domain filings and defers to ECI on discrepancies. "
            "Every value is a SELF-DECLARED filing and is always labelled as such."
        ),
    )
    ls_source = db.ensure_source(
        name="MyNeta (ADR) — Lok Sabha 2024 affidavit analysis",
        url=f"{MYNETA_LS}/",
        publisher="Association for Democratic Reforms",
        license=None,
        access_mode="scrape",
        notes=(
            "Self-declared affidavit analysis for the 2024 Lok Sabha winners; TN's 39 "
            "MPs filtered by constituency and validated by winner-name similarity."
        ),
    )

    audits: list[str] = []

    # ---- MLAs (TamilNadu2026) -------------------------------------------------
    mla_seats = seated_members(db, "mla")
    # Vacant seats have no active tenure, but the affidavit still belongs to
    # the person who won there: include the most recent (resigned) holder.
    vacant_rows = db.conn.execute(
        """
        SELECT l.name_en, p.id, p.name_en
        FROM localities l
        JOIN offices o ON o.locality_id = l.id AND o.office_type = 'mla'
        JOIN tenures t ON t.office_id = o.id AND t.status = 'resigned'
        JOIN persons p ON p.id = t.person_id
        WHERE NOT EXISTS (
          SELECT 1 FROM tenures t2 WHERE t2.office_id = o.id
            AND t2.end_date IS NULL AND t2.status = 'active'
        )
        """
    ).fetchall()
    for seat, pid, pname in vacant_rows:
        mla_seats.setdefault(norm_name(seat), []).append((pid, pname))

    print("Fetching MyNeta TN2026 winners listing…")
    tn_winners = fetch_winner_listing(session, MYNETA_TN, "winners", MIN_ANALYZED_MLAS)
    tn_matched, tn_skipped = match_rows_to_seats(tn_winners, mla_seats, "TN2026")
    for line in tn_skipped:
        print(f"  SKIP: {line}")

    by_person: dict[int, list[int]] = {}
    for cid, (pid, _k, _r) in tn_matched.items():
        by_person.setdefault(pid, []).append(cid)
    dupes = {pid: cids for pid, cids in by_person.items() if len(cids) > 1}
    if dupes:
        fail(f"TN2026 rows collided on one person: {dupes}")

    print(f"Enriching {len(tn_matched)} MLA profiles from detail pages…")
    for i, (cid, (person_id, _seat, row)) in enumerate(sorted(tn_matched.items()), 1):
        write_candidate_facts(
            db, session, MYNETA_TN, cid, person_id, row, tn_source, retrieved_at, audits
        )
        if i % 50 == 0:
            print(f"  {i}/{len(tn_matched)}")

    # ---- MPs (LokSabha2024, all-India listing filtered to TN) -----------------
    mp_seats = seated_members(db, "mp_ls")
    print("Fetching MyNeta LokSabha2024 winners listing…")
    ls_winners = fetch_winner_listing(session, MYNETA_LS, "ls-winners", 400)
    ls_matched, ls_skipped = match_rows_to_seats(ls_winners, mp_seats, "LS2024")
    for line in ls_skipped:
        print(f"  SKIP: {line}")

    print(f"Enriching {len(ls_matched)} MP profiles from detail pages…")
    for cid, (person_id, _seat, row) in sorted(ls_matched.items()):
        write_candidate_facts(
            db, session, MYNETA_LS, cid, person_id, row, ls_source, retrieved_at, audits
        )

    db.conn.commit()

    covered_mla_pids = {m[0] for m in tn_matched.values()}
    pending_mla = sorted(
        seat
        for seat, entries in mla_seats.items()
        if any(pid not in covered_mla_pids for pid, _ in entries)
    )
    covered_mp_pids = {m[0] for m in ls_matched.values()}
    pending_mp = sorted(
        seat
        for seat, entries in mp_seats.items()
        if any(pid not in covered_mp_pids for pid, _ in entries)
    )

    print("\n=== Affidavit import report ===")
    print(f"MLA profiles: {len(tn_matched)}/{EXPECTED_MLAS}")
    print(f"MP profiles:  {len(ls_matched)}/{EXPECTED_MPS}")
    if audits:
        print(f"LISTING/DETAIL DISCREPANCIES ({len(audits)}; detail kept, both stored):")
        for line in audits:
            print(f"  {line}")
    if pending_mla:
        print(f"MLA affidavits pending on MyNeta ({len(pending_mla)}): {', '.join(pending_mla)}")
    if pending_mp:
        print(f"MP affidavits pending on MyNeta ({len(pending_mp)}): {', '.join(pending_mp)}")


if __name__ == "__main__":
    main()
