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

## Current status (as of 2026-07-05)

v0 milestones M1–M6 are `done` plus an owner-requested spine-completion pass
(see docs/PLAN.md for detail, docs/DECISIONS.md D-001…D-022 for every resolved
decision; D-021 records the owner's north star: an informed electorate).
Live: constituency pages with representatives, self-declared
affidavit profiles, election results; /locate (point-in-polygon); /vacancies
tracker (7 vacant seats, daily monitor cron); /government (department-first
cards with anchor ids, built as future click-targets for department-tagged
news); news ingestion (11-outlet §4E registry, poll-news 30-min cron,
headline+link only, conservative district tagging — D-020); /methodology and
live /freshness (now including per-outlet news freshness). **M7 news
clustering is built** (cluster-news pipeline, /news and /news/d/[lgd] feeds
with coverage tables and locked-state UI, D-022) **and awaits the owner's
ANTHROPIC_API_KEY** (.env.local + GH Actions secret) for the live run and
exit-criteria check; the hourly cron skips politely until the secret
exists. Production = Supabase (Mumbai),
repo = github.com/Aakash-Marthandan/Project-Arivom, CI green.

Known pending (all reported by importer runs, never hidden): 26 MLA + 3 MP
affidavits awaiting ADR analysis; representative contacts awaiting official
directories; by-election notification awaited (watch the vacancy-signal
queue); AC 185 election petition status note; 5 registry outlets without
machine-readable feeds — Dinamalar, Dinakaran, Hindu Tamil Thisai, News18
Tamil, Sun News (re-check from India egress); data.gov.in personal API key
and TN-government-site access arrive when the owner relocates to India
(~2026-07-13, D-010/D-017).

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
  30-min cron; registry in `pipelines/data/outlets.json`), and
  `cluster-news` (clusters + checked bilingual summaries, hourly cron;
  the only LLM pipeline — needs `ANTHROPIC_API_KEY`, D-022). Lint:
  `uv run ruff check .`. All importers are idempotent and print
  audit/pending reports; read them.
- **Production deploys:** `SUPABASE_DB_URL` in `.env.local` is the Mumbai
  session-pooler URL (IPv4; the direct db host is IPv6-only and unreachable
  here). Migrations: `supabase db push --yes --db-url "$SUPABASE_DB_URL"`.
  Data: rerun the importers with `DATABASE_URL="$SUPABASE_DB_URL"` (slow over
  WAN; run in background). Keep local and prod data in step.
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
