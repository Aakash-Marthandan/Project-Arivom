"""Arivom's own sourced records, assembled for one news cluster (D-040).

The summariser used to see only what outlets reported, so the best it could
do with a contested claim was attribute it: "he said the scheme was dropped".
That is the false-balance failure D-021 exists to reject — scrupulously even
and close to useless to a citizen.

We are, however, sitting on sourced records that bear on exactly these
claims: election results and margins, self-declared affidavit data, and the
district indicators from UDISE, NFHS-5 and JJM. When a story touches one, the
summary can say "he said X; the published record is Y" instead. That is the
whole difference between reporting an argument and informing a voter.

Rules this module exists to keep:

- Anchors are OUR facts, and they arrive with their own provenance. Every
  row carries the source that produced it, so an anchor cited in a summary
  can be traced exactly like any other displayed fact (pillar 1).
- Anchors are context, never a verdict. They are handed to the model as
  material to check claims against; nothing here decides who is right.
- Anchors are actor-blind. We pull the record for whoever the story matched,
  of whatever party, and for the district it is tagged to. There is no path
  where the selection depends on who a story favours (pillar 2).
"""

from __future__ import annotations

import re
from typing import Any

# District indicator keys worth putting next to a claim, with the plain
# wording used in the anchor block. Kept short deliberately: an anchor pack
# that dwarfs the reporting buries the story it is meant to inform.
# Indicators are anchored only when the story is actually about that
# domain. A bus terminus story is not improved by a pupil-teacher ratio, and
# an anchor pack full of irrelevant numbers invites the summariser to reach
# for one. Keyed by domain prefix; the subject test is bilingual.
INDICATOR_DOMAINS: dict[str, re.Pattern[str]] = {
    "education": re.compile(
        r"school|student|teacher|educat|classroom|enrol|dropout|"
        r"பள்ளி|மாணவ|ஆசிரிய|கல்வி",
        re.IGNORECASE | re.UNICODE,
    ),
    "health": re.compile(
        r"health|hospital|birth|nutrit|anaem|stunt|clinic|disease|"
        r"சுகாதார|மருத்துவ|பிறப்பு|ஊட்டச்சத்து",
        re.IGNORECASE | re.UNICODE,
    ),
    "water": re.compile(
        r"water|tap|drinking|supply|drought|"
        r"தண்ணீர்|குடிநீர்|நீர்|வறட்சி",
        re.IGNORECASE | re.UNICODE,
    ),
}

INDICATOR_LABELS: dict[str, str] = {
    "education.schools": "schools",
    "education.teachers": "teachers",
    "education.ptr": "pupil-teacher ratio",
    "education.enrolment": "school enrolment",
    "health.institutional_births": "institutional births",
    "health.child_stunting": "children stunted",
    "health.anaemia_children": "children with anaemia",
    "water.rural_tap_percent": "rural households with tap water",
}

# Self-declared affidavit facts are DE-EMPHASISED by owner directive (D-016):
# one tap away under a neutral disclosure, never removed and never
# sensationalised. Injecting them into every evidence pack would push the
# summariser to reach for wealth and criminal cases in stories that are not
# about them — emphasis by the back door. So they are anchored only when the
# story itself concerns them, decided by SUBJECT keywords below, never by who
# the person is.
SENSITIVE_LABELS: dict[str, str] = {
    "declared_assets": "declared assets",
    "declared_liabilities": "declared liabilities",
    "criminal_cases": "declared criminal cases",
}

SENSITIVE_SUBJECT = re.compile(
    r"asset|wealth|crore|corrupt|bribe|disproportionate|income tax|raid|"
    r"chargesheet|criminal case|conviction|acquit|"
    r"சொத்து|ஊழல்|லஞ்சம்|வருமான வரி|சோதனை|குற்றவழக்கு|தண்டனை",
    re.IGNORECASE | re.UNICODE,
)


def cluster_anchors(db: Any, cluster_id: int, limit: int = 8) -> list[dict[str, Any]]:
    """Our own sourced facts bearing on this cluster.

    Returns rows of {label, value, source_name, retrieved_at, self_declared}.
    Empty is a perfectly normal result: most stories touch nothing we hold,
    and inventing an anchor would be far worse than having none.
    """
    anchors: list[dict[str, Any]] = []

    # 1. Who the story is really about.
    #
    # A person is only anchored when at least TWO member items matched them.
    # The lexicon deliberately matches short names ("Vijay", "Stalin"), which
    # is right for tagging and wrong here: a passing mention of a resident
    # called "P Raj Kumar" once matched a sitting MP, and a single loose match
    # would have put that MP's declared assets beside a bus terminus story.
    # Two outlets independently naming the same person is a strong signal they
    # are the subject; one mention is not worth the risk.
    people = db.conn.execute(
        """
        SELECT p.id, p.name_en, l.name_en AS seat, l.level::text AS seat_level,
               f.value AS result, s.name AS source_name, f.retrieved_at,
               count(DISTINCT i.id) AS mentions
        FROM cluster_coverage cc
        JOIN news_items i ON i.id = cc.news_item_id,
             jsonb_array_elements(i.entities -> 'persons') AS pe
        JOIN persons p ON p.id = (pe ->> 'person_id')::bigint
        JOIN tenures t ON t.person_id = p.id AND t.end_date IS NULL AND t.status = 'active'
        JOIN offices o ON o.id = t.office_id
        JOIN localities l ON l.id = o.locality_id
        LEFT JOIN facts f ON f.subject_type = 'locality' AND f.subject_id = l.id
          AND f.key = 'election_result'
        LEFT JOIN sources s ON s.id = f.source_id
        WHERE cc.cluster_id = %s AND pe ? 'person_id'
        GROUP BY p.id, p.name_en, l.name_en, l.level, f.value, s.name, f.retrieved_at
        HAVING count(DISTINCT i.id) >= 2
        ORDER BY count(DISTINCT i.id) DESC
        LIMIT 3
        """,
        (cluster_id,),
    ).fetchall()

    for _pid, name, seat, seat_level, result, source_name, retrieved, _n in people:
        if not result:
            continue
        margin = result.get("margin") if isinstance(result, dict) else None
        share = result.get("vote_share") if isinstance(result, dict) else None
        detail = ", ".join(
            part for part in (
                f"won by {margin} votes" if margin is not None else None,
                f"{share} vote share" if share is not None else None,
            ) if part
        )
        anchors.append({
            "label": f"{name}, sitting member for {seat} ({seat_level.upper()})",
            "value": detail or "seat held",
            "source_name": source_name or "Arivom civic record",
            "retrieved_at": retrieved,
            "self_declared": False,
        })

    # 2. Self-declared affidavit facts, ONLY when the story is about them
    #    (D-016 de-emphasis; see SENSITIVE_LABELS above). The test is the
    #    story's own subject matter, never who the person is or what they
    #    declared — a low-asset and a high-asset member are treated alike.
    if people:
        if SENSITIVE_SUBJECT.search(_subject_text(db, cluster_id)):
            person_ids = [row[0] for row in people]
            for key, label in SENSITIVE_LABELS.items():
                for name, value, src, retrieved in db.conn.execute(
                    """
                    SELECT p.name_en, f.value, s.name, f.retrieved_at
                    FROM facts f
                    JOIN persons p ON p.id = f.subject_id
                    LEFT JOIN sources s ON s.id = f.source_id
                    WHERE f.subject_type = 'person' AND f.subject_id = ANY(%s)
                      AND f.key = %s
                    LIMIT 3
                    """,
                    (person_ids, key),
                ).fetchall():
                    anchors.append({
                        "label": f"{name}, {label}",
                        "value": _plain(value),
                        "source_name": src or "affidavit via MyNeta",
                        "retrieved_at": retrieved,
                        "self_declared": True,
                    })

    # 3. Indicators for the district the cluster is tagged to.
    district = db.conn.execute(
        "SELECT locality_id FROM news_clusters WHERE id = %s", (cluster_id,)
    ).fetchone()
    wanted = [
        key for key in INDICATOR_LABELS
        if INDICATOR_DOMAINS[key.split(".", 1)[0]].search(_subject_text(db, cluster_id))
    ]
    if district and district[0] and wanted:
        for key, value, src, retrieved, place in db.conn.execute(
            """
            SELECT f.key, f.value, s.name, f.retrieved_at, l.name_en
            FROM facts f
            JOIN localities l ON l.id = f.subject_id
            LEFT JOIN sources s ON s.id = f.source_id
            WHERE f.subject_type = 'locality' AND f.subject_id = %s AND f.key = ANY(%s)
            """,
            (district[0], wanted),
        ).fetchall():
            anchors.append({
                "label": f"{place}, {INDICATOR_LABELS[key]}",
                "value": _plain(value),
                "source_name": src or "Arivom data indicator",
                "retrieved_at": retrieved,
                "self_declared": False,
            })

    return anchors[:limit]


def _subject_text(db: Any, cluster_id: int) -> str:
    """Every headline and gist in the cluster, for subject gating."""
    rows = db.conn.execute(
        """
        SELECT i.headline_orig || ' ' || COALESCE(i.entities ->> 'gist', '')
        FROM cluster_coverage cc JOIN news_items i ON i.id = cc.news_item_id
        WHERE cc.cluster_id = %s
        """,
        (cluster_id,),
    ).fetchall()
    return " ".join(r[0] or "" for r in rows)


def _plain(value: Any) -> str:
    """Flatten a fact's JSON value to something a summariser can quote."""
    if isinstance(value, dict):
        series = value.get("series")
        if isinstance(series, list) and series:
            latest = series[-1]
            year = latest.get("year", "")
            parts = [
                f"{k} {v}" for k, v in latest.items()
                if k != "year" and v is not None
            ]
            return f"{', '.join(parts)} ({year})" if parts else str(year)
        for key in ("display", "approx", "value", "total", "percent", "count"):
            if key in value:
                return str(value[key])
        # Internal bookkeeping never belongs in text a summariser may quote.
        skip = {"self_declared", "source", "retrieved_at", "confidence"}
        return ", ".join(
            f"{k} {v}" for k, v in list(value.items())[:3] if k not in skip
        )
    return str(value)


def anchor_block(anchors: list[dict[str, Any]]) -> str:
    """The evidence-pack section for our own records, marked [A1], [A2], ..."""
    if not anchors:
        return ""
    lines = [
        "Arivom's own sourced records. These are OUR published facts, not the "
        "outlets' reporting. Use them to give a citizen the verifiable position "
        "behind a claim. Cite them as [A1], [A2] and so on. Do not use one "
        "unless it genuinely bears on this story.",
        "",
    ]
    for n, a in enumerate(anchors, start=1):
        declared = " (self-declared)" if a["self_declared"] else ""
        lines.append(f"[A{n}] {a['label']}{declared}: {a['value']} — source: {a['source_name']}")
    return "\n".join(lines)
