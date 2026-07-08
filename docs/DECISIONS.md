# Arivom — Decision Log

Resolved ambiguities and design decisions not fully specified by `docs/DESIGN.md`.
Newest first. Each entry: date, decision, rationale, and what would change it.

---

## 2026-07-08 — Civic-context order for the feed

### D-037: Consequential first, your places next, newest after
Owner direction: rank news by importance to a rational Tamil citizen's
context, deepened by their saved places — regions alone are not
relevance. Resolved, with the neutrality lines drawn tight:
- **Three ordering signals, all published** (methodology "stories"
  section): (1) the checked civic classification when it exists —
  civic_priority "high" outranks everything, from key day; (2) until
  then, an interim SUBJECT rubric in code (`src/lib/civic-rank.ts`):
  bilingual keyword classes for elections, courts,
  legislature/government decisions, public-safety alerts, and
  household prices. Subjects only; party and person names are never
  ranking signals and never will be. (3) A story tagged to one of the
  reader's saved districts gets a boost — my-places cookie only, on
  surfaces already per-reader.
- **Ranking orders, never hides.** Every story stays in the feed,
  later in it. Tier 1 of the finite feed is now "the set we think a
  reader needs" by these rules, not merely the newest.
- **Pools guarantee presence:** /news merges a few recent stories per
  saved district into the ranking pool (ranking cannot lift what was
  never fetched). Home's statewide sector ranks by rubric alone (the
  reader's districts already own sectors above); district and
  constituency feeds rank rubric+recency and stay cache-safe.
- **The feed renderer respects the caller:** NewsFeed gained
  order="given" — its classic newest-first interleave silently erased
  any upstream ordering (found by probing: the rubric matched at
  runtime while the render ignored it).
- **Pre-key card hygiene:** the per-item "only one outlet so far" line
  is suppressed until the first cluster exists — with nothing to
  contrast against it was noise on every card; it returns by itself
  on key day (hasAnyClusters).
- **Key-day handover is automatic:** the ranker prefers
  civic_priority/civic_class the moment the pipeline writes them; the
  interim rubric simply stops matching anything it should not.

---

## 2026-07-08 — The finite feed and the world beyond Tamil Nadu

### D-036: Beyond-TN outlets; the feed ends on purpose
Owner direction: add national and international news chosen for a Tamil
citizen's life, and make the feed's finitude a stated value — the
anti-doomscroll as product doctrine. Resolved:
- **Outlet selection principle** (each entry carries its
  selection_note in the registry): national papers of record whose
  Union-government coverage reaches TN households (The Hindu National,
  The Indian Express India), and the only major world service written
  in Tamil (BBC Tamil) plus its English world feed (BBC World).
  Established, feed-stable, headline+link only. Selection is
  subject-relevance, never slant; the registry note is the published
  reason.
- **Locality first, world last.** A new `coverage` field in the
  registry marks these outlets; the web derives the list at build time
  (single source of truth). Beyond-TN items never enter home sectors or
  the statewide default feed; they live only in the news feed's final
  tier. Exception by design: an item a beyond-TN outlet datelines to a
  TN district is locally relevant and joins that district's feed.
- **The staged finite feed** (/news): three bounded tiers (12 TN, 15
  TN, 15 beyond-TN) behind honest "More news" links. Depth lives in
  the URL (?d=2/3): server-rendered, works without JS, each step a
  choice. Between tiers, escalating one-line honesty about news as a
  supplement to life; after the last tier, a proud stop: "The feed
  ends here, on purpose", a feedback door (prefilled public GitHub
  issue: what were you looking for?), and two lasting doors (your
  district's data, or /locate; how stories are chosen). No infinite
  scroll, no auto-load, ever.
- **Honesty boundary:** until the API key lands, tiers order by
  recency and the copy claims only quantity, never a priority ranking
  we cannot yet compute. Classification sharpens the ordering on key
  day with no copy change needed.

---

## 2026-07-07 — Rewarding exploration without the attention economy

### D-035: Reward orientation, not engagement; edges grant rights
Owner directive: make being an informed voter feel rewarding, as a
counter to attention-economy dopamine loops — but with no overt reward
system. The line we drew: reward **orientation** (knowing where you are
and what more there is to know), never **engagement** (variable reward,
accumulation, streaks). Two systemic pieces plus a philosophical anchor:
- **The knowledge map** ("இன்னும் அறிவோம்" / "More to know") ends every
  place page: the full landscape of journeys a voter can take from here,
  each row named by the QUESTION it answers ("How are the schools,
  health and drinking water?"). A device-local footprint (localStorage
  `arivom_seen`, locale-stripped paths, never sent anywhere — same
  posture as my-places D-023) marks where you have been with a quiet
  dot; unseen rows show an arrow invitation. The reward is watching your
  own map fill in — a museum floor-plan, not a score.
- **Hard nevers, enforced in the component doc** (`knowledge-map.tsx`):
  no counts, no percentages, no completion state (nothing happens when
  all dots fill), no praise, no streaks. If a future feature wants any
  of these, it violates D-035.
- **Edges grant rights.** Where the user reaches data the GOVERNMENT has
  not published (ward councillors, official contact directories), the
  empty state links `/right-to-know`: a factual page on the RTI Act,
  its Section 4 proactive-disclosure duty, where the current edges are,
  and how a citizen files an RTI. Curiosity at the edge becomes civic
  agency — the mechanism by which, at scale, users push the government
  to publish more (the owner's north star for this system).
- **Critical distinction:** only GOVERNMENT-side gaps get the
  right-to-know framing. Our own not-yet-built surfaces (news analysis
  awaiting the API key, ward pilot) keep their honest interim copy —
  claiming an RTI right over our own backlog would be dishonest. Ward
  and contact states are government-side (SEC publishes results as
  unusable PDFs; no official contact directory exists) and qualify.
- **Refinements (same day):** forgetting is as easy as remembering —
  /more gains a one-tap "மறக்கச் செய்" erasing the device's footprints
  (rendered only when there is something to forget; warm confirmation).
  /right-to-know's filing section carries citizen-grade precision: the
  ₹10 TN fee (waived below the poverty line), the in-person/postal
  channel for state bodies, and rtionline.gov.in labelled
  Union-bodies-only so nobody is sent to a portal that cannot take
  their application.
- Neutral throughout (pillar 2): the map lists journeys and questions,
  never opinions; /right-to-know states the law, never advocacy.

---

## 2026-07-07 — M10: transparency pages

### D-034: Freshness SLAs measure our checking; corrections come from a cited seed
- **SLA semantics.** `sources.cadence` records how often the pipelines
  CHECK a source (the cron reality: outlets half-hourly, vacancy watch
  daily, the import battery monthly, everything else on demand) — not
  how often the source publishes, which each panel's methodology covers.
  /freshness compares last-check age against exact thresholds printed
  in the legend; on-schedule / overdue / stopped, no colour for
  on-demand sources. ensure_source upserts cadence with COALESCE so a
  caller that does not pass one never clobbers it.
- **Corrections log.** Append-only in practice: the curated seed
  (pipelines/data/corrections.json) is the only write path until M9's
  moderation queue; every entry is bilingual, cites its public record
  (DECISIONS anchor), and keeps the original value (pillar 1). The
  importer validates copy rules (no em dashes), rejects empty fields
  and duplicate keys, and reports database entries missing from the
  seed instead of deleting them. Launched with the three real
  corrections already in the project record, not a synthetic test row.

---

## 2026-07-07 — Audit round 2: department identity from the source's links

### D-033: Cards carry the department; allocation subjects sit under it
The owner's second catch: a card named "Governor". Not a split bug this
time — the enwiki cell genuinely has an item whose VISIBLE text is
"Governor" (the official allocation subject "matters relating to the
Governor") while its LINK TARGET is the actual department (Department
of Legislative Assembly). The visible text is the editor's shorthand;
the link target is the identity. Resolution:
- Portfolio entries are now {name, subjects}: name = the linked
  department (title minus " (Tamil Nadu)"/" (தமிழ்நாடு)", en also minus
  "Department of "), subjects = the visible allocation text when it
  differs. Unlinked items keep their text as the name. Plain comma
  cells bind each segment to a link whose text sits inside it.
- /government renders one card per entry: department as the title,
  subjects as a muted line ("Legislative Assembly" / "Governor";
  "Law" / "Law, Courts, Prisons, Prevention of Corruption").
- This also exposed that D-032 still comma-split SINGLE-item lists
  (en 79 → 55 truly faithful entries). ta stays at 116 subject-level
  entries — its table is plain text; faithful to each source.
- Import tripwire: any entry NAME matching a constitutional office
  word (Governor/Speaker/CM, both languages) prints a SUSPECT line in
  every run's report. Trailing punctuation trimmed from names.
- **Position echo (ta plain cells).** A Tamil portfolio cell that
  echoes the minister's own position title ("சிறு, குறு, நடுத்தரத்
  தொழில் அமைச்சர்" beside identical portfolio text) is ONE ministry
  phrase, not a comma list — merged into a single card using the
  source's own consistency. Kills the "குறு"/"சிறு" fragments;
  ta 116 → 112 entries, remaining short names (சட்டம், பொது) are real
  departments. Wikipedia's "Artificial Inteligence" typo is displayed
  verbatim (source-faithful) — fix upstream on the wiki or wait for
  the tn.gov.in directory to become canonical.
- Label unification (owner, audit round 1): /constituencies is
  "Search / தேடல்" everywhere — tab bar, header, /more, footer; the
  unused nav.constituencies key is removed from both catalogs.

---

## 2026-07-07 — Audit round: department extraction fidelity

### D-032: Departments keep the source's own list structure
The owner's audit caught /government showing fragments ("Aged" and
"and Differently Abled Persons Municipal Administration") as separate
department cards. Root cause was structural, not cosmetic: the enwiki
ministers table lists portfolios as <li> items whose names legitimately
contain commas; the importer flattened cells to text and the UI
re-split on commas, fabricating entries. Resolution:
- `expand_table_grid(segments=True)` (common.py) preserves cell items
  (<li>, then <br>, else whole text); the ministers importer stores
  `portfolios_ta/en` as ARRAYS — one entry per source-listed
  department. A cell the source left as plain comma text (the tawiki
  convention) is still comma-split: each side stays faithful to its
  own source's formatting.
- The UI renders one card per array entry and never re-splits
  (src/lib/departments.ts `departmentList`, with legacy string
  tolerance until the prod re-import).
- Result: en cards 92 mangled → 79 faithful; ta unchanged at 116
  (plain cells). Known residual: a TAMIL department name containing a
  comma inside would still fragment — undetectable mechanically until
  the official tn.gov.in directory becomes the canonical list (D-019);
  the import report now prints per-language entry counts so drift
  shows up.

---

## 2026-07-07 — M12: JJM water; HMIS blocked from current egress

### D-031: JJM rural tap coverage via the mission dashboard's own endpoint
- **Source.** The JJM public dashboard's JSON WebMethod
  (`JJMIndia.aspx/BindDistrictMap`) — the exact call the dashboard map
  makes. Parameters use the page's own shipped encoding (char codes
  +1); presentation obfuscation, not authentication. 37 districts
  return; Chennai (fully urban) has no row by mission design and the
  UI says so honestly.
- **What ships.** Published coverage percent verbatim + both counts
  (rural households, with tap connection), the as-on date, and the
  Har Ghar Jal certification flag (shown only when village assemblies
  certified; an uncertified "reported" figure earns no badge). Import
  gate: published percent must equal their own counts within 0.1.
- **Framing.** "Mission-reported data" badge — administrative counts
  reported by implementing agencies, not a survey; methodology notes
  it measures reported infrastructure coverage, not water quality or
  supply hours.
- **HMIS (the M12 health-cadence leg) is blocked from current egress:**
  data.gov.in mirrors are state-level and end ~2019-20; the HMIS
  portal itself times out from outside India. Re-check after the
  owner relocates (~2026-07-13, with D-010/D-017); the district panel
  design accepts a monthly sub-section when it lands.

---

## 2026-07-07 — M12 first slice: NFHS-5 health indicators

### D-030: NFHS-5 district factsheets via data.gov.in; twelve clean indicators
M12 pulled forward while M9/M10 are owner-gated. Resolved:
- **Source.** The data.gov.in mirror of the NFHS-5 (2019-21) India
  district factsheets (GODL license), fetched with the existing
  paginated helper on the public sample key (10-record pages). NFHS is
  a sample survey (MoHFW + IIPS); the UI frames every figure as a
  survey estimate, never a count.
- **Scope: twelve indicators, verbatim.** Household environment
  (electricity, improved water, improved sanitation, clean fuel,
  health insurance), births (institutional births, 4+ ANC visits) and
  child nutrition / anaemia (stunted, wasted, underweight, anaemic
  children 6-59m, anaemic women 15-49) — every value verified in-range
  for all 32 TN rows. Nothing computed or combined.
- **Withheld: vaccination and sex ratio at birth.** Vaccination fields
  arrive negative-mangled in the mirror for most districts (likely the
  factsheets' parenthesised low-sample convention through Excel), and
  district SRB has high sampling variance and invites misreading.
  Both join only after verification against the official factsheet
  PDFs — same posture as D-028's withheld GER/NER.
- **District universe.** NFHS-5 used the pre-2019 list: 32 districts
  match; the six created later (Chengalpattu, Kallakurichi,
  Mayiladuthurai, Ranipet, Tenkasi, Tirupathur) were surveyed inside
  parents and show an honest note instead of data, reported every run.
- **Fact shape.** One fact per district, `key='health.nfhs5'`,
  value `{survey, period, indicators{…}}`; survey-round data, so the
  monthly cron only picks up mirror corrections. HMIS (monthly) and
  JJM remain for the rest of M12.

---

## 2026-07-07 — Dark mode

### D-029: "Paper at night" follows the system preference
The dark theme is the same editorial identity on a warm ink field (the
D-027 dark ground): the warm paper hues stay, the peacock accent
lightens to hold WCAG AA on dark, and the freshness status colors
invert to deep fills with light text. It follows
`prefers-color-scheme` with no toggle: zero client JS, no flash on
load, and the OS is where people already state this preference. The
PWA status-bar theme-color switches by media query; manifest colors
stay light (install splash). A manual override can join after owner
review — the tokens and the `.dark` class variant are already in
place.

---

## 2026-07-07 — M8: UDISE+ education indicators

### D-028: UDISE+ via the public dashboard API; counts only, rates deferred
DESIGN §4D names UDISE+ as the education source with district as the
display unit. Resolved ambiguities:
- **Access path.** data.gov.in's UDISE mirrors stop around 2019 and are
  fragmented per district, and bulk report cards are PDFs. The UDISE+
  dashboard itself renders from a public API
  (`api.udiseplus.gov.in/open-services/v1.1/`), authenticated by a static
  public client token shipped in the dashboard's own JS bundle — public
  data through the publisher's own public channel, same class as the
  D-006 curl fetches. The importer pins that token with a comment on how
  to re-read it if it rotates (the run fails loudly, never silently).
  District-wise rows: `regionType 22` + state code 33; the same call
  pattern the dashboard's report grids use.
- **Scope: counts and PTR only, outcome rates deferred.** The API also
  publishes GER/NER/dropout, but its level bucketing for TN produced
  figures we could not reconcile (e.g. primary GER 54.3 with primary
  enrollment far below the classes-1–5 sum), and a misread ratio
  misinforms in exactly the way pillar 1 exists to prevent. M8 ships
  what is unambiguous: enrollment by level and gender, schools, teachers,
  pupil-teacher ratios, and functional infrastructure counts. Rates join
  when their semantics are verified against the published state report
  card PDFs.
- **Level buckets are computed, not copied.** The API's own level
  rollups follow school-category logic, verified numerically: its "Sec"
  spans classes 9–12 for TN and its "PrePry"/"Pry" split shifts tens of
  thousands of students across the class-1–5 boundary. We bucket the
  class-wise enrollment fields ourselves (pre-primary, 1–5, 6–8, 9–10,
  11–12) and assert per district-year that the buckets sum exactly to
  the published total. The computation is documented on /methodology.
- **Built-in cross-validation.** Every run must reproduce UDISE's own
  independently published state totals from our district-wise sums
  (tolerance 1%, else the run fails). 2022-23 through 2024-25 match
  exactly today.
- **CHENNAI (EXT. GCC).** UDISE carries an education district for the
  extended Greater Chennai Corporation area with no LGD counterpart. It
  counts toward the state rollup and is reported on every run; it never
  attaches to an LGD district.
- **Coverage.** District-wise data exists for 2021-22 onward (37
  districts in 2021-22 — Mayiladuthurai reports from 2022-23); earlier
  years and 2025-26 are advertised but unpublished, reported as pending.
- **Facts shape.** One fact per indicator per locality,
  `key='education.*'`, value `{"series": [{"year": "2021-22", …}]}`
  ascending, `extraction_method='api'`, monthly cron alongside LGD.
  State rollup facts attach to the state locality; PTR (not summable)
  reads the state-wise row directly.

---

## 2026-07-06 — Brand identity

### D-027: The Arivom mark — four layers, one emergence
After four iteration rounds (session artifact), the owner chose the final
mark: on the peacock tile, back to front — an **AdS/CFT tensor network**
(MERA: 16 CFT boundary sites with disentangler bonds at the tile's edge,
isometry layers 16-8-4-1 coarse-graining into the bulk; straight chord
bonds, low contrast; a nod to the owner's physics work) → a **screen**
with deck → an **open reader** as two page-panels of the screen's content
→ **Tamil Nadu in white**, taller than the pages, cut from the
platform's real served boundary (district union, ST_Simplify 0.04).
Assets: `public/logo.svg` (peacock) and `public/logo-dark.svg` (ink field,
for dark mode); PWA icons + favicon regenerated from the mark (qlmanage
rasterization; maskable uses the square-field variant). The bulk of the
network deliberately hides behind the screen: the interface is the
boundary theory. Regenerate icons by re-running the generator against the
state geometry; never hand-edit the PNGs.

---

## 2026-07-06 — Story markers and depth features (owner directive)

### D-026: Data markers translated through the pillars; audit ideas executed
Owner asked for card markers — "importance, controversy level, and user
contributed statistic" — plus execution of the audit's further ideas.
Translations, so every marker stays a fact rather than a judgment:
- **Importance → civic priority tier.** The extraction stage assigns
  `civic_priority` = high | normal with a published rubric (statewide
  policy impact, elections, courts, public safety affecting many people =
  high). D-021 explicitly sanctions ranking by civic usefulness; the chip
  is shown only when high, labelled plainly, criteria going into the
  methodology page with the D-025 section.
- **Controversy level → the "sources differ" fact + escalation notices.**
  A numeric or worded controversy SCORE is an opaque editorial judgment —
  the exact class of thing pillar 2 bans (no composite scores, no
  sentiment blending). What we can display truthfully: the summarizer
  already detects when outlets report conflicting facts; that becomes a
  boolean `sources_disagree` marker rendered as "sources differ" (the
  summary text names the disagreement with citations), alongside the
  existing communal/sub-judice/allegations lock notices. Factual,
  verifiable, calm.
- **User-contributed statistic → designed slot, filled at M9.** Community
  signals (issue confirmations, ratings) require phone-verified accounts,
  moderation, and the N>=25 display floor per DESIGN §8; anonymous or
  fabricated interim numbers are on the never list. The card/story layout
  reserves the slot; it renders nothing until real contributions exist.
- **Audit ideas executed this round:** coverage timeline on story pages;
  "in numbers" blocks (our sourced facts — seat, margin, vacancy status —
  when a story's matched entities touch them, with provenance chips);
  report-an-issue links (public GitHub issues, auditable); person
  follows (device cookie, like places) with a home sector; search across
  constituencies, people, and stories on the Search tab; daily
  "Today in Tamil Nadu" brief (pipeline-selected top civic stories,
  key-gated) surfaced on home; Lighthouse CI gate (perf >= 0.90,
  a11y >= 0.95 on /ta and /ta/news); weekly editorial QA sample workflow
  printing 20 displayed titles/summaries for a human read.
- **Cards rebalanced** (owner: too much image): content-first with a
  side thumbnail; the full-width hero lives on story pages only.

---

## 2026-07-06 — Editorial doctrine (owner directive, after platform audit)

### D-025: Curate for the voting booth; rewrite for the kitchen table
The audit (session artifact, 2026-07-06) measured ~40-45% of a random feed
sample as non-civic noise (celebrity, cricket, astrology, viral items) and
headlines displayed in the outlets' sensational voice. Owner directive:
raise the editorial standard. Resolution, carefully scoped against
pillar 2 (curation is subject-based selection with published criteria;
never actor-based tilt; "editorializing" in the forbidden sense remains
opinions/slant/labels, which stay banned):
- **Civic classification** per item by the extraction stage:
  `civic` (governance, courts, elections, public services, safety,
  policy) / `adjacent` (economy, education, health, environment, weather,
  infrastructure) / `soft` (entertainment, sports, astrology, celebrity,
  viral, out-of-scope national masala). Feeds render civic + adjacent
  only; `soft` stays in the database (registry/coverage analysis) but
  never in product. Unclassified items still render until the backlog is
  classified (no key yet) — honesty over emptiness.
- **The Arivom headline.** Every displayed item gets clean bilingual
  titles (`title_clean_en/ta`) written by the pipeline in our voice:
  informative, calm, no exclamations, no teasers, no sensational
  vocabulary, no unresolved pronouns; spot-checked by the same neutrality
  test as summaries. The outlet's original headline stays one tap away on
  the story page. This also delivers language purity: en mode renders our
  English titles, ta mode our Tamil ones. Interim until classification
  runs: feeds filter items to the mode's language.
- **Selection criteria are actor-blind.** Within civic news nothing is
  boosted or buried by party or person; the spot-check applies the same
  test to our titles. Criteria get a public "How stories are chosen"
  methodology section when classification goes live, plus an
  excluded-count on /freshness.
- **Ingest hygiene:** a section-URL blocklist (cinema, sports, astrology,
  gallery, devotional, video etc.) drops the mechanically identifiable
  ~15% at the poller, reported per outlet per run; existing
  section-noise rows were deleted once (they were cached headlines, not
  history). Low-civic-yield outlets (polimer-news, oneindia-tamil) stay
  under watch in the registry after classification data lands.
- **Coverage display loses its denominator** (owner: national outlets
  will join the registry). Cards carry a sources-count pill; the dot-row
  shows one dot per covering source; story pages keep covered /
  not-covered lists which stay honest at any registry size.

---

## 2026-07-06 — M7.5 polish round: Ground-style stories

### D-024: Story images, dedicated story pages, per-outlet coverage notes
Owner direction: cards were too compact; Ground News is the reference for
feed and detail. Decisions:
- **Images are links, never copies.** news_items.image_url holds the URL
  of the outlet's own published story image (RSS media:content /
  media:thumbnail / enclosure at poll time; article og:image as a fallback
  during extraction). The UI hotlinks it lazy, referrer-free, unoptimized,
  with a kolam-dot placeholder when absent or blocked. We never download,
  store, or re-serve the asset — the same posture as headlines + links.
- **Clusters get dedicated story pages** (/news/s/[id]): checked long
  summary (5-8 sentences, same citation and neutrality rules as the short
  one), the coverage dot-row, per-outlet cards, share (native sheet or
  clipboard), provenance chip, locked notice. Cards across every feed
  route there; single-source items still link out to the outlet.
- **Per-outlet coverage notes, strictly content-descriptive.** Because we
  read every tracked outlet's reporting of an event, the story page shows
  one checked sentence per outlet on what its coverage ADDS ("carries the
  minister's full statement", "adds official figures") — never wording
  that judges quality, accuracy, or slant. The frontier spot-check fails
  any note that drifts from description into judgment (pillar 2). The UI
  labels the section "What each outlet covers" and repeats the no-ratings
  disclaimer.
- **Feed cards** show source-count pill, title, marker-stripped summary
  preview (2-line clamp), thumbnail, dots, relative time; card → story
  page morphs via View Transitions where supported.

---

## 2026-07-05 — M7.5 owner decisions: the app experience

### D-023: News-first home, geography scopes, PWA-now, build-before-key
Owner review of the M6/M7 surfaces ("clean but bare-bones; news feels like
a tab, not baked in") produced a design direction (see the session's design
artifact) and four decisions:
- **News IS the home.** The home page becomes a personalized feed of news
  sectioned by the user's geographies: their added constituencies (plural,
  device-remembered, no account), those constituencies' districts, and
  Tamil Nadu statewide. Each sector shows a LIMITED number of stories with
  a "show more" into that scope's full feed; the feed has an explicit end
  ("you're caught up"). No doomscroll mechanics, ever (D-021). The
  geography-scope model is built to admit wider sectors later (regions,
  South India, pan-India) — the owner intends to expand beyond Tamil Nadu
  in the future, always from a Tamil citizen's central perspective; no
  non-TN ingestion is built until that milestone exists.
- **Packaging: PWA now, native evaluated at v0.5.** Installable PWA
  (manifest, offline shell, standalone display) ships now; a store-wrapped
  native app stays on the do-not-build list until an explicit v0.5
  evaluation alongside accounts (M9). This amends the CLAUDE.md
  do-not-build entry from "Native app" to "Native app (PWA allowed as of
  D-023; native gated on v0.5 evaluation)".
- **Sequence: experience first, key later.** The owner wants to feel the
  app on the news already ingested (M6 items) BEFORE providing the
  ANTHROPIC_API_KEY; clustering then lights up cluster cards, summaries,
  and coverage dots on surfaces that already render honestly with
  single-source items. Nothing may fabricate clusters or stats in the
  meantime; empty/singleton states are the design.
- **Visual identity: deepen, don't replace.** The party-neutral
  "editorial paper + peacock" palette and Catamaran/Noto Sans Tamil stack
  stay; M7.5 takes them to app-grade: motion tokens (transform/opacity
  only, reduced-motion honored), press states, skeleton loading, the
  coverage dot-row as the signature transparency visual, kolam-dot
  accents, bottom tab bar on mobile, View Transitions where supported.
  Client JS budget on feed routes: under ~40KB gzipped; fonts stay
  self-hosted/subset via next/font.

---

## 2026-07-05 — M7 decisions

### D-022: News clustering — owner-approved LLM setup and posture
Two owner decisions plus the operational details they imply.
- **Anthropic-only, no embeddings provider (owner choice).** DESIGN §7's
  "embedding similarity" is satisfied at our scale by our own bilingual
  entity lexicon (persons, districts, parties already in the DB with ta+en
  names) for candidate blocking, plus cheap-model confirmation of borderline
  merges. One API key (`ANTHROPIC_API_KEY`), one provider. Model tiers per
  DESIGN §10's "cheap bulk, frontier spot-check": claude-haiku-4-5 for
  entity extraction and merge judgments, claude-sonnet-5 for the bilingual
  summary drafts (user-facing Tamil quality), claude-opus-4-8 with adaptive
  thinking for the spot-check + escalation classification. Revisit
  embeddings if merge recall proves weak on entity-less stories.
- **Transient full-text reading (owner choice).** The pipeline may fetch and
  read an article at run time to extract entities and write an own-words
  summary. Article text is NEVER stored in the database and never
  republished; only a short derived excerpt sits in the gitignored local
  cache (24h) to keep re-runs polite. Headlines + links + own-words
  summaries remain the only stored news content (§4E hard policy).
- **Clusters materialize at two or more items.** A single-source story stays
  a plain item (shown as a headline card labelled single-source); clusters
  exist for multi-outlet events, which is also what coverage tables need.
- **Summaries are checked or withheld.** Draft → frontier spot-check
  (claim support, neutrality, Tamil faithfulness, citation validity) → one
  revise cycle → publish on pass (`review_status='llm_checked'`) or withhold
  with a loud report. An unchecked summary never reaches the database.
  Every summary sentence carries [n] markers resolving to member items
  (`citations` column holds the id order).
- **Moderation only ever locks.** The spot-check call also classifies the
  event (communal / sub judice / allegations against a named person);
  positives set `discussion_locked` + `lock_category`. The pipeline never
  clears a lock; unlocking is a human path (escalation protocol, §9).
- **Conservative cluster locality.** A cluster gets a district only when
  every district-bearing member agrees on it; else NULL and the story is
  statewide-only. District feeds live at /news/d/[lgd] with an explicit
  statewide fallback when empty.
- **Known limitations, accepted for v0:** clusters never merge with each
  other (only items join clusters); extraction retries failed items every
  run until they age out of the 7-day window; per-run caps (300 extractions,
  250 merge checks, 40 summaries) bound cost and are reported when hit.
- **Cadence and cost.** Hourly cron (`cluster-news.yml`, :20), gated to skip
  politely until the ANTHROPIC_API_KEY secret exists. Expected cost at
  current volume is roughly $10-30/month; all LLM calls are disk-cached and
  schema-constrained, and summaries regenerate only when cluster membership
  changes (content_hash).

---

## 2026-07-05 — Pre-M7 owner directive

### D-021: North star — an informed electorate (owner directive)
Before M7 the owner named the project's founding inspiration: the news
philosophy of "News Night 2.0" in HBO's *The Newsroom* (which led him to
Ground News, then to building Arivom). The operative mission: **ensure an
informed electorate.** Applied as a design test alongside D-016: when
ranking or presenting anything — news clusters, feeds, page hierarchy —
ask "does this help a Tamil Nadu citizen vote and hold power to account?",
never "does this get attention?". Concretely for M7+: civic usefulness
orders clusters (not recency alone, not volume); context sits next to
facts; no sensationalism in copy or ordering. One deliberate divergence
from the inspiration: The Newsroom's anchors editorialize; Arivom never
does (pillar 2) — the same mission is pursued through sourced facts and
coverage transparency instead of opinion. The show is design philosophy,
never product voice or user-facing copy.

---

## 2026-07-05 — M6 decisions

### D-020: News ingestion — registry scope, provenance, tagging, cadence
DESIGN §4E/§7 and PLAN M6 left operational details open; resolved as follows.
- **Registry outcome (verified 2026-07-05, outside India):** 11 outlets flow —
  The Hindu (TN section feed), Times of India (Chennai section), New Indian
  Express, DT Next, Dinamani, Daily Thanthi, Maalaimalar, Puthiya Thalaimurai,
  Polimer News, News7 Tamil, Oneindia Tamil (7 Tamil + 4 English; exit
  criterion was ≥6). Dinamalar (feed page now redirects home), Dinakaran
  (WAF 403), Hindu Tamil Thisai (no feed endpoint), News18 Tamil (bot-block
  403), and Sun News (no feed) are `pending` in the registry with reasons;
  several may open up from India egress (D-017). Quintype-platform outlets
  expose only site-wide `stories.rss` (section feeds return HTML).
- **Fact-checkers registered, not polled.** Factly, BOOM, Alt News have live
  feeds; YouTurn does not. All four are registry + `sources` rows, but their
  national scope means item ingestion would pollute TN feeds — their
  consumption model arrives with M7 coverage work.
- **National-feed scoping by the outlet's own taxonomy.** New Indian
  Express's feed is national; only items under
  `/states/tamil-nadu/` (registry `include_url_prefixes`) are stored. No
  keyword guessing. TN-market outlets are ingested whole — M7 coverage
  tables need to know what an outlet did NOT cover, which requires the
  full feed.
- **Provenance on news_items (D-003 extension).** `source_id` (the outlet's
  registry row) + `retrieved_at`, NOT NULL, via migration
  20260705100000. /freshness now unions news_items, so per-outlet
  freshness is visible publicly. `outlet` column holds the registry slug.
- **Dedupe + refresh semantics.** Canonical URL (tracking params stripped,
  fragment dropped) is the identity; `ON CONFLICT (url)` refreshes
  headline, published time, tag and `retrieved_at` — an edited headline is
  re-observed, not duplicated. Re-poll therefore produces zero new rows
  (verified: second run 0 new / 281 re-observed).
- **Conservative district tagging.** A headline is tagged to a district only
  when exactly one district matches (English word-boundary match including
  common press spellings — Trichy/Tiruchi/Tiruchy, Tuticorin, Kanyakumari,
  Nilgiris, Villupuram… — or Tamil name as word-initial substring so case
  suffixes match, plus press forms கோவை/திருச்சி/நெல்லை). Ambiguous or
  unmatched headlines stay untagged (~15% tagged on first run) rather than
  wrongly tagged; M7's entity work supersedes this. Aliases are matching
  aids only, never stored or displayed.
- **Per-item language.** `lang` = 'ta' if the headline contains Tamil-script
  codepoints, else 'en' (D-005 spirit: script decides, not the outlet's
  nominal language).
- **Cadence and gate.** 30-minute GitHub Actions cron (offset :07/:37),
  needing only DATABASE_URL — like the vacancy monitor it runs regardless
  of PIPELINES_ENABLED (D-018 precedent). The run writes a `news_poll_run`
  fact (per-outlet health) that M7's news pages can surface as "last
  checked". The poller fails loudly if fewer than 6 outlets flow.
- **Hard policy retained:** headline + link + feed metadata only; the parser
  never reads description/content elements, so article text cannot enter
  the database even by accident.

---

## 2026-07-04 — Spine completion (owner-requested, pre-M6)

### D-019: Profiles, government page, and framing corrections
Owner review before M6 drove five changes:
- **Assets/liabilities audit:** parsing verified correct (medians ₹4.6 Cr
  assets vs ₹57 lakh liabilities; the similar-range cases the owner saw are
  genuine declarations; the one duplicate pair is the dual-seat winner's
  two per-seat rows). The 20-sample spot-check became a full-population
  listing-vs-detail reconciliation: when MyNeta's two surfaces disagree,
  the detail page (enumerated record) wins, both values are stored, and
  the discrepancy is printed (3 found, all criminal-case counts).
- **Profiles:** age and self-declared profession imported from MyNeta
  detail pages for 208 MLAs and 36 MPs; MP affidavits added via the
  LokSabha2024 listing (constituency + name-similarity matched). Identity
  facts (age, education, profession) are visible; sensitive facts remain
  in the D-016 disclosure. MyNeta fetches moved to curl (the same
  TLS-fingerprint discrimination as the ECI portal, intermittent).
- **Contacts:** no reachable official directory yet (assembly/tn.gov.in
  geo-blocked, sansad legacy feed dead, sansad.in scrape-blocked). The
  contact fact model and UI section exist with an honest pending note and
  a hard policy line: only officially published channels, never personal
  numbers. Populate when official directories are reachable (D-017).
- **Government page:** /government lists the council of ministers (35,
  bilingual portfolios) from the ta+en 17th-assembly articles matched via
  constituency, plus the assembly's party composition computed from our
  own tenure records with vacant seats linked. Official department links
  and ministers' office contacts follow the official directory.
- **Provisional framing:** the badge left the representative card; a
  reworded note lives under the vote figures only ("the outcome itself
  and the government are settled"), matching a formed, running government.
- **Department-first government page (2026-07-05):** each card is one
  department (portfolios split at render time on commas only; sourced
  text stored intact), ordered department → position → name, with a
  stable anchor id per card so M6/M7 can attach department-tagged news
  to clicks. The split is disclosed in a note; entry counts differ per
  locale because the two source wikis phrase combined portfolios
  differently (ta 116 / en 92).

## 2026-07-04 — M5 decisions

### D-018: Tracker monitor is detection-only; runs daily regardless of PIPELINES_ENABLED
The vacancy monitor uses Google News RSS (en+ta) strictly as a discovery
aid (DESIGN §4E): it records unreviewed `vacancy_signal` facts and a
`vacancy_monitor_run` record (the tracker's "last checked"), and can never
change a seat's status. Status changes happen only through the curated,
per-entry-cited seed applied by import-vacancies with member-name
validation — the literal "human confirmation before status flip" of DESIGN
§6. Because the monitor needs only DATABASE_URL (no data.gov.in key), its
daily cron runs independently of the PIPELINES_ENABLED gate (D-010). The
ECI portal remains a JS app without a stable machine-readable feed; its
reachability is recorded honestly on every run, and a proper ECI parser
can slot in as an additional feed when one becomes available (or via an
India egress for the CEO site, see D-017).

## 2026-07-04 — Data consolidation research (owner-requested)

### D-017: Post-election research pass; Tamil-name completion; vacancy records
Owner-requested research to make the data concrete now that results are a
month old. Outcomes:
- **Tamil names: 234/234 complete.** New primary bulk source: ETV Bharat
  Tamil's complete winners table (professional newsroom; joined by AC
  number, validated by exact vote equality with ECI; filled 93 seats the
  wiki tables left untranslated). One member (AC 185, won by 1 vote) came
  via curated news citations in pipelines/data/curated_names_ta.json.
  D-014's pending list is now empty.
- **Vacancies: 7 seats confirmed and applied** via a curated, per-entry-
  cited seed (pipelines/data/vacancies_2026.json): Tiruchirappalli East
  (C. Joseph Vijay became CM, retained Perambur, 10 May), Madurantakam,
  Dharapuram, Perundurai (25 May), Ambasamudram (26 May, all four AIADMK
  members joined TVK), Viralimalai (16 June), Karur (29 June). By-election
  not yet notified by ECI as of 2026-07-04. The import validates the seated
  member's name before any status flip; the `vacancies` view now reflects
  reality. M5's automated ECI pipeline supersedes the curation; the seed
  becomes its regression fixture.
- **Form 20 finality:** no evidence of publication yet; vote figures keep
  the provisional framing. The representation itself is settled (assembly
  constituted, ministry formed).
- **Watch item for M5:** AC 185 Tiruppattur (Sivaganga) has an election
  dispute in the Madras High Court (1-vote margin; interim order restricted
  the member's assembly participation). Not yet displayed; needs a
  status-note pattern in the tracker.
- **Access finding:** TN government sites (assembly.tn.gov.in, tn.gov.in,
  elections.tn.gov.in) are unreachable from non-India networks (geo-blocked
  at TLS). Official-source ingestion needs an India egress; revisit when the
  owner relocates (~2026-07-13). The official members list remains the
  preferred replacement for news-sourced Tamil names when reachable.

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

