-- LLM cost controls for the news pipeline (D-039).
--
-- Two tables, both pipeline-internal. Neither holds civic facts, so neither
-- is public-readable: cost telemetry is operational data, not published data.
--
-- llm_spend  — append-only ledger of every billed model call. Exists so the
--              hard budget ceiling survives CI (pipelines/.cache is ephemeral
--              on GitHub Actions) and so spend is auditable per stage.
-- llm_batches — in-flight Message Batches API jobs. The Batches API is
--              asynchronous (50% cheaper); a run submits work and a later run
--              collects it, so the job id has to outlive the process.

-- Records that the cheap headline screen has already looked at an item.
-- Needed because triage only WRITES when it sets something aside: a kept item
-- is otherwise indistinguishable from an unscreened one, and would be paid
-- for again on every run.
ALTER TABLE news_items ADD COLUMN triaged_at TIMESTAMPTZ;

COMMENT ON COLUMN news_items.triaged_at IS
  'When the headline-only triage screened this item (D-039). Independent of '
  'civic_class, which is only ever set by the full read in stage 1.';

CREATE INDEX news_items_untriaged_idx ON news_items (created_at DESC)
  WHERE triaged_at IS NULL;

CREATE TABLE llm_spend (
  id            BIGSERIAL PRIMARY KEY,
  occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  stage         TEXT NOT NULL,
  model         TEXT NOT NULL,
  input_tokens  INTEGER NOT NULL,
  output_tokens INTEGER NOT NULL,
  -- Message Batches API calls bill at 50%; recorded so cost_usd is the
  -- amount actually charged, not the list price.
  batched       BOOLEAN NOT NULL DEFAULT false,
  cost_usd      NUMERIC(12, 6) NOT NULL,
  items         INTEGER NOT NULL DEFAULT 1
);

COMMENT ON TABLE llm_spend IS
  'Append-only ledger of billed Anthropic calls. Enforces the hard budget '
  'ceiling (ARIVOM_LLM_BUDGET_USD) across runs and CI. Never displayed.';
COMMENT ON COLUMN llm_spend.items IS
  'How many news items or clusters this one call covered — batched requests '
  'carry many, so cost-per-item is cost_usd / items.';

CREATE INDEX llm_spend_occurred_idx ON llm_spend (occurred_at DESC);

CREATE TABLE llm_batches (
  batch_id      TEXT PRIMARY KEY,
  stage         TEXT NOT NULL,
  submitted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  collected_at  TIMESTAMPTZ,
  request_count INTEGER NOT NULL,
  -- custom_id -> the pipeline context needed to apply the result when it
  -- lands (item ids, cluster id, member ordering).
  context       JSONB NOT NULL
);

COMMENT ON TABLE llm_batches IS
  'In-flight Message Batches API jobs. Submitted by one pipeline run and '
  'collected by a later one; results expire after 29 days.';

CREATE INDEX llm_batches_pending_idx ON llm_batches (submitted_at)
  WHERE collected_at IS NULL;

-- Operational tables: RLS on, no public policy. Pipelines connect with the
-- service role and bypass RLS; anon/authenticated get nothing.
ALTER TABLE llm_spend ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_batches ENABLE ROW LEVEL SECURITY;
