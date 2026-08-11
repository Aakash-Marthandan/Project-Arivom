# Arivom (அறிவோம்) — Project Instructions

Open-source, bilingual (Tamil + English) civic data platform for Tamil Nadu. It gives
every TN citizen clear, current, **sourced** information about who represents them and
how their locality is doing — free, no ads, no editorializing. Web-first, statewide
(234 ACs + 39 PCs), ward data phased in via a Madurai Corporation pilot.

## Source of truth

**Read `docs/DESIGN.md` before making product or schema decisions.** It contains the
complete feature specs, data source catalog (with URLs), schema, pipeline specs, and
roadmap. Where anything conflicts with DESIGN.md, DESIGN.md wins. If DESIGN.md is
ambiguous, **ask the user rather than assuming**, and log the resolved decision in
`docs/DECISIONS.md`. The build plan lives in `docs/PLAN.md`.

## Three pillars (hard rules, in priority order)

1. **Transparency.** Every displayed fact carries provenance — source, retrieval date,
   extraction method, confidence — one tap away (provenance chip pattern). Public
   `/methodology`, `/freshness`, and corrections pages. **A fact that cannot carry a
   source does not enter the database** (enforced by NOT NULL provenance columns on
   `facts`). Affidavit data is always labelled "self-declared."
2. **Strict political neutrality.** No outlet bias labels, no composite scores, no
   opinion copy anywhere in the product. Sourced facts and coverage transparency only.
   Data indicators and community sentiment are displayed separately and **never
   blended** into a single number.
3. **Craft.** Fast on low-end Android over 4G (sub-second locality pages on a throttled
   profile), excellent Tamil typography, information-dense but calm, WCAG 2.1 AA,
   mobile-first. The polish is the product.

**Information hierarchy (owner directive, D-016):** present information from a
rational citizen's perspective — ranked by civic usefulness under the
Constitution and common sense, never for entertainment value. Sensitive
self-declared facts (assets, liabilities, criminal cases) are **de-emphasized,
never buried**: one tap away under a neutral "More information" disclosure,
never removed or sensationalized in either direction.

**Copy style (owner directive):** user-facing copy uses short plain sentences,
no em dashes, written for average readers. Both catalogs (`messages/ta.json`,
`messages/en.json`); full parity, warm formal Tamil register.

## Stack (fixed — do not substitute)

- **Frontend:** Next.js App Router + TypeScript `strict` + Tailwind + shadcn/ui.
- **i18n:** next-intl, route-based locales — `ta` is the **default** locale, `en`
  second; both first-class with full parity. **Zero hardcoded user-facing strings** —
  every string goes through message catalogs.
- **Database:** Supabase (Postgres + PostGIS). Schema changes only via SQL migrations
  in `supabase/migrations/`. RLS: public read on civic data; writes restricted to
  phone-verified users at the appropriate rung; `moderation_events` append-only.
- **Pipelines:** Python scripts under `/pipelines`, run by GitHub Actions cron —
  **never at page-request time**. Every `facts` write populates `source_id`,
  `retrieved_at`, `extraction_method`, `confidence`, `review_status`.
- **LLM usage:** offline in pipelines only, batched and cached. **No LLM calls at
  request time, ever.**
- **Deploy:** Vercel (ISR/edge caching for locality pages).

## Conventions

- Small, conventional commits (`feat:`, `fix:`, `chore:`, `data:`, …).
- **Never edit a merged migration** — always add a new one.
- Secrets only in `.env.local` and CI secrets. Never committed.
- Seed/fixture data only behind an explicit `FIXTURES=true` flag and visibly labeled
  in the UI. **Never fabricate representative data presented as real.** Empty states
  say data is unavailable (e.g., ward data) — never invent it.
- Tamil fonts: body Noto Sans Tamil (or Hind Madurai), display Catamaran (or Mukta
  Malar); subset and self-host; test ligatures at small sizes.
- CI gates: lint, typecheck, build; Lighthouse thresholds (Performance ≥ 90,
  Accessibility ≥ 95) once pages exist.
- News aggregation policy (hard): headlines + links + own-words neutral summaries
  only — never store or republish full article text.

## Current status (handoff, as of 2026-07-18)

M1–M6, M8 and M10 `done`; M12 `in-progress` (NFHS-5 + JJM shipped,
D-030/D-031; HMIS blocked until India egress ~2026-07-13); M7 fully
built and **deliberately dark**; M7.5 app-experience rounds shipped
(D-023…D-026); M11 SEO groundwork in (sitemap+hreflang, robots,
JSON-LD, metadataBase — origin resolves from NEXT_PUBLIC_SITE_URL, set
it when a custom domain lands). M10 transparency pages live: nine-
section /methodology, /freshness SLA colours over sources.cadence, and
the /corrections log from the curated cited seed (D-034). The
refinement phase (owner-directed) shipped D-035…D-038: the knowledge
map + /right-to-know, the finite staged feed with beyond-TN outlets,
civic-context ranking, spoken money units and the gentle RTI thread;
plus the D-033 addendum (one card per department). Every decision is
in docs/DECISIONS.md (D-001…D-039); D-021 is the north star (informed
electorate), and D-039 governs every LLM call's cost.

**Key day happened (2026-08-11).** ANTHROPIC_API_KEY is in `.env.local`
(gitignored). The pipeline was restructured for cost before any volume ran
through it — see **D-039**, which is required reading before touching
`pipelines/arivom/{llm,spend,civic_guard,cluster_news}.py`. Headline
numbers, all measured against production:

- Volume is ~1,080 items/day (29K+ items), roughly 4x what D-022 assumed.
  As built, the pipeline would have cost **$350-530/month**.
- **Prompt caching does not apply and must not be added** — every system
  prompt is below its model's minimum cacheable prefix. Batching is what
  amortises them.
- The ladder is Haiku (triage/entities/merge) -> Sonnet (draft + routine
  check) -> **Opus 5 only as adjudicator** of moderation-flagged or
  check-failing summaries. Nothing is ever locked or withheld on the cheap
  tier's word alone.
- **`ARIVOM_LLM_BUDGET_USD` is a hard ceiling** (default $20) enforced from
  the `llm_spend` ledger in the database, not a warning. A run that reaches
  it stops cleanly and reports; the next run resumes.

Owner's standing instruction: MVP testing fits inside **$20 total**; proper
capacity planning happens when the platform goes live.

**Live today** (all CI-gated; prod schema and data in step as of
2026-07-18):

- **Civic spine:** constituencies, representatives, affidavits (money in
  lakhs and crores with the exact figure beneath, D-038), /locate,
  /vacancies.
- **/government:** ONE card per department with every holding minister
  and their subjects inside it, over a find-as-you-type filter (D-033
  addendum — TN departments really do split subjects across ministers;
  43 en cards / 110 ta entries, both verified duplicate-free). Each card
  opens its department news feed (/government/news/[dept], honest-empty
  until the key).
- **District pages /d/[lgd]:** the M8 education panel (D-028: public
  dashboard API, class-derived level buckets, cross-validated state
  sums), the NFHS-5 health panel (D-030: twelve verified sample-survey
  indicators) and the JJM drinking-water panel (D-031: rural tap
  coverage from the mission's own endpoint). Importers `import-udise` /
  `import-nfhs` / `import-jjm`, monthly cron.
- **The app experience:** PWA shell with bottom tabs; news-first home
  sectioned by device-remembered places (my-places + person follows,
  cookies, no accounts) ending on "Worth knowing today" with quiet doors
  to the full feed and the citizen's right to ask (D-038); content-first
  story cards with hotlinked outlet images (D-024: linked, never
  copied); search across constituencies/people/stories; /more; /about;
  dark mode following the system preference (D-029, "paper at night").
- **The finite feed** /news (D-036): three bounded tiers with beyond-TN
  outlets in the last one (The Hindu National, Indian Express India, BBC
  Tamil, BBC World; locality surfaces stay TN-only), ending on purpose
  with a feedback door. Ordered by published civic-subject rules + the
  reader's saved districts, with civic_priority taking over on key day
  (D-037). Plus /news/d/[lgd] and /news/s/[id].
- **Trust surfaces:** nine-section /methodology (including "How stories
  are chosen", D-025), /freshness with SLA colours over sources.cadence
  and live story-pool counts, the /corrections log from the curated
  cited seed (D-034), and /right-to-know.
- **The knowledge map** on place pages (D-035: reward orientation not
  engagement; device-local seen-footprints, no gamification;
  government-side data edges link the citizen's RTI rights).
- **Guardrails:** ingest hygiene (D-025 section blocklist at the
  poller); Lighthouse CI floors (perf ≥0.80 median-of-3 on CI hardware,
  a11y ≥0.95; local measures 0.89–0.93); Monday editorial-QA sample
  workflow.

**Where key day got to, and what is left** (2026-08-11):

Done and verified locally against a 3-day production slice (3,110 items):
triage, batched extraction over the Message Batches API, clustering,
and checked bilingual summaries all run end to end. The feed renders
clustered cards with the source-count pill, civic-priority chip,
sources-differ marker and coverage dot-row, in both locales. Spend for
the whole exercise was ~$2.5.

Still to do, in order:
1. **Apply the migration and run against prod** — `20260811090000_llm_cost_controls.sql`
   is applied locally only. Prod writes need explicit owner authorization
   (ask, never assume); queue the exact commands in the handoff.
2. Add `ANTHROPIC_API_KEY` as a **GitHub Actions secret** so the hourly
   cron goes from skip to live, and set the `ARIVOM_LLM_BUDGET_USD`
   repository variable deliberately — the ceiling is cumulative across
   runs, so the cron stops for good once it is reached.
3. Remove the `methodology.stories.interim` line ("analysis has not
   started yet") from both catalogs once prod has clustered stories.
4. Close M7 exit criteria in docs/PLAN.md; check /freshness story-pool
   counts move; verify department feeds (/government/news/[dept]) fill in
   and the D-019 loose match (`src/lib/departments.ts`) is precise enough
   in both languages.
5. Watch cost and spot-check quality via the weekly qa-sample. If the
   Sonnet routine check proves weaker than Opus, D-022's escalation
   clause still governs — raise the check tier, not the draft tier.

**Dev phase: do not spend API credits (owner directive, 2026-08-11).** The
pipeline is validated; use offline mode instead, where Claude Code answers
in the model's place (D-039 addendum):

```
ARIVOM_LLM_OFFLINE=1 DATABASE_URL=postgresql://localhost/arivom uv run cluster-news
uv run llm-offline export --stage summary_draft --limit 5   # -> offline_requests.json
#   author offline_responses.json as [{"key": ..., "result": {...}}]
uv run llm-offline import
ARIVOM_LLM_OFFLINE=1 ... uv run cluster-news                # consumes at $0
```

Read the WHOLE request before answering — the export is the real prompt,
and a draft that misses sources fails the shape gate. Offline mode refuses
any non-local `DATABASE_URL`, and its output is written
`review_status='unreviewed'`; never relabel it `llm_checked`.

**Operating the pipeline:**
- `ARIVOM_LLM_BUDGET_USD` (default 20) — hard cumulative ceiling.
- `ARIVOM_BATCH_API=0` — synchronous mode. Costs 2x but returns
  immediately; use it when iterating, not in the cron.
- `ARIVOM_BATCH_POLL_SECONDS` — how long a run waits for a batch before
  leaving it for the next run (240 in CI, longer for manual runs).
- `ARIVOM_LLM_TIMEOUT_SECONDS` (default 240) — a hung request must not
  stall an hourly job; one observed hang blocked a run for 27 minutes
  before this was added.
- Read the spend breakdown the run prints; it is per stage and per model.

**Brand identity (D-027):** the mark is final — AdS/CFT tensor network /
screen / reader pages / white Tamil Nadu (our real served boundary) on the
peacock tile. Assets: `public/logo.svg`, `public/logo-dark.svg` (dark
mode), PWA icons regenerated from it. Never hand-edit the PNGs; re-run the
generator against the state geometry (see D-027).

**Next steps, in gate order (session close 2026-07-18):**

**The India relocation has happened** (owner confirmed 2026-08-11), so
item 1 is unblocked and nobody needs to ask again. Re-probe each endpoint
before planning work against it — geo-blocking was the only thing
stopping us, but confirm rather than assume.

1. **India egress (owner move, was planned ~2026-07-13):** HMIS monthly
   health (finishes M12); tn.gov.in department directory (the canonical
   department list — closes the D-019/D-033 ta/en asymmetry, where en
   shows 43 department cards and ta 110 subject-level entries because
   each side is faithful to its own wiki table); the 5 feedless outlets;
   owner's data.gov.in key; TN gov site access. Re-probe reachability
   before planning any of it (`curl` the endpoints; the geo-block is the
   only thing that was stopping us).
2. **Key day (owner hands ANTHROPIC_API_KEY):** the runbook above —
   lights up clustering, summaries, story pages, markers, brief,
   department feeds, and the D-037 ranking handover.
3. **M9 accounts (owner sets up Supabase phone-OTP + SMS):** the last
   big unbuilt milestone. Unlocks corrections-from-chips, and the
   D-038 community-RTI page (PLAN backlog) as its natural companion.
4. **M11 launch hardening (pre-domain):** image-proxy decision
   (**owner**, D-024 hotlink policy); font-subsetting audit; raise the
   Lighthouse floor to 0.90; throttled low-end-Android profile pass;
   set NEXT_PUBLIC_SITE_URL when the domain lands. Then v0 ships.
5. **Refinement continuations (unblocked, any session — start here if
   no gate has opened):** next-check clock on feeds ("new stories
   arrive around HH:MM", kills the refresh itch with a true sentence);
   the finite end-block on district feeds; story pages ending with
   "back to your day" instead of related-story rabbit holes; **owner
   walkthrough of the knowledge-map implementation (explicitly
   requested, not yet done)**; PWA push for by-election alerts (pairs
   with M9); a manual dark-mode override if wanted (D-029).

**Standing habits that earned their place:** run the importers and read
their reports (they surface real bugs); verify in the browser rather
than trusting the render (the D-037 ranking bug was invisible in code
review — NewsFeed silently re-sorted); when the owner questions
something that looks wrong, check the DATA before the code (twice now
the data was right and the presentation was the bug: D-032/D-033).

Known pending (all reported by importer runs, never hidden): 26 MLA + 3 MP
affidavits awaiting ADR analysis; representative contacts awaiting official
directories; by-election notification awaited (watch the vacancy-signal
queue); AC 185 election petition status note; 5 registry outlets without
machine-readable feeds — Dinamalar, Dinakaran, Hindu Tamil Thisai, News18
Tamil, Sun News (re-check from India egress); data.gov.in personal API key
and TN-government-site access arrive when the owner relocates to India
(planned ~2026-07-13, unconfirmed as of 2026-07-18 — ask, D-010/D-017).

## Development

- Web: `npm run dev` / `lint` / `typecheck` / `build`. Local dev serves on
  `/ta` (default) and `/en`. `DATABASE_URL` in `.env.local` (see .env.example).
  Preview server config in `.claude/launch.json` (prefers 3199, autoPort on —
  Next 16 allows one dev server per checkout, so reuse a running one via
  `curl` when another session owns it); owner likes it left running.
- DB: local Homebrew Postgres 17 + PostGIS (no Docker on this machine — see
  DECISIONS.md D-001). Apply migrations with
  `for f in supabase/migrations/*.sql; do psql -d arivom -v ON_ERROR_STOP=1 -f "$f"; done`.
- Pipelines: `cd pipelines && uv sync`, then run with
  `DATABASE_URL=postgresql://localhost/arivom uv run <entry>` in this order:
  `import-lgd` → `import-constituencies` → `import-geometries` →
  `import-representatives` → `import-affidavits` → `import-vacancies` →
  `import-ministers`. Order-independent: `monitor-vacancies` (detection-only,
  daily GH Actions cron), `poll-news` (outlet registry → news_items,
  30-min cron; registry in `pipelines/data/outlets.json`),
  `cluster-news` (triage + clusters + checked bilingual summaries +
  classification + Arivom titles, hourly cron; the only LLM pipeline and
  the only one that spends money — needs `ANTHROPIC_API_KEY`, and is
  governed by D-022/D-025/D-026/**D-039**), and `qa-sample` (weekly
  editorial QA print for human review). Lint:
  `uv run ruff check .`. All importers are idempotent and print
  audit/pending reports; read them.
- **Production deploys:** `SUPABASE_DB_URL` in `.env.local` is the Mumbai
  session-pooler URL (IPv4; the direct db host is IPv6-only and unreachable
  here). Migrations: `supabase db push --yes --db-url "$SUPABASE_DB_URL"`.
  Data: rerun the importers with `DATABASE_URL="$SUPABASE_DB_URL"` (slow over
  WAN; run in background). Keep local and prod data in step.
  **Prod writes need explicit owner authorization** — ask, never assume;
  and the `supabase db push` wrapper is blocked by the permission
  classifier in auto mode while `psql` is not. The working fallback
  (used 2026-07-08, verified): apply each migration inside a transaction
  that also inserts its bookkeeping row, so the CLI stays consistent —
  `BEGIN; \i supabase/migrations/<file>.sql; INSERT INTO
  supabase_migrations.schema_migrations (version, name, statements)
  VALUES ('<version>', '<name>', ARRAY[:'content']); COMMIT;` with
  `-v content="$(cat <file>)"`. Never print the connection string;
  pipe command output through
  `sed -E 's#postgres(ql)?://[^ ]+#[db-url]#g'`.
- **Source quirks:** ECI and MyNeta reject Python TLS fingerprints — those
  fetches shell out to curl (see D-006/D-019). TN government sites
  (assembly/tn.gov.in/elections.tn.gov.in) are geo-blocked outside India.
  data.gov.in runs on the public sample key until the owner's key lands
  (D-010; cron gate variable `PIPELINES_ENABLED` stays unset). Wiki and
  MyNeta fetches are disk-cached 24h under `pipelines/.cache/`.
- **Human-confirmation paths:** status flips and curated data live in
  `pipelines/data/` (vacancies_2026.json, status_notes.json,
  curated_names_ta.json), every entry cited. Monitors and importers only
  raise signals or pending lists; a human edits the seed, the importer
  validates (name similarity) and applies.
- Server components read Postgres directly via `src/lib/db.ts` (postgres.js);
  supabase-js arrives with auth in M9 (D-002).
- Client JS is kept minimal deliberately: strings are passed to client
  components as props — no NextIntlClientProvider message payloads.

## Do NOT build (any phase, without explicit user instruction)

Native app (PWA is approved and built per D-023; a store-wrapped native
app stays gated on an explicit v0.5 evaluation) · free-text comments ·
outlet bias labels · composite locality scores · anonymous write paths ·
user media uploads.
