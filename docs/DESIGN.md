# Tamil Nadu Civic Data Platform — Design Document (v1.0)

## TL;DR

- **What to build:** A free, open-source, fully bilingual (Tamil + English, full parity) web-first civic data platform for Tamil Nadu that gives an average rational Tamil citizen an unbiased, provenance-first way to see *who represents me*, *how my area is doing on basic services*, and *what happened in my district this week* — launching statewide across all 234 assembly constituencies (ACs) and 39 parliamentary constituencies (PCs), with ward data phased in via a Madurai Corporation pilot.
- **Why now:** The 4 May 2026 result produced Tamil Nadu's first-ever hung assembly — TVK (C. Joseph Vijay) emerged largest with 108 of 234 seats (10 short of the 118 majority), DMK 59, AIADMK 47, at a record 85.1% turnout — and by June 2026 seven seats had gone vacant (Vijay must vacate one of his two won seats; six AIADMK MLAs resigned to join TVK), making a **live vacancy/by-election tracker** a genuinely flagship, time-sensitive feature.
- **How it holds together:** Three enforced pillars — (1) **Transparency** (every fact carries source, retrieval date, method, confidence; a fact that cannot carry a source does not enter the repository), (2) **Strict political neutrality** (no editorializing, no outlet bias labels, no composite scores; data indicators and community sentiment are *never* blended), and (3) **Thoughtful UX** (fast on low-end Android over 4G, exceptional Tamil typography, accessible). Stack: Next.js (App Router) + Tailwind + shadcn/ui + next-intl, Supabase (Postgres + PostGIS, phone-OTP auth), Vercel, Python + GitHub Actions pipelines, LLMs used offline (never at page-request time).

---

## 1. Executive Summary and Three Pillars

This document specifies a free, open-source, fully bilingual civic data platform for Tamil Nadu. Its purpose is to cut through the distraction and bias of the open internet and give every Tamil citizen an informed, ethical, rational, and polished way to access civic information about their locality and representatives. It is designed from the perspective of an average rational Tamil citizen who wants three things quickly: who represents me, how is my area doing on basic services, and what actually happened in my district this week.

The platform launches web-first (server-side rendering + SEO), statewide, covering all 234 ACs and 39 PCs. Ward-tier data is phased in via a Madurai Corporation pilot. A flagship live vacancy and by-election tracker addresses the unprecedented political flux following the May 2026 hung assembly.

**Three pillars govern every decision, and are referenced throughout this document:**

1. **Transparency.** Every fact carries visible provenance — source, retrieval date, extraction method, confidence — one tap away. There is a public methodology page, a corrections log, and a `/freshness` page showing last-updated timestamps per dataset. **Hard rule: a fact that cannot carry a source does not enter the repository.**
2. **Strict political neutrality.** No editorializing, no outlet bias labels, no composite opaque scores. Coverage transparency and raw sourced facts speak for themselves. Affidavit data is always labelled "self-declared." Data indicators and community sentiment are displayed separately and never blended into a single number.
3. **Thoughtful structuring of every detail for a top-tier user experience.** Fast on low-end Android over 4G, exceptional Tamil typography, information-dense but uncluttered, accessible (WCAG AA).

**Licensing (public-benefit civic project):** Code under **AGPL-3.0**; curated data under **ODbL**; AI-generated summaries under **CC BY-SA**.

---

## 2. User Personas and Top User Journeys

**Persona 1 — Meena, 34, Madurai, teacher, primarily Tamil.** Wants to know who her new MLA is after the 2026 election and how to contact them. Journey: opens site → allows location or types "Madurai" → sees representation chain (MLA, MP, ward councillor where available) with photo, party, contact, self-declared affidavit summary. All content renders identically in Tamil.

**Persona 2 — Arun, 27, Coimbatore, engineer, bilingual.** Wants to know if his area's schools are improving. Journey: locality page → *Data Indicators* → Education panel → district UDISE+ trend with full methodology and a one-tap source link and retrieval date.

**Persona 3 — Kavitha, 45, Tiruchirappalli, small-business owner.** Wants a neutral view of "what happened in my district this week." Journey: locality news feed → event clusters, each with a neutral bilingual AI summary + a coverage-transparency table showing which tracked outlets covered it.

**Persona 4 — Suresh, 52, retired, civic-minded.** Notices a wrong MLA phone number. Journey: taps the provenance chip → "Report a correction" structured form → correction enters the moderation queue and appears (once resolved) in the public corrections log.

The four journeys map directly to the task's canonical queries: "who represents me," "is my area's school situation improving," "what happened in my district this week," and "report a wrong phone number."

---

## 3. Complete Feature Specifications

### Feature 1 — Geography and Representative Spine
User enters or selects a location and sees their complete representation chain: ward councillor (where data exists), MLA, MP. Each card shows photo, party, contact channels, tenure history, self-declared affidavit summary (assets, liabilities, criminal cases, education), and past election results for the constituency. Statewide coverage of 234 ACs and 39 PCs at launch. Ward-tier phased in from Madurai Corporation.

- **Empty state (no ward data):** "Ward-level councillor data is not yet available for your area. Here is your MLA and MP." Never fabricated.
- **Error state (geolocation fails):** fallback to a manual locality picker keyed to the LGD hierarchy.
- **Affidavit labelling:** every asset/criminal/education field is tagged "self-declared filing (source: ECI affidavit, retrieved <date>)."
- **Bilingual parity:** every field, including party names and constituency names, rendered in both Tamil and English.

### Feature 2 — Live Vacancy and By-Election Tracker (flagship)
Given the May 2026 hung assembly, this tracks which seats are vacant, why (death/resignation/disqualification), by-election status, updated daily. Data drawn from ECI press releases, the TN Chief Electoral Officer, and the eGazette. Each entry carries provenance and a "last checked" timestamp. As of mid-2026 the tracker's default state for pending seats is **"By-election awaiting ECI notification."**

- **Empty/quiet state:** "No vacancies currently recorded" with last-checked timestamp.
- **Bilingual parity:** reason codes and status labels localized.

### Feature 3 — News Layer (Ground News-adapted for TN)
Per-locality and statewide feeds of stories clustered by event across multiple tracked outlets. Each cluster carries a neutral AI-generated bilingual summary with citations and a **coverage-transparency table** showing which tracked outlets covered the story and which did not. **Explicitly NO outlet bias labels.** Headlines + links + short own-words summaries only, for copyright compliance.

- **Empty state:** "No clustered stories for this locality this week — showing statewide feed."
- **Locked-discussion state:** controversial clusters show the neutral summary + coverage table with a visible "Discussion locked" note (see escalation protocol).

### Feature 4 — Two-Prong Locality Assessment (never blended)
- **(a) Data Indicators:** per-sector panels (education first, then health, then water/sanitation) computed from public datasets with full disclosed methodology, source link, and retrieval date.
- **(b) Community Sentiment:** verified-user locality ratings per sector, one live rating per user per locality per sector, shown with sample size, **only above a participation floor of N=25**, with anti-brigading measures (phone verification, temporal smoothing, anomaly detection with display freeze and a public note).
- The two prongs are visually and structurally separated; there is no combined score.
- **Below-floor state:** "Not enough verified ratings yet (need at least 25) — data indicators still shown above."

### Feature 5 — Staged Community Ladder
- **Rung 0** (read + reactions) and **Rung 1** (structured contributions: correction reports, issue confirmations, locality ratings via forms — not free text) live statewide at launch.
- **Rung 2** (short comments on news clusters, pre-moderated) unlocked per-district, gated on moderation capacity; **Madurai first**.
- **Rung 3** (open threads) much later.
- Phone-OTP verified accounts, no anonymous contributions, no user media uploads initially. LLM-first moderation with human review queues and published SLAs. **Red lines:** no user discussion on communal tensions, sub judice matters, or unverified corruption allegations against named individuals; big controversial stories get coverage clusters with discussion locked (escalation protocol).

### Feature 6 — Scheme Discovery Module (phase 2)
Eligibility-oriented browsing of TN government schemes, sourced from the TN scheme directory and myScheme.

### Feature 7 — WhatsApp Digest Bot + Public API (phase 2)
Public read API + bulk downloads. Native mobile app deferred; web-first with SSR and SEO targeting queries like "**என் எம்எல்ஏ யார்**" ("who is my MLA").

---

## 4. Full Data Source Catalog

Verified live and accessible as of July 2026 unless flagged. Granularity, access mode, format, cadence, license, and reliability noted per source.

### A. Electoral and Representative Data

1. **ECI Results Portal (2026 TN assembly).** `https://results.eci.gov.in/ResultAcGenMay2026/` — state code **S22**. Party-wise `partywiseresult-S22.htm`; vote share `voteshareresult-S22.htm`; per-constituency `ConstituencywiseS22{AC}.htm` (e.g. `…S2240.htm` = Katpadi AC 40); round-wise `RoundwiseS22{ac}.htm`. **Access:** HTML scrape. **Granularity:** constituency. **Reliability caveat:** the portal itself states final data comes via Form 20 — treat the `.htm` results as preliminary RO-entered trends. No explicit license; public government data.
2. **Form 20 (polling-station-level results).** TN CEO PDFs per AC: pattern `https://www.elections.tn.gov.in/Form20_TNLA2021.aspx` (2016 at `Form20.aspx`); a 2026 page is expected on the same pattern once published — verify. **Access:** PDF, per-constituency. Definitive detailed record.
3. **Candidate affidavit archive.** Legacy `affidavitarchive.nic.in` is **superseded**; current official portal `https://affidavit.eci.gov.in/` (searchable by state/constituency/party). Candidate profile scans hosted under `results.eci.gov.in/uploads4/candprofile/…`. **Access:** scrape + PDF/JPG scans.
4. **ADR / MyNeta.** `https://www.myneta.info/` and TN 2026 at `https://www.myneta.info/TamilNadu2026/`. Structured criminal/financial/education/income analysis of self-declared affidavits (state_id 27 = TN for RS/older pages). **Access:** HTML scrape, per-candidate pages. **Reliability:** high; MyNeta explicitly mirrors ECI public-domain data and defers to ECI on discrepancies. Always label "self-declared." Per ADR, 404 of 722 major-party candidates in the 2026 TN election declared serious criminal cases.
5. **TN Chief Electoral Officer.** `https://www.elections.tn.gov.in/`. MP lists, Form 20, notifications, candidate lists. **Reliability:** authoritative state source; some pages are older vintage — verify currency for 2026.
6. **TN State Election Commission (TNSEC).** `https://www.tnsec.tn.gov.in/`. Urban local body (Feb 2022) and rural local body (Dec 2019) election results. **Universe:** 25 municipal corporations, 148 municipalities; town panchayats reported as **490 as of 2026** (older sources cite 561 — see Data Gaps §13 for this conflict). Rural: 12,620 village panchayats, 385 panchayat unions, 37 district panchayats. The 2022 urban polls (19 Feb 2022) elected 12,838 councillors across 21 corporations, 138 municipalities and 489 town panchayats. **Access:** results published as PDFs — the primary reason ward data is hard to machine-ingest statewide.
7. **TN Legislative Assembly.** Official `https://www.assembly.tn.gov.in/`; members list `https://assembly.tn.gov.in/16thassembly/members.php` (note: the 17th Assembly was constituted May 2026 — member pages will migrate). Proceedings via NeVA/eVidhan `https://tnla.neva.gov.in/`. Digital repository of debates 1921–present, OCR'd and searchable in Tamil + English: `https://tnlasdigital.tn.gov.in/jspui/`.
8. **PRS Legislative Research.** `https://prsindia.org/`. MP Track (attendance, questions, debates, private-member bills) `https://prsindia.org/mptrack`; MLA Track `https://prsindia.org/mlatrack`; state legislature vital stats `https://prsindia.org/legislatures/states`. **Access:** static HTML (scrapeable, unlike sansad.in) + downloadable worksheets/PDFs at `https://prsindia.org/mptrack/download`; no formal public API. **License:** CC BY 4.0 site-wide (with a non-commercial disclaimer nuance on individual reports — attribute "PRS Legislative Research"; confirm directly for commercial reuse). **Reliability:** highest practical source for legislator performance metrics; ministers/Speaker excluded from participation counts. PRS's own upstream sources: sansad.in, egazette.gov.in, neva.gov.in.
9. **Lok Sabha members (TN's 39 MPs).** Digital Sansad `https://sansad.in/ls/members` (filter by state). **Access caveat:** JavaScript single-page app, robots-disallowed, no documented public API — requires a headless browser. **Fallback:** data.gov.in "List of Lok Sabha Members (English)" resource with a free API key (JSON/CSV/XML), plus a legacy XML feed (`164.100.47.193/android_rssfeed_ls/code.aspx?code=member`). TN-specific list also at `https://www.elections.tn.gov.in/Web/mp_tn.htm`.
10. **Rajya Sabha members (TN 18 seats).** `https://sansad.in/rs/members` (same SPA caveats). TN RS composition is set by pre-May-2026 biennial cycles (June 2025 + April 2026 unopposed elections) and is **unaffected** by the hung assembly, since RS terms run six years.
11. **Vacancy / by-election tracking.** ECI press releases `https://www.eci.gov.in/` (JS app; legacy readable archive at `eci.gov.in/files/category/11-press-releases/`), eGazette `https://egazette.gov.in/`, and TN CEO. **Current status (June 2026):** seven assembly seats reported vacant (Vijay vacated one of Perambur/Tiruchirappalli East; six AIADMK MLAs resigned to join TVK); by-polls not yet notified; situation fluid (AIADMK faction reconciliation on 27 May 2026 may affect the final count). Verify count against ECI before display.

### B. Administrative Geography

12. **Local Government Directory (LGD).** `https://lgdirectory.gov.in/`. Full TN hierarchy with unique codes: districts, sub-districts (taluks), blocks, villages, ULBs, and their rural/urban wards. **TN state code 33.** **Access:** web services + downloadable entities; also mirrored on `data.gov.in/catalog/local-government-directory-lgd`. Authoritative standard-location codes mandated across e-governance. **This is the spine of the `localities` table.**
13. **DataMeet maps.** `https://github.com/datameet/maps`. AC and PC boundary shapefiles (scraped from ECI), district boundaries, Survey-of-India index maps. **License:** CC BY 2.5/4.0. **Caveat:** some names/boundaries are stale or pre-delimitation for certain states; TN is generally usable but verify against the 2008 delimitation and crowdsourced corrections. Convert shapefiles → GeoJSON/PostGIS via `ogr2ogr`.
14. **Greater Chennai Corporation / OpenCity.** GCC ward and area-sabha maps (updated Dec 2022) via `https://data.opencity.in/`.
15. **PIN-code-to-locality.** India Post directory; the all-India pincode dataset on data.gov.in as a fallback keyed to LGD/village names.

### C. Government Transparency and Administrative Data

16. **TN Government Portal.** `https://www.tn.gov.in/`; schemes directory `https://www.tn.gov.in/scheme` (department-wise, beneficiary-wise A–Z).
17. **Government Orders / Gazette.** Stationery & Printing Dept `https://www.stationeryprinting.tn.gov.in/gazette.php`; search `search_gazette.php`; extraordinary gazettes by year. **Access:** PDF. Publishes land-acquisition, name-change, and public-interest notifications relevant to constituency/administrative changes.
18. **TN Open Government Data.** `https://tn.data.gov.in/`. CSV/XLS/ODS/XML/RDF/KML/GML datasets by department; API list at `/apis`. **License:** NDSAP. **Caveat:** intermittent maintenance windows observed — cache aggressively.
19. **OpenCity Urban Data Portal (CivicDataLab).** `https://data.opencity.in/`. CKAN platform, 534+ datasets / 1,323+ documents; Chennai/TN electoral (2016 assembly), health-centre lists/maps, ward maps, wetlands, and UDISE-for-Chennai data. Strong prior-art bridge for Chennai-specific granularity.
20. **CM Helpline / grievances.** CPGRAMS public dashboards (national) for grievance-volume context; TN CM Helpline (1100) — note this is a service line, not an open dataset, so treat as reference only.

### D. Sector Indicator Datasets (fine granularity)

21. **Education — UDISE+.** `https://udiseplus.gov.in/`; Know Your School `https://kys.udiseplus.gov.in/`; report cards downloadable by UDISE code; national reports at `education.gov.in`. TN operates its own EMIS syncing to UDISE+; TN codes start with **33**. **Granularity:** school-level, with district as the unit of distribution. **Cadence:** annual, 30 Sept reference date. **Reliability caveat:** voluntary self-uploaded data — label as such.
22. **Health — HMIS + NFHS-5.** HMIS district monthly reports: `https://www.data.gov.in/catalog/item-wise-monthly-hmis-report-district-level-tamil-nadu`. NFHS-5 district factsheets (district-level estimates for most indicators; sensitive indicators only at state level): `https://www.data.gov.in/catalog/national-family-health-survey-5-nfhs-5-india-districts-factsheet-data`. TN NHM `https://www.nhm.tn.gov.in/`. **Cadence:** HMIS monthly; NFHS per survey round (NFHS-5 = 2019–21).
23. **Water/Sanitation — Jal Jeevan Mission.** Dashboard `https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx`; district ranking / Har Ghar Jal coverage. **Granularity:** village/district. **Access:** HTML scrape. TN reported 80–<100% coverage as of the 5-year JJM review. Also Swachh Bharat and TWAD (TN Water Supply and Drainage Board) as supplementary sources.
24. **Environment — TNPCB / CPCB air quality.** TNPCB AQI `https://tnpcb.gov.in/aqi.php` and `aqi_caaqms.php`; CPCB real-time `https://cpcb.nic.in/real-time-air-qulity-data/`. CAAQMS station data flows CPCB → TNPCB via API, displayed as 24-hr averages. **Caveat:** limited station coverage (Chennai 8, Trichy 5, Madurai/Coimbatore/Thoothukudi/Cuddalore 3 each, Mettur 2, Salem 1) — never imply statewide coverage.
25. **Economy/Employment — MGNREGA.** `https://nrega.nic.in/` public MIS ("Generate Reports"), including job cards, muster rolls, work registers, and wages at **panchayat/village** granularity. **Access:** HTML scrape (state code 33). **Reliability caveat:** several SEO aggregator sites made **unverified** claims about a "VB-G RAM G Act 2025" replacing MGNREGA — do not repeat; rely only on the official nrega.nic.in portal and confirm any statutory change against a primary government source.
26. **Census 2011.** `censusindia.gov.in` district/village handbooks — baseline demographic granularity down to village.
27. **Cross-sector indices.** NITI Aayog SDG India Index and district dashboards for state/district benchmark context (use as labelled secondary indicators only, given composite-score sensitivity).

### E. Tamil Nadu News Ecosystem (Outlet Registry for the Aggregation Layer)

**Tamil dailies:** Dinamalar (RSS `https://www.dinamalar.com/rssfeed.asp`), Dinakaran, Dinamani, Daily Thanthi, Maalaimalar, Hindu Tamil Thisai. **TV/digital:** Puthiyathalaimurai (`https://www.puthiyathalaimurai.com/`), Polimer, News7, News18 Tamil, Sun News, Oneindia Tamil (RSS `https://tamil.oneindia.com/rss/`). **English:** The Hindu, Times of India Chennai, New Indian Express, DT Next. **Fact-checkers:** YouTurn, Factly, BOOM, Alt News.

For each outlet the registry stores: RSS URL (where available), site structure for aggregation, district/locality tagging practice, paywall status, and a copyright note. **Aggregation policy (hard):** headlines + links + own-words neutral summaries only. Google News Tamil (`news.google.com/?hl=ta&gl=IN&ceid=IN:ta`) is a discovery aid, not a content source.

### F. Civic Tech Prior Art and Open-Data Communities

DataMeet, OpenCity/CivicDataLab, Janaagraha / iChangeMyCity, Reap Benefit, Open Budgets India, Justice Hub. **Instructive precedent:** the **Neta app** (founded by Pratham Mittal; launched nationally in August 2018 by former President Pranab Mukherjee) let voters rate MLAs/MPs and crossed 1 lakh downloads within hours — demonstrating strong demand but relying on opaque cumulative/composite scoring and facing rating-manipulation risk. This platform explicitly avoids those failure modes by never blending data and sentiment and never publishing composite scores. (Note: "myneta.com" — a separate civic-issue-tracking product — is distinct from ADR's affidavit repository "myneta.info"; keep the two clearly separated in the source registry.)

### G. Schemes and Services

myScheme `https://www.myscheme.gov.in/` (eligibility-based discovery; TN government-services home at `/schemes/gshtn`); TN e-Sevai / TNeGA (`https://www.tnesevai.co.in/` and via `services.india.gov.in`); TN scheme directory `https://www.tn.gov.in/scheme`; welfare board data via respective department pages.

---

## 5. Data Architecture and Schema (DDL-level)

PostgreSQL + PostGIS on Supabase.

```sql
-- Localities: LGD/ECI-coded hierarchy with geometry
CREATE TABLE localities (
  id BIGSERIAL PRIMARY KEY,
  lgd_code TEXT UNIQUE,            -- Local Government Directory code (TN state = 33)
  eci_code TEXT,                   -- ECI constituency code where applicable
  name_en TEXT NOT NULL,
  name_ta TEXT NOT NULL,
  level TEXT NOT NULL,             -- state|district|taluk|block|ulb|panchayat|ward|ac|pc
  parent_id BIGINT REFERENCES localities(id),
  geom GEOMETRY(MultiPolygon, 4326),
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_localities_geom ON localities USING GIST (geom);

CREATE TABLE offices (             -- MLA, MP (LS/RS), ward councillor, etc.
  id BIGSERIAL PRIMARY KEY,
  office_type TEXT NOT NULL,       -- mla|mp_ls|mp_rs|councillor
  locality_id BIGINT REFERENCES localities(id),
  title_en TEXT, title_ta TEXT
);

CREATE TABLE persons (
  id BIGSERIAL PRIMARY KEY,
  name_en TEXT NOT NULL, name_ta TEXT NOT NULL,
  photo_url TEXT, party_en TEXT, party_ta TEXT
);

CREATE TABLE tenures (
  id BIGSERIAL PRIMARY KEY,
  office_id BIGINT REFERENCES offices(id),
  person_id BIGINT REFERENCES persons(id),
  start_date DATE, end_date DATE,   -- NULL end_date = current
  status TEXT                        -- active|vacant|resigned|deceased|disqualified
);
-- Vacancy tracker = VIEW over offices with no active tenure OR tenure.status='vacant'
CREATE VIEW vacancies AS
  SELECT o.* FROM offices o
  LEFT JOIN tenures t ON t.office_id = o.id AND t.end_date IS NULL AND t.status='active'
  WHERE t.id IS NULL;

CREATE TABLE sources (
  id BIGSERIAL PRIMARY KEY,
  name TEXT, url TEXT, publisher TEXT,
  license TEXT, access_mode TEXT      -- api|scrape|pdf|bulk|rti
);

CREATE TABLE facts (
  id BIGSERIAL PRIMARY KEY,
  subject_type TEXT, subject_id BIGINT,   -- polymorphic (person/locality/office)
  key TEXT,                                -- e.g. 'declared_assets','criminal_cases'
  value JSONB,
  source_id BIGINT REFERENCES sources(id) NOT NULL,   -- HARD PROVENANCE REQUIREMENT
  retrieved_at TIMESTAMPTZ NOT NULL,
  extraction_method TEXT,                  -- manual|llm_bulk|parser|api
  confidence NUMERIC,
  review_status TEXT                       -- unreviewed|llm_checked|human_verified
);

CREATE TABLE news_items (
  id BIGSERIAL PRIMARY KEY,
  outlet TEXT, url TEXT UNIQUE, headline_orig TEXT,
  lang TEXT, published_at TIMESTAMPTZ, locality_id BIGINT
);
CREATE TABLE news_clusters (
  id BIGSERIAL PRIMARY KEY,
  summary_en TEXT, summary_ta TEXT,        -- neutral AI summary w/ citations
  locality_id BIGINT, event_time TIMESTAMPTZ,
  discussion_locked BOOLEAN DEFAULT false
);
CREATE TABLE cluster_coverage (
  cluster_id BIGINT REFERENCES news_clusters(id),
  news_item_id BIGINT REFERENCES news_items(id)
);

CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  phone_hash TEXT UNIQUE,          -- never store raw phone number
  identity_tier INT DEFAULT 0,     -- 0..3 rung
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE contributions (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT, type TEXT,       -- correction|issue_confirm|rating|comment
  rung_required INT, payload JSONB,
  moderation_state TEXT            -- pending|approved|rejected
);
CREATE TABLE ratings (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT, locality_id BIGINT, sector TEXT, score INT,
  created_at TIMESTAMPTZ,
  UNIQUE(user_id, locality_id, sector)   -- one live rating per user/locality/sector
);
CREATE TABLE moderation_events (           -- append-only audit log
  id BIGSERIAL PRIMARY KEY,
  contribution_id BIGINT, actor TEXT, action TEXT,
  reason TEXT, created_at TIMESTAMPTZ DEFAULT now()
);
```

Row-Level Security (Supabase): public read on facts/localities/offices/persons/tenures/news_*; writes to contributions/ratings restricted to authenticated (phone-verified) users at the appropriate rung; moderation_events append-only, no update/delete.

---

## 6. Pipeline Specifications

All pipelines are Python scripts on GitHub Actions cron. **LLM usage pattern:** cheap model class for bulk extraction/clustering, frontier model for spot-checks; batch and cache aggressively; **never call an LLM at page-request time.** Every write to `facts` populates `source_id`, `retrieved_at`, `extraction_method`, `confidence`, `review_status`.

| Source | Fetch | Parse | Validation | Cadence | Freshness SLA |
|---|---|---|---|---|---|
| MyNeta affidavits | Scrape TN pages | LLM_bulk extract assets/criminal/education | numeric ranges, OCR flag → confidence | Weekly in cycle, else monthly | 30 days |
| Vacancy tracker (ECI/CEO/eGazette) | Scrape press releases | Parse + NER | human confirm before status flip | Daily | 24 hours |
| Form 20 / ECI results | Fetch HTM/PDF | table parse | cross-check totals | Per election + by-polls | Per event |
| UDISE+ | Bulk ingest per release | district aggregation | schema check | Annual | Per academic year |
| HMIS | data.gov.in pull | column map | range check | Monthly | 45 days |
| NFHS-5 | Bulk CSV | district join | factsheet cross-check | Per round | Per release |
| JJM / MGNREGA | Dashboard scrape | table parse | totals reconcile | Monthly | 45 days |
| Air quality (CPCB/TNPCB) | API/scrape | station map | 24-hr avg only | Daily | 48 hours |
| News (registry) | RSS poll | dedupe + cluster + summarize | citation check | Every 30 min | 1 hour |

A public **`/freshness`** page reads `MAX(retrieved_at)` per source and renders a bilingual table with green/amber/red status against each SLA.

---

## 7. News Aggregation and Clustering Spec

Ingest via RSS/HTML from the §4E outlet registry. Cluster stories by event using embedding similarity + temporal proximity + named-entity overlap (constituency/person/scheme). Each cluster produces: a **neutral bilingual summary** (cheap-model draft, frontier-model spot-check, cached) with inline citations to each source item; and a **coverage table** listing every tracked outlet and whether it covered the event. **No bias labels, no sentiment scoring of outlets.** Store only headline + link + own-words summary (never full article text). Clusters flagged by the moderation classifier as communal/sub judice/allegation-heavy are marked `discussion_locked=true` via the escalation protocol.

---

## 8. Community and Moderation System Spec

Phone-OTP accounts via Supabase auth; store only `phone_hash`. Rung-gated typed contributions (forms, not free text at Rung 0/1). **LLM-first moderation** classifies each contribution/comment against the red lines (communal tensions, sub judice matters, unverified corruption allegations against named individuals); high-confidence violations auto-blocked, uncertain items routed to a human queue with a **published SLA** (target: Rung 1 corrections triaged within 72h; Rung 2 comments within 24h in unlocked districts). Ratings: one per user/locality/sector, displayed only above N=25, with temporal smoothing and anomaly detection that freezes display and posts a public note on suspected brigading. All moderation actions written to the append-only `moderation_events` log.

---

## 9. Neutrality, Transparency, and Editorial Policy Spec

- **Methodology page** (bilingual): documents every indicator's computation, source, cadence, and known limitations; explains why data and sentiment are never blended and why no composite scores exist.
- **Corrections policy:** any user can report via structured form; accepted corrections are logged publicly with timestamps and the changed field; the original value is retained in history.
- **Escalation protocol:** when a story is communally sensitive, sub judice, or centers on unverified allegations against a named person, editors (or the automated classifier) lock discussion, keep the neutral coverage cluster visible, and post a short bilingual notice explaining the lock.
- **Affidavit framing:** always "self-declared filing," with source and retrieval date.
- **No composite scores anywhere**, and **no outlet bias labels** anywhere.

---

## 10. Technical Architecture and Stack

- **Frontend:** Next.js (App Router) + Tailwind + shadcn/ui; **next-intl** with Tamil and English as first-class locales (route-based `/ta` and `/en`); SSR for locality pages + SEO (structured data, hreflang, Tamil-query targeting).
- **Backend/data:** Supabase (Postgres + PostGIS, phone-OTP auth, storage); Vercel hosting; ISR/edge caching for locality pages.
- **Pipelines:** Python + GitHub Actions cron (schema above).
- **LLM pattern:** cheap model class for bulk extraction/clustering; frontier model spot-checks; batch + cache; **never at request time.**
- **Search/geo:** PostGIS point-in-polygon to resolve a user's location → AC/PC/ward/locality chain.

---

## 11. Design System and Tamil Typography

- **Visual identity:** distinctive and non-template — a restrained editorial system (generous whitespace, strong typographic hierarchy, minimal chrome) that signals neutrality and credibility rather than partisanship or "app" flashiness.
- **Tamil web fonts (Google Fonts):** body **Noto Sans Tamil** (broadest glyph coverage) or **Hind Madurai**; display/headings **Catamaran** (Latin+Tamil pairing) or **Mukta Malar**. Pair each Tamil face with a matching Latin face for bilingual parity in weight and x-height; test rendering of complex Tamil ligatures at small sizes on low-end Android.
- **Performance budgets:** sub-second locality pages on low-end Android over 4G; enforce Lighthouse thresholds in CI (e.g., Performance ≥ 90, Accessibility ≥ 95) as a merge gate; subset and self-host fonts; lazy-load non-critical panels.
- **Accessibility:** WCAG 2.1 AA; sufficient contrast for Tamil text; full keyboard navigation; screen-reader labels localized.
- **Mobile-first** responsive layouts; provenance chip pattern reused across every fact.

---

## 12. Phased Roadmap (solo developer + AI coding tools)

**Build order optimized for a solo dev using Claude Code / Lovable:**

- **v0 — statewide launch:** (1) `localities` from LGD + DataMeet geometries; (2) representative spine for 234 AC + 39 PC with MyNeta affidavits and ECI results; (3) vacancy/by-election tracker; (4) news layer with clustering + coverage tables; (5) Data Indicators — **education (UDISE+)** first; (6) Rung 0/1 community; (7) `/freshness`, methodology, corrections log; bilingual parity throughout.
- **v0.5:** health (HMIS/NFHS-5) + water (JJM) indicators; community-sentiment display (N≥25); Rung 2 comments unlocked in **Madurai**; **ward pilot in Madurai Corporation** (manual + parsed TNSEC PDFs).
- **v1:** scheme discovery (myScheme + TN directory); WhatsApp digest bot; public read API + bulk downloads; expanded ward coverage to more corporations; air-quality panel where stations exist.

Rationale: the representative spine and vacancy tracker deliver immediate, election-timely value and depend only on well-structured, scrapeable sources; sentiment and ward tiers are deferred because they carry the highest data-quality and abuse risk.

---

## 13. Known Data Gaps and Their Workarounds

- **Ward-level councillor data is not reliably machine-available statewide.** TNSEC publishes local-body results as PDFs, not structured data. **Workaround:** Madurai Corporation pilot with manual + parsed ingest; explicit empty states elsewhere ("Ward data not yet available"). Do not fabricate.
- **Conflicting ULB counts.** Town-panchayat totals differ across sources (490 as of 2026 vs. an older 561). **Workaround:** display the current TNSEC figure with a footnote noting the discrepancy and retrieval date; do not silently pick one.
- **sansad.in has no public API and blocks scraping.** **Workaround:** use the data.gov.in Lok Sabha/Rajya Sabha member resources (API key) or a headless-browser fallback; use PRS for participation metrics.
- **UDISE+ and HMIS are self-reported** and voluntarily uploaded. **Workaround:** label reliability explicitly and always show the source and reference date.
- **Real-time air quality covers only limited stations** (mostly urban). **Workaround:** show the panel only for localities near a station; never imply statewide coverage.
- **By-election schedule not yet notified as of mid-2026.** **Workaround:** tracker shows "Awaiting ECI notification" with a last-checked timestamp; the seven-seat vacancy count is provisional pending ECI confirmation and possible AIADMK reconciliation effects.
- **ECI results `.htm` pages are preliminary.** **Workaround:** mark constituency results "provisional" until the corresponding Form 20 PDF is ingested.
- **Unverified statutory claims (e.g., a rumored MGNREGA-replacing "VB-G RAM G Act").** **Workaround:** ingest only from official portals; never propagate aggregator claims without a primary-source confirmation, per the provenance rule.

---

## 14. Appendices

**Appendix A — Glossary of TN administrative terms.**
- **State (மாநிலம்)** → **District / மாவட்டம்** (38 districts) → **Taluk / Sub-district / வட்டம்** → **Block / Panchayat Union (வட்டார ஊராட்சி)** → local body.
- **Rural local bodies:** Village Panchayat (**ஊராட்சி**), Panchayat Union (block level), District Panchayat (**மாவட்ட ஊராட்சி**).
- **Urban local bodies (ULBs):** Town Panchayat, Municipality (**நகராட்சி**), Municipal Corporation (**மாநகராட்சி**).
- **Ward:** smallest electoral unit within a ULB or village panchayat, represented by a councillor.
- **AC = Assembly Constituency** (234, each electing one MLA). **PC = Parliamentary Constituency** (39 Lok Sabha; TN also has 18 Rajya Sabha seats elected by MLAs).
- **LGD:** Local Government Directory, the standard code system (TN state code **33**).

**Appendix B — Locality hierarchy reference (for `localities.level`).**
`state → district → taluk → block → {panchayat | ulb} → ward`, plus the parallel electoral overlay `ac` and `pc`. All rows keyed to LGD codes where they exist; ECI codes attached to `ac`/`pc` rows; geometries from DataMeet (AC/PC/district) and GCC/TNSEC (wards, where available). A user's GPS point resolves via PostGIS to exactly one `ac`, one `pc`, and (where geometry exists) one `ward`, from which the full representation chain is derived.