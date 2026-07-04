"""Import self-declared affidavit summaries for the 234 winning MLAs.

Source: MyNeta (ADR), which mirrors ECI's public-domain affidavit filings
(DESIGN.md §4.4, reliability high). The winners-analyzed listing provides
assets, liabilities, criminal-case counts, and education per winner; pages
are fully structured, so extraction is a deterministic parser — no LLM
needed (D-015). Every fact is stored per DESIGN.md's hard rule: framed as a
SELF-DECLARED filing, never as verified ground truth.

Validation, per the M4 exit criteria:
- the 234 rows must map 1:1 onto our ACs (name-normalized, fuzzy-audited);
- a ≥20-candidate sample is cross-checked against MyNeta's per-candidate
  detail pages (a second, independently rendered surface) — any mismatch
  fails the run.
"""

from __future__ import annotations

import random
import re
import time
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .common import Db, fail, http_session, norm_name, now_utc

MYNETA_BASE = "https://www.myneta.info/TamilNadu2026"
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

EXPECTED_WINNERS = 234

# MyNeta constituency spelling → ours (normalized), for the two names whose
# spellings differ beyond fuzzy range. Classification aid only.
CONSTITUENCY_ALIASES = {
    "anaikattu": "anaicut",     # MyNeta uses the ECI spelling variant
    "sankari": "sangagiri",     # ours follows the Wikidata rendering
}
# ADR analyzes affidavits progressively after a result; require a sane floor
# and report the outstanding ACs on every run rather than failing.
MIN_ANALYZED = 180
SPOT_CHECK_SAMPLE = 20


def fetch_cached(session: Any, url: str, key: str, ttl: int = 86400) -> str:
    cache = CACHE_DIR / "myneta"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{key}.html"
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        return path.read_text(errors="replace")
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    path.write_text(resp.text)
    time.sleep(0.5)  # be polite to ADR's servers
    return resp.text


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
        assets = parse_rupees(cells[6])
        liabilities = parse_rupees(cells[7])
        out[cid] = {
            "candidate_id": cid,
            "name": cells[1],
            "constituency": cells[2],
            "party": cells[3],
            "criminal_cases": int(cases) if cases.isdigit() else 0,
            "education": cells[5],
            "assets": assets,
            "liabilities": liabilities,
        }
    return out


def fetch_all_winners(session: Any) -> dict[int, dict[str, Any]]:
    def page_url(page: int) -> str:
        return (
            f"{MYNETA_BASE}/index.php?action=summary&subAction=winner_analyzed"
            f"&sort=candidate&page={page}"
        )

    first_html = fetch_cached(session, page_url(1), "winners-p1")
    m = re.search(
        r"Showing page\s+\d+\s+of\s+(\d+)\s+pages", re.sub(r"<[^>]+>", " ", first_html)
    )
    if not m:
        fail("MyNeta winners: could not read pagination count")
    total_pages = int(m.group(1))

    winners: dict[int, dict[str, Any]] = {}
    for page in range(1, total_pages + 1):
        rows = parse_winner_rows(fetch_cached(session, page_url(page), f"winners-p{page}"))
        if len(rows) < 10 and page < total_pages:
            # Thin page = likely a cached transient failure: refetch once.
            (CACHE_DIR / "myneta" / f"winners-p{page}.html").unlink(missing_ok=True)
            rows = parse_winner_rows(fetch_cached(session, page_url(page), f"winners-p{page}"))
        winners.update(rows)
    if len(winners) < MIN_ANALYZED:
        fail(
            f"MyNeta winners: only {len(winners)} parsed across {total_pages} pages "
            f"(floor {MIN_ANALYZED}) — page structure changed?"
        )
    return winners


def parse_detail_page(html: str) -> dict[str, Any]:
    """Assets/liabilities/case-count from a candidate detail page (used only
    to cross-check the listing parse — a second rendering of the same data)."""
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
    return out


def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    myneta_source = db.ensure_source(
        name="MyNeta (ADR) — Tamil Nadu 2026 affidavit analysis",
        url=f"{MYNETA_BASE}/",
        publisher="Association for Democratic Reforms",
        license=None,
        access_mode="scrape",
        notes=(
            "Structured analysis of candidates' self-declared ECI election affidavits "
            "(assets, liabilities, criminal cases, education). MyNeta mirrors ECI "
            "public-domain filings and defers to ECI on discrepancies. Every value is "
            "a SELF-DECLARED filing and is always labelled as such in the UI."
        ),
    )

    # Winning MLA per AC: constituency-name → (person_id, person_name).
    mla_rows = db.conn.execute(
        """
        SELECT l.name_en, p.id, p.name_en
        FROM localities l
        JOIN offices o ON o.locality_id = l.id AND o.office_type = 'mla'
        JOIN tenures t ON t.office_id = o.id AND t.end_date IS NULL AND t.status = 'active'
        JOIN persons p ON p.id = t.person_id
        WHERE l.level = 'ac'
        """
    ).fetchall()
    if len(mla_rows) != EXPECTED_WINNERS:
        fail("run import-representatives before import-affidavits")
    # Two ACs can share a display name (both Tiruppatturs) — key to a LIST
    # and let winner-name similarity pick the right seat.
    person_by_ac: dict[str, list[tuple[int, str]]] = {}
    for ac, pid, pname in mla_rows:
        person_by_ac.setdefault(norm_name(ac), []).append((pid, pname))

    print("Fetching MyNeta winners listing…")
    winners = fetch_all_winners(session)

    # --- Match every MyNeta row to an AC/person -------------------------------
    # Constituency name locates candidate ACs; the WINNER-NAME similarity
    # against ECI both validates the attachment and disambiguates same-named
    # constituencies (TN has two Tiruppatturs).
    from difflib import SequenceMatcher, get_close_matches

    def name_sim(a: str, b: str) -> float:
        return SequenceMatcher(None, norm_name(a), norm_name(b)).ratio()

    matched: dict[int, tuple[int, str, dict[str, Any]]] = {}  # cid → (person, ac, row)
    problems: list[str] = []
    for cid, row in winners.items():
        # Reservation suffixes ride along on MyNeta names: 'VANUR (SC)'.
        bare = re.sub(r"\s*\((SC|ST)\)\s*$", "", row["constituency"])
        key = norm_name(bare)
        key = CONSTITUENCY_ALIASES.get(key, key)
        candidates = [key] if key in person_by_ac else get_close_matches(
            key, list(person_by_ac), n=3, cutoff=0.75
        )
        if not candidates:
            problems.append(f"candidate {cid}: constituency '{row['constituency']}' unmatched")
            continue
        scored = sorted(
            (
                (name_sim(row["name"], pname), k, pid, pname)
                for k in candidates
                for pid, pname in person_by_ac[k]
            ),
            reverse=True,
        )
        best_sim, best_key, best_pid, best_winner = scored[0]
        if best_sim < 0.45:
            problems.append(
                f"candidate {cid} '{row['name']}' ({row['constituency']}): best AC "
                f"'{best_key}' has winner '{best_winner}' (sim {best_sim:.2f})"
            )
            continue
        if best_key != key or len(person_by_ac[best_key]) > 1:
            print(
                f"  MATCH: MyNeta '{row['constituency']}' → '{best_key}' "
                f"[{best_winner}] (name sim {best_sim:.2f})"
            )
        if row["assets"] is None:
            problems.append(f"candidate {cid} ({row['name']}): unparseable assets")
            continue
        matched[cid] = (best_pid, best_key, row)
    if problems:
        fail("MyNeta matching failed:\n  " + "\n  ".join(problems))
    by_person: dict[int, list[int]] = {}
    for cid, (pid, _k, _r) in matched.items():
        by_person.setdefault(pid, []).append(cid)
    dupes = {pid: cids for pid, cids in by_person.items() if len(cids) > 1}
    if dupes:
        details = []
        for pid, cids in dupes.items():
            for cid in cids:
                r = matched[cid][2]
                details.append(
                    f"person {pid} ← cid {cid} '{r['name']}' "
                    f"({r['constituency']}) → {matched[cid][1]}"
                )
        fail("MyNeta rows collided on one person:\n  " + "\n  ".join(details))

    # --- Spot-check a sample against detail pages (M4 exit criteria) ----------
    rng = random.Random(2026)  # deterministic sample, reproducible runs
    sample = rng.sample(sorted(matched), SPOT_CHECK_SAMPLE)
    print(f"Cross-checking {SPOT_CHECK_SAMPLE} candidates against detail pages…")
    for cid in sample:
        row = matched[cid][2]
        detail = parse_detail_page(
            fetch_cached(
                session, f"{MYNETA_BASE}/candidate.php?candidate_id={cid}", f"cand-{cid}"
            )
        )
        checks = [
            ("assets", row["assets"][0], detail.get("assets")),
            ("liabilities", row["liabilities"][0] if row["liabilities"] else 0,
             detail.get("liabilities")),
            ("criminal_cases", row["criminal_cases"], detail.get("criminal_cases")),
        ]
        for field, listed, detailed in checks:
            if detailed is not None and listed != detailed:
                fail(
                    f"spot-check FAILED: candidate {cid} {row['name']} {field}: "
                    f"listing {listed} vs detail page {detailed}"
                )
    print(f"  all {SPOT_CHECK_SAMPLE} spot-checks passed")

    # --- Write facts (self-declared, parser-extracted) ------------------------
    for cid, (person_id, _ac, row) in sorted(matched.items()):
        common = dict(
            subject_type="person",
            subject_id=person_id,
            source_id=myneta_source,
            retrieved_at=retrieved_at,
            extraction_method="parser",
            confidence=1.0,
        )
        assets_amount, assets_approx = row["assets"]
        db.upsert_fact(
            key="declared_assets",
            value={
                "self_declared": True,
                "amount_inr": assets_amount,
                "approx": assets_approx,
                "myneta_candidate_id": cid,
            },
            **common,
        )
        liab = row["liabilities"] or (0, "")
        db.upsert_fact(
            key="declared_liabilities",
            value={"self_declared": True, "amount_inr": liab[0], "approx": liab[1]},
            **common,
        )
        db.upsert_fact(
            key="criminal_cases",
            value={"self_declared": True, "count": row["criminal_cases"]},
            **common,
        )
        db.upsert_fact(
            key="education",
            value={"self_declared": True, "category": row["education"]},
            **common,
        )

    db.conn.commit()

    with_cases = sum(1 for _, _, r in matched.values() if r["criminal_cases"] > 0)
    crorepatis = sum(1 for _, _, r in matched.values() if r["assets"][0] >= 10_000_000)
    covered_pids = {m[0] for m in matched.values()}
    pending_acs = sorted(
        ac
        for ac, entries in person_by_ac.items()
        if any(pid not in covered_pids for pid, _ in entries)
    )
    print("\n=== Affidavit import report ===")
    print(f"winners matched: {len(matched)}/{EXPECTED_WINNERS}")
    if pending_acs:
        print(
            f"AFFIDAVIT ANALYSIS PENDING on MyNeta for {len(pending_acs)} ACs "
            "(honest empty state shown until ADR publishes):"
        )
        print("  " + ", ".join(pending_acs))
    print(f"with declared criminal cases: {with_cases}")
    print(f"with declared assets ≥ ₹1 crore: {crorepatis}")
    print("education categories:", sorted({r['education'] for _, _, r in matched.values()}))


if __name__ == "__main__":
    main()
