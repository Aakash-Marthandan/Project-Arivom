"""Transient article reading for clustering and summaries (M7, D-022).

The owner-approved posture: the pipeline may FETCH and READ an article at
run time to extract entities and write an own-words summary, but article
text is never stored in the database and never republished (DESIGN §4E
hard aggregation policy). Only a short derived excerpt is cached locally
(gitignored .cache/, 24h) so idempotent re-runs don't hammer outlet sites.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "articles"
CACHE_TTL = 24 * 3600
EXCERPT_CHARS = 2500
MAX_BYTES = 1_500_000


def _extract_excerpt(html: str) -> tuple[str, str | None]:
    """Derived text for LLM input, plus the outlet's og:image URL (D-024 —
    a link to their asset, never a copy)."""
    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []

    og_image = None
    og_img_el = soup.find("meta", property="og:image")
    if og_img_el and (og_img_el.get("content") or "").startswith("http"):
        og_image = og_img_el["content"].strip()

    og = soup.find("meta", property="og:description")
    if og and og.get("content"):
        parts.append(og["content"].strip())

    # Prefer paragraphs inside the article body; fall back to any
    # substantial paragraph on the page.
    container = soup.find("article") or soup.find("main") or soup
    paragraphs = [
        " ".join(p.get_text(" ", strip=True).split())
        for p in container.find_all("p")
    ]
    parts.extend(p for p in paragraphs if len(p) > 60)

    seen: set[str] = set()
    unique = [p for p in parts if not (p in seen or seen.add(p))]
    return " ".join(unique)[:EXCERPT_CHARS], og_image


def fetch_excerpt(session: Any, url: str) -> tuple[str | None, str, str | None]:
    """Return (excerpt, fetch_status, og_image_url). Excerpt is derived
    text for LLM input only — never written to the database."""
    key = hashlib.sha256(url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < CACHE_TTL:
        cached = json.loads(cache_file.read_text())
        return cached["excerpt"], cached["status"], cached.get("image")

    excerpt, status, image = None, "failed", None
    try:
        resp = session.get(url, timeout=25, stream=True)
        resp.raise_for_status()
        content = resp.raw.read(MAX_BYTES, decode_content=True)
        excerpt, image = _extract_excerpt(
            content.decode(resp.encoding or "utf-8", errors="replace")
        )
        if excerpt:
            status = "fetched"
        else:
            excerpt = None
    except Exception:  # noqa: BLE001 — a failed fetch is a recorded state, not a crash
        pass

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps({"excerpt": excerpt, "status": status, "image": image}, ensure_ascii=False)
    )
    return excerpt, status, image
