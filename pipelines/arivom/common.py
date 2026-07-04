"""Shared helpers for Arivom importers: DB access, provenance, validation."""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "ArivomCivicData/0.1 (open-source civic data platform for Tamil Nadu)"

# Public sample key documented by data.gov.in for testing; register a free
# key and set DATA_GOV_IN_API_KEY for real runs (CI secret).
_SAMPLE_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"

TAMIL_BLOCK = range(0x0B80, 0x0C00)


def has_tamil(text: str | None) -> bool:
    """A string counts as Tamil only if it contains Tamil-script codepoints."""
    if not text:
        return False
    return any(ord(ch) in TAMIL_BLOCK for ch in text)


def norm_name(name: str) -> str:
    """Normalize an English place name for matching across sources."""
    name = unicodedata.normalize("NFKD", name)
    name = name.lower().strip()
    for token in (".", "-", "'", "(", ")", ","):
        name = name.replace(token, " ")
    return " ".join(name.split())


def http_session() -> requests.Session:
    session = requests.Session()
    # Generous backoff: the public data.gov.in sample key is tightly
    # rate-limited; pipelines value completeness over speed.
    retry = Retry(
        total=8,
        backoff_factor=4,
        backoff_max=90,
        status_forcelist=[429, 500, 502, 503, 504],
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = USER_AGENT
    return session


def datagovin_key() -> str:
    return os.environ.get("DATA_GOV_IN_API_KEY", _SAMPLE_KEY)


def fetch_datagovin_resource(
    session: requests.Session,
    resource_id: str,
    filters: dict[str, str] | None = None,
    page_size: int = 500,
) -> list[dict[str, Any]]:
    """Fetch every record of a data.gov.in resource, paginated."""
    records: list[dict[str, Any]] = []
    offset = 0
    while True:
        params: dict[str, str | int] = {
            "api-key": datagovin_key(),
            "format": "json",
            "limit": page_size,
            "offset": offset,
        }
        for field, value in (filters or {}).items():
            params[f"filters[{field}]"] = value
        resp = session.get(
            f"https://api.data.gov.in/resource/{resource_id}", params=params, timeout=60
        )
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("records", [])
        records.extend(batch)
        total = int(payload.get("total", 0))
        offset += len(batch)
        if not batch or offset >= total:
            return records


def sparql(session: requests.Session, query: str) -> list[dict[str, Any]]:
    resp = session.get(
        "https://query.wikidata.org/sparql",
        params={"query": query, "format": "json"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["results"]["bindings"]


@dataclass
class Db:
    conn: psycopg.Connection

    @classmethod
    def connect(cls) -> Db:
        url = os.environ.get("DATABASE_URL", "postgresql://localhost/arivom")
        conn = psycopg.connect(url)
        # Long import transactions over a WAN pooler can trip conservative
        # server-side statement timeouts; raise it for pipeline sessions.
        conn.execute("SET statement_timeout = '300s'")
        return cls(conn=conn)

    def ensure_source(
        self,
        *,
        name: str,
        url: str | None,
        publisher: str,
        license: str | None,
        access_mode: str,
        notes: str | None = None,
    ) -> int:
        row = self.conn.execute(
            """
            INSERT INTO sources (name, url, publisher, license, access_mode, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE
              SET url = EXCLUDED.url,
                  publisher = EXCLUDED.publisher,
                  license = EXCLUDED.license,
                  access_mode = EXCLUDED.access_mode,
                  notes = EXCLUDED.notes
            RETURNING id
            """,
            (name, url, publisher, license, access_mode, notes),
        ).fetchone()
        assert row is not None
        return row[0]

    def upsert_locality_by_lgd(
        self,
        *,
        lgd_code: str,
        name_en: str,
        name_ta: str,
        level: str,
        parent_id: int | None,
        source_id: int,
        retrieved_at: datetime,
    ) -> int:
        row = self.conn.execute(
            """
            INSERT INTO localities
              (lgd_code, name_en, name_ta, level, parent_id, source_id, retrieved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lgd_code) DO UPDATE
              SET name_en = EXCLUDED.name_en,
                  name_ta = EXCLUDED.name_ta,
                  level = EXCLUDED.level,
                  parent_id = EXCLUDED.parent_id,
                  source_id = EXCLUDED.source_id,
                  retrieved_at = EXCLUDED.retrieved_at
            RETURNING id
            """,
            (lgd_code, name_en, name_ta, level, parent_id, source_id, retrieved_at),
        ).fetchone()
        assert row is not None
        return row[0]

    def upsert_locality_by_eci(
        self,
        *,
        eci_code: str,
        name_en: str,
        name_ta: str,
        level: str,
        parent_id: int | None,
        district_id: int | None,
        source_id: int,
        retrieved_at: datetime,
    ) -> int:
        row = self.conn.execute(
            """
            INSERT INTO localities
              (eci_code, name_en, name_ta, level, parent_id, district_id,
               source_id, retrieved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (level, eci_code) WHERE eci_code IS NOT NULL DO UPDATE
              SET name_en = EXCLUDED.name_en,
                  name_ta = EXCLUDED.name_ta,
                  parent_id = EXCLUDED.parent_id,
                  district_id = EXCLUDED.district_id,
                  source_id = EXCLUDED.source_id,
                  retrieved_at = EXCLUDED.retrieved_at
            RETURNING id
            """,
            (eci_code, name_en, name_ta, level, parent_id, district_id, source_id, retrieved_at),
        ).fetchone()
        assert row is not None
        return row[0]

    def upsert_fact(
        self,
        *,
        subject_type: str,
        subject_id: int,
        key: str,
        value: Any,
        source_id: int,
        retrieved_at: datetime,
        extraction_method: str,
        confidence: float | None = None,
        review_status: str = "unreviewed",
    ) -> None:
        """Idempotent on (subject_type, subject_id, key, source_id)."""
        updated = self.conn.execute(
            """
            UPDATE facts
              SET value = %s, retrieved_at = %s, extraction_method = %s,
                  confidence = %s, review_status = %s
            WHERE subject_type = %s AND subject_id = %s AND key = %s AND source_id = %s
            """,
            (
                json.dumps(value, ensure_ascii=False),
                retrieved_at,
                extraction_method,
                confidence,
                review_status,
                subject_type,
                subject_id,
                key,
                source_id,
            ),
        )
        if updated.rowcount == 0:
            self.conn.execute(
                """
                INSERT INTO facts
                  (subject_type, subject_id, key, value, source_id, retrieved_at,
                   extraction_method, confidence, review_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    subject_type,
                    subject_id,
                    key,
                    json.dumps(value, ensure_ascii=False),
                    source_id,
                    retrieved_at,
                    extraction_method,
                    confidence,
                    review_status,
                ),
            )


def expand_table_grid(table: Any) -> list[list[str]]:
    """Expand an HTML table into a dense grid, resolving row/colspans."""
    grid: list[list[str]] = []
    pending: dict[int, tuple[str, int]] = {}  # col index -> (text, remaining rows)
    for tr in table.find_all("tr"):
        row: list[str] = []
        col = 0
        cells = tr.find_all(["td", "th"])
        cell_iter = iter(cells)
        while True:
            if col in pending:
                text, remaining = pending[col]
                row.append(text)
                if remaining > 1:
                    pending[col] = (text, remaining - 1)
                else:
                    del pending[col]
                col += 1
                continue
            cell = next(cell_iter, None)
            if cell is None:
                # Flush any trailing pending cells.
                if any(c >= col for c in pending):
                    max_col = max(c for c in pending if c >= col)
                    while col <= max_col:
                        if col in pending:
                            text, remaining = pending[col]
                            row.append(text)
                            if remaining > 1:
                                pending[col] = (text, remaining - 1)
                            else:
                                del pending[col]
                        else:
                            row.append("")
                        col += 1
                break
            text = " ".join(cell.get_text(" ", strip=True).split())
            rowspan = int(cell.get("rowspan", 1) or 1)
            colspan = int(cell.get("colspan", 1) or 1)
            for _ in range(colspan):
                row.append(text)
                if rowspan > 1:
                    pending[col] = (text, rowspan - 1)
                col += 1
        grid.append(row)
    return grid


def now_utc() -> datetime:
    return datetime.now(UTC)


def fail(message: str) -> None:
    """Loud failure: importers never paper over an unexpected universe."""
    print(f"FATAL: {message}", file=sys.stderr)
    raise SystemExit(1)
