"""News clustering, neutral bilingual summaries, coverage (M7, DESIGN §7).

Four stages, all offline, all idempotent, all disk-cached and metered:

0. TRIAGE — a headline-only pass over new items that removes confidently
   non-civic material (cricket, cinema, astrology, viral) before anything
   expensive happens to it. Triage may only ELIMINATE: a "keep" verdict
   claims nothing about the item, it just buys the item a full read. The
   displayed classification is always set by stage 1 with the article in
   hand, so a cheap model never decides what a citizen gets to see.
   40 headlines per call (D-039).

1. ENTITY EXTRACTION — per surviving item: deterministic match against our
   own bilingual lexicon (persons, districts, parties from the database),
   plus a cheap-model pass over the headline and a transiently fetched
   article excerpt (D-022: read, never stored). Result lands in
   news_items.entities. 8 items per call.

2. CLUSTERING — incremental: an unclustered item joins an existing cluster
   (or pairs with another unclustered item) only when they share strong
   entities within a 72h window AND a cheap-model judgment confirms they
   describe the same specific event. All of one item's candidates are
   judged in a single call, so the sequential semantics are unchanged but
   the call count is not. Clusters materialize at >= 2 items (D-022).

3. SUMMARIES — for clusters whose membership changed: a mid-tier model
   drafts a neutral bilingual title + summary with inline [n] citations
   from the members' reporting, and the same tier spot-checks claim
   support, neutrality, Tamil register and citations. The frontier model
   adjudicates only what the routine check cannot settle — any moderation
   positive (communal / sub judice / allegations), and any draft still
   failing after one revise cycle, so nothing is withheld or locked on a
   cheap model's word alone (D-039). One revise cycle; a failing summary is
   withheld and reported, never published unchecked.

The informed-electorate test (D-021) governs ordering and copy: civic
usefulness, never sensation. No bias labels anywhere (pillar 2).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from . import civic_guard, offline
from .anchors import anchor_block, cluster_anchors
from .articles import fetch_excerpt
from .common import (
    Db,
    article_session,
    has_tamil,
    norm_name,
    now_utc,
    script_clean,
)
from .llm import (
    HAIKU,
    OPUS,
    SONNET,
    arr,
    batch_params,
    cache_lookup,
    cache_store,
    collect_batch,
    llm_available,
    obj_schema,
    pending_batches,
    require_llm,
    structured,
    submit_batch,
)
from .poll_news import EN_DISTRICT_ALIASES, TA_DISTRICT_ALIASES
from .spend import BudgetExhausted, Ledger

WINDOW_DAYS = 7          # working set: items/clusters from the last week
PAIR_WINDOW_H = 72       # max time gap for two items to be the same event
TRIAGE_CAP = 2000        # headlines triaged per run (cheap; clears backlog fast)
EXTRACT_CAP = 300        # entity extractions per run (backlog is reported)
CONFIRM_CAP = 250        # merge confirmations per run
SUMMARY_CAP = 40         # summary generations per run

TRIAGE_PER_CALL = 40     # headlines per triage request
EXTRACT_PER_CALL = 8     # items (with excerpts) per extraction request

# Signals too generic to link two stories on their own.
GENERIC_STRINGS = {"tamil nadu", "தமிழ்நாடு", "tamilnadu", "india", "இந்தியா", "tn"}

MARKER = re.compile(r"\[(\d+)\]")


# ---------------------------------------------------------------------------
# Lexicon: bilingual entities we already store, with provenance (D-005 etc.)
# ---------------------------------------------------------------------------


class Lexicon:
    def __init__(self, db: Db):
        self.persons = db.conn.execute(
            "SELECT id, name_en, name_ta FROM persons"
        ).fetchall()
        # (id, display, normalized, word-boundary pattern) for English names.
        self._person_en = [
            (pid, en, norm_name(en), re.compile(rf"\b{re.escape(en)}\b", re.IGNORECASE))
            for pid, en, _ta in self.persons
            if en
        ]
        self.districts = db.conn.execute(
            "SELECT id, name_en, name_ta FROM localities WHERE level = 'district'"
        ).fetchall()
        self._district_en: dict[str, int] = {}
        self._district_ta: dict[str, int] = {}
        for did, en, ta in self.districts:
            for name in (en, *EN_DISTRICT_ALIASES.get(en, [])):
                self._district_en[norm_name(name)] = did
            for name in (ta, *TA_DISTRICT_ALIASES.get(en, [])):
                self._district_ta[name] = did

    def persons_in(self, text: str) -> dict[int, str]:
        hits: dict[int, str] = {}
        for pid, en, _norm, pattern in self._person_en:
            if pattern.search(text):
                hits[pid] = en
        for pid, en, ta in self.persons:
            if ta and ta in text:
                hits.setdefault(pid, en or ta)
        return hits

    # Honorifics and roles that precede names in headlines, never part of them.
    _STOP_TOKENS = {"cm", "chief", "minister", "mla", "mp", "dr", "mr", "mrs", "thiru", "selvi"}

    def match_person(self, name: str) -> int | None:
        if has_tamil(name):
            hits = {
                pid
                for pid, _en, ta in self.persons
                if ta and (ta in name or name in ta)
            }
            return hits.pop() if len(hits) == 1 else None
        target = norm_name(name)
        best, best_ratio = None, 0.0
        for pid, _en, en_norm, _pattern in self._person_en:
            ratio = SequenceMatcher(None, target, en_norm).ratio()
            if ratio > best_ratio:
                best, best_ratio = pid, ratio
        if best_ratio >= 0.88:
            return best
        # Headlines use short names ("Vijay", "Stalin"); match only when the
        # tokens pick out exactly one stored person — ambiguity means no match.
        tokens = [t for t in target.split() if t not in self._STOP_TOKENS and len(t) > 1]
        if not tokens:
            return None
        candidates = {
            pid
            for pid, _en, en_norm, _pattern in self._person_en
            if all(t in en_norm.split() for t in tokens)
        }
        return candidates.pop() if len(candidates) == 1 else None

    def match_district(self, place: str) -> int | None:
        if has_tamil(place):
            for ta, did in self._district_ta.items():
                if ta in place or place in ta:
                    return did
            return None
        return self._district_en.get(norm_name(place))


# ---------------------------------------------------------------------------
# Stage 0 — headline triage (D-039)
# ---------------------------------------------------------------------------

# Returns only the positions to drop. Echoing an id and a verdict per item put
# 58% of this stage's cost in output tokens (measured 2026-08-11); a bare list
# of the few soft positions costs about half a token per item instead.
TRIAGE_SCHEMA = obj_schema({"soft": arr({"type": "integer"})})

TRIAGE_SYSTEM = """You screen Tamil Nadu news headlines for Arivom, a civic information
platform whose mission is an informed electorate. You are a FIRST PASS whose only
job is to set aside material that plainly has no civic relevance, so the platform
does not spend a full reading on it.

You get numbered headlines. Return the numbers of the ones that are clearly and
entirely NON-CIVIC, and nothing else. Return an empty list if none are.

Non-civic means the headline is clearly and entirely one of: film, television or
celebrity news; sports and cricket; astrology, numerology, horoscopes or
devotional events and festivals; viral, voyeuristic or curiosity items; human
interest with no policy bearing; lifestyle, recipes, beauty, relationships,
travel tips; gaming; shopping offers and consumer product launches; press-release
surveys and brand announcements.

Everything else stays, including anything you are unsure about. Do NOT set aside:
government, courts, elections, legislature, police and public safety, policy,
corruption, defence, foreign affairs; the ECONOMY in every form (company results,
IPOs, market moves, industry and sector data, employment, trade, tax); jobs,
education, health, environment, weather, agriculture, infrastructure, prices,
transport, welfare schemes, civic protest, local administration. Keep anything
whose subject you cannot tell from the headline alone. Keep anything where a
celebrity or sportsperson appears in a governmental, legal, electoral or civic
context (a film star's political party, a cricketer's tax case, a court order
about a stadium).

The cost of wrongly setting aside a story is that a citizen never sees civic
news. The cost of wrongly keeping one is a fraction of a cent. When the two are
in tension, keep it."""


def triage_items(db: Db, lexicon: Lexicon, ledger: Ledger, report: dict[str, Any]) -> None:
    """Mark confidently non-civic items so they are never fetched or read.

    Sets civic_class='soft' and nothing else: the item stays in the database
    for registry and coverage analysis (D-025) and is already excluded from
    every feed by the existing `civic_class <> 'soft'` filter, so no UI
    change is needed and nothing is deleted.
    """
    rows = db.conn.execute(
        """
        SELECT id, headline_orig FROM news_items
        WHERE triaged_at IS NULL AND entities IS NULL
          AND created_at > now() - make_interval(days => %s)
        ORDER BY published_at DESC
        LIMIT %s
        """,
        (WINDOW_DAYS, TRIAGE_CAP + 1),
    ).fetchall()
    backlog = len(rows) > TRIAGE_CAP
    rows = rows[:TRIAGE_CAP]
    if not rows:
        return

    for start in range(0, len(rows), TRIAGE_PER_CALL):
        chunk = rows[start : start + TRIAGE_PER_CALL]
        user = "Headlines:\n" + "\n".join(
            f"{n}. {headline}" for n, (_id, headline) in enumerate(chunk, start=1)
        )
        result = structured(
            model=HAIKU, system=TRIAGE_SYSTEM, user=user, schema=TRIAGE_SCHEMA,
            max_tokens=512, ledger=ledger, stage="triage", items=len(chunk),
        )
        if result is None:
            report["triage_failed"] += len(chunk)
            continue

        # Positions, not ids: a number outside the range we sent is ignored, so
        # a miscounted reply can never mark the wrong story soft.
        proposed = [
            chunk[position - 1]
            for position in dict.fromkeys(result["soft"])
            if 1 <= position <= len(chunk)
        ]
        # Our own civic data overrules the cheap model (D-039). Measured on a
        # real sample, triage alone set aside a Tamil Nadu Assembly exchange
        # between two named legislators; the guard catches exactly that.
        soft = []
        for item_id, headline in proposed:
            if civic_guard.protected(headline, lexicon):
                report["triage_vetoed"] += 1
                continue
            soft.append(item_id)
        if soft:
            db.conn.execute(
                "UPDATE news_items SET civic_class = 'soft' WHERE id = ANY(%s)", (soft,)
            )
        # Mark the whole chunk screened, kept items included, so a verdict is
        # never paid for twice.
        db.conn.execute(
            "UPDATE news_items SET triaged_at = now() WHERE id = ANY(%s)",
            ([item_id for item_id, _h in chunk],),
        )
        db.conn.commit()
        report["triaged"] += len(chunk)
        report["triaged_soft"] += len(soft)
    db.conn.commit()
    if backlog:
        report["notes"].append(f"triage backlog beyond the {TRIAGE_CAP}-item cap")


# ---------------------------------------------------------------------------
# Stage 1 — entity extraction
# ---------------------------------------------------------------------------

ITEM_FIELDS = {
    "id": {"type": "integer"},
    "persons": arr({"type": "string"}),
    "places": arr({"type": "string"}),
    "organizations": arr({"type": "string"}),
    "gist_en": {"type": "string"},
    "department": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "department_ta": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "civic_class": {"type": "string", "enum": ["civic", "adjacent", "soft"]},
    "civic_priority": {"type": "string", "enum": ["high", "normal"]},
    "title_clean_en": {"type": "string"},
    "title_clean_ta": {"type": "string"},
}

EXTRACT_SCHEMA = obj_schema({"items": arr(obj_schema(ITEM_FIELDS))})

EXTRACT_SYSTEM = """You process Tamil Nadu news items for Arivom, a civic information platform
whose mission is an informed electorate. You are given several numbered items, each
with a headline (Tamil or English) and possibly an article excerpt. Return one entry
per item, echoing its id exactly. For each item return:
- persons: full names of people mentioned (as written, do not translate or transliterate).
- places: cities, towns, districts, localities mentioned (as written).
- organizations: parties, government bodies, companies, institutions (as written).
- gist_en: what specifically happened, in your OWN words, in English, at most 15 words.
- department: the ONE Tamil Nadu government department the story chiefly concerns,
  named in English (for example "School Education", "Highways", "Health",
  "Municipal Administration"), or null when no department clearly applies.
- department_ta: the same department in Tamil, using the TN government's own
  usage (for example "பள்ளிக் கல்வித் துறை", "நெடுஞ்சாலைத் துறை",
  "சுகாதாரத் துறை"); null exactly when department is null.
- civic_class (D-025, judge the SUBJECT of the story, never who it favours):
  "civic" = governance, courts, elections, legislature, public services,
  public safety, policy, corruption or accountability matters.
  "adjacent" = economy, employment, education, health, environment, weather,
  infrastructure, prices that affect households.
  "soft" = entertainment, celebrity, sports, astrology or devotion, viral or
  voyeuristic items, and stories with no Tamil Nadu civic relevance.
- civic_priority (D-026, only meaningful for civic/adjacent; use "normal" for soft):
  "high" = statewide policy impact, elections and by-elections, court rulings,
  legislature decisions, or public-safety matters affecting many people.
  "normal" = everything else. Judge the subject, never who it favours.
- title_clean_en and title_clean_ta: the same story retold as ONE calm,
  informative headline in each language, in Arivom's voice: state what
  happened; no exclamation marks, no teasers or cliffhangers, no
  sensational words (no அதிர்ச்சி/பகீர்/shocking/slams), no unresolved
  pronouns, no ALL CAPS, under 90 characters. Tamil: warm formal register,
  simple words. Do not add facts that are not in the material.

Script rules, absolute: title_clean_ta is written in Tamil script only, apart
from Latin letters and digits where a name or abbreviation genuinely needs
them. title_clean_en is written in Latin script only. Never emit Devanagari,
CJK, Kana, Hangul, Cyrillic, Arabic or any other script in either field — if
you cannot render a word in the right script, paraphrase it.

Return exactly one entry per item given, echoing each id, and no others.
Judge each item only on its own material; items in one request are unrelated.
Be precise; the gist and titles must be neutral and factual."""


def _extract_user(chunk: list[tuple[int, str, str | None]]) -> str:
    parts = []
    for item_id, headline, excerpt in chunk:
        block = f"## Item {item_id}\nHeadline: {headline}"
        if excerpt:
            block += f"\n\nArticle excerpt:\n{excerpt}"
        parts.append(block)
    return "\n\n".join(parts)


def _apply_extraction(
    db: Db, lexicon: Lexicon, entry: dict[str, Any], fetch_meta: dict[int, tuple[str, str | None]]
) -> str | None:
    """Write one extracted item; returns the civic_class actually stored."""
    item_id = entry["id"]
    fetch_status, og_image = fetch_meta.get(item_id, ("failed", None))
    headline_row = db.conn.execute(
        "SELECT headline_orig FROM news_items WHERE id = %s", (item_id,)
    ).fetchone()
    headline = headline_row[0] if headline_row else ""

    person_hits = lexicon.persons_in(headline)
    for name in entry["persons"]:
        pid = lexicon.match_person(name)
        if pid is not None:
            person_hits.setdefault(pid, name)
    district_ids = {
        did
        for place in entry["places"]
        if (did := lexicon.match_district(place)) is not None
    }
    entities = {
        "persons": [{"name": name, "person_id": pid} for pid, name in person_hits.items()]
        + [{"name": n} for n in entry["persons"] if lexicon.match_person(n) is None],
        "places": entry["places"],
        "orgs": entry["organizations"],
        "district_ids": sorted(district_ids),
        "gist": entry["gist_en"][:200],
        # Loose-matched to /government department cards at display time
        # (D-019: source-verbatim names differ per locale).
        "department": entry["department"],
        "department_ta": entry["department_ta"],
    }
    # Arivom-voice titles (D-025): accept only when the language is genuinely
    # right AND the script is clean; a NULL falls back to the original
    # headline in the UI rather than showing a bad rewrite.
    title_en = entry["title_clean_en"].strip()
    title_ta = entry["title_clean_ta"].strip()
    if not title_en or has_tamil(title_en) or not script_clean(title_en):
        title_en = None
    if not has_tamil(title_ta) or not script_clean(title_ta):
        title_ta = None

    # Our published civic rubric overrules a "soft" call the same way it
    # overrules triage (D-039) — but here we do not substitute a class of our
    # own. Disagreement leaves civic_class NULL, which the product already
    # treats as unclassified-and-visible (D-025), so the story stays in the
    # feed and we claim nothing we cannot defend.
    civic_class = entry["civic_class"]
    if civic_class == "soft" and civic_guard.protected(headline, lexicon):
        civic_class = None

    db.conn.execute(
        """
        UPDATE news_items
        SET entities = %s, fetch_status = %s,
            image_url = COALESCE(image_url, %s),
            civic_class = %s, civic_priority = %s,
            title_clean_en = %s, title_clean_ta = %s
        WHERE id = %s
        """,
        (
            json.dumps(entities, ensure_ascii=False), fetch_status, og_image,
            civic_class, entry["civic_priority"],
            title_en, title_ta, item_id,
        ),
    )
    return civic_class


def extract_entities(
    db: Db, session: Any, lexicon: Lexicon, ledger: Ledger, report: dict[str, Any],
    use_batch_api: bool,
) -> None:
    rows = db.conn.execute(
        """
        SELECT id, headline_orig, url FROM news_items
        WHERE entities IS NULL
          AND civic_class IS DISTINCT FROM 'soft'
          AND created_at > now() - make_interval(days => %s)
        ORDER BY published_at DESC
        LIMIT %s
        """,
        (WINDOW_DAYS, EXTRACT_CAP + 1),
    ).fetchall()
    backlog = len(rows) > EXTRACT_CAP
    rows = rows[:EXTRACT_CAP]
    if not rows:
        return

    # Fetch excerpts first (disk-cached 24h; never stored in the database).
    prepared: list[tuple[int, str, str | None]] = []
    fetch_meta: dict[int, tuple[str, str | None]] = {}
    for item_id, headline, url in rows:
        excerpt, fetch_status, og_image = fetch_excerpt(session, url)
        fetch_meta[item_id] = (fetch_status, og_image)
        prepared.append((item_id, headline, excerpt))
        if fetch_status != "fetched":
            report["fetch_failed"] += 1

    chunks = [
        prepared[i : i + EXTRACT_PER_CALL]
        for i in range(0, len(prepared), EXTRACT_PER_CALL)
    ]

    # Anything already paid for in a previous run applies for free.
    live_chunks: list[list[tuple[int, str, str | None]]] = []
    for chunk in chunks:
        user = _extract_user(chunk)
        cached = cache_lookup(
            model=HAIKU, system=EXTRACT_SYSTEM, user=user, schema=EXTRACT_SCHEMA
        )
        if cached is not None:
            _apply_chunk(db, lexicon, chunk, cached, fetch_meta, report)
        else:
            live_chunks.append(chunk)

    if use_batch_api and live_chunks:
        _extract_via_batch_api(db, lexicon, live_chunks, fetch_meta, ledger, report)
    else:
        for chunk in live_chunks:
            user = _extract_user(chunk)
            result = structured(
                model=HAIKU, system=EXTRACT_SYSTEM, user=user, schema=EXTRACT_SCHEMA,
                max_tokens=6000, ledger=ledger, stage="extract", items=len(chunk),
            )
            if result is None:
                report["extract_failed"] += len(chunk)
                continue
            _apply_chunk(db, lexicon, chunk, result, fetch_meta, report)

    db.conn.commit()
    if backlog:
        report["notes"].append(f"extraction backlog beyond the {EXTRACT_CAP}-item cap")


def _apply_chunk(
    db: Db,
    lexicon: Lexicon,
    chunk: list[tuple[int, str, str | None]],
    result: dict[str, Any],
    fetch_meta: dict[int, tuple[str, str | None]],
    report: dict[str, Any],
) -> None:
    sent = {item_id for item_id, _h, _e in chunk}
    seen: set[int] = set()
    for entry in result.get("items", []):
        if entry["id"] not in sent or entry["id"] in seen:
            continue  # invented or duplicated id — the item retries next run
        seen.add(entry["id"])
        stored = _apply_extraction(db, lexicon, entry, fetch_meta)
        report["extracted"] += 1
        if stored == "soft":
            report["classified_soft"] += 1
        elif entry["civic_class"] == "soft":
            report["class_vetoed"] += 1
    report["extract_failed"] += len(sent - seen)


def _extract_via_batch_api(
    db: Db,
    lexicon: Lexicon,
    chunks: list[list[tuple[int, str, str | None]]],
    fetch_meta: dict[int, tuple[str, str | None]],
    ledger: Ledger,
    report: dict[str, Any],
) -> None:
    """Submit extraction chunks to the Message Batches API (50% off) and apply
    whatever comes back. A job that has not ended by the polling deadline is
    left in llm_batches for a later run — no work and no money is lost."""
    requests, context = [], {"model": HAIKU, "chunks": {}}
    for n, chunk in enumerate(chunks):
        custom_id = f"extract-{n}"
        requests.append(
            (
                custom_id,
                batch_params(
                    model=HAIKU, system=EXTRACT_SYSTEM, user=_extract_user(chunk),
                    schema=EXTRACT_SCHEMA, max_tokens=6000,
                ),
            )
        )
        context["chunks"][custom_id] = [item_id for item_id, _h, _e in chunk]

    batch_id = submit_batch(requests=requests, stage="extract", db=db, context=context)
    if batch_id is None:
        return
    report["notes"].append(f"submitted {len(requests)} extraction requests as batch {batch_id}")

    results = collect_batch(
        batch_id=batch_id, db=db, ledger=ledger, stage="extract",
        items=sum(len(c) for c in chunks),
    )
    if results is None:
        report["notes"].append(
            f"batch {batch_id} still running; a later run will collect it "
            f"({len(requests)} requests)"
        )
        return
    by_id = {f"extract-{n}": chunk for n, chunk in enumerate(chunks)}
    for custom_id, result in results.items():
        chunk = by_id.get(custom_id)
        if chunk is None:
            continue
        cache_store(
            model=HAIKU, system=EXTRACT_SYSTEM, user=_extract_user(chunk),
            schema=EXTRACT_SCHEMA, result=result,
        )
        _apply_chunk(db, lexicon, chunk, result, fetch_meta, report)


def collect_pending(db: Db, lexicon: Lexicon, ledger: Ledger, report: dict[str, Any]) -> None:
    """Apply results from batches an earlier run submitted, before doing new work."""
    session = article_session()
    for batch_id, context in pending_batches(db, stage="extract"):
        results = collect_batch(
            batch_id=batch_id, db=db, ledger=ledger, stage="extract", wait=False,
            items=sum(len(v) for v in context.get("chunks", {}).values()),
        )
        if results is None:
            continue
        for custom_id, result in results.items():
            item_ids = context.get("chunks", {}).get(custom_id, [])
            rows = db.conn.execute(
                "SELECT id, headline_orig, url FROM news_items WHERE id = ANY(%s)",
                (item_ids,),
            ).fetchall()
            chunk, fetch_meta = [], {}
            for item_id, headline, url in rows:
                excerpt, status, image = fetch_excerpt(session, url)
                chunk.append((item_id, headline, excerpt))
                fetch_meta[item_id] = (status, image)
            _apply_chunk(db, lexicon, chunk, result, fetch_meta, report)
        report["notes"].append(f"collected batch {batch_id} from an earlier run")
    db.conn.commit()


# ---------------------------------------------------------------------------
# Stage 2 — incremental clustering
# ---------------------------------------------------------------------------


def signature(item: dict[str, Any]) -> dict[str, set]:
    ent = item["entities"] or {}
    strings = set()
    for value in [*ent.get("places", []), *ent.get("orgs", [])] + [
        p["name"] for p in ent.get("persons", []) if "person_id" not in p
    ]:
        key = value if has_tamil(value) else norm_name(value)
        if key and key not in GENERIC_STRINGS:
            strings.add(key)
    districts = set(ent.get("district_ids", []))
    if item["locality_id"]:
        districts.add(item["locality_id"])
    return {
        "persons": {p["person_id"] for p in ent.get("persons", []) if "person_id" in p},
        "districts": districts,
        "strings": strings,
    }


def blocks(a: dict[str, set], b: dict[str, set]) -> bool:
    """Cheap gate before an LLM judgment: entity overlap strong enough to
    plausibly be the same event."""
    shared_strings = len(a["strings"] & b["strings"])
    return bool(
        a["persons"] & b["persons"]
        or shared_strings >= 2
        or (a["districts"] & b["districts"] and shared_strings >= 1)
    )


def within_window(a: datetime | None, b: datetime | None) -> bool:
    return bool(a and b and abs((a - b).total_seconds()) < PAIR_WINDOW_H * 3600)


# One call decides among all of an item's candidates at once. The judgment is
# identical to asking pair by pair — the candidates are mutually exclusive —
# but it costs one request instead of one per pair, and the 94-token system
# prompt is paid once instead of N times (D-039).
CONFIRM_SCHEMA = obj_schema(
    {"match": {"anyOf": [{"type": "integer"}, {"type": "null"}]}}
)

CONFIRM_SYSTEM = """You judge which candidate, if any, describes the SAME SPECIFIC EVENT as a
given news item, for clustering.
Same event = the same concrete occurrence: one incident, one announcement, one decision,
one meeting. Coverage of the same event by different outlets, in Tamil or English, counts.
NOT the same event: merely the same topic, the same person doing different things, similar
incidents in different places, or follow-up developments days later.
Return the number of the one candidate describing the same event, or null if none does.
When two candidates could both fit, return null."""


def describe(headline: str, gist: str | None, published: datetime | None) -> str:
    line = f"- {headline}"
    if gist:
        line += f" (gist: {gist})"
    if published:
        line += f" [{published.date().isoformat()}]"
    return line


def confirm_match(
    item: dict[str, Any], candidates: list[list[str]], ledger: Ledger
) -> int | None:
    """Return the index of the matching candidate, or None."""
    blocks_text = []
    for n, lines in enumerate(candidates, start=1):
        blocks_text.append(f"Candidate {n}:\n" + "\n".join(lines[:4]))
    result = structured(
        model=HAIKU,
        system=CONFIRM_SYSTEM,
        user=(
            "Item:\n"
            + describe(item["headline"], (item["entities"] or {}).get("gist"), item["published_at"])
            + "\n\n"
            + "\n\n".join(blocks_text)
            + "\n\nWhich candidate describes the same specific event as the item?"
        ),
        schema=CONFIRM_SCHEMA,
        max_tokens=128,
        ledger=ledger,
        stage="confirm",
    )
    if not result or result.get("match") is None:
        return None
    index = result["match"] - 1
    return index if 0 <= index < len(candidates) else None


def cluster_locality(db: Db, member_ids: list[int]) -> int | None:
    """A cluster gets a district only when every member that carries a
    district signal agrees on it (conservative, like item tagging)."""
    rows = db.conn.execute(
        "SELECT locality_id, entities FROM news_items WHERE id = ANY(%s)",
        (member_ids,),
    ).fetchall()
    districts: set[int] = set()
    for locality_id, entities in rows:
        ids = set((entities or {}).get("district_ids", []))
        if locality_id:
            ids.add(locality_id)
        if len(ids) == 1:
            districts.add(ids.pop())
    return districts.pop() if len(districts) == 1 else None


def run_clustering(
    db: Db, source_id: int, retrieved_at: datetime, ledger: Ledger, report: dict[str, Any]
) -> None:
    since = now_utc() - timedelta(days=WINDOW_DAYS)
    items = [
        {
            "id": r[0], "headline": r[1], "published_at": r[2],
            "locality_id": r[3], "entities": r[4], "cluster_id": r[5],
        }
        for r in db.conn.execute(
            """
            SELECT i.id, i.headline_orig, i.published_at, i.locality_id, i.entities,
                   cc.cluster_id
            FROM news_items i
            LEFT JOIN cluster_coverage cc ON cc.news_item_id = i.id
            WHERE i.entities IS NOT NULL AND i.published_at > %s
              AND i.civic_class IS DISTINCT FROM 'soft'
            ORDER BY i.published_at ASC
            """,
            (since,),
        ).fetchall()
    ]

    clusters: dict[int, dict[str, Any]] = {}
    for item in items:
        if item["cluster_id"] is None:
            continue
        c = clusters.setdefault(
            item["cluster_id"],
            {"members": [], "sig": {"persons": set(), "districts": set(), "strings": set()}},
        )
        c["members"].append(item)
        for k, v in signature(item).items():
            c["sig"][k] |= v

    unclustered = [i for i in items if i["cluster_id"] is None]
    pool: list[dict[str, Any]] = []
    confirms = 0

    for item in unclustered:
        if confirms >= CONFIRM_CAP:
            break
        sig = signature(item)

        # Existing clusters first, then still-unclustered items: one call
        # ranks them all, so a single judgment settles the item.
        cluster_candidates = [
            (cid, c) for cid, c in clusters.items()
            if blocks(sig, c["sig"])
            and any(within_window(item["published_at"], m["published_at"]) for m in c["members"])
        ][:3]
        pool_candidates = [
            other for other in pool
            if blocks(sig, other["sig"])
            and within_window(item["published_at"], other["published_at"])
        ][:3]
        if not cluster_candidates and not pool_candidates:
            item["sig"] = sig
            pool.append(item)
            continue

        described = [
            [
                describe(m["headline"], (m["entities"] or {}).get("gist"), m["published_at"])
                for m in c["members"][-4:]
            ]
            for _cid, c in cluster_candidates
        ] + [
            [describe(o["headline"], (o["entities"] or {}).get("gist"), o["published_at"])]
            for o in pool_candidates
        ]

        confirms += 1
        choice = confirm_match(item, described, ledger)
        if choice is None:
            item["sig"] = sig
            pool.append(item)
            continue

        if choice < len(cluster_candidates):
            cid, c = cluster_candidates[choice]
            db.conn.execute(
                "INSERT INTO cluster_coverage (cluster_id, news_item_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (cid, item["id"]),
            )
            c["members"].append(item)
            for k, v in sig.items():
                c["sig"][k] |= v
            db.conn.execute(
                """
                UPDATE news_clusters
                SET event_time = LEAST(event_time, %s), locality_id = %s, updated_at = now()
                WHERE id = %s
                """,
                (
                    item["published_at"],
                    cluster_locality(db, [m["id"] for m in c["members"]]),
                    cid,
                ),
            )
            report["joined_cluster"] += 1
        else:
            other = pool_candidates[choice - len(cluster_candidates)]
            row = db.conn.execute(
                """
                INSERT INTO news_clusters (event_time, locality_id, source_id, retrieved_at)
                VALUES (%s, %s, %s, %s) RETURNING id
                """,
                (
                    min(item["published_at"], other["published_at"]),
                    cluster_locality(db, [item["id"], other["id"]]),
                    source_id,
                    retrieved_at,
                ),
            ).fetchone()
            assert row is not None
            cid = row[0]
            for member in (other, item):
                db.conn.execute(
                    "INSERT INTO cluster_coverage (cluster_id, news_item_id) VALUES (%s, %s)",
                    (cid, member["id"]),
                )
            clusters[cid] = {
                "members": [other, item],
                "sig": {k: sig[k] | other["sig"][k] for k in sig},
            }
            pool.remove(other)
            report["new_clusters"] += 1

    db.conn.commit()
    report["confirm_calls"] = confirms
    if confirms >= CONFIRM_CAP:
        report["notes"].append(f"merge-confirmation cap ({CONFIRM_CAP}) reached; rest next run")


# ---------------------------------------------------------------------------
# Stage 3 — summaries with citations, spot-check, moderation
# ---------------------------------------------------------------------------

SUMMARY_SCHEMA = obj_schema(
    {
        "title_en": {"type": "string"},
        "title_ta": {"type": "string"},
        "summary_en": {"type": "string"},
        "summary_ta": {"type": "string"},
        "summary_long_en": {"type": "string"},
        "summary_long_ta": {"type": "string"},
        "sources_disagree": {"type": "boolean"},
        "coverage_notes": arr(
            obj_schema(
                {
                    "source": {"type": "integer"},
                    "note_en": {"type": "string"},
                    "note_ta": {"type": "string"},
                }
            )
        ),
    }
)

SUMMARY_SYSTEM = """You write neutral news summaries for Arivom, a Tamil Nadu civic
information platform whose mission is an informed electorate. You get several
outlets' reporting of ONE event, numbered [1], [2], ... and sometimes a block of
Arivom's own sourced records numbered [A1], [A2], ...

WHAT YOU ARE WRITING (read this before the format rules).

You are writing a STORY, not a list of things that happened. A citizen who
reads only your summary should finish it understanding what occurred, why it
matters to them, how it came about, and where it now stands — and should be
able to hold it in their head afterwards.

A set of true sentences in the right order is not yet a story. Every sentence
below is accurate and the summary still fails:

  "A minister moved a resolution in the Assembly. The resolution asks the
   Centre to amend the law. An earlier bill did not receive assent. It was
   moved on the third day of the budget debate."

Four facts, each sitting alone. Nothing tells the reader why the second
sentence follows the first, or what the third has to do with either. They
finish with four facts and no understanding. Write connected prose instead:
each sentence should advance the reader's understanding of the one before it.

THE SHAPE OF THE STORY

1. Open with what happened AND what it would change. Not "a minister moved a
   resolution" but what that resolution would do if it succeeded.
2. Then why it matters, concretely: who is affected, how many, what becomes
   different for them. Use the reporting's number when it gives one.
3. Then how this came about — the previous attempt, the blockage, the ruling,
   the incident that prompted it. This is what turns an isolated occurrence
   into a story a reader can place. Without it you have a bulletin.
4. Then what is genuinely contested, attributed to whoever contests it, with
   the verifiable position beside it where our records allow.
5. Close on where the matter now stands: whose decision comes next, what has
   to happen, by when — as the reporting states it, never invented.

Procedure, personal exchanges and rhetorical jabs are not the story. One short
sentence at most, or leave them out entirely.

If the reporting genuinely contains nothing that changed, say so plainly in
one or two sentences and stop. A short honest summary beats a padded one.

THE TWO WAYS THIS GOES WRONG

1. THE DOCUMENT INVENTORY. When the story is about a document — a resolution,
a bill, a court order, a report, a scheme — do not list what the document
contains. A reader does not need every clause. The tell is the grammatical
subject: if three sentences in a row are about the resolution, the scheme or
the report, you are inventorying, not narrating. Vary what each sentence is
about — what it would change, who it lands on, what came before it, where it
goes next.

  Inventory (wrong):
    "The minister moved a resolution seeking to scrap the levy. The
     resolution says the levy burdens small traders. It cites a 2024 study.
     The resolution also notes an earlier bill was not assented to."

  Story (right):
    "Tamil Nadu asked the Centre on Monday to scrap the levy, which would end
     a charge that around 40,000 small traders in the state currently pay.
     The Assembly tried this once before: an identical bill passed
     unanimously in 2021 and has sat with the President unsigned since, which
     is why the state is using a resolution this time. The demand follows a
     2024 study, cited in the text, finding the levy fell hardest on traders
     turning over under 10 lakh rupees. It now goes to the Centre, which has
     not said when it will respond."

  Same facts, same sources, same neutrality. The second tells a reader why
  the thing exists, what it would do to whom, and where it now sits.

2. THE SPEC SHEET. When the story is about a scheme, a deadline or a
programme, do not just list its parameters. Dates, counts and amounts belong
in the story, but a reader needs to know what they mean: who becomes eligible,
who was left out, what the extension responds to, what a family actually pays.

OPENING AND CLOSING

Open with the CHANGE, never the procedural act. Not "a minister moved a
resolution urging the Centre to abolish X" but "Tamil Nadu asked the Centre
to abolish X, which would mean Y". The act is how it happened; the change is
what happened.

Close on where the matter now stands — whose decision is next, what has to
happen, by when. If the reporting does not say, say where the decision sits,
which the facts usually make plain: a resolution goes to the Centre, a
reserved order goes back to the court, an application window closes on a
date. Never invent a timetable the reporting does not give.

THE LINE YOU DO NOT CROSS

You are making editorial judgments about STRUCTURE: what leads, what context
the reader needs, what is consequential enough to include, what is not worth
their time. That is your job and you should do it with conviction. Ordering
information by consequence is not bias.

You are making NO judgment about SUBSTANCE. Never characterise anyone's
motives. Never assign blame or credit. Never use an adjective that carries a
verdict. Never imply which side is right. Never speculate about what someone
intended or what will happen. Attribute every contested claim to whoever made
it. If you cannot point to the sentence in the reporting that supports a
word, delete the word.

Telling the reader what to conclude is the thing this platform must never do.
Telling them what matters, and in what order, is why they came.

USING ARIVOM'S OWN RECORDS [A1], [A2], ...
When a claim in the reporting touches a fact we already publish, put our record
beside it: "he said the seat was won narrowly [2]; the recorded margin was 1,455
votes [A1]". This is the single most useful thing you can do for a reader.
Rules: cite the anchor with its [A] marker; never contradict an anchor with a
claim presented as fact; where an anchor is labelled self-declared, say
"self-declared" in the sentence; and if no anchor bears on the story, use none.
Anchors are context, never a verdict — do not use them to declare who is right.

Produce:
- title_en and title_ta: short neutral titles naming the event (under 80 characters each).
- summary_en: 2 to 4 short plain sentences, opening with what changed (feed preview).
- summary_ta: the same summary in Tamil. Warm formal register. Simple words average readers know.
- summary_long_en and summary_long_ta: a fuller account, 5 to 8 short sentences,
  same citation and neutrality rules, covering the facts across ALL sources
  (background a reader needs, numbers, who said what, what happens next if stated).
- coverage_notes: for EVERY source [n], one entry {source: n, note_en, note_ta}
  describing in ONE sentence per language what THAT outlet's coverage adds or
  focuses on compared to the others ("adds official casualty figures",
  "carries the minister's full statement", "reports from the scene with
  eyewitness accounts", "matches the shared account with no extra detail").
  Content description ONLY: never words that judge quality, accuracy, or slant.

Hard rules:
- Use only facts present in the provided reporting. Attribute claims, numbers in
  dispute, and allegations to their source ("according to [2]", "X said [1]").
  Never state an allegation as fact.
- Strictly neutral: no opinions, no loaded adjectives, no praise or blame, no speculation.
- Your OWN words only. Never copy sentences. Never quote more than 8 consecutive words.
- Short plain sentences. No em dashes. Use digits for numbers.
- End every sentence with the citation marker(s) [n] of the source(s) supporting
  it, in both languages.
- If sources disagree, say so plainly and cite each side, and set
  sources_disagree to true (else false).
- Rank information by what a citizen needs to know, not by drama.
- Titles obey the same order: name what changed, not who traded remarks."""

CHECK_SCHEMA = obj_schema(
    {
        "claims_supported": {"type": "boolean"},
        "neutral": {"type": "boolean"},
        "tamil_faithful": {"type": "boolean"},
        "citations_valid": {"type": "boolean"},
        # D-040: a summary can be perfectly accurate and still waste a
        # citizen's time. This is a test of ordering, not of viewpoint.
        # Filled in BEFORE the booleans below: naming the subjects makes the
        # reads_as_story judgment a procedure the checker executes rather than
        # an impression it forms. Cheap in tokens, and auditable afterwards.
        "sentence_subjects": arr({"type": "string"}),
        "leads_with_substance": {"type": "boolean"},
        "reads_as_story": {"type": "boolean"},
        "context_supplied": {"type": "boolean"},
        "no_substance_judgment": {"type": "boolean"},
        "theatre_contained": {"type": "boolean"},
        "anchors_used_correctly": {"type": "boolean"},
        "issues": arr({"type": "string"}),
        "moderation": obj_schema(
            {
                "communal": {"type": "boolean"},
                "sub_judice": {"type": "boolean"},
                "allegations_named_person": {"type": "boolean"},
            }
        ),
        "verdict": {"type": "string", "enum": ["pass", "revise"]},
        "feedback": {"type": "string"},
    }
)

CHECK_SYSTEM = """You verify a draft bilingual news summary against source reporting
for Arivom, a Tamil Nadu civic platform with a strict neutrality policy (no
editorializing anywhere, ever).

Check, strictly, across the short summaries, the long summaries, AND the
per-source coverage notes:
1. claims_supported: every factual claim is supported by the sources its [n]
   markers point to; every coverage note accurately describes what that
   source's provided reporting actually contains.
2. neutral: no editorializing, loaded language, unattributed allegations, or
   speculation in either language. Attributed claims ("according to [1]") are
   fine. Coverage notes must be content-descriptive ONLY — any wording that
   judges an outlet's quality, accuracy, or slant fails this check.
3. tamil_faithful: every Tamil text conveys the same content as its English
   counterpart, in genuine Tamil script, warm formal register, simple
   vocabulary, no em dashes.
4. citations_valid: every marker refers to a provided source or anchor; every
   summary sentence carries at least one marker.
5. leads_with_substance: the summary OPENS with what changed or was decided —
   the decision, number, amount, scope or effect — and not with who spoke or
   who criticised whom. A summary that opens "X said" or "X criticised Y"
   fails this, even if every word of it is true. If the reporting genuinely
   contains nothing that changed, a summary that says so plainly in one or two
   sentences PASSES; padding theatre out to full length fails.
6. reads_as_story: the summary is connected prose, not a list of true
   sentences sitting side by side.
   FIRST fill in sentence_subjects: the grammatical subject of each sentence
   of summary_en, in order, as it appears ("the resolution", "residents",
   "the fire"). Do this before you judge, and judge against what you wrote.
   Then FAIL if any of these hold:
     - three or more sentences share the same subject, or refer to the same
       thing through a pronoun ("the resolution ... it ... the resolution");
     - the middle sentences could be reordered without loss;
     - the summary lists what a document contains rather than what it would
       do, to whom, and where it now stands;
     - it lists a scheme's parameters without saying what they mean for the
       people they land on.
   A summary can be entirely accurate and still fail this. Judge whether a
   reader finishes with understanding, not just with facts.
7. context_supplied: the reader is given what turns this occurrence into
   something they can place — the previous attempt, the blockage, the
   ruling, the incident that prompted it, or the number that frames it —
   whenever the reporting or the anchors contain it. A summary that reports
   only today, when the material offered background, fails. It passes if
   the material genuinely had no context to give.
   The close counts too: a summary that never says where the matter now
   stands — whose decision is next, what has to happen — fails this when the
   facts made it plain.
8. no_substance_judgment: the summary orders and frames, and does NOT
   conclude. FAIL any characterisation of motive, any assignment of blame
   or credit, any adjective carrying a verdict, any implication that one
   side is right, and any speculation about intent or outcome. Attribution
   ("according to [2]") is fine and expected. This is the guard on the
   editorial latitude the summary prompt grants: structure is the writer's,
   conclusions are the reader's.
9. theatre_contained: personal exchanges, insults, walkouts, seating and
   similar spectacle do not occupy space a figure, amount or effect should
   hold, and never lead. At most one short closing sentence. Judge the SPACE
   GIVEN, never whether the subject is flattering to anyone.
10. anchors_used_correctly: where Arivom records [A1], [A2] were supplied and
   genuinely bear on a claim, they are used to give the verifiable position;
   anchors are never contradicted by a claim stated as fact; anything labelled
   self-declared is described as self-declared. Using no anchor when none
   applies passes. Anchors must not be used to declare a winner.

Separately, classify the EVENT for the escalation protocol (regardless of summary quality):
- communal: the story touches communal or religious tension.
- sub_judice: the story centres on a matter currently before a court.
- allegations_named_person: the story centres on unverified corruption or
  criminal allegations against a named individual.

verdict "pass" only if checks 1-10 all hold; otherwise "revise" with concrete,
actionable feedback naming the sentence at fault.

Checks 5 to 9 are about what a citizen gets for their time. They are NOT a
licence to prefer one side. Never fail a summary for reporting a fact that is
awkward for anyone, and never ask for a claim to be softened. Structure,
proportion and connectedness only — check 8 is the boundary, and it binds the
summary writer and you equally."""


def members_for_summary(db: Db, session: Any, cluster_id: int) -> list[dict[str, Any]]:
    rows = db.conn.execute(
        """
        SELECT i.id, i.outlet, i.headline_orig, i.lang, i.published_at, i.url
        FROM cluster_coverage cc
        JOIN news_items i ON i.id = cc.news_item_id
        WHERE cc.cluster_id = %s
        ORDER BY i.published_at ASC
        """,
        (cluster_id,),
    ).fetchall()
    members = []
    seen_outlets: set[str] = set()
    for item_id, outlet, headline, lang, published_at, url in rows:
        # One item per outlet in the evidence pack (latest wins by replacing).
        member = {
            "id": item_id, "outlet": outlet, "headline": headline,
            "lang": lang, "published_at": published_at, "url": url,
        }
        if outlet in seen_outlets:
            for i, m in enumerate(members):
                if m["outlet"] == outlet:
                    members[i] = member
                    break
        else:
            members.append(member)
            seen_outlets.add(outlet)
    members = members[:6]
    for m in members:
        excerpt, _status, _image = fetch_excerpt(session, m["url"])
        m["excerpt"] = (excerpt or "")[:1800]
    return members


def evidence_block(members: list[dict[str, Any]]) -> str:
    lines = []
    for n, m in enumerate(members, start=1):
        lines.append(
            f"[{n}] {m['outlet']} ({m['lang']}, "
            f"{m['published_at'].date().isoformat() if m['published_at'] else 'undated'})\n"
            f"Headline: {m['headline']}"
            + (
                f"\nReporting: {m['excerpt']}"
                if m["excerpt"]
                else "\n(only the headline is available)"
            )
        )
    return "\n\n".join(lines)


ANCHOR_MARKER = re.compile(r"\[A(\d+)\]")


def markers_valid(text: str, n_sources: int, n_anchors: int = 0) -> bool:
    """Every sentence must be traceable. Source markers [n] resolve to member
    items; anchor markers [An] resolve to Arivom's own sourced records."""
    found = [int(m) for m in MARKER.findall(text)]
    anchors = [int(m) for m in ANCHOR_MARKER.findall(text)]
    if any(a < 1 or a > n_anchors for a in anchors):
        return False
    return bool(found or anchors) and all(1 <= m <= n_sources for m in found)


def _shape_ok(draft: dict[str, Any], n: int, n_anchors: int = 0) -> bool:
    """Deterministic gate before any model reads the draft — malformed output
    is caught for free rather than spending a check call to discover it."""
    notes_ok = (
        len(draft["coverage_notes"]) == n
        and {note["source"] for note in draft["coverage_notes"]} == set(range(1, n + 1))
        and all(
            has_tamil(note["note_ta"]) and note["note_en"].strip()
            for note in draft["coverage_notes"]
        )
    )
    return bool(
        notes_ok
        and markers_valid(draft["summary_en"], n, n_anchors)
        and markers_valid(draft["summary_ta"], n, n_anchors)
        and markers_valid(draft["summary_long_en"], n, n_anchors)
        and markers_valid(draft["summary_long_ta"], n, n_anchors)
        and has_tamil(draft["summary_ta"])
        and has_tamil(draft["summary_long_ta"])
        and has_tamil(draft["title_ta"])
        and draft["title_en"].strip()
    )


def _check(
    *, model: str, evidence: str, draft: dict[str, Any], ledger: Ledger, effort: str, stage: str
) -> dict[str, Any] | None:
    return structured(
        model=model,
        system=CHECK_SYSTEM,
        user=f"Sources:\n\n{evidence}\n\nDraft:\n{json.dumps(draft, ensure_ascii=False)}",
        schema=CHECK_SCHEMA,
        max_tokens=8000,
        thinking=True,
        effort=effort,
        ledger=ledger,
        stage=stage,
    )


def _moderation_positive(verdict: dict[str, Any] | None) -> bool:
    moderation = (verdict or {}).get("moderation", {})
    return any(
        moderation.get(key)
        for key in ("communal", "sub_judice", "allegations_named_person")
    )


def summarize_clusters(
    db: Db, session: Any, source_id: int, retrieved_at: datetime,
    ledger: Ledger, report: dict[str, Any], only_ids: list[int] | None = None,
) -> None:
    """Summarise clusters whose membership changed.

    `only_ids` narrows the run to specific clusters. It exists because
    reviewing a prompt change means regenerating a fixed sample on identical
    inputs, and the alternative — reaching in and rewriting content_hash to
    fake "unchanged" — depends on reproducing this function's hashing exactly
    and silently regenerates everything when it does not.
    """
    since = now_utc() - timedelta(days=WINDOW_DAYS)
    clusters = db.conn.execute(
        """
        SELECT c.id, c.content_hash,
               (SELECT count(*) FROM cluster_coverage cc WHERE cc.cluster_id = c.id) AS n
        FROM news_clusters c
        WHERE (c.updated_at > %s OR c.retrieved_at > %s)
          AND (%s::bigint[] IS NULL OR c.id = ANY(%s))
        ORDER BY c.event_time DESC
        """,
        (since, since, only_ids, only_ids),
    ).fetchall()

    generated = 0
    for cluster_id, old_hash, n_members in clusters:
        if n_members < 2:
            continue
        member_rows = db.conn.execute(
            """
            SELECT i.id, i.headline_orig FROM cluster_coverage cc
            JOIN news_items i ON i.id = cc.news_item_id
            WHERE cc.cluster_id = %s ORDER BY i.id
            """,
            (cluster_id,),
        ).fetchall()
        content_hash = hashlib.sha256(
            json.dumps(member_rows, ensure_ascii=False, default=str).encode()
        ).hexdigest()[:32]
        if content_hash == old_hash:
            continue
        if generated >= SUMMARY_CAP:
            report["notes"].append(f"summary cap ({SUMMARY_CAP}) reached; rest next run")
            break
        generated += 1

        members = members_for_summary(db, session, cluster_id)
        # Our own sourced records bearing on this story, so the summary can
        # put the verifiable position beside a contested claim (D-040).
        anchors = cluster_anchors(db, cluster_id)
        block = anchor_block(anchors)
        evidence = evidence_block(members) + (f"\n\n{block}" if block else "")
        n = len(members)
        n_anchors = len(anchors)
        if anchors:
            report["anchored"] += 1

        draft = structured(
            model=SONNET, system=SUMMARY_SYSTEM, user=f"Sources:\n\n{evidence}",
            schema=SUMMARY_SCHEMA, max_tokens=5000, ledger=ledger, stage="summary_draft",
        )
        verdict = None
        adjudicated = False

        for attempt in range(2):
            if draft is None:
                break
            if not _shape_ok(draft, n, n_anchors):
                verdict = {
                    "verdict": "revise",
                    "feedback": (
                        "invalid citation markers, missing Tamil, or coverage_notes "
                        "not covering every source exactly once"
                    ),
                }
            else:
                # Routine check: same tier as the draft, shallow effort. It is
                # verification against supplied evidence, not open reasoning.
                verdict = _check(
                    model=SONNET, evidence=evidence, draft=draft, ledger=ledger,
                    effort="low", stage="summary_check",
                )
                # The frontier model has the last word on anything that would
                # LOCK a discussion — moderation is a rights-affecting call, so
                # it never rests on the cheap tier's judgment alone (D-039).
                if _moderation_positive(verdict):
                    adjudicated = True
                    verdict = _check(
                        model=OPUS, evidence=evidence, draft=draft, ledger=ledger,
                        effort="high", stage="summary_adjudicate",
                    ) or verdict
            if verdict is None or verdict["verdict"] == "pass":
                break
            if attempt == 0:
                draft = structured(
                    model=SONNET, system=SUMMARY_SYSTEM,
                    user=(
                        f"Sources:\n\n{evidence}\n\n"
                        f"A previous draft failed review with this feedback; fix it:\n"
                        f"{verdict.get('feedback', '')}\n{'; '.join(verdict.get('issues', []))}"
                    ),
                    schema=SUMMARY_SCHEMA, max_tokens=5000, ledger=ledger,
                    stage="summary_redraft",
                )

        # Withholding is also a consequential call: a citizen loses a story.
        # Before withholding on the cheap tier's word, let the frontier model
        # adjudicate the final draft (D-039).
        if (
            draft is not None
            and not adjudicated
            and verdict is not None
            and verdict["verdict"] != "pass"
            and _shape_ok(draft, n, n_anchors)
        ):
            adjudicated = True
            verdict = _check(
                model=OPUS, evidence=evidence, draft=draft, ledger=ledger,
                effort="high", stage="summary_adjudicate",
            ) or verdict
        if adjudicated:
            report["adjudicated"] += 1

        moderation = (verdict or {}).get("moderation", {})
        lock_category = next(
            (
                cat
                for key, cat in (
                    ("communal", "communal"),
                    ("sub_judice", "sub_judice"),
                    ("allegations_named_person", "allegations"),
                )
                if moderation.get(key)
            ),
            None,
        )

        if draft is not None and verdict is not None and verdict["verdict"] == "pass":
            coverage_notes = [
                {
                    "news_item_id": members[note["source"] - 1]["id"],
                    "note_en": note["note_en"].strip(),
                    "note_ta": note["note_ta"].strip(),
                }
                for note in sorted(draft["coverage_notes"], key=lambda x: x["source"])
            ]
            db.conn.execute(
                """
                UPDATE news_clusters
                SET title_en = %s, title_ta = %s, summary_en = %s, summary_ta = %s,
                    summary_long_en = %s, summary_long_ta = %s,
                    sources_disagree = %s,
                    coverage_notes = %s,
                    citations = %s, anchors = %s, content_hash = %s, review_status = %s,
                    source_id = %s, retrieved_at = %s, updated_at = now(),
                    discussion_locked = discussion_locked OR %s,
                    lock_category = COALESCE(lock_category, %s)
                WHERE id = %s
                """,
                (
                    draft["title_en"].strip(), draft["title_ta"].strip(),
                    draft["summary_en"].strip(), draft["summary_ta"].strip(),
                    draft["summary_long_en"].strip(), draft["summary_long_ta"].strip(),
                    bool(draft["sources_disagree"]),
                    json.dumps(coverage_notes, ensure_ascii=False),
                    json.dumps([m["id"] for m in members]),
                    # Frozen with the summary so an [A n] marker always
                    # resolves to what it actually cited (D-040).
                    json.dumps(
                        [
                            {k: v for k, v in a.items() if k != "retrieved_at"}
                            for a in anchors
                        ],
                        ensure_ascii=False,
                    )
                    if anchors
                    else None,
                    content_hash,
                    # Offline answers did not go through the draft-then-check
                    # chain, so the row must not say they did (pillar 1).
                    "unreviewed" if offline.enabled() else "llm_checked",
                    source_id, retrieved_at,
                    lock_category is not None, lock_category, cluster_id,
                ),
            )
            report["summarized"] += 1
            if lock_category:
                report["locked"] += 1
        else:
            # Withhold rather than publish unchecked (pillar 1 in spirit):
            # keep hash NULL so the next run retries, and say so loudly.
            db.conn.execute(
                "UPDATE news_clusters SET discussion_locked = discussion_locked OR %s, "
                "lock_category = COALESCE(lock_category, %s), updated_at = now() WHERE id = %s",
                (lock_category is not None, lock_category, cluster_id),
            )
            report["summary_failed"] += 1
            print(f"SUMMARY WITHHELD for cluster {cluster_id}: failed spot-check twice")

    db.conn.commit()


# ---------------------------------------------------------------------------


def main() -> None:
    import os

    if offline.enabled():
        # Dev mode (D-039 addendum): answers come from the offline cache, not
        # the API. Refuse production outright — this content is fixture data.
        offline.guard_local_database()
        print("OFFLINE MODE: no API calls; unanswered requests are queued.")
    else:
        require_llm()
        assert llm_available()
    use_batch_api = (
        os.environ.get("ARIVOM_BATCH_API", "1") != "0" and not offline.enabled()
    )
    session = article_session()
    db = Db.connect()
    retrieved_at = now_utc()
    ledger = Ledger(db)

    source_id = db.ensure_source(
        name="Arivom news pipeline (clustering and summaries)",
        url="https://github.com/Aakash-Marthandan/Project-Arivom",
        publisher="Arivom pipeline over tracked outlets' reporting",
        license=None,
        access_mode="api",
        cadence="hourly",
        notes=(
            "DEVELOPMENT FIXTURE RUN (offline mode): summaries were written by "
            "an assistant in the editor, not by the model chain below, and are "
            "recorded review_status='unreviewed'. Never for production. "
            if offline.enabled() else ""
        ) + (
            "Clusters registry outlets' items by event and writes neutral bilingual "
            "summaries with inline citations. Triage, entity and merge judgments: "
            "claude-haiku-4-5; drafts and routine spot-check: claude-sonnet-5; "
            "adjudication of moderation-flagged and check-failing summaries: "
            "claude-opus-5. Article text is read transiently and never stored "
            "(D-022). Summaries failing the spot-check are withheld, never published."
        ),
    )

    report: dict[str, Any] = {
        "triaged": 0, "triaged_soft": 0, "triage_vetoed": 0, "triage_failed": 0,
        "extracted": 0, "extract_failed": 0, "fetch_failed": 0,
        "classified_soft": 0, "class_vetoed": 0,
        "joined_cluster": 0, "new_clusters": 0, "confirm_calls": 0,
        "summarized": 0, "summary_failed": 0, "adjudicated": 0, "locked": 0,
        "anchored": 0,
        "notes": [],
    }

    lexicon = Lexicon(db)
    stopped_early = None
    try:
        collect_pending(db, lexicon, ledger, report)
        triage_items(db, lexicon, ledger, report)
        extract_entities(db, session, lexicon, ledger, report, use_batch_api)
        run_clustering(db, source_id, retrieved_at, ledger, report)
        summarize_clusters(db, session, source_id, retrieved_at, ledger, report)
    except BudgetExhausted as exc:
        # Not a crash: everything already paid for has been committed. Stop
        # cleanly so the next run resumes from here.
        stopped_early = str(exc)

    print("\n=== Cluster run report ===")
    for key, value in report.items():
        if key != "notes":
            print(f"  {key}: {value}")
    for note in report["notes"]:
        print(f"  NOTE: {note}")

    print("\n=== LLM spend ===")
    for line in ledger.report():
        print(line)
    print(f"  this run: ${ledger.spent_this_run:.4f} over {ledger.calls} calls")
    if stopped_early:
        print(f"\n  STOPPED EARLY: {stopped_early}")

    total_clusters = db.conn.execute("SELECT count(*) FROM news_clusters").fetchone()
    with_summary = db.conn.execute(
        "SELECT count(*) FROM news_clusters WHERE summary_en IS NOT NULL"
    ).fetchone()
    assert total_clusters and with_summary
    print(f"  clusters total: {total_clusters[0]}, with checked summaries: {with_summary[0]}")


if __name__ == "__main__":
    main()
