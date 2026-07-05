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

## Importers (run in this order)

```sh
uv run import-lgd              # LGD hierarchy: state, districts, taluks
uv run import-constituencies   # ECI universe: 234 ACs + 39 PCs, bilingual
uv run import-geometries       # DataMeet AC polygons, derived PCs, districts
uv run import-representatives  # 234 MLAs (2026) + 39 MPs (2024), bilingual
uv run import-affidavits       # self-declared profiles (MyNeta, MLA + MP)
uv run import-vacancies        # curated vacancy seed + status notes
uv run import-ministers        # council of ministers, bilingual portfolios
```

Independent of the order above (each needs only the localities spine):

```sh
uv run monitor-vacancies       # detection-only; daily GitHub Actions cron
uv run poll-news               # outlet registry → news_items; 30-min cron
```

poll-news ingests headline + link + feed metadata only — the parser never
reads article text (DESIGN §4E hard aggregation policy). The outlet
registry lives in `data/outlets.json`; outlets without a machine-readable
feed stay `pending` there with the reason, and every run reports them.

Every importer is idempotent and prints an audit and pending report; read it.
Status changes only enter through the curated, cited seeds in `data/`
(`vacancies_2026.json`, `status_notes.json`, `curated_names_ta.json`); the
importer validates the seated member's name before applying anything.

Quirks: ECI and MyNeta fetches shell out to curl (they reject Python TLS
fingerprints); wiki and MyNeta responses are disk-cached 24h in `.cache/`;
TN government sites are geo-blocked outside India (DECISIONS.md D-017).
