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

### D-006: Constituency universe = ECI portal; numbers for PCs = TN SHB 2020
The 234-AC universe (numbers + English names) comes from the ECI 2026 results
portal constituency dropdown (single fetch). The 39-PC universe with official
PC numbers comes from the "General Election to Lok Sabha by Parliamentary
Constituencies: SHB 2020" dataset on data.gov.in (PC numbering is fixed by the
2008 delimitation, so a 2020 source is current); reservation status (SC/ST) is
stored as a sourced fact, not in the name. AC→PC mapping and AC→district come
from Wikidata (P527 / P131), validated for completeness (every AC exactly one
PC; hard fail otherwise). elections.tn.gov.in was unreachable at build time.

### D-007: M1 imports state/districts/taluks + AC/PC; villages deferred
Villages (~17k) and local bodies are not needed by any M1 page and have the
worst `name_local` coverage; importing them under the no-fabricated-Tamil rule
would produce a large partial set with no consumer. Deferred to the milestone
that consumes them (geometry/ward work). Taluks with genuinely-Tamil LGD names
are imported; the gap list is printed by the importer run.

### D-008: Constituency URLs are code-based
`/constituencies/ac/111`, `/constituencies/pc/22` — language-neutral, stable
across renames, derived from `eci_code`. Name slugs can be added later as
redirecting aliases without breaking these.

### D-003: Provenance columns extended beyond `facts`
DESIGN.md §5 puts provenance columns on `facts` only. Pillar 1 says *every displayed
fact* carries provenance, and M1 displays locality names/hierarchy. So `localities`,
`offices`, `persons`, and `tenures` also carry `source_id NOT NULL` +
`retrieved_at NOT NULL`. This strengthens, not contradicts, DESIGN.md §5.

