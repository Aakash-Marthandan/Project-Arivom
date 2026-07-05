"""Offline LLM access for pipelines (M7, DESIGN §7 / §10 LLM pattern).

Cheap model class for bulk work, frontier model for spot-checks, batched
and disk-cached — and NEVER called at page-request time. Every call is
structured (JSON schema constrained) and cached under .cache/llm/ keyed by
the full request, so idempotent re-runs cost nothing.

Model tiers (D-022): Haiku for mechanical judgments (entity extraction,
cluster-merge confirmation), Sonnet for user-facing bilingual drafts,
Opus with adaptive thinking for the summary spot-check + moderation
classification.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .common import fail

HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-5"
OPUS = "claude-opus-4-8"

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "llm"

_client = None


def llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def require_llm() -> None:
    if not llm_available():
        fail(
            "ANTHROPIC_API_KEY is not set. The clustering pipeline needs it "
            "(offline LLM use per DESIGN §7); add it to .env.local locally "
            "and as a GitHub Actions secret for the cron."
        )


def _get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic

        _client = Anthropic()
    return _client


def structured(
    *,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int = 2048,
    thinking: bool = False,
) -> dict[str, Any] | None:
    """One schema-constrained call, disk-cached. Returns None on refusal or
    truncation (callers treat that item as failed and report it)."""
    key = hashlib.sha256(
        json.dumps(
            {"model": model, "system": system, "user": user, "schema": schema},
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())["result"]

    kwargs: dict[str, Any] = {}
    if thinking:
        kwargs["thinking"] = {"type": "adaptive"}
    response = _get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        **kwargs,
    )
    if response.stop_reason not in ("end_turn", "stop_sequence"):
        print(f"LLM WARNING: stop_reason={response.stop_reason} for {model}")
        return None
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        return None
    result = json.loads(text)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"model": model, "result": result}, ensure_ascii=False))
    return result


def obj_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    """JSON schema object node with the strictness the API requires."""
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties),
        "additionalProperties": False,
    }


def arr(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}
