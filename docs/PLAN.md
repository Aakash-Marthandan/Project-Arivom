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

### M2 — Geometry & "who represents me" resolution — `done` (2026-07-03)
Shipped: AC polygons from DataMeet (pyshp → GeoJSON → PostGIS, ST_MakeValid,
SRID 4326); PC polygons derived as union of member ACs (D-012); current
district polygons from geoBoundaries ADM2 2021 (ODbL). Point-in-polygon
resolver + `/locate` flow: geolocation button (privacy note, graceful denial),
server-side resolution, always-present bilingual name search fallback; result
carries a boundary-provenance chip and a 2008-delimitation accuracy note.
The 10 withheld districts (D-009) resolved spatially at 90–100% overlap; full
AC↔district audit runs on every import — 13 standing conflicts flagged, one
narrow adjudication (Sirkazhi → Mayiladuthurai, D-011). Verified in-browser:
Madurai/Trichy/Chennai/Kanyakumari points, outside-TN state, denied path,
locale switch preserving coordinates. Deployed to production.

### M3 — Representative spine: persons & tenures — `done` (2026-07-03)
Shipped: 234/234 MLAs (ECI 2026, provisional-framed) + 39/39 Lok Sabha MPs
with bilingual names via vote-anchored, party-validated joins (D-013);
representative cards with provenance chips, election-result stat blocks
(votes/share/margin/runner-up), provisional badges, and the ward-tier empty
state; per-seat person identity with the dual-seat winner correctly modeled.
33 MLAs display in English pending a sourced Tamil rendering (D-014 — never
transliterated; reported on every import run). RS members descoped to the
state-level-display milestone (D-013). Contact channels and photos arrive
with M4 affidavit/person reconciliation.

### M4 — Affidavit data (MyNeta) — `done` (2026-07-04)
Shipped: self-declared affidavit summaries (assets, liabilities, criminal
cases, education) for 208/234 winning MLAs — full ADR coverage at import
time; the 26 ACs ADR hasn't analyzed yet show an honest pending note and are
reported on every run. Deterministic parser extraction (D-015 — MyNeta pages
are structured; llm_bulk reserved for unstructured PDFs), name-similarity-
guarded attachment (caught the two-Tiruppattur collision), and the required
≥20-candidate spot-check automated into every import (cross-validates the
listing against detail pages; run fails on any mismatch). UI: affidavit
block on MLA cards with "self-declared" badge, ECI-via-MyNeta provenance
chip, localized education categories, Indian-grouped ₹ formatting.

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
