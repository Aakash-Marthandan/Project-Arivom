"""Cost accounting and the hard budget ceiling for LLM calls (D-039).

The news pipeline is the only part of Arivom that spends money per run, so
it is the only part that can run away. Every billed call is recorded in
`llm_spend` before its result is used, and every call is refused once
cumulative spend reaches the ceiling.

The ceiling is a stop, not a warning. A run that hits it finishes what it
has already paid for, reports loudly, and exits cleanly — it never leaves a
half-written cluster behind, because the pipeline commits per stage.

Ledger lives in the database rather than on disk because pipelines/.cache is
ephemeral on GitHub Actions: a disk-only ledger would reset the budget to
zero on every cron run, which is the exact opposite of a ceiling.
"""

from __future__ import annotations

import os
from typing import Any

# USD per million tokens (input, output), Anthropic list prices.
# Sonnet 5 carries introductory pricing ($2/$10) through 2026-08-31; the
# figures below are what we are actually charged today. Revisit on that date.
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (5.00, 25.00),
}

# The Message Batches API bills every token at half price.
BATCH_DISCOUNT = 0.5

DEFAULT_BUDGET_USD = 20.0


class BudgetExhausted(RuntimeError):
    """Raised when a call would take cumulative spend past the ceiling."""


def cost_of(model: str, input_tokens: int, output_tokens: int, *, batched: bool) -> float:
    try:
        price_in, price_out = PRICES[model]
    except KeyError:  # a model we have no price for is a bug, not a $0 call
        raise RuntimeError(
            f"No price on record for {model!r}; add it to spend.PRICES before use."
        ) from None
    usd = (input_tokens * price_in + output_tokens * price_out) / 1_000_000
    return usd * (BATCH_DISCOUNT if batched else 1.0)


class Ledger:
    """Append-only spend record with a hard ceiling.

    Construct once per run and pass it down; `db` is an arivom.common.Db.
    """

    def __init__(self, db: Any, budget_usd: float | None = None):
        self.db = db
        self.budget = (
            budget_usd
            if budget_usd is not None
            else float(os.environ.get("ARIVOM_LLM_BUDGET_USD", DEFAULT_BUDGET_USD))
        )
        self.spent_before = self._total_spent()
        self.spent_this_run = 0.0
        self.calls = 0

    def _total_spent(self) -> float:
        row = self.db.conn.execute("SELECT COALESCE(sum(cost_usd), 0) FROM llm_spend").fetchone()
        return float(row[0]) if row else 0.0

    @property
    def total(self) -> float:
        return self.spent_before + self.spent_this_run

    @property
    def remaining(self) -> float:
        return max(0.0, self.budget - self.total)

    def check(self, projected_usd: float = 0.0) -> None:
        """Refuse before spending. `projected_usd` is a conservative estimate
        of the call about to be made, so we stop just short rather than just
        past the ceiling."""
        if self.total + projected_usd > self.budget:
            raise BudgetExhausted(
                f"LLM budget ceiling reached: ${self.total:.4f} spent of "
                f"${self.budget:.2f} (next call ~${projected_usd:.4f}). "
                f"Raise ARIVOM_LLM_BUDGET_USD to continue."
            )

    def record(
        self,
        *,
        stage: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        batched: bool = False,
        items: int = 1,
    ) -> float:
        usd = cost_of(model, input_tokens, output_tokens, batched=batched)
        self.db.conn.execute(
            """
            INSERT INTO llm_spend
              (stage, model, input_tokens, output_tokens, batched, cost_usd, items)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (stage, model, input_tokens, output_tokens, batched, usd, items),
        )
        # Commit immediately: an un-committed ledger row after a crash means
        # money spent that the ceiling can never see.
        self.db.conn.commit()
        self.spent_this_run += usd
        self.calls += 1
        return usd

    def report(self) -> list[str]:
        rows = self.db.conn.execute(
            """
            SELECT stage, model, sum(cost_usd), sum(items), count(*)
            FROM llm_spend GROUP BY stage, model ORDER BY sum(cost_usd) DESC
            """
        ).fetchall()
        lines = [
            f"  {stage:22s} {model:18s} ${float(usd):8.4f}  "
            f"{int(items):6d} items / {int(calls):5d} calls"
            for stage, model, usd, items, calls in rows
        ]
        lines.append(
            f"  {'TOTAL':22s} {'':18s} ${self.total:8.4f}  "
            f"of ${self.budget:.2f} budget  (${self.remaining:.4f} left)"
        )
        return lines
