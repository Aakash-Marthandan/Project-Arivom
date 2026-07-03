# Arivom data pipelines

Python importers that populate the Arivom database from public sources.
They run on GitHub Actions cron (see `.github/workflows/`), **never** at
page-request time.

## Principles (enforced, not aspirational)

- Every row written carries `source_id` + `retrieved_at`; the schema rejects
  anything else (NOT NULL). See `docs/DESIGN.md` pillar 1.
- A Tamil name is accepted only if it contains Tamil-script codepoints.
  Rows that cannot obtain a genuine Tamil name are skipped and reported —
  never silently filled with English or invented text (see `docs/DECISIONS.md`
  D-005).
- Importers are idempotent: re-running updates in place, no duplicates.
- Importers fail loudly on unexpected universes (e.g. AC count ≠ 234).

## Setup

```sh
cd pipelines
uv sync
```

## Environment

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string (local dev: `postgresql://localhost/arivom`) |
| `DATA_GOV_IN_API_KEY` | Free key from data.gov.in. Falls back to the public sample key (fine for dev, rate-limited). |

## Importers

```sh
uv run import-lgd              # LGD hierarchy: state, districts, taluks
uv run import-constituencies   # ECI universe: 234 ACs + 39 PCs, bilingual
```

Run `import-lgd` first — constituencies link to districts.
