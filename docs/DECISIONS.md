# Arivom — Decision Log

Resolved ambiguities and design decisions not fully specified by `docs/DESIGN.md`.
Newest first. Each entry: date, decision, rationale, and what would change it.

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

