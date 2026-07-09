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

## Current status (handoff, as of 2026-07-08)

M1–M6, M8 and M10 `done`; M12 `in-progress` (NFHS-5 + JJM shipped,
D-030/D-031; HMIS blocked until India egress ~2026-07-13); M7 fully
built and **deliberately dark**; M7.5 app-experience rounds shipped
(D-023…D-026); M11 SEO groundwork in (sitemap+hreflang, robots,
JSON-LD, metadataBase — origin resolves from NEXT_PUBLIC_SITE_URL, set
it when a custom domain lands). M10 transparency pages live: ten-
section /methodology, /freshness SLA colours over sources.cadence, and
the /corrections log from the curated cited seed (D-034). The
refinement phase (owner-directed) shipped D-035…D-038: the knowledge
map + /right-to-know, the finite staged feed with beyond-TN outlets,
civic-context ranking, spoken money units and the gentle RTI thread.
Every decision is in docs/DECISIONS.md (D-001…D-038); D-021 is the
north star (informed electorate).

**The one gate: ANTHROPIC_API_KEY.** Owner will provide it when the app is
near-complete so API testing happens once, efficiently — do not ask for it
early. Until then the hourly cluster-news cron skips politely, and every
LLM-dependent surface renders an honest interim (language-filtered original
headlines, no clusters/markers/brief). Built-and-waiting on the key:
clustering, checked bilingual summaries (short+long), per-outlet coverage
notes, civic/adjacent/soft classification, Arivom-voice titles,
civic-priority + sources-differ markers, department tagging, story pages'
full depth, the daily brief, entity-matched person news.

**Live today** (all CI-gated, prod schema current): the civic spine
(constituencies, representatives, affidavits, /locate, /vacancies,
/government); M8 education indicators — district pages /d/[lgd] with the
UDISE+ education panel (D-028: public dashboard API, class-derived level
buckets, cross-validated state sums; importer `import-udise`, monthly
cron), the NFHS-5 health panel (D-030: twelve verified sample-survey
indicators, importer `import-nfhs`) and the JJM drinking-water panel
(D-031: rural tap coverage from the mission dashboard's own endpoint,
importer `import-jjm`; **prod pending — owner: (1) `supabase db push`
(two new migrations: sources.cadence, corrections), (2) run
`import-udise`, `import-nfhs`, `import-jjm`, `import-ministers`
(D-032/D-033 re-import) and `import-corrections` against
$SUPABASE_DB_URL, (3) once: `UPDATE sources SET cadence='manual'
WHERE cadence IS NULL` on prod**); the app experience — PWA shell with bottom tabs,
news-first home sectioned by device-remembered places (my-places +
person follows, cookies, no accounts), content-first story cards with
hotlinked outlet images (D-024: linked, never copied), the finite
staged /news feed with beyond-TN tiers (D-036: The Hindu National,
Indian Express India, BBC Tamil, BBC World; locality surfaces stay
TN-only; the feed ends on purpose with a feedback door; D-037: tiers order by
published civic-subject rules + the reader's saved districts, with
civic_priority taking over on key day) +
/news/d/[lgd] + /news/s/[id], search across
constituencies/people/stories, /more, /about; dark mode following the
system preference (D-029, "paper at night"); department news feeds
behind /government cards (/government/news/[dept], honest-empty until
the key; extraction now emits department + department_ta); the "How
stories are chosen" methodology section and live story-pool counts on
/freshness (D-025); the knowledge map on place pages plus the
/right-to-know page (D-035: reward orientation not engagement;
device-local seen-footprints, no gamification; government-side data
edges link the citizen's RTI rights); ingest hygiene (D-025 section blocklist at the
poller); Lighthouse CI floors (perf ≥0.80 median-of-3 on CI hardware,
a11y ≥0.95; local measures 0.89–0.93) and a Monday editorial-QA sample
workflow.

**Key-day runbook** (when the owner hands over the key):
1. Add `ANTHROPIC_API_KEY=` to `.env.local` AND as a GitHub Actions secret.
2. `cd pipelines && DATABASE_URL=postgresql://localhost/arivom uv run
   cluster-news` — first run processes the extraction backlog in capped
   batches (300 extract / 250 confirm / 40 summaries per run; rerun until
   backlog clears; all calls disk-cached under `.cache/llm/`).
3. Verify in browser (both locales): clustered story cards with markers,
   the feed order handover (D-037: civic_priority now outranks the
   interim subject rubric; spot-check tier 1),
   /news/s/[id] summaries + coverage notes + timeline + in-numbers, home
   brief + MLA-mentions, feeds now civic+adjacent-only with Arivom titles.
4. Run against prod (`DATABASE_URL="$SUPABASE_DB_URL"`), confirm the
   hourly cron goes from skip to live.
5. Close M7 exit criteria in docs/PLAN.md; remove the "analysis has not
   started" interim line (`methodology.stories.interim`) from both
   catalogs; check the /freshness story-pool counts move; verify the
   department feeds (/government/news/[dept]) fill in and the D-019
   loose match (src/lib/departments.ts) is precise enough in both
   languages.
6. Watch cost + spot-check quality via the qa-sample output; escalate the
   summary-draft model only if the spot-check failure rate is high (D-022).

**Brand identity (D-027):** the mark is final — AdS/CFT tensor network /
screen / reader pages / white Tamil Nadu (our real served boundary) on the
peacock tile. Assets: `public/logo.svg`, `public/logo-dark.svg` (dark
mode), PWA icons regenerated from it. Never hand-edit the PNGs; re-run the
generator against the state geometry (see D-027).

**Next steps, in gate order (session close 2026-07-08):**
1. **Owner, anytime:** the prod runbook above (db push + five importers
   + the one-time cadence UPDATE). Until then prod shows honest empty
   states for the new panels and the old department cards.
2. **India egress (~2026-07-13):** HMIS monthly health (finishes M12);
   tn.gov.in department directory (canonical department list — closes
   D-019/D-033 ta/en asymmetry); the 5 feedless outlets; owner's
   data.gov.in key; TN gov site access.
3. **Key day (owner hands ANTHROPIC_API_KEY):** the runbook below —
   lights up clustering, summaries, story pages, markers, brief,
   department feeds, and the D-037 ranking handover.
4. **M9 accounts (owner sets up Supabase phone-OTP + SMS):** the last
   big unbuilt milestone. Unlocks corrections-from-chips, and the
   D-038 community-RTI page (PLAN backlog) as its natural companion.
5. **M11 launch hardening (pre-domain):** image-proxy decision
   (**owner**, D-024 hotlink policy); font-subsetting audit; raise the
   Lighthouse floor to 0.90; throttled low-end-Android profile pass;
   set NEXT_PUBLIC_SITE_URL when the domain lands. Then v0 ships.
6. **Refinement continuations (unblocked, any session):** next-check
   clock on feeds ("new stories arrive around HH:MM"); the finite
   end-block on district feeds; story pages ending with "back to your
   day"; owner walkthrough of the knowledge-map implementation
   (requested); PWA push for by-election alerts (pairs with M9); a
   manual dark-mode override if wanted (D-029).

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
  30-min cron; registry in `pipelines/data/outlets.json`),
  `cluster-news` (clusters + checked bilingual summaries + classification
  + Arivom titles, hourly cron; the only LLM pipeline — needs
  `ANTHROPIC_API_KEY`, D-022/D-025/D-026), and `qa-sample` (weekly
  editorial QA print for human review). Lint:
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
