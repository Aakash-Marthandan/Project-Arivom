# Arivom — Decision Log

Resolved ambiguities and design decisions not fully specified by `docs/DESIGN.md`.
Newest first. Each entry: date, decision, rationale, and what would change it.

---

## 2026-07-04 — Editorial directive (owner)

### D-016: Rational-citizen information hierarchy
Owner directive: pages present information from a rational citizen's
perspective — ranked by civic usefulness under a widely accepted moral
frame (the Constitution, common sense), never for entertainment value.
Operationalized as **de-emphasize, never bury**: sensitive self-declared
facts (assets, liabilities, criminal cases — owner confirmed assets belong
here too) move out of the immediate view into a neutral "More information"
disclosure (native `<details>`, no JS), while identity-adjacent facts
(education) stay visible. The
constitutional context cuts both ways and bounds this rule: the Supreme
Court's ADR jurisprudence entitles voters to candidates' criminal
antecedents and even mandates their publicity, so such facts must remain
exactly one tap away with a neutral label — never removed, paywalled, or
pushed behind additional friction, and never sensationalized in either
direction. Presentation may change (e.g. surfacing during election periods
when the information is most decision-relevant); the data itself is
untouched. Applies platform-wide as new surfaces are built (news layer:
prefer civically substantive clusters over engagement-bait framing).

## 2026-07-04 — M4 decisions

### D-015: Affidavits — deterministic parser; partial ADR coverage; guarded attachment
MyNeta's winners-analyzed listing is fully structured, so extraction is a
deterministic parser (`extraction_method='parser'`, confidence 1.0) — the
DESIGN's `llm_bulk` pattern stays reserved for genuinely unstructured
documents (e.g. Form 20 PDFs later; also no LLM key is configured yet).
Facts per winner: declared_assets, declared_liabilities, criminal_cases,
education — every value stored with `self_declared: true` and always
UI-framed as a self-declared ECI filing via MyNeta (ADR), per DESIGN.md.
Coverage is whatever ADR has analyzed (208/234 at first import): the 26
outstanding ACs show an honest "not yet analyzed" note and are listed on
every import run. Attachment safety: rows bind to a person only when the
MyNeta winner name is similar to the ECI winner name — this both validates
every row and disambiguates same-named constituencies (the two Tiruppatturs,
whose shared display name had silently collided in a name-keyed lookup).
The M4 spot-check cross-validates 20 sampled candidates against MyNeta's
per-candidate detail pages on every run; any mismatch fails the import.

## 2026-07-03 — M3 decisions

### D-013: Representative spine sourcing — vote-anchored bilingual joins
MLA winners/parties/votes: ECI 2026 portal per-AC pages (provisional until
Form 20, framed as such in UI and facts). Tamil renderings come from Tamil
Wikipedia, joined **by constituency number and validated by exact vote-count
equality** (script-independent); fallbacks in order: statewide results table
(±1% drift tolerated at lower confidence) → pre-election candidates table
(party-anchored, self-calibrated against pass-1 names) → per-AC articles
(vote-anchored AND party-validated — a vote coincidence with the wrong party
is rejected; this caught a real mis-extraction). Lok Sabha 2024: enwiki
results table (EN authority) + tawiki elected-members table, validated by
party match plus alliance-votes cross-check (the ECI 2024 portal is offline;
sansad.in blocks scraping). Person identity is **per seat**
(`tn2026:ac<n>:<name>`): two same-named winners in different seats stay two
people; a dual-seat winner (C. Joseph Vijay: Perambur + Tiruchirappalli East)
appears as two rows until person-level reconciliation lands with affidavit
data (M4). Rajya Sabha members are descoped to the milestone that displays
state-level representation — importing them now would be dead data. Tenure
start = result-declaration date (oath dates are not machine-available);
basis recorded in each election_result fact.

### D-014: Missing Tamil renderings are NULL, never transliterated
33 of 234 winners (mostly first-term members) have no Tamil rendering of
their name in any machine-checkable source yet. `persons.name_ta` is now
nullable (migration 20260704020000): the UI shows the sourced English name
with a visible "Tamil name pending source verification — we do not use
machine transliterations" note, and every import run prints the outstanding
list until it reaches zero. Manual sourced curation (or wiki catch-up) closes
these; a machine transliteration would violate D-005.

## 2026-07-03 — M2 decisions

### D-011: District conflict audit — flag by default, adjudicate narrowly
With geometry loaded, every AC's stored district is audited against the
majority-overlap district polygon (geoBoundaries 2021). The audit found 13
standing disagreements, and **neither side wins uniformly**: geoBoundaries
lacks Chennai district's 2018 GCC expansion (so ACs 7–10, 27, 30–34 are
correct as stored), its Kanchipuram↔Chengalpattu line is offset (ACs 36–37
correct as stored), and Tirukkoyilur (76) is genuinely contested between
sources (Kallakurichi vs Viluppuram). Policy: audit prints every mismatch on
each run; stored values are never auto-overwritten. One narrow, documented
override (`SPATIAL_OVERRIDES` in the importer): AC 160 Sirkazhi, whose stored
value traced only to a stale Wikidata claim (pre-2020 split) — reassigned to
Mayiladuthurai (99% overlap, recorded as a spatial fact). The authoritative
adjudicator for the rest is the TN CEO district-wise AC list (unreachable at
build time); revisit when reachable.

### D-012: PC geometry derived from member ACs; districts from geoBoundaries
PC polygons are computed as the union of member-AC polygons rather than
imported from DataMeet's 51 MB PC shapefile: guarantees the point resolver
can never place a point in an AC and a different PC, and keeps the download
small. District polygons come from geoBoundaries gbOpen ADM2 2021 (ODbL —
same license as our curated data), the only found open source with the
post-2019 TN districts.

---

## 2026-07-03 — Environment finalization (post-M1)

### D-010: Interim data-source operations until ~2026-07-13
Repository is `github.com/Aakash-Marthandan/Project-Arivom` (public); Supabase
is connected via the GitHub integration. The owner registers a personal
data.gov.in API key after relocating to India (~10 days). Until then:
pipelines keep using the public documented sample key (rate-limited but
sufficient for the small M1/M2 datasets); the `pipelines.yml` cron stays
dormant (`PIPELINES_ENABLED` variable unset); local imports remain the dev
data source. M2 proceeds on public sources (DataMeet boundaries need no key).
Production data load + cron activation happen once `DATABASE_URL` and
`DATA_GOV_IN_API_KEY` secrets are set.

---

## 2026-07-03 — M1 kickoff decisions

### D-001: Local dev database is plain Postgres + PostGIS (no Docker)
This machine has no Docker, so the Supabase local stack (`supabase start`) cannot
run. Migrations in `supabase/migrations/` are written as plain SQL compatible with
both, applied locally and in CI via `psql` in filename order against a PostGIS-enabled
Postgres. They remain fully compatible with `supabase db reset`/`db push` for the
hosted project. Revisit if Docker becomes available.

### D-002: Server-side reads use a direct Postgres connection (postgres.js)
Locality/constituency pages are server-rendered from Postgres via the `postgres`
npm client using `DATABASE_URL`, rather than supabase-js/PostgREST. Reasons: works
identically against local Postgres and hosted Supabase (pooler URL); one fewer
network hop on the hot path (performance pillar); no auth needed for public read
data. supabase-js enters in M9 for phone-OTP auth and RLS-scoped writes. RLS is
still enabled from M1 so PostgREST exposure is safe when it arrives.

### D-004: LGD ingestion via the data.gov.in mirror, not lgdirectory.gov.in
The LGD portal's bulk download requires a captcha — an explicit signal against
unattended automation, and unusable in CI. DESIGN.md §4.12 lists the data.gov.in
mirror as a sanctioned access path; its LGD resources (districts, sub-districts,
villages, local bodies) are current (updated 2026-07-03 at time of checking) and
include `*_name_local` columns. Requires a data.gov.in API key (free; CI secret;
public sample key for local dev).

### D-005: Tamil names — source hierarchy and hard-fail policy
LGD `*_name_local` is inconsistently populated for TN (some rows Tamil, some
uppercase English, some blank). Policy: a name is accepted as Tamil only if it
contains Tamil-script codepoints. Fallback for districts and constituencies is
Wikidata labels (CC0), which cover 100% of TN districts, ACs (Q54375510), and
PCs (Q47481352). Every Wikidata-sourced Tamil name is also recorded as a `facts`
row pointing at the Wikidata source, so the name's provenance survives even
though `localities` has a single `source_id` (which stays with the authority for
the row's existence: LGD or ECI). Rows that cannot obtain a genuine Tamil name
are NOT imported (name_ta is NOT NULL); importers report the gap loudly. We
never silently fill Tamil fields with English or invented text.

### D-006: Constituency sourcing — layered, cross-validated (revised)
- **AC universe** (numbers + English names): ECI 2026 results portal dropdown.
  The portal's WAF rejects Python HTTP clients at the TLS layer while serving
  curl, so that one fetch shells out to curl (documented in code).
- **PC universe** (numbers + names + reservation): "General Election to Lok
  Sabha by PC: SHB 2020" on data.gov.in (PC numbering is delimitation-fixed,
  so a 2020 source is current). Reservation stored as a sourced fact.
- **AC→PC linkage + AC reservation**: DataMeet's ECI-derived AC shapefile
  attribute table — numeric AC_NO→PC_NO, cross-checked against SHB PC names.
  Chosen after Wikidata P527 and the enwiki table each proved wrong for
  different ACs (e.g. Sholinganallur, Mettuppalayam); DataMeet adjudicated
  and is delimitation-authoritative for this mapping.
- **AC→current district**: enwiki constituency table (structurally clean rows
  only — the page has hand-edited rows with shifted cells) → Wikidata P131
  (district-class filtered) → DataMeet delimitation-era value as last resort.
- **Tamil names**: Wikidata labels (with tawiki article-title fallback when a
  ta label contains non-Tamil text), matched name-first with district-based
  disambiguation; multi-/duplicate-ordinal P1545 values are not trusted.
- elections.tn.gov.in was unreachable at build time; when reachable it can
  strengthen the district linkage (official AC-wise electors report).

### D-009: Stale-district guard — withhold rather than mislead
When the ONLY district signal for an AC is DataMeet's delimitation-era value
and that district was later split (Tiruppur 2009; Ranipet, Tirupathur,
Chengalpattu, Kallakurichi, Tenkasi 2019; Mayiladuthurai 2020), the current
district is uncertain, so `district_id` stays NULL and the page simply omits
the district line. Affects 10 ACs as of the M1 import (list printed by each
run). Displaying a possibly-wrong district would violate pillar 1 in spirit;
M2's boundary import resolves these spatially (AC polygon ∩ current district
polygons).

### D-007: M1 imports state/districts/taluks + AC/PC; villages deferred
Villages (~17k) and local bodies are not needed by any M1 page and have the
worst `name_local` coverage; importing them under the no-fabricated-Tamil rule
would produce a large partial set with no consumer. Deferred to the milestone
that consumes them (geometry/ward work). Taluks take Tamil names from LGD
where genuinely Tamil, else Wikidata (Q122987736 items); 282 of 316 imported,
34 skipped and reported (M1 run).

### D-008: Constituency URLs are code-based
`/constituencies/ac/111`, `/constituencies/pc/22` — language-neutral, stable
across renames, derived from `eci_code`. Name slugs can be added later as
redirecting aliases without breaking these.

### D-003: Provenance columns extended beyond `facts`
DESIGN.md §5 puts provenance columns on `facts` only. Pillar 1 says *every displayed
fact* carries provenance, and M1 displays locality names/hierarchy. So `localities`,
`offices`, `persons`, and `tenures` also carry `source_id NOT NULL` +
`retrieved_at NOT NULL`. This strengthens, not contradicts, DESIGN.md §5.

