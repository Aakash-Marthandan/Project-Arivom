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

## Do NOT build (any phase, without explicit user instruction)

Native app · free-text comments · outlet bias labels · composite locality scores ·
anonymous write paths · user media uploads.
