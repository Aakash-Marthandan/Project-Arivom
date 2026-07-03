# அறிவோம் · Arivom

**Let us know our Tamil Nadu.** An open-source, fully bilingual (தமிழ் + English)
civic data platform: who represents you, how your locality is doing, and what
happened in your district this week — every fact with its source, free, with no
ads and no editorializing.

## Three pillars

1. **Transparency** — every displayed fact carries provenance (source, retrieval
   date, method, confidence) one tap away. A fact that cannot carry a source
   does not enter the database — enforced by `NOT NULL` constraints, not policy.
2. **Strict political neutrality** — no outlet bias labels, no composite scores,
   no opinion copy. Sourced facts and coverage transparency only.
3. **Craft** — fast on low-end Android over 4G, excellent Tamil typography,
   information-dense but calm, WCAG AA.

Full specification: [docs/DESIGN.md](docs/DESIGN.md) ·
Build plan: [docs/PLAN.md](docs/PLAN.md) ·
Decision log: [docs/DECISIONS.md](docs/DECISIONS.md)

## Stack

Next.js (App Router) + TypeScript strict + Tailwind + shadcn/ui + next-intl
(`ta` default locale, `en` second) · Supabase (Postgres + PostGIS) via SQL
migrations · Python pipelines under [`pipelines/`](pipelines/) on GitHub
Actions cron (never at page-request time) · Vercel.

## Development

Prerequisites: Node 22+, PostgreSQL 17 + PostGIS, [uv](https://docs.astral.sh/uv/).

```sh
# 1. Database
createdb arivom
for f in supabase/migrations/*.sql; do
  psql -d arivom -v ON_ERROR_STOP=1 -f "$f"
done

# 2. Real data (LGD hierarchy → constituencies → geometries)
cd pipelines && uv sync
DATABASE_URL=postgresql://localhost/arivom uv run import-lgd
DATABASE_URL=postgresql://localhost/arivom uv run import-constituencies
DATABASE_URL=postgresql://localhost/arivom uv run import-geometries
cd ..

# 3. Web app
cp .env.example .env.local   # adjust DATABASE_URL if needed
npm install
npm run dev
```

Open http://localhost:3000/ta (Tamil, default) or `/en`.

## Licensing

Code: [AGPL-3.0](LICENSE) · Curated data: ODbL · AI-generated summaries
(future): CC BY-SA. Not affiliated with any political party.
