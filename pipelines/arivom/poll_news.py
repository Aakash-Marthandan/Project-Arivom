"""News ingestion poller (M6, DESIGN.md §4E and §7).

Reads the curated outlet registry (data/outlets.json), registers each
outlet as a `sources` row, and ingests feed items into `news_items` —
headline + link + feed metadata ONLY, never article text or summaries
(hard aggregation policy, DESIGN §4E). Runs every 30 minutes on GitHub
Actions cron; needs only DATABASE_URL (D-018 precedent).

Dedupe is by canonical URL (tracking parameters stripped; `url` is UNIQUE).
Re-observing a known item refreshes its headline, published time and
retrieved_at — so /freshness reflects the latest successful poll per
outlet — without creating duplicates.

Locality tagging is a conservative heuristic: an item is tagged to a
district only when exactly ONE district is named in the headline (English
word match incl. common press spellings, or Tamil name as a word-initial
substring so case suffixes still match). Anything ambiguous stays NULL;
M7's entity work can do better. Outlets whose feed is national carry
`include_url_prefixes` in the registry, and only items under those
sections (the outlet's own taxonomy) are stored.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .common import Db, fail, has_tamil, http_session, now_utc

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "outlets.json"

ATOM = "{http://www.w3.org/2005/Atom}"

# Query parameters that identify campaigns/visitors, not content.
TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|igshid$|mc_cid$|mc_eid$|ref$)")

# Newspaper spellings that differ from our LGD/DB district names.
# Matching aid only — never displayed, never stored.
EN_DISTRICT_ALIASES = {
    "Tiruchirappalli": ["Trichy", "Tiruchi", "Tiruchy", "Tiruchirapalli"],
    "Thoothukkudi": ["Thoothukudi", "Tuticorin"],
    "Kanniyakumari": ["Kanyakumari"],
    "Kancheepuram": ["Kanchipuram"],
    "The Nilgiris": ["Nilgiris"],
    "Thiruvallur": ["Tiruvallur"],
    "Thiruvarur": ["Tiruvarur"],
    "Viluppuram": ["Villupuram"],
    "Sivaganga": ["Sivagangai"],
    "Tiruppur": ["Tirupur"],
    "Tirupathur": ["Tirupattur"],
    "Tiruvannamalai": ["Thiruvannamalai"],
}
TA_DISTRICT_ALIASES = {
    "Coimbatore": ["கோவை"],
    "Tiruchirappalli": ["திருச்சி"],
    "Tirunelveli": ["நெல்லை"],
    "Ramanathapuram": ["ராமநாதபுரம்"],  # DB name carries the initial இ
    "Kancheepuram": ["காஞ்சீபுரம்"],
}
TAMIL_LETTER = re.compile(r"[஀-௿]")


def load_registry() -> list[dict[str, Any]]:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        outlets = json.load(f)["outlets"]
    slugs = [o["slug"] for o in outlets]
    if len(slugs) != len(set(slugs)):
        fail("outlet registry has duplicate slugs")
    return outlets


def canonical_url(url: str) -> str:
    """Strip fragments and tracking parameters; keep content-bearing query."""
    parts = urlsplit(url.strip())
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not TRACKING_PARAMS.match(k.lower())
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc.lower(), parts.path, urlencode(query), "")
    )


def parse_when(text: str | None) -> datetime | None:
    """RFC 822 (RSS) or ISO 8601 (Atom) → aware UTC datetime, else None."""
    if not text:
        return None
    for parser in (
        parsedate_to_datetime,
        lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
    ):
        try:
            when = parser(text.strip())
        except (ValueError, TypeError):
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return when.astimezone(UTC)
    return None


def parse_feed(content: bytes) -> list[dict[str, Any]]:
    """Minimal RSS 2.0 / Atom parser: title, url, published. Nothing else —
    descriptions and content are deliberately never read (§4E policy)."""
    root = ET.fromstring(content)
    items = []
    for item in root.iter("item"):  # RSS 2.0
        title = " ".join(unescape(item.findtext("title") or "").split())
        link = (item.findtext("link") or "").strip()
        if not link:
            guid = (item.findtext("guid") or "").strip()
            link = guid if guid.startswith("http") else ""
        items.append(
            {"title": title, "url": link, "published": parse_when(item.findtext("pubDate"))}
        )
    if not items:
        for entry in root.iter(f"{ATOM}entry"):
            title = " ".join(unescape(entry.findtext(f"{ATOM}title") or "").split())
            link = ""
            for el in entry.findall(f"{ATOM}link"):
                if el.get("rel") in (None, "alternate"):
                    link = (el.get("href") or "").strip()
                    break
            when = entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")
            items.append({"title": title, "url": link, "published": parse_when(when)})
    return [i for i in items if i["title"] and i["url"]]


class DistrictTagger:
    """Tag a headline to a district only when exactly one district matches."""

    def __init__(self, districts: list[tuple[int, str, str]]):
        self.patterns: list[tuple[int, re.Pattern[str], list[str]]] = []
        for district_id, name_en, name_ta in districts:
            en_names = [name_en, *EN_DISTRICT_ALIASES.get(name_en, [])]
            en_pattern = re.compile(
                r"\b(?:" + "|".join(re.escape(n) for n in en_names) + r")\b",
                re.IGNORECASE,
            )
            ta_names = [name_ta, *TA_DISTRICT_ALIASES.get(name_en, [])]
            self.patterns.append((district_id, en_pattern, ta_names))

    @staticmethod
    def _tamil_word_start(headline: str, name: str) -> bool:
        """Tamil names match at a word start so case suffixes (மதுரைக்கு)
        still hit, while mid-word hits (…புதுமதுரை) do not."""
        start = 0
        while (pos := headline.find(name, start)) != -1:
            if pos == 0 or not TAMIL_LETTER.match(headline[pos - 1]):
                return True
            start = pos + 1
        return False

    def tag(self, headline: str) -> int | None:
        hits = set()
        for district_id, en_pattern, ta_names in self.patterns:
            if en_pattern.search(headline) or any(
                self._tamil_word_start(headline, n) for n in ta_names
            ):
                hits.add(district_id)
                if len(hits) > 1:
                    return None  # ambiguous — leave untagged
        return hits.pop() if len(hits) == 1 else None


def outlet_source_notes(outlet: dict[str, Any]) -> str:
    bits = [f"Outlet registry entry (M6, DESIGN §4E); role: {outlet['role']}."]
    if outlet.get("feed_scope"):
        bits.append(f"Feed scope: {outlet['feed_scope']}.")
    if outlet.get("tagging_practice"):
        bits.append(f"Tagging practice: {outlet['tagging_practice']}.")
    bits.append(f"Paywall: {outlet.get('paywall', 'unknown')}.")
    bits.append(f"{outlet['copyright_note']} (aggregation policy, never article text).")
    if outlet.get("notes"):
        bits.append(outlet["notes"])
    return " ".join(bits)


def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()
    outlets = load_registry()

    state_row = db.conn.execute(
        "SELECT id FROM localities WHERE level = 'state' AND lgd_code = '33'"
    ).fetchone()
    assert state_row is not None
    state_id = state_row[0]

    tagger = DistrictTagger(
        db.conn.execute(
            "SELECT id, name_en, name_ta FROM localities WHERE level = 'district'"
        ).fetchall()
    )

    run_report: list[dict[str, Any]] = []
    pending: list[str] = []
    langs_flowing: dict[str, set[str]] = {"ta": set(), "en": set()}

    for outlet in outlets:
        # Every §4E outlet is registered, polled or not: the sources table
        # mirrors the registry, and the notes say honestly why an outlet
        # is not flowing yet.
        source_id = db.ensure_source(
            name=f"News outlet: {outlet['name']}",
            url=outlet.get("feed") or outlet["homepage"],
            publisher=outlet["name"],
            license=None,
            access_mode="api",
            notes=outlet_source_notes(outlet),
        )

        if outlet["role"] != "news":
            continue  # fact-check consumption model arrives with M7
        if outlet["status"] != "active":
            pending.append(f"{outlet['slug']}: {outlet.get('notes', 'no feed')}")
            continue

        entry: dict[str, Any] = {
            "outlet": outlet["slug"], "ok": False,
            "items": 0, "new": 0, "seen": 0, "tagged": 0, "skipped_scope": 0,
        }
        try:
            resp = session.get(outlet["feed"], timeout=60)
            resp.raise_for_status()
            items = parse_feed(resp.content)
            entry["ok"] = True
        except Exception as exc:  # noqa: BLE001 — record failure, keep polling
            entry["error"] = str(exc)[:200]
            run_report.append(entry)
            print(f"FEED FAILED [{outlet['slug']}]: {entry['error']}")
            continue

        prefixes = outlet.get("include_url_prefixes")
        for item in items:
            url = canonical_url(item["url"])
            if prefixes and not any(url.startswith(p) for p in prefixes):
                entry["skipped_scope"] += 1
                continue
            entry["items"] += 1
            locality_id = tagger.tag(item["title"])
            lang = "ta" if has_tamil(item["title"]) else "en"
            row = db.conn.execute(
                """
                INSERT INTO news_items
                  (outlet, url, headline_orig, lang, published_at, locality_id,
                   source_id, retrieved_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE
                  SET headline_orig = EXCLUDED.headline_orig,
                      published_at = COALESCE(EXCLUDED.published_at,
                                              news_items.published_at),
                      locality_id = EXCLUDED.locality_id,
                      retrieved_at = EXCLUDED.retrieved_at
                RETURNING (xmax = 0) AS inserted
                """,
                (
                    outlet["slug"],
                    url,
                    item["title"],
                    lang,
                    item["published"],
                    locality_id,
                    source_id,
                    retrieved_at,
                ),
            ).fetchone()
            assert row is not None
            entry["new" if row[0] else "seen"] += 1
            if locality_id is not None:
                entry["tagged"] += 1
        if entry["items"]:
            langs_flowing[outlet["lang"]].add(outlet["slug"])
        run_report.append(entry)

    # Poller health record (the M7 news pages' "last checked", and audit).
    poller_source = db.ensure_source(
        name="News poller (outlet registry)",
        url="https://github.com/Aakash-Marthandan/Project-Arivom",
        publisher="Arivom pipeline over the §4E outlet registry",
        license=None,
        access_mode="api",
        notes=(
            "Health record of the 30-minute news poll: per-outlet item/new/failure "
            "counts. Items themselves carry the outlet's own source row."
        ),
    )
    db.upsert_fact(
        subject_type="locality",
        subject_id=state_id,
        key="news_poll_run",
        value={"checked_at": retrieved_at.isoformat(), "outlets": run_report},
        source_id=poller_source,
        retrieved_at=retrieved_at,
        extraction_method="api",
        confidence=1.0,
    )
    db.conn.commit()

    print("\n=== News poll report ===")
    for entry in run_report:
        print(f"  {entry}")
    if pending:
        print("\nPending outlets (no machine-readable feed yet):")
        for line in pending:
            print(f"  - {line}")
    total_new = sum(e["new"] for e in run_report)
    total_seen = sum(e["seen"] for e in run_report)
    failures = [e["outlet"] for e in run_report if not e["ok"]]
    print(
        f"\nflowing: {len(langs_flowing['ta'])} Tamil + {len(langs_flowing['en'])} English "
        f"outlets; new items: {total_new}; re-observed: {total_seen}"
        + (f"; FAILED: {', '.join(failures)}" if failures else "")
    )
    if len(langs_flowing["ta"]) + len(langs_flowing["en"]) < 6:
        fail("fewer than 6 outlets flowing (M6 exit criterion)")


if __name__ == "__main__":
    main()
