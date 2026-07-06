"""News clustering, neutral bilingual summaries, coverage (M7, DESIGN §7).

Three stages, all offline, all idempotent, all disk-cached:

1. ENTITY EXTRACTION — per new item: deterministic match against our own
   bilingual lexicon (persons, districts, parties from the database), plus
   a cheap-model pass over the headline and a transiently fetched article
   excerpt (D-022: read, never stored). Result lands in news_items.entities.

2. CLUSTERING — incremental: an unclustered item joins an existing cluster
   (or pairs with another unclustered item) only when they share strong
   entities within a 72h window AND a cheap-model judgment confirms they
   describe the same specific event. Clusters materialize at >= 2 items;
   single-source stories stay plain items (D-022).

3. SUMMARIES — for clusters whose membership changed: a mid-tier model
   drafts a neutral bilingual title + summary with inline [n] citations
   from the members' reporting; a frontier model spot-checks claim
   support, neutrality, Tamil register and citations, and classifies the
   event for the escalation protocol (communal / sub judice / allegations
   -> discussion_locked + lock_category; the pipeline only ever locks,
   never unlocks). One revise cycle; a failing summary is withheld and
   reported, never published unchecked.

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

from .articles import fetch_excerpt
from .common import Db, has_tamil, http_session, norm_name, now_utc
from .llm import HAIKU, OPUS, SONNET, arr, llm_available, obj_schema, require_llm, structured
from .poll_news import EN_DISTRICT_ALIASES, TA_DISTRICT_ALIASES

WINDOW_DAYS = 7          # working set: items/clusters from the last week
PAIR_WINDOW_H = 72       # max time gap for two items to be the same event
EXTRACT_CAP = 300        # entity extractions per run (backlog is reported)
CONFIRM_CAP = 250        # merge confirmations per run
SUMMARY_CAP = 40         # summary generations per run

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
# Stage 1 — entity extraction
# ---------------------------------------------------------------------------

EXTRACT_SCHEMA = obj_schema(
    {
        "persons": arr({"type": "string"}),
        "places": arr({"type": "string"}),
        "organizations": arr({"type": "string"}),
        "gist_en": {"type": "string"},
        "department": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    }
)

EXTRACT_SYSTEM = """You extract entities from Tamil Nadu news items for a civic data platform.
Given a headline (Tamil or English) and possibly an article excerpt, return:
- persons: full names of people mentioned (as written, do not translate or transliterate).
- places: cities, towns, districts, localities mentioned (as written).
- organizations: parties, government bodies, companies, institutions (as written).
- gist_en: what specifically happened, in your OWN words, in English, at most 15 words.
- department: the ONE Tamil Nadu government department the story chiefly concerns,
  named in English (for example "School Education", "Highways", "Health",
  "Municipal Administration"), or null when no department clearly applies.
Be precise; include only entities actually present. The gist must be neutral and factual."""


def extract_entities(db: Db, session: Any, lexicon: Lexicon, report: dict[str, Any]) -> None:
    rows = db.conn.execute(
        """
        SELECT id, headline_orig, url, outlet, lang
        FROM news_items
        WHERE entities IS NULL AND created_at > now() - make_interval(days => %s)
        ORDER BY published_at DESC
        LIMIT %s
        """,
        (WINDOW_DAYS, EXTRACT_CAP + 1),
    ).fetchall()
    backlog = len(rows) > EXTRACT_CAP
    rows = rows[:EXTRACT_CAP]

    for item_id, headline, url, _outlet, _lang in rows:
        excerpt, fetch_status = fetch_excerpt(session, url)
        user = f"Headline: {headline}"
        if excerpt:
            user += f"\n\nArticle excerpt:\n{excerpt}"
        result = structured(
            model=HAIKU, system=EXTRACT_SYSTEM, user=user,
            schema=EXTRACT_SCHEMA, max_tokens=1024,
        )
        if result is None:
            report["extract_failed"] += 1
            continue

        person_hits = lexicon.persons_in(headline)
        for name in result["persons"]:
            pid = lexicon.match_person(name)
            if pid is not None:
                person_hits.setdefault(pid, name)
        district_ids = {
            did
            for place in result["places"]
            if (did := lexicon.match_district(place)) is not None
        }
        entities = {
            "persons": [
                {"name": name, "person_id": pid} for pid, name in person_hits.items()
            ]
            + [
                {"name": n}
                for n in result["persons"]
                if lexicon.match_person(n) is None
            ],
            "places": result["places"],
            "orgs": result["organizations"],
            "district_ids": sorted(district_ids),
            "gist": result["gist_en"][:200],
            # Loose-matched to /government department cards at display time
            # (D-019: source-verbatim names differ per locale).
            "department": result["department"],
        }
        db.conn.execute(
            "UPDATE news_items SET entities = %s, fetch_status = %s WHERE id = %s",
            (json.dumps(entities, ensure_ascii=False), fetch_status, item_id),
        )
        report["extracted"] += 1
        if fetch_status != "fetched":
            report["fetch_failed"] += 1

    db.conn.commit()
    if backlog:
        report["notes"].append(f"extraction backlog beyond the {EXTRACT_CAP}-item cap")


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


CONFIRM_SCHEMA = obj_schema({"same_event": {"type": "boolean"}})

CONFIRM_SYSTEM = """You judge whether news items describe the SAME SPECIFIC EVENT for clustering.
Same event = the same concrete occurrence: one incident, one announcement, one decision,
one meeting. Coverage of the same event by different outlets, in Tamil or English, counts.
NOT the same event: merely the same topic, the same person doing different things, similar
incidents in different places, or follow-up developments days later."""


def describe(headline: str, gist: str | None, published: datetime | None) -> str:
    line = f"- {headline}"
    if gist:
        line += f" (gist: {gist})"
    if published:
        line += f" [{published.date().isoformat()}]"
    return line


def confirm_same_event(item: dict[str, Any], other_lines: list[str]) -> bool:
    result = structured(
        model=HAIKU,
        system=CONFIRM_SYSTEM,
        user=(
            "Item A:\n"
            + describe(item["headline"], (item["entities"] or {}).get("gist"), item["published_at"])
            + "\n\nItem/cluster B:\n"
            + "\n".join(other_lines[:4])
            + "\n\nDo A and B describe the same specific event?"
        ),
        schema=CONFIRM_SCHEMA,
        max_tokens=64,
    )
    return bool(result and result["same_event"])


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


def run_clustering(db: Db, source_id: int, retrieved_at: datetime, report: dict[str, Any]) -> None:
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
        sig = signature(item)
        merged = False

        # Existing clusters first (newest members shown to the judge).
        candidates = [
            (cid, c) for cid, c in clusters.items()
            if blocks(sig, c["sig"])
            and any(within_window(item["published_at"], m["published_at"]) for m in c["members"])
        ]
        for cid, c in candidates[:3]:
            if confirms >= CONFIRM_CAP:
                break
            confirms += 1
            lines = [
                describe(m["headline"], (m["entities"] or {}).get("gist"), m["published_at"])
                for m in c["members"][-4:]
            ]
            if confirm_same_event(item, lines):
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
                    SET event_time = LEAST(event_time, %s), locality_id = %s,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        item["published_at"],
                        cluster_locality(db, [m["id"] for m in c["members"]]),
                        cid,
                    ),
                )
                report["joined_cluster"] += 1
                merged = True
                break
        if merged:
            continue

        # Then other still-unclustered items: a confirmed pair births a cluster.
        for other in pool:
            if confirms >= CONFIRM_CAP:
                break
            if not blocks(sig, other["sig"]):
                continue
            if not within_window(item["published_at"], other["published_at"]):
                continue
            confirms += 1
            other_line = describe(
                other["headline"], (other["entities"] or {}).get("gist"), other["published_at"]
            )
            if confirm_same_event(item, [other_line]):
                row = db.conn.execute(
                    """
                    INSERT INTO news_clusters
                      (event_time, locality_id, source_id, retrieved_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
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
                merged = True
                break
        if not merged:
            item["sig"] = sig
            pool.append(item)

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
    }
)

SUMMARY_SYSTEM = """You write neutral news summaries for Arivom, a Tamil Nadu civic
information platform whose mission is an informed electorate. You get several
outlets' reporting of ONE event, numbered [1], [2], ...

Produce:
- title_en and title_ta: short neutral titles naming the event (under 80 characters each).
- summary_en: 2 to 4 short plain sentences describing what happened.
- summary_ta: the same summary in Tamil. Warm formal register. Simple words average readers know.

Hard rules:
- Use only facts present in the provided reporting. Attribute claims, numbers in
  dispute, and allegations to their source ("according to [2]", "X said [1]").
  Never state an allegation as fact.
- Strictly neutral: no opinions, no loaded adjectives, no praise or blame, no speculation.
- Your OWN words only. Never copy sentences. Never quote more than 8 consecutive words.
- Short plain sentences. No em dashes. Use digits for numbers.
- End every sentence with the citation marker(s) [n] of the source(s) supporting
  it, in both languages.
- If sources disagree, say so plainly and cite each side.
- Rank information by what a citizen needs to know, not by drama."""

CHECK_SCHEMA = obj_schema(
    {
        "claims_supported": {"type": "boolean"},
        "neutral": {"type": "boolean"},
        "tamil_faithful": {"type": "boolean"},
        "citations_valid": {"type": "boolean"},
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

Check, strictly:
1. claims_supported: every factual claim in BOTH summaries is supported by the
   sources its [n] markers point to.
2. neutral: no editorializing, loaded language, unattributed allegations, or
   speculation in either language. Attributed claims ("according to [1]") are fine.
3. tamil_faithful: the Tamil summary conveys the same content as the English one,
   in genuine Tamil script, warm formal register, simple vocabulary, no em dashes.
4. citations_valid: every marker refers to a provided source; every sentence
   carries at least one marker.

Separately, classify the EVENT for the escalation protocol (regardless of summary quality):
- communal: the story touches communal or religious tension.
- sub_judice: the story centres on a matter currently before a court.
- allegations_named_person: the story centres on unverified corruption or
  criminal allegations against a named individual.

verdict "pass" only if checks 1-4 all hold; otherwise "revise" with concrete,
actionable feedback."""


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
        excerpt, _status = fetch_excerpt(session, m["url"])
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


def markers_valid(text: str, n_sources: int) -> bool:
    found = [int(m) for m in MARKER.findall(text)]
    return bool(found) and all(1 <= m <= n_sources for m in found)


def summarize_clusters(
    db: Db, session: Any, source_id: int, retrieved_at: datetime, report: dict[str, Any]
) -> None:
    since = now_utc() - timedelta(days=WINDOW_DAYS)
    clusters = db.conn.execute(
        """
        SELECT c.id, c.content_hash,
               (SELECT count(*) FROM cluster_coverage cc WHERE cc.cluster_id = c.id) AS n
        FROM news_clusters c
        WHERE c.updated_at > %s OR c.retrieved_at > %s
        ORDER BY c.event_time DESC
        """,
        (since, since),
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
        evidence = evidence_block(members)
        n = len(members)

        draft = structured(
            model=SONNET, system=SUMMARY_SYSTEM,
            user=f"Sources:\n\n{evidence}", schema=SUMMARY_SCHEMA, max_tokens=3000,
        )
        verdict = None
        for attempt in range(2):
            if draft is None:
                break
            if not (
                markers_valid(draft["summary_en"], n)
                and markers_valid(draft["summary_ta"], n)
                and has_tamil(draft["summary_ta"])
                and has_tamil(draft["title_ta"])
                and draft["title_en"].strip()
            ):
                verdict = {
                    "verdict": "revise",
                    "feedback": "invalid citation markers or missing Tamil",
                }
            else:
                verdict = structured(
                    model=OPUS, system=CHECK_SYSTEM,
                    user=(
                        f"Sources:\n\n{evidence}\n\nDraft:\n{json.dumps(draft, ensure_ascii=False)}"
                    ),
                    schema=CHECK_SCHEMA, max_tokens=8000, thinking=True,
                )
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
                    schema=SUMMARY_SCHEMA, max_tokens=3000,
                )

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
            db.conn.execute(
                """
                UPDATE news_clusters
                SET title_en = %s, title_ta = %s, summary_en = %s, summary_ta = %s,
                    citations = %s, content_hash = %s, review_status = 'llm_checked',
                    source_id = %s, retrieved_at = %s, updated_at = now(),
                    discussion_locked = discussion_locked OR %s,
                    lock_category = COALESCE(lock_category, %s)
                WHERE id = %s
                """,
                (
                    draft["title_en"].strip(), draft["title_ta"].strip(),
                    draft["summary_en"].strip(), draft["summary_ta"].strip(),
                    json.dumps([m["id"] for m in members]),
                    content_hash, source_id, retrieved_at,
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
    require_llm()
    assert llm_available()
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    source_id = db.ensure_source(
        name="Arivom news pipeline (clustering and summaries)",
        url="https://github.com/Aakash-Marthandan/Project-Arivom",
        publisher="Arivom pipeline over tracked outlets' reporting",
        license=None,
        access_mode="api",
        notes=(
            "Clusters registry outlets' items by event and writes neutral bilingual "
            "summaries with inline citations. Drafts: claude-sonnet-5; entity/merge "
            "judgments: claude-haiku-4-5; spot-check and escalation classification: "
            "claude-opus-4-8. Article text is read transiently and never stored "
            "(D-022). Summaries failing the spot-check are withheld, never published."
        ),
    )

    report: dict[str, Any] = {
        "extracted": 0, "extract_failed": 0, "fetch_failed": 0,
        "joined_cluster": 0, "new_clusters": 0, "confirm_calls": 0,
        "summarized": 0, "summary_failed": 0, "locked": 0, "notes": [],
    }

    lexicon = Lexicon(db)
    extract_entities(db, session, lexicon, report)
    run_clustering(db, source_id, retrieved_at, report)
    summarize_clusters(db, session, source_id, retrieved_at, report)

    print("\n=== Cluster run report ===")
    for key, value in report.items():
        if key != "notes":
            print(f"  {key}: {value}")
    for note in report["notes"]:
        print(f"  NOTE: {note}")

    total_clusters = db.conn.execute("SELECT count(*) FROM news_clusters").fetchone()
    with_summary = db.conn.execute(
        "SELECT count(*) FROM news_clusters WHERE summary_en IS NOT NULL"
    ).fetchone()
    assert total_clusters and with_summary
    print(f"  clusters total: {total_clusters[0]}, with checked summaries: {with_summary[0]}")


if __name__ == "__main__":
    main()
