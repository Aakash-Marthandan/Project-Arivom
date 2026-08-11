"""Offline LLM access for pipelines (M7, DESIGN §7 / §10 LLM pattern).

Cheap model class for bulk work, frontier model reserved for adjudication,
batched and disk-cached — and NEVER called at page-request time. Every call
is structured (JSON schema constrained), cached under .cache/llm/ keyed by
the full request, and metered against a hard budget ceiling.

Model tiers (D-022 as revised by D-039): Haiku for mechanical judgments
(triage, entity extraction, cluster-merge confirmation), Sonnet for
user-facing bilingual drafts AND their routine spot-check, Opus 5 only as
adjudicator — moderation-sensitive events and drafts the cheap checker could
not clear. The frontier model still has the last word on anything hard; it
just no longer reads every routine summary.

Three cost mechanisms, in order of how much they save:

1. Request batching (many items in one `structured` call, assembled by the
   caller). A system prompt is 600+ tokens and a headline is ~50, so one
   item per call pays the instructions 1,000+ times a day. Packing many
   items into one request amortises them away.
2. The Message Batches API (`submit_batch` / `collect_batch`). Flat 50% off
   every token. The pipeline is a cron job, so nothing here is latency
   sensitive; results are collected by a later run.
3. Effort control. Verification against supplied evidence is a bounded task
   and does not need frontier-depth reasoning by default.

Prompt caching is deliberately NOT used: measured 2026-08-11, all four
system prompts (613 / 94 / 684 / 515 tokens) sit below their model's minimum
cacheable prefix (4096 for Haiku, 1024 for Sonnet), so a cache_control marker
would cost the 1.25x write premium and never produce a read. Batching
achieves the same amortisation without that trap. Re-check if a system prompt
ever grows past its model's minimum.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from . import offline
from .common import fail
from .spend import Ledger

HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-5"
OPUS = "claude-opus-5"

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "llm"

# How long a run will wait for a Message Batches job before giving up and
# leaving it for the next run to collect. Most batches finish well inside
# this; the API's own ceiling is 24h.
BATCH_POLL_SECONDS = int(os.environ.get("ARIVOM_BATCH_POLL_SECONDS", "1500"))
BATCH_POLL_INTERVAL = 20

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


# The SDK defaults to a 10-minute timeout with 2 retries, so one slow
# generation can block a run for 30 minutes. Observed 2026-08-11: a summary
# call hung ~27 minutes and stalled the whole pipeline. An hourly cron must
# fail fast instead — a request that dies is retried by the NEXT run, which
# costs nothing extra because completed work is already committed.
REQUEST_TIMEOUT = float(os.environ.get("ARIVOM_LLM_TIMEOUT_SECONDS", "240"))
MAX_RETRIES = 1


def _get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic

        _client = Anthropic(timeout=REQUEST_TIMEOUT, max_retries=MAX_RETRIES)
    return _client


def _cache_key(model: str, system: str, user: str, schema: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {"model": model, "system": system, "user": user, "schema": schema},
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def _cache_get(key: str) -> dict[str, Any] | None:
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())["result"]
    return None


def _cache_put(key: str, model: str, result: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(
        json.dumps({"model": model, "result": result}, ensure_ascii=False)
    )


def _estimate_input_tokens(system: str, user: str) -> int:
    """Cheap pre-call estimate for the budget guard. Deliberately pessimistic:
    Tamil tokenizes to roughly one token per 2 characters, English closer to
    one per 4, and stopping a little early beats overshooting the ceiling."""
    return (len(system) + len(user)) // 2


def _params(
    *,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int,
    thinking: bool,
    effort: str | None,
) -> dict[str, Any]:
    output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": schema}}
    if effort:
        output_config["effort"] = effort
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": output_config,
    }
    if thinking:
        params["thinking"] = {"type": "adaptive"}
    return params


def structured(
    *,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int = 2048,
    thinking: bool = False,
    effort: str | None = None,
    ledger: Ledger | None = None,
    stage: str = "unknown",
    items: int = 1,
) -> dict[str, Any] | None:
    """One schema-constrained call, disk-cached and metered. Returns None on
    refusal or truncation (callers treat that item as failed and report it).

    Raises spend.BudgetExhausted rather than silently overspending.
    """
    key = _cache_key(model, system, user, schema)
    cached = _cache_get(key)
    if cached is not None:
        return cached  # a cache hit costs nothing and is not metered

    if offline.enabled():
        # Dev mode: record what we would have asked and return a miss. The
        # caller treats this item as failed and retries next run, by which
        # time an answer may have been imported into the cache.
        offline.queue(
            key=key, model=model, system=system, user=user, schema=schema, stage=stage
        )
        return None

    if ledger is not None:
        ledger.check(_projected_cost(model, system, user, max_tokens))

    try:
        response = _get_client().messages.create(
            **_params(
                model=model, system=system, user=user, schema=schema,
                max_tokens=max_tokens, thinking=thinking, effort=effort,
            )
        )
    except Exception as exc:  # noqa: BLE001 — a dead call is a reported state
        # Timeouts, rate limits and overloads are all "try again next run".
        # Nothing was committed for this item, so the next run picks it up.
        # Crashing here would abandon every stage after this one.
        print(f"LLM ERROR ({stage}, {model}): {type(exc).__name__}: {exc}")
        return None
    if ledger is not None:
        ledger.record(
            stage=stage, model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            items=items,
        )

    # Opus 5 and Sonnet 5 can decline a request outright (stop_reason
    # "refusal"); content is empty then, so check before reading it.
    if response.stop_reason not in ("end_turn", "stop_sequence"):
        print(f"LLM WARNING: stop_reason={response.stop_reason} for {model} ({stage})")
        return None
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        return None
    result = json.loads(text)
    _cache_put(key, model, result)
    return result


def _projected_cost(model: str, system: str, user: str, max_tokens: int) -> float:
    from .spend import cost_of

    return cost_of(
        model,
        _estimate_input_tokens(system, user),
        int(max_tokens * 0.5),
        batched=False,
    )


# ---------------------------------------------------------------------------
# Message Batches API — 50% off, asynchronous
# ---------------------------------------------------------------------------


def submit_batch(
    *,
    requests: list[tuple[str, dict[str, Any]]],
    stage: str,
    db: Any,
    context: dict[str, Any],
) -> str | None:
    """Submit (custom_id, params) pairs as one batch job and remember it.

    Returns the batch id, or None when there was nothing to submit. The job
    outlives this process: `context` is stored so whichever run collects the
    results knows what they belong to.
    """
    if not requests:
        return None
    if offline.enabled():
        return None  # offline mode queues via structured(); never submits
    batch = _get_client().messages.batches.create(
        requests=[{"custom_id": cid, "params": params} for cid, params in requests]
    )
    db.conn.execute(
        """
        INSERT INTO llm_batches (batch_id, stage, request_count, context)
        VALUES (%s, %s, %s, %s)
        """,
        (batch.id, stage, len(requests), json.dumps(context, ensure_ascii=False)),
    )
    db.conn.commit()
    return batch.id


def collect_batch(
    *,
    batch_id: str,
    db: Any,
    ledger: Ledger | None = None,
    stage: str = "unknown",
    wait: bool = True,
    items: int | None = None,
) -> dict[str, Any] | None:
    """Return {custom_id: parsed result} once the job has ended, else None.

    Results are metered here, when the real token counts are known. Failed or
    expired entries are simply absent from the returned mapping — callers
    treat a missing custom_id as an item to retry next run.
    """
    client = _get_client()
    deadline = time.monotonic() + (BATCH_POLL_SECONDS if wait else 0)
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        if time.monotonic() >= deadline:
            return None  # still running; a later run collects it
        time.sleep(BATCH_POLL_INTERVAL)

    results: dict[str, Any] = {}
    in_tokens = out_tokens = 0
    for entry in client.messages.batches.results(batch_id):
        if entry.result.type != "succeeded":
            continue
        message = entry.result.message
        in_tokens += message.usage.input_tokens
        out_tokens += message.usage.output_tokens
        if message.stop_reason not in ("end_turn", "stop_sequence"):
            continue
        text = next((b.text for b in message.content if b.type == "text"), None)
        if text is None:
            continue
        results[entry.custom_id] = json.loads(text)

    if ledger is not None and (in_tokens or out_tokens):
        ledger.record(
            stage=stage,
            model=_batch_model(db, batch_id),
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            batched=True,
            # A batched request usually carries many news items; without the
            # caller's real count this would record requests and make
            # cost-per-item read ~8x too high.
            items=items if items is not None else max(1, len(results)),
        )
    db.conn.execute(
        "UPDATE llm_batches SET collected_at = now() WHERE batch_id = %s", (batch_id,)
    )
    db.conn.commit()
    return results


def _batch_model(db: Any, batch_id: str) -> str:
    row = db.conn.execute(
        "SELECT context->>'model' FROM llm_batches WHERE batch_id = %s", (batch_id,)
    ).fetchone()
    return (row[0] if row and row[0] else HAIKU)


def pending_batches(db: Any, stage: str | None = None) -> list[tuple[str, dict[str, Any]]]:
    """Batch jobs submitted by an earlier run and not yet collected."""
    sql = "SELECT batch_id, context FROM llm_batches WHERE collected_at IS NULL"
    args: tuple[Any, ...] = ()
    if stage is not None:
        sql += " AND stage = %s"
        args = (stage,)
    sql += " ORDER BY submitted_at"
    return [(r[0], r[1]) for r in db.conn.execute(sql, args).fetchall()]


def batch_params(
    *,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int = 2048,
    thinking: bool = False,
    effort: str | None = None,
) -> dict[str, Any]:
    """Request params shaped for the Batches API — same shape as a live call."""
    return _params(
        model=model, system=system, user=user, schema=schema,
        max_tokens=max_tokens, thinking=thinking, effort=effort,
    )


def cache_lookup(
    *, model: str, system: str, user: str, schema: dict[str, Any]
) -> dict[str, Any] | None:
    """Public cache probe so batch callers can skip work already paid for."""
    return _cache_get(_cache_key(model, system, user, schema))


def cache_store(
    *, model: str, system: str, user: str, schema: dict[str, Any], result: Any
) -> None:
    _cache_put(_cache_key(model, system, user, schema), model, result)


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
