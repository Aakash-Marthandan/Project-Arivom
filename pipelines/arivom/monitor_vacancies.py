"""Daily vacancy/by-election signal monitor (M5, DESIGN.md §6).

Detection only, never decision: this monitor scans discovery feeds for
Tamil Nadu by-election and vacancy news, records NEW items as unreviewed
`vacancy_signal` facts, and updates a `vacancy_monitor_run` record that
powers the tracker page's "last checked" timestamp.

A signal NEVER flips a seat's status. The only write path for status
changes is the human-curated, per-entry-cited seed applied by
import-vacancies (name-validated against the seated member). This is the
"human confirmation before status flip" required by DESIGN.md §6.

Sources: Google News RSS (English + Tamil queries) as a discovery aid,
exactly the role DESIGN.md §4E assigns it. The ECI portal itself is a JS
application without a stable public feed; its press-release page is
attempted and its reachability recorded honestly in the run record.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Any

from .common import Db, has_tamil, http_session, now_utc

FEEDS = [
    {
        "name": "google-news-en",
        "url": (
            "https://news.google.com/rss/search?"
            "q=%22Tamil%20Nadu%22%20(by-election%20OR%20bypoll%20OR%20%22vacant%20seat%22"
            "%20OR%20%22election%20commission%22%20resignation)&hl=en-IN&gl=IN&ceid=IN:en"
        ),
    },
    {
        "name": "google-news-ta",
        "url": (
            "https://news.google.com/rss/search?"
            "q=%E0%AE%87%E0%AE%9F%E0%AF%88%E0%AE%A4%E0%AF%8D%E0%AE%A4%E0%AF%87%E0%AE%B0%E0%AF%8D"
            "%E0%AE%A4%E0%AE%B2%E0%AF%8D%20OR%20%E0%AE%95%E0%AE%BE%E0%AE%B2%E0%AE%BF%E0%AE%AF"
            "%E0%AE%BF%E0%AE%9F%E0%AE%AE%E0%AF%8D&hl=ta&gl=IN&ceid=IN:ta"
        ),
    },
]
ECI_PRESS_URL = "https://www.eci.gov.in/files/category/11-press-releases/"

# A by-election mention is a signal on its own; vacancy/resignation words
# only count in an assembly context (otherwise every job-vacancy story about
# காலியிடங்கள் would flood the review queue).
BYPOLL = re.compile(r"by-?election|by-?poll|இடைத்தேர்தல்", re.IGNORECASE)
VACANCY = re.compile(r"vacan|resign|காலியிட|பதவி விலக", re.IGNORECASE)
CONTEXT = re.compile(
    r"assembly|constituency|\bMLA\b|\bseat\b|சட்டமன்ற|தொகுதி|எம்\.?\s?எல்\.?\s?ஏ",
    re.IGNORECASE,
)


def is_signal(title: str) -> bool:
    return bool(BYPOLL.search(title) or (VACANCY.search(title) and CONTEXT.search(title)))


def fetch_feed(session: Any, url: str) -> list[dict[str, str]]:
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    items = []
    for item in root.iter("item"):
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "url": (item.findtext("link") or "").strip(),
                "published": (item.findtext("pubDate") or "").strip(),
            }
        )
    return items


def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    monitor_source = db.ensure_source(
        name="Vacancy monitor (Google News discovery feeds)",
        url="https://news.google.com/",
        publisher="Arivom pipeline over Google News RSS",
        license=None,
        access_mode="scrape",
        notes=(
            "Discovery aid only (DESIGN.md §4E): raises unreviewed signals about TN "
            "by-election and vacancy news for human review. Signals never change seat "
            "status; the curated, cited seed in import-vacancies is the only write path."
        ),
    )

    state_row = db.conn.execute(
        "SELECT id FROM localities WHERE level = 'state' AND lgd_code = '33'"
    ).fetchone()
    assert state_row is not None
    state_id = state_row[0]

    # AC names (both scripts) for tagging which constituencies a signal mentions.
    ac_names = db.conn.execute(
        "SELECT eci_code, name_en, name_ta FROM localities WHERE level = 'ac'"
    ).fetchall()

    known = {
        row[0]
        for row in db.conn.execute(
            "SELECT key FROM facts WHERE subject_type='locality' AND subject_id=%s "
            "AND key LIKE 'vacancy_signal:%%'",
            (state_id,),
        )
    }

    run_report: list[dict[str, Any]] = []
    new_signals = 0

    for feed in FEEDS:
        entry: dict[str, Any] = {"name": feed["name"], "ok": False, "items": 0, "new": 0}
        try:
            items = fetch_feed(session, feed["url"])
            entry["ok"] = True
            entry["items"] = len(items)
        except Exception as exc:  # noqa: BLE001 — record failure, keep monitoring
            entry["error"] = str(exc)[:200]
            run_report.append(entry)
            continue

        for item in items:
            if not item["url"] or not is_signal(item["title"]):
                continue
            digest = hashlib.sha256(item["url"].encode()).hexdigest()[:12]
            key = f"vacancy_signal:{digest}"
            if key in known:
                continue
            mentioned = [
                code
                for code, en, ta in ac_names
                if re.search(rf"\b{re.escape(en)}\b", item["title"], re.IGNORECASE)
                or (has_tamil(item["title"]) and ta in item["title"])
            ]
            db.upsert_fact(
                subject_type="locality",
                subject_id=state_id,
                key=key,
                value={
                    "title": item["title"],
                    "url": item["url"],
                    "published": item["published"],
                    "feed": feed["name"],
                    "mentioned_acs": mentioned,
                },
                source_id=monitor_source,
                retrieved_at=retrieved_at,
                extraction_method="scrape",
                confidence=0.5,
                review_status="unreviewed",
            )
            known.add(key)
            new_signals += 1
            entry["new"] += 1
            print(f"NEW SIGNAL [{feed['name']}]: {item['title'][:110]}")
        run_report.append(entry)

    # Record ECI portal reachability honestly (JS app, no stable feed).
    eci_entry: dict[str, Any] = {"name": "eci-press-page", "ok": False}
    try:
        resp = session.get(ECI_PRESS_URL, timeout=30)
        eci_entry["ok"] = resp.status_code == 200
        eci_entry["note"] = "JS application; no machine-readable listing"
    except Exception as exc:  # noqa: BLE001
        eci_entry["error"] = str(exc)[:200]
    run_report.append(eci_entry)

    db.upsert_fact(
        subject_type="locality",
        subject_id=state_id,
        key="vacancy_monitor_run",
        value={"checked_at": retrieved_at.isoformat(), "sources": run_report},
        source_id=monitor_source,
        retrieved_at=retrieved_at,
        extraction_method="scrape",
        confidence=1.0,
    )
    db.conn.commit()

    print("\n=== Vacancy monitor report ===")
    for entry in run_report:
        print(f"  {entry}")
    print(f"new signals: {new_signals}")
    if new_signals:
        print(
            "Review the signals above; confirmed changes go into "
            "pipelines/data/vacancies_2026.json and are applied by import-vacancies."
        )


if __name__ == "__main__":
    main()
