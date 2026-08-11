"""Development mode: Claude Code answers the pipeline instead of the API.

Owner directive 2026-08-11 — stop spending API credits during the dev phase.
The pipeline still runs unchanged; only the transport changes. A run in
offline mode writes the requests it would have sent to a queue file, an
assistant fills in the answers, and importing them seeds the ordinary
`.cache/llm/` disk cache. The next run finds every answer already cached and
completes at zero cost.

    ARIVOM_LLM_OFFLINE=1 uv run cluster-news      # queues what it needs
    uv run llm-offline export --limit 20          # -> offline_requests.json
    ... fill in offline_responses.json ...
    uv run llm-offline import                     # seeds the cache
    ARIVOM_LLM_OFFLINE=1 uv run cluster-news      # runs on cached answers

Two rules make this honest rather than a fabrication:

1. **It cannot touch production.** Offline mode refuses to run against
   anything but a local database. Content written this way is development
   fixture data, and CLAUDE.md is explicit that fixtures never masquerade as
   real (they exist behind an explicit flag and are visibly labelled).
2. **It never claims to be spot-checked.** Summaries produced this way are
   written `review_status='unreviewed'`, not `'llm_checked'` — the D-022
   draft-then-frontier-check chain did not run, and the database must not
   say it did. `/freshness` and the audit trail stay truthful.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "llm"
QUEUE_FILE = CACHE_DIR / "offline_queue.jsonl"
REQUESTS_FILE = Path("offline_requests.json")
RESPONSES_FILE = Path("offline_responses.json")


def enabled() -> bool:
    return os.environ.get("ARIVOM_LLM_OFFLINE") == "1"


def guard_local_database() -> None:
    """Offline answers are fixtures; fixtures never reach production."""
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        return
    local = ("localhost" in dsn) or ("127.0.0.1" in dsn) or dsn.startswith("postgresql:///")
    if not local:
        sys.exit(
            "ARIVOM_LLM_OFFLINE=1 refuses to run against a non-local database.\n"
            "Answers written in offline mode are development fixtures and must "
            "never enter production (CLAUDE.md: never fabricate representative "
            "data presented as real). Point DATABASE_URL at localhost, or unset "
            "ARIVOM_LLM_OFFLINE to use the real API."
        )


def queue(
    *, key: str, model: str, system: str, user: str, schema: dict[str, Any], stage: str
) -> None:
    """Record a request the pipeline wanted to make. Deduplicated by cache key."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if QUEUE_FILE.exists():
        seen = {
            json.loads(line)["key"]
            for line in QUEUE_FILE.read_text().splitlines()
            if line.strip()
        }
        if key in seen:
            return
    with QUEUE_FILE.open("a") as fh:
        fh.write(
            json.dumps(
                {
                    "key": key, "stage": stage, "model": model,
                    "system": system, "user": user, "schema": schema,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _pending() -> list[dict[str, Any]]:
    if not QUEUE_FILE.exists():
        return []
    out = []
    for line in QUEUE_FILE.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if not (CACHE_DIR / f"{entry['key']}.json").exists():
            out.append(entry)
    return out


def export_main() -> None:
    limit = 20
    stage_filter = None
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        if arg == "--stage" and i + 1 < len(args):
            stage_filter = args[i + 1]

    pending = _pending()
    if stage_filter:
        pending = [p for p in pending if p["stage"] == stage_filter]
    chunk = pending[:limit]

    REQUESTS_FILE.write_text(json.dumps(chunk, ensure_ascii=False, indent=2))
    by_stage: dict[str, int] = {}
    for entry in pending:
        by_stage[entry["stage"]] = by_stage.get(entry["stage"], 0) + 1
    print(f"pending total: {len(pending)}  {by_stage}")
    print(f"exported {len(chunk)} to {REQUESTS_FILE}")
    print(
        f"Fill in {RESPONSES_FILE} as [{{\"key\": ..., \"result\": {{...}}}}], "
        f"each result matching that request's schema, then: uv run llm-offline import"
    )


def import_main() -> None:
    if not RESPONSES_FILE.exists():
        sys.exit(f"{RESPONSES_FILE} not found — export first, then fill it in.")
    answers = json.loads(RESPONSES_FILE.read_text())
    queued = {entry["key"]: entry for entry in _pending()}

    stored = skipped = 0
    for answer in answers:
        key = answer.get("key")
        if key not in queued:
            skipped += 1
            continue
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{key}.json").write_text(
            json.dumps(
                {"model": queued[key]["model"], "offline": True, "result": answer["result"]},
                ensure_ascii=False,
            )
        )
        stored += 1
    print(f"stored {stored} offline answers into the cache; {skipped} unmatched keys ignored")
    print("re-run the pipeline (ARIVOM_LLM_OFFLINE=1) to consume them at zero cost")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("export", "import", "status"):
        sys.exit("usage: llm-offline (export [--limit N] [--stage S] | import | status)")
    if sys.argv[1] == "export":
        export_main()
    elif sys.argv[1] == "import":
        import_main()
    else:
        pending = _pending()
        by_stage: dict[str, int] = {}
        for entry in pending:
            by_stage[entry["stage"]] = by_stage.get(entry["stage"], 0) + 1
        print(f"pending offline requests: {len(pending)}  {by_stage}")
