# Arivom — Build Plan

Derived from `docs/DESIGN.md` §12 (Phased Roadmap). Each milestone is sized for one
working session (solo dev + Claude Code). Status values: `planned | in-progress |
done`. Update this file as milestones complete; log any resolved DESIGN.md ambiguities
in `docs/DECISIONS.md`.

Cross-cutting rules applying to **every** milestone: bilingual parity (ta default, en
second, zero hardcoded strings); provenance on every fact; no LLM at request time;
mobile-first + WCAG AA; fixtures only behind `FIXTURES=true`, visibly labeled.

---

## Phase v0 — statewide launch

### M1 — Foundation: scaffold, schema, first real data, first page — `done` (2026-07-03)
The user-approved starting scope. Shipped: all exit criteria met — CI green
(lint, typecheck, migrations against PostGIS service container, build with
empty-state exercise), importers idempotent, 234 ACs + 39 PCs + 38 districts +
282 taluks live bilingually with provenance chips. Notable deviations, all in
docs/DECISIONS.md: LGD via data.gov.in mirror (captcha on the portal, D-004);
AC linkage via DataMeet + layered cross-validation (D-006); district withheld
for 10 ACs pending M2 spatial resolution (D-009); /freshness placeholder came
out live-from-DB rather than static copy.

- Repo scaffold: Next.js App Router + TS strict + Tailwind + shadcn/ui + next-intl
  (`/ta` default, `/en`); CI via GitHub Actions (lint, typecheck, build).
- Initial Supabase migration implementing the DESIGN.md §5 core schema: `localities`,
  `offices`, `persons`, `tenures`, `facts`, `sources`, `news_items`, `news_clusters`,
  `cluster_coverage`, `users`, `contributions`, `ratings`, `moderation_events`, plus
  the `vacancies` view. PostGIS enabled. Provenance columns (`source_id`,
  `retrieved_at`, `extraction_method`) NOT NULL on `facts`. RLS baseline (public read
  on civic tables).
- Python importers under `/pipelines`: LGD locality hierarchy (TN state code 33) and
  ECI constituency list (234 ACs, 39 PCs) → `localities` with `sources` rows.
- Bilingual constituency page rendering real imported data (name, level, hierarchy,
  provenance chip).
- Placeholder `/methodology` and `/freshness` pages (bilingual, honest "in progress"
  copy).
- **Exit criteria:** CI green; `supabase db reset` applies cleanly; importers
  idempotent (re-run safe); an AC page renders real LGD/ECI data in both locales.

### M2 — Geometry & "who represents me" resolution — `planned`
- Import DataMeet AC/PC/district boundaries (`ogr2ogr` → GeoJSON → PostGIS,
  SRID 4326) attached to `localities.geom`; verify against 2008 delimitation.
- Point-in-polygon resolver: location → AC + PC (+ district) chain (DESIGN.md §10).
- Homepage locality entry: browser geolocation with graceful fallback to a manual
  LGD-keyed locality picker (typeahead, bilingual).
- **Exit criteria:** entering a GPS point or picking a locality lands on the right
  constituency page; geolocation-denied path works.

### M3 — Representative spine: persons & tenures — `planned`
- Importers: ECI 2026 results (`results.eci.gov.in` S22 pages) → winners as
  `persons` + `tenures` for 234 ACs, marked **provisional** until Form 20; TN's 39
  Lok Sabha MPs + 18 Rajya Sabha members via data.gov.in resources (sansad.in is
  scrape-blocked — see DESIGN.md §13).
- Constituency page: representative card (photo, party, tenure, contact where
  sourced) with provenance chips; past-results section.
- Empty state for ward tier ("Ward-level councillor data is not yet available…").
- **Exit criteria:** every AC/PC page shows its current representative (or vacancy)
  with sources, in both locales.

### M4 — Affidavit data (MyNeta) — `planned`
- Pipeline: scrape MyNeta TN 2026 candidate pages; LLM_bulk extraction of assets/
  liabilities/criminal cases/education into `facts` with confidence + review_status;
  batched and cached.
- UI: "self-declared filing (source: ECI affidavit via MyNeta, retrieved <date>)"
  framing on every affidavit field.
- **Exit criteria:** MLA cards show affidavit summaries with correct labelling and
  provenance; spot-check ≥20 candidates against source pages.

### M5 — Vacancy & by-election tracker (flagship) — `planned`
- Daily pipeline over ECI press releases / TN CEO / eGazette; parse + NER; **human
  confirmation required before a status flip** (DESIGN.md §6).
- Tracker page over the `vacancies` view: seat, reason code, status (default
  "By-election awaiting ECI notification"), last-checked timestamp; quiet state.
- **Exit criteria:** tracker lists the current vacant seats with provenance and
  localized reason/status labels; daily cron green.

### M6 — News ingestion — `planned`
- Outlet registry (DESIGN.md §4E) as config + `sources` rows: RSS URL, tagging
  practice, paywall status, copyright note.
- RSS/HTML poller (30-min cron) → `news_items` (headline + link + metadata only,
  never article text); dedupe; locality tagging where derivable.
- **Exit criteria:** items flowing from ≥6 outlets across Tamil and English; no
  full-text storage; re-poll produces no duplicates.

### M7 — News clustering, summaries & coverage tables — `planned`
- Clustering: embedding similarity + temporal proximity + named-entity overlap →
  `news_clusters` + `cluster_coverage`.
- Neutral bilingual summaries with inline citations: cheap-model draft, frontier
  spot-check, cached in pipeline (never at request time).
- Locality + statewide feeds; coverage-transparency table (covered / not covered per
  tracked outlet — **no bias labels**); moderation classifier sets
  `discussion_locked` per the escalation protocol; locked-state UI.
- **Exit criteria:** a locality feed shows clustered events with bilingual summaries,
  citations, and coverage tables; empty state falls back to statewide feed.

### M8 — Data indicators: education (UDISE+) — `planned`
- UDISE+ ingest (district aggregation, TN codes 33xx) → `facts` with methodology
  metadata; label as voluntary self-reported data.
- Locality page "Data Indicators" panel: education trends with one-tap source link,
  retrieval date, and methodology notes. Structurally separate from any future
  sentiment display (never blended).
- **Exit criteria:** district education panel renders with full provenance in both
  locales; methodology section documents the computation.

### M9 — Accounts & Rung 0/1 community — `planned`
- Supabase phone-OTP auth; store `phone_hash` only; rung field on `users`.
- Structured contributions (forms, no free text): correction reports (from the
  provenance chip), issue confirmations, locality ratings (stored, not displayed
  until N≥25 in v0.5).
- LLM-first moderation classifier (red lines per DESIGN.md §8) + human review queue;
  all actions to append-only `moderation_events`; RLS write policies.
- **Exit criteria:** a signed-in user can file a correction from a provenance chip;
  it lands in the moderation queue; every action is audit-logged.

### M10 — Transparency pages & corrections log — `planned`
- `/methodology`: full bilingual content — every indicator's computation, source,
  cadence, limitations; why data and sentiment are never blended; no composite
  scores.
- `/freshness`: live `MAX(retrieved_at)` per source vs. SLA table (green/amber/red).
- Public corrections log: accepted corrections with timestamps, changed field, and
  retained original value.
- **Exit criteria:** all three pages render live data bilingually; a resolved test
  correction appears in the log.

### M11 — Launch hardening: performance, a11y, SEO — `planned`
- Font subsetting + self-hosting; lazy-load non-critical panels; ISR/edge caching.
- Lighthouse CI merge gate (Perf ≥ 90, A11y ≥ 95); sub-second locality page on a
  throttled low-end-Android profile; WCAG AA audit pass.
- SEO: SSR structured data, hreflang, sitemap, Tamil query targeting
  ("என் எம்எல்ஏ யார்"). Production Vercel deploy. **v0 ships.**
- **Exit criteria:** budgets met on throttled profile; both locales indexed;
  production live.

---

## Phase v0.5

### M12 — Health & water indicators — `planned`
HMIS (monthly) + NFHS-5 (per round) + JJM ingest → district panels with the same
provenance/methodology treatment as education.

### M13 — Community sentiment display — `planned`
Ratings display per sector above N=25 floor with sample size; temporal smoothing,
anomaly detection with display freeze + public note; below-floor empty state;
strictly separated from data indicators.

### M14 — Rung 2 comments (Madurai) — `planned`
Pre-moderated short comments on news clusters, unlocked per-district starting with
Madurai; published moderation SLAs (24h comments / 72h corrections); locked-cluster
enforcement.

### M15 — Madurai ward pilot — `planned`
TNSEC PDF parsing + manual curation for Madurai Corporation wards → councillor tier
on locality pages; explicit empty states everywhere else; ULB-count discrepancy
footnote (490 vs 561 town panchayats) per DESIGN.md §13.

---

## Phase v1

### M16 — Scheme discovery — `planned`
TN scheme directory + myScheme ingest; eligibility-oriented browsing (Feature 6).

### M17 — Public API & WhatsApp digest — `planned`
Public read API + bulk downloads (ODbL); WhatsApp digest bot (Feature 7).

### M18 — Expanded wards & air quality — `planned`
More corporations' ward data; TNPCB/CPCB air-quality panel only for localities near
stations (never imply statewide coverage).
