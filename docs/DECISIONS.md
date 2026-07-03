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

### D-003: Provenance columns extended beyond `facts`
DESIGN.md §5 puts provenance columns on `facts` only. Pillar 1 says *every displayed
fact* carries provenance, and M1 displays locality names/hierarchy. So `localities`,
`offices`, `persons`, and `tenures` also carry `source_id NOT NULL` +
`retrieved_at NOT NULL`. This strengthens, not contradicts, DESIGN.md §5.

