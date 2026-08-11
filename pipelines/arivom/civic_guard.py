"""A veto over cheap-model triage, built from data we already hold (D-039).

The headline-only triage in stage 0 is a cost measure, and a cheap model
judging a headline in isolation will occasionally be wrong. One direction of
error is harmless (a non-civic item gets read anyway, costing a fraction of a
cent). The other direction removes civic news from a citizen's feed, which is
the one thing this project must not do.

So triage is never trusted on its own. Before an item is set aside it is
checked against two things Arivom already knows, at no API cost:

1. The published civic-subject rubric (D-037) — the same bilingual keyword
   classes the feed ranks by, mirrored from src/lib/civic-rank.ts. Keep the
   two in sync; both are described on /methodology.
2. Our own representative lexicon — a headline naming a sitting MLA, MP or
   minister is civic by definition, whatever the subject looks like.

On pillar 2, since (2) matches on person names: this is not actor-based
tilt and cannot become it. The lexicon is every sitting representative in
the database, of every party, applied uniformly, and the only thing a
match can do is keep a story that would otherwise have been dropped. It
never boosts, never buries, never orders. D-037's rule that the RANKING
rubric carries no party or person names is untouched — CIVIC_SUBJECTS
below is subjects only, and it is the part that feeds ranking.

Either match vetoes the removal. This is deliberately asymmetric: the guard
can only ever keep a story, never remove one.
"""

from __future__ import annotations

import re
from typing import Any

# Mirrors CIVIC_SUBJECTS in src/lib/civic-rank.ts (D-037). Subjects only —
# party and person names never appear here, and never will (pillar 2).
CIVIC_SUBJECTS: list[re.Pattern[str]] = [
    # Elections and by-elections
    re.compile(
        r"தேர்தல்|வாக்குப்பதிவு|வாக்காளர்|வேட்பாளர்|by-?election|election|polling|voter",
        re.IGNORECASE | re.UNICODE,
    ),
    # Courts and their orders
    re.compile(
        r"நீதிமன்ற|தீர்ப்பு|சிபிஐ|அமலாக்க|supreme court|high court|verdict|judgment|tribunal",
        re.IGNORECASE | re.UNICODE,
    ),
    # Legislature and government decisions
    re.compile(
        r"சட்டமன்ற|சட்டப்பேரவை|மசோதா|அரசாணை|அமைச்சரவை|அமைச்சர்|"
        r"assembly|legislature|ordinance|cabinet|government order|minister",
        re.IGNORECASE | re.UNICODE,
    ),
    # Public safety and weather alerts
    re.compile(
        r"வெள்ளம்|புயல்|கனமழை|எச்சரிக்கை|வெப்பஅலை|வெடிவிபத்து|"
        r"flood|cyclone|heavy rain|red alert|heatwave|outbreak",
        re.IGNORECASE | re.UNICODE,
    ),
    # Household economics
    re.compile(
        r"விலை உயர்வு|ரேஷன்|மின்கட்டண|சொத்துவரி|"
        r"price hike|ration|tariff|fuel price|property tax",
        re.IGNORECASE | re.UNICODE,
    ),
]


def matches_civic_subject(headline: str) -> bool:
    return any(pattern.search(headline) for pattern in CIVIC_SUBJECTS)


def protected(headline: str, lexicon: Any) -> bool:
    """True when this headline must not be set aside by triage."""
    return bool(matches_civic_subject(headline) or lexicon.persons_in(headline))
