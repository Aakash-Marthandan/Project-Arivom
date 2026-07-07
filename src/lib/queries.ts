import { sql } from "./db";

export type ConstituencyLevel = "ac" | "pc";

export interface ConstituencyListItem {
  id: number;
  eci_code: string;
  name_en: string;
  name_ta: string;
  level: ConstituencyLevel;
  district_en: string | null;
  district_ta: string | null;
}

export interface SourceInfo {
  id: number;
  name: string;
  url: string | null;
  publisher: string;
  license: string | null;
  access_mode: string;
  retrieved_at: Date;
}

export interface ConstituencyDetail {
  id: number;
  eci_code: string;
  name_en: string;
  name_ta: string;
  level: ConstituencyLevel;
  retrieved_at: Date;
  district_id: number | null;
  district_en: string | null;
  district_ta: string | null;
  district_lgd: string | null;
  parent_id: number | null;
  parent_eci_code: string | null;
  parent_name_en: string | null;
  parent_name_ta: string | null;
  source_name: string;
  source_url: string | null;
  source_publisher: string;
  source_license: string | null;
  source_access_mode: string;
}

export interface FactWithSource {
  key: string;
  value: unknown;
  extraction_method: string;
  retrieved_at: Date;
  source_name: string;
  source_url: string | null;
  source_publisher: string;
  source_license: string | null;
}

export interface FreshnessRow {
  source_name: string;
  source_url: string | null;
  publisher: string;
  license: string | null;
  access_mode: string;
  cadence: "half-hourly" | "hourly" | "daily" | "monthly" | "manual" | null;
  last_retrieved: Date;
  age_hours: number;
  record_count: number;
}

export async function listConstituencies(
  query?: string,
): Promise<ConstituencyListItem[]> {
  const q = query?.trim();
  return sql<ConstituencyListItem[]>`
    SELECT l.id, l.eci_code, l.name_en, l.name_ta,
           l.level::text AS level,
           d.name_en AS district_en, d.name_ta AS district_ta
    FROM localities l
    LEFT JOIN localities d ON d.id = l.district_id
    WHERE l.level IN ('ac', 'pc')
    ${
      q
        ? sql`AND (l.name_en ILIKE ${"%" + q + "%"}
               OR l.name_ta LIKE ${"%" + q + "%"}
               OR d.name_en ILIKE ${"%" + q + "%"}
               OR d.name_ta LIKE ${"%" + q + "%"}
               OR l.eci_code = ${q})`
        : sql``
    }
    ORDER BY l.level, (l.eci_code)::int
  `;
}

export async function getConstituency(
  level: ConstituencyLevel,
  code: string,
): Promise<ConstituencyDetail | null> {
  const rows = await sql<ConstituencyDetail[]>`
    SELECT l.id, l.eci_code, l.name_en, l.name_ta,
           l.level::text AS level, l.retrieved_at,
           l.district_id,
           d.name_en AS district_en, d.name_ta AS district_ta,
           d.lgd_code AS district_lgd,
           p.id AS parent_id, p.eci_code AS parent_eci_code,
           p.name_en AS parent_name_en, p.name_ta AS parent_name_ta,
           s.name AS source_name, s.url AS source_url,
           s.publisher AS source_publisher, s.license AS source_license,
           s.access_mode AS source_access_mode
    FROM localities l
    JOIN sources s ON s.id = l.source_id
    LEFT JOIN localities d ON d.id = l.district_id
    LEFT JOIN localities p ON p.id = l.parent_id AND p.level = 'pc'
    WHERE l.level = ${level} AND l.eci_code = ${code}
  `;
  return rows[0] ?? null;
}

export async function getAssemblySegments(
  pcId: number,
): Promise<ConstituencyListItem[]> {
  return sql<ConstituencyListItem[]>`
    SELECT l.id, l.eci_code, l.name_en, l.name_ta,
           l.level::text AS level,
           d.name_en AS district_en, d.name_ta AS district_ta
    FROM localities l
    LEFT JOIN localities d ON d.id = l.district_id
    WHERE l.level = 'ac' AND l.parent_id = ${pcId}
    ORDER BY (l.eci_code)::int
  `;
}

export async function getLocalityFacts(
  localityId: number,
): Promise<FactWithSource[]> {
  return sql<FactWithSource[]>`
    SELECT f.key, f.value, f.extraction_method, f.retrieved_at,
           s.name AS source_name, s.url AS source_url,
           s.publisher AS source_publisher, s.license AS source_license
    FROM facts f
    JOIN sources s ON s.id = f.source_id
    WHERE f.subject_type = 'locality' AND f.subject_id = ${localityId}
    ORDER BY f.key
  `;
}

export interface Representative {
  office_type: "mla" | "mp_ls" | "mp_rs" | "councillor";
  person_id: number;
  name_en: string;
  /** NULL = no sourced Tamil rendering yet (D-014) — never transliterated. */
  name_ta: string | null;
  party_en: string | null;
  party_ta: string | null;
  photo_url: string | null;
  start_date: string | null;
  retrieved_at: Date;
  source_name: string;
  source_url: string | null;
  source_publisher: string;
  source_license: string | null;
}

/** Current (active, open-ended) representatives for a locality. */
export async function getRepresentatives(
  localityId: number,
): Promise<Representative[]> {
  return sql<Representative[]>`
    SELECT o.office_type::text AS office_type,
           p.id AS person_id, p.name_en, p.name_ta, p.party_en, p.party_ta,
           p.photo_url, t.start_date::text AS start_date, t.retrieved_at,
           s.name AS source_name, s.url AS source_url,
           s.publisher AS source_publisher, s.license AS source_license
    FROM offices o
    JOIN tenures t ON t.office_id = o.id
      AND t.end_date IS NULL AND t.status = 'active'
    JOIN persons p ON p.id = t.person_id
    JOIN sources s ON s.id = t.source_id
    WHERE o.locality_id = ${localityId}
    ORDER BY o.office_type
  `;
}

export async function getPersonFacts(personId: number): Promise<FactWithSource[]> {
  return sql<FactWithSource[]>`
    SELECT f.key, f.value, f.extraction_method, f.retrieved_at,
           s.name AS source_name, s.url AS source_url,
           s.publisher AS source_publisher, s.license AS source_license
    FROM facts f
    JOIN sources s ON s.id = f.source_id
    WHERE f.subject_type = 'person' AND f.subject_id = ${personId}
    ORDER BY f.key
  `;
}

export interface ResolvedLocality {
  level: "ac" | "pc" | "district";
  eci_code: string | null;
  name_en: string;
  name_ta: string;
}

/**
 * Point-in-polygon resolution: which AC, PC, and district contain this
 * WGS84 point. Uses the GIST index on localities.geom; returns at most one
 * row per level.
 */
export async function resolveLocation(
  lon: number,
  lat: number,
): Promise<ResolvedLocality[]> {
  return sql<ResolvedLocality[]>`
    SELECT level::text AS level, eci_code, name_en, name_ta
    FROM localities
    WHERE level IN ('ac', 'pc', 'district')
      AND geom IS NOT NULL
      AND ST_Contains(geom, ST_SetSRID(ST_MakePoint(${lon}, ${lat}), 4326))
    ORDER BY level
  `;
}

export interface VacantSeat {
  locality_id: number;
  eci_code: string;
  name_en: string;
  name_ta: string;
  district_en: string | null;
  district_ta: string | null;
  vacancy: unknown;
  retrieved_at: Date;
  source_name: string;
  source_url: string | null;
  source_publisher: string;
  source_license: string | null;
  extraction_method: string;
}

/** MLA seats without an active tenure, with their vacancy fact (M5 tracker). */
export async function getVacantSeats(): Promise<VacantSeat[]> {
  return sql<VacantSeat[]>`
    SELECT l.id AS locality_id, l.eci_code, l.name_en, l.name_ta,
           d.name_en AS district_en, d.name_ta AS district_ta,
           f.value AS vacancy, f.retrieved_at, f.extraction_method,
           s.name AS source_name, s.url AS source_url,
           s.publisher AS source_publisher, s.license AS source_license
    FROM offices o
    JOIN localities l ON l.id = o.locality_id
    LEFT JOIN localities d ON d.id = l.district_id
    JOIN facts f ON f.subject_type = 'locality' AND f.subject_id = l.id
      AND f.key = 'vacancy'
    JOIN sources s ON s.id = f.source_id
    WHERE o.office_type = 'mla'
      AND NOT EXISTS (
        SELECT 1 FROM tenures t
        WHERE t.office_id = o.id AND t.end_date IS NULL AND t.status = 'active'
      )
    ORDER BY (f.value ->> 'vacated_on')
  `;
}

/** When the vacancy monitor last ran (null before its first run). */
export async function getMonitorLastChecked(): Promise<Date | null> {
  const rows = await sql<{ retrieved_at: Date }[]>`
    SELECT retrieved_at FROM facts
    WHERE key = 'vacancy_monitor_run'
    ORDER BY retrieved_at DESC LIMIT 1
  `;
  return rows[0]?.retrieved_at ?? null;
}

export interface Minister {
  person_id: number;
  name_en: string;
  name_ta: string | null;
  party_en: string | null;
  party_ta: string | null;
  minister: unknown;
  seat_code: string;
  seat_en: string;
  seat_ta: string;
  retrieved_at: Date;
  source_name: string;
  source_url: string | null;
  source_publisher: string;
  source_license: string | null;
  extraction_method: string;
}

/** Council of ministers: persons with a minister fact and an active seat. */
export async function getMinisters(): Promise<Minister[]> {
  return sql<Minister[]>`
    SELECT p.id AS person_id, p.name_en, p.name_ta, p.party_en, p.party_ta,
           f.value AS minister, f.retrieved_at, f.extraction_method,
           l.eci_code AS seat_code, l.name_en AS seat_en, l.name_ta AS seat_ta,
           s.name AS source_name, s.url AS source_url,
           s.publisher AS source_publisher, s.license AS source_license
    FROM facts f
    JOIN persons p ON p.id = f.subject_id AND f.subject_type = 'person'
    JOIN tenures t ON t.person_id = p.id AND t.end_date IS NULL AND t.status = 'active'
    JOIN offices o ON o.id = t.office_id AND o.office_type = 'mla'
    JOIN localities l ON l.id = o.locality_id
    JOIN sources s ON s.id = f.source_id
    WHERE f.key = 'minister'
    ORDER BY (f.value ->> 'is_chief_minister') DESC, p.name_en
  `;
}

export interface PartySeats {
  party_en: string | null;
  party_ta: string | null;
  seats: number;
}

/** Party-wise composition of active MLA tenures (computed from our rows). */
export async function getAssemblyComposition(): Promise<PartySeats[]> {
  return sql<PartySeats[]>`
    SELECT p.party_en, p.party_ta, count(*)::int AS seats
    FROM tenures t
    JOIN offices o ON o.id = t.office_id AND o.office_type = 'mla'
    JOIN persons p ON p.id = t.person_id
    WHERE t.end_date IS NULL AND t.status = 'active'
    GROUP BY p.party_en, p.party_ta
    ORDER BY seats DESC, p.party_en
  `;
}

export interface NewsClusterMember {
  id: number;
  outlet: string;
  url: string;
  headline: string;
  lang: "ta" | "en";
  published_at: string | null;
  image_url: string | null;
}

export interface NewsCluster {
  id: number;
  title_en: string | null;
  title_ta: string | null;
  summary_en: string | null;
  summary_ta: string | null;
  citations: number[] | null;
  summary_long_en: string | null;
  summary_long_ta: string | null;
  coverage_notes:
    | { news_item_id: number; note_en: string; note_ta: string }[]
    | null;
  event_time: Date | null;
  district_en: string | null;
  district_ta: string | null;
  district_lgd: string | null;
  discussion_locked: boolean;
  lock_category: string | null;
  sources_disagree: boolean;
  priority_high: boolean;
  retrieved_at: Date;
  source_name: string;
  source_url: string | null;
  source_publisher: string;
  source_license: string | null;
  members: NewsClusterMember[];
}

export interface NewsSingleItem {
  id: number;
  outlet: string;
  url: string;
  headline: string;
  lang: "ta" | "en";
  published_at: Date | null;
  district_en: string | null;
  district_ta: string | null;
  district_lgd: string | null;
  retrieved_at: Date;
  image_url: string | null;
  title_clean_en: string | null;
  title_clean_ta: string | null;
  civic_priority: string | null;
}

/** Multi-outlet event clusters, newest first (M7). */
export async function getNewsClusters(
  districtId?: number,
  limit = 30,
): Promise<NewsCluster[]> {
  return sql<NewsCluster[]>`
    SELECT c.id, c.title_en, c.title_ta, c.summary_en, c.summary_ta,
           c.citations, c.summary_long_en, c.summary_long_ta,
           c.coverage_notes, c.event_time, c.discussion_locked,
           c.lock_category, c.sources_disagree, c.retrieved_at,
           d.name_en AS district_en, d.name_ta AS district_ta,
           d.lgd_code AS district_lgd,
           s.name AS source_name, s.url AS source_url,
           s.publisher AS source_publisher, s.license AS source_license,
           m.members, m.priority_high
    FROM news_clusters c
    JOIN sources s ON s.id = c.source_id
    LEFT JOIN localities d ON d.id = c.locality_id
    JOIN LATERAL (
      SELECT json_agg(json_build_object(
               'id', i.id, 'outlet', i.outlet, 'url', i.url,
               'headline', i.headline_orig, 'lang', i.lang,
               'published_at', i.published_at, 'image_url', i.image_url
             ) ORDER BY i.published_at) AS members,
             bool_or(i.civic_priority = 'high') AS priority_high,
             count(*) AS n
      FROM cluster_coverage cc
      JOIN news_items i ON i.id = cc.news_item_id
      WHERE cc.cluster_id = c.id
    ) m ON m.n >= 2
    WHERE c.event_time > now() - interval '14 days'
    ${districtId ? sql`AND c.locality_id = ${districtId}` : sql``}
    ORDER BY c.event_time DESC
    LIMIT ${limit}
  `;
}

/**
 * Recent items not (yet) part of any cluster: single-source stories.
 * D-025: soft-classified items never render; until an item has an
 * Arivom-voice title in the reader's language, feeds fall back to
 * language-filtered original headlines (honest interim).
 */
export async function getUnclusteredItems(
  lang: "ta" | "en",
  districtId?: number,
  limit = 30,
  days = 3,
): Promise<NewsSingleItem[]> {
  return sql<NewsSingleItem[]>`
    SELECT i.id, i.outlet, i.url, i.headline_orig AS headline, i.lang,
           i.published_at, i.retrieved_at, i.image_url,
           i.title_clean_en, i.title_clean_ta, i.civic_priority,
           d.name_en AS district_en, d.name_ta AS district_ta,
           d.lgd_code AS district_lgd
    FROM news_items i
    LEFT JOIN localities d ON d.id = i.locality_id
    WHERE NOT EXISTS (
      SELECT 1 FROM cluster_coverage cc WHERE cc.news_item_id = i.id
    )
    AND (i.civic_class IS NULL OR i.civic_class <> 'soft')
    AND (
      ${lang === "ta" ? sql`i.title_clean_ta IS NOT NULL` : sql`i.title_clean_en IS NOT NULL`}
      OR i.lang = ${lang}
    )
    AND i.published_at > now() - make_interval(days => ${days})
    ${districtId ? sql`AND i.locality_id = ${districtId}` : sql``}
    ORDER BY i.published_at DESC
    LIMIT ${limit}
  `;
}

/** The story pool in one line (D-025): stored, excluded, awaiting. */
export async function getNewsPoolStats(): Promise<{
  total: number;
  soft: number;
  unclassified: number;
}> {
  const rows = await sql<
    { total: number; soft: number; unclassified: number }[]
  >`
    SELECT count(*)::int AS total,
           (count(*) FILTER (WHERE civic_class = 'soft'))::int AS soft,
           (count(*) FILTER (WHERE civic_class IS NULL))::int AS unclassified
    FROM news_items
  `;
  return rows[0] ?? { total: 0, soft: 0, unclassified: 0 };
}

/**
 * Distinct department tags the extraction has produced, both languages
 * (D-019: matched loosely to /government card names at display time).
 * Empty until cluster-news runs with the API key.
 */
export async function getDepartmentTags(): Promise<string[]> {
  const rows = await sql<{ tag: string }[]>`
    SELECT DISTINCT tag FROM (
      SELECT entities->>'department' AS tag FROM news_items
      UNION
      SELECT entities->>'department_ta' AS tag FROM news_items
    ) tags
    WHERE tag IS NOT NULL
  `;
  return rows.map((r) => r.tag);
}

/** Stories tagged with any of the given department names (either language). */
export async function getNewsItemsByDepartmentTags(
  tags: string[],
  lang: "ta" | "en",
  limit = 30,
  days = 30,
): Promise<NewsSingleItem[]> {
  if (tags.length === 0) return [];
  return sql<NewsSingleItem[]>`
    SELECT i.id, i.outlet, i.url, i.headline_orig AS headline, i.lang,
           i.published_at, i.retrieved_at, i.image_url,
           i.title_clean_en, i.title_clean_ta, i.civic_priority,
           d.name_en AS district_en, d.name_ta AS district_ta,
           d.lgd_code AS district_lgd
    FROM news_items i
    LEFT JOIN localities d ON d.id = i.locality_id
    WHERE (
      i.entities->>'department' = ANY(${tags})
      OR i.entities->>'department_ta' = ANY(${tags})
    )
    AND (i.civic_class IS NULL OR i.civic_class <> 'soft')
    AND (
      ${lang === "ta" ? sql`i.title_clean_ta IS NOT NULL` : sql`i.title_clean_en IS NOT NULL`}
      OR i.lang = ${lang}
    )
    AND i.published_at > now() - make_interval(days => ${days})
    ORDER BY i.published_at DESC
    LIMIT ${limit}
  `;
}

export interface PlaceCard {
  id: number;
  eci_code: string;
  level: ConstituencyLevel;
  name_en: string;
  name_ta: string;
  district_id: number | null;
  district_en: string | null;
  district_ta: string | null;
  district_lgd: string | null;
  rep_en: string | null;
  rep_ta: string | null;
  party_en: string | null;
  party_ta: string | null;
}

/** The home feed's per-place strip: constituency, district, current rep. */
export async function getPlaceCards(
  places: { level: string; code: string }[],
): Promise<PlaceCard[]> {
  if (places.length === 0) return [];
  const keys = places.map((p) => `${p.level}:${p.code}`);
  const rows = await sql<PlaceCard[]>`
    SELECT l.id, l.eci_code, l.level::text AS level, l.name_en, l.name_ta,
           d.id AS district_id, d.name_en AS district_en,
           d.name_ta AS district_ta, d.lgd_code AS district_lgd,
           p.name_en AS rep_en, p.name_ta AS rep_ta,
           p.party_en, p.party_ta
    FROM localities l
    LEFT JOIN localities d ON d.id = l.district_id
    LEFT JOIN offices o ON o.locality_id = l.id
      AND ((l.level = 'ac' AND o.office_type = 'mla')
        OR (l.level = 'pc' AND o.office_type = 'mp_ls'))
    LEFT JOIN tenures t ON t.office_id = o.id
      AND t.end_date IS NULL AND t.status = 'active'
    LEFT JOIN persons p ON p.id = t.person_id
    WHERE l.level::text || ':' || l.eci_code = ANY(${keys})
  `;
  // Preserve the user's ordering.
  const byKey = new Map(rows.map((r) => [`${r.level}:${r.eci_code}`, r]));
  return keys
    .map((k) => byKey.get(k))
    .filter((r): r is PlaceCard => r !== undefined);
}

/** When the news poller last completed (null before its first run). */
export async function getNewsLastChecked(): Promise<Date | null> {
  const rows = await sql<{ retrieved_at: Date }[]>`
    SELECT retrieved_at FROM facts
    WHERE key = 'news_poll_run'
    ORDER BY retrieved_at DESC LIMIT 1
  `;
  return rows[0]?.retrieved_at ?? null;
}

/**
 * Items whose extracted entities mention any of these persons (M7.5).
 * Empty until the clustering pipeline's extraction stage has run.
 */
export async function getPersonNewsItems(
  personIds: number[],
  limit = 5,
): Promise<NewsSingleItem[]> {
  if (personIds.length === 0) return [];
  return sql<NewsSingleItem[]>`
    SELECT i.id, i.outlet, i.url, i.headline_orig AS headline, i.lang,
           i.published_at, i.retrieved_at, i.image_url,
           i.title_clean_en, i.title_clean_ta, i.civic_priority,
           d.name_en AS district_en, d.name_ta AS district_ta,
           d.lgd_code AS district_lgd
    FROM news_items i
    LEFT JOIN localities d ON d.id = i.locality_id
    WHERE i.entities IS NOT NULL
      AND (i.civic_class IS NULL OR i.civic_class <> 'soft')
      AND EXISTS (
        SELECT 1 FROM jsonb_array_elements(i.entities -> 'persons') AS p
        WHERE (p ->> 'person_id')::bigint = ANY(${personIds})
      )
      AND i.published_at > now() - interval '14 days'
    ORDER BY i.published_at DESC
    LIMIT ${limit}
  `;
}

/** One cluster with members, for the dedicated story page (D-024). */
export async function getNewsClusterById(
  id: number,
): Promise<NewsCluster | null> {
  const rows = await sql<NewsCluster[]>`
    SELECT c.id, c.title_en, c.title_ta, c.summary_en, c.summary_ta,
           c.citations, c.summary_long_en, c.summary_long_ta,
           c.coverage_notes, c.event_time, c.discussion_locked,
           c.lock_category, c.sources_disagree, c.retrieved_at,
           d.name_en AS district_en, d.name_ta AS district_ta,
           d.lgd_code AS district_lgd,
           s.name AS source_name, s.url AS source_url,
           s.publisher AS source_publisher, s.license AS source_license,
           m.members, m.priority_high
    FROM news_clusters c
    JOIN sources s ON s.id = c.source_id
    LEFT JOIN localities d ON d.id = c.locality_id
    JOIN LATERAL (
      SELECT json_agg(json_build_object(
               'id', i.id, 'outlet', i.outlet, 'url', i.url,
               'headline', i.headline_orig, 'lang', i.lang,
               'published_at', i.published_at, 'image_url', i.image_url
             ) ORDER BY i.published_at) AS members,
             bool_or(i.civic_priority = 'high') AS priority_high,
             count(*) AS n
      FROM cluster_coverage cc
      JOIN news_items i ON i.id = cc.news_item_id
      WHERE cc.cluster_id = c.id
    ) m ON m.n >= 1
    WHERE c.id = ${id}
  `;
  return rows[0] ?? null;
}

export interface PersonSearchRow {
  person_id: number;
  name_en: string;
  name_ta: string | null;
  seat_level: string;
  seat_code: string;
  seat_en: string;
  seat_ta: string;
}

/** Search-everything (D-026): current officeholders by name. */
export async function searchPersons(q: string): Promise<PersonSearchRow[]> {
  const like = `%${q}%`;
  return sql<PersonSearchRow[]>`
    SELECT p.id AS person_id, p.name_en, p.name_ta,
           l.level::text AS seat_level, l.eci_code AS seat_code,
           l.name_en AS seat_en, l.name_ta AS seat_ta
    FROM persons p
    JOIN tenures t ON t.person_id = p.id
      AND t.end_date IS NULL AND t.status = 'active'
    JOIN offices o ON o.id = t.office_id
    JOIN localities l ON l.id = o.locality_id
    WHERE p.name_en ILIKE ${like} OR p.name_ta LIKE ${like}
    ORDER BY p.name_en
    LIMIT 6
  `;
}

export interface StorySearchRow {
  kind: "cluster" | "item";
  id: number;
  title: string;
  lang: string;
  url: string | null;
  outlet: string | null;
}

/** Search-everything (D-026): stories by our titles first, headlines second. */
export async function searchStories(
  q: string,
  lang: "ta" | "en",
): Promise<StorySearchRow[]> {
  const like = `%${q}%`;
  return sql<StorySearchRow[]>`
    (
      SELECT 'cluster' AS kind, c.id, COALESCE(
               ${lang === "ta" ? sql`c.title_ta` : sql`c.title_en`},
               c.title_en, c.title_ta
             ) AS title,
             ${lang} AS lang, NULL AS url, NULL AS outlet
      FROM news_clusters c
      WHERE (c.title_en ILIKE ${like} OR c.title_ta LIKE ${like})
        AND c.event_time > now() - interval '30 days'
    )
    UNION ALL
    (
      SELECT 'item' AS kind, i.id, COALESCE(
               ${lang === "ta" ? sql`i.title_clean_ta` : sql`i.title_clean_en`},
               i.headline_orig
             ) AS title,
             i.lang, i.url, i.outlet
      FROM news_items i
      WHERE (i.headline_orig ILIKE ${like}
             OR i.title_clean_en ILIKE ${like}
             OR i.title_clean_ta LIKE ${like})
        AND (i.civic_class IS NULL OR i.civic_class <> 'soft')
        AND i.published_at > now() - interval '14 days'
      ORDER BY i.published_at DESC
      LIMIT 6
    )
    LIMIT 8
  `;
}

export interface ClusterNumberRow {
  person_id: number;
  name_en: string;
  name_ta: string | null;
  seat_level: string;
  seat_code: string;
  seat_en: string;
  seat_ta: string;
  election_result: unknown;
  result_retrieved_at: Date | null;
  result_source_name: string | null;
  result_source_url: string | null;
  result_source_publisher: string | null;
  result_source_license: string | null;
}

/**
 * "In numbers" (D-026): our own sourced records touched by a story — the
 * matched persons' seats and election figures. Facts only, provenance
 * attached; renders nothing when the story matches nobody we track.
 */
export async function getClusterNumbers(
  clusterId: number,
): Promise<ClusterNumberRow[]> {
  return sql<ClusterNumberRow[]>`
    WITH member_persons AS (
      SELECT DISTINCT (p ->> 'person_id')::bigint AS person_id
      FROM cluster_coverage cc
      JOIN news_items i ON i.id = cc.news_item_id,
           jsonb_array_elements(i.entities -> 'persons') AS p
      WHERE cc.cluster_id = ${clusterId} AND p ? 'person_id'
    )
    SELECT p.id AS person_id, p.name_en, p.name_ta,
           l.level::text AS seat_level, l.eci_code AS seat_code,
           l.name_en AS seat_en, l.name_ta AS seat_ta,
           f.value AS election_result, f.retrieved_at AS result_retrieved_at,
           s.name AS result_source_name, s.url AS result_source_url,
           s.publisher AS result_source_publisher,
           s.license AS result_source_license
    FROM member_persons mp
    JOIN persons p ON p.id = mp.person_id
    JOIN tenures t ON t.person_id = p.id
      AND t.end_date IS NULL AND t.status = 'active'
    JOIN offices o ON o.id = t.office_id
    JOIN localities l ON l.id = o.locality_id
    LEFT JOIN facts f ON f.subject_type = 'locality' AND f.subject_id = l.id
      AND f.key = 'election_result'
    LEFT JOIN sources s ON s.id = f.source_id
    ORDER BY p.name_en
    LIMIT 4
  `;
}

/** Deterministic daily brief: today's top civic clusters, explainably
 * ranked (priority, then breadth of coverage). No opaque scoring. */
export async function getDailyBrief(limit = 5): Promise<NewsCluster[]> {
  return sql<NewsCluster[]>`
    SELECT c.id, c.title_en, c.title_ta, c.summary_en, c.summary_ta,
           c.citations, c.summary_long_en, c.summary_long_ta,
           c.coverage_notes, c.event_time, c.discussion_locked,
           c.lock_category, c.sources_disagree, c.retrieved_at,
           d.name_en AS district_en, d.name_ta AS district_ta,
           d.lgd_code AS district_lgd,
           s.name AS source_name, s.url AS source_url,
           s.publisher AS source_publisher, s.license AS source_license,
           m.members, m.priority_high
    FROM news_clusters c
    JOIN sources s ON s.id = c.source_id
    LEFT JOIN localities d ON d.id = c.locality_id
    JOIN LATERAL (
      SELECT json_agg(json_build_object(
               'id', i.id, 'outlet', i.outlet, 'url', i.url,
               'headline', i.headline_orig, 'lang', i.lang,
               'published_at', i.published_at, 'image_url', i.image_url
             ) ORDER BY i.published_at) AS members,
             bool_or(i.civic_priority = 'high') AS priority_high,
             count(DISTINCT i.outlet) AS outlets
      FROM cluster_coverage cc
      JOIN news_items i ON i.id = cc.news_item_id
      WHERE cc.cluster_id = c.id
    ) m ON m.outlets >= 2
    WHERE c.event_time > now() - interval '24 hours'
      AND c.summary_en IS NOT NULL
    ORDER BY m.priority_high DESC, m.outlets DESC, c.event_time DESC
    LIMIT ${limit}
  `;
}

/** The outlets currently flowing into news_items (coverage-table universe). */
export async function getTrackedOutlets(): Promise<string[]> {
  const rows = await sql<{ outlet: string }[]>`
    SELECT DISTINCT outlet FROM news_items ORDER BY outlet
  `;
  return rows.map((r) => r.outlet);
}

export async function getDistrictByLgd(
  lgdCode: string,
): Promise<{ id: number; name_en: string; name_ta: string } | null> {
  const rows = await sql<{ id: number; name_en: string; name_ta: string }[]>`
    SELECT id, name_en, name_ta FROM localities
    WHERE level = 'district' AND lgd_code = ${lgdCode}
  `;
  return rows[0] ?? null;
}

export interface DistrictDetail {
  id: number;
  lgd_code: string;
  name_en: string;
  name_ta: string;
  retrieved_at: Date;
  source_name: string;
  source_url: string | null;
  source_publisher: string;
  source_license: string | null;
  source_access_mode: string;
}

/** District page detail: the locality row plus its record provenance. */
export async function getDistrict(
  lgdCode: string,
): Promise<DistrictDetail | null> {
  const rows = await sql<DistrictDetail[]>`
    SELECT l.id, l.lgd_code, l.name_en, l.name_ta, l.retrieved_at,
           s.name AS source_name, s.url AS source_url,
           s.publisher AS source_publisher, s.license AS source_license,
           s.access_mode AS source_access_mode
    FROM localities l
    JOIN sources s ON s.id = l.source_id
    WHERE l.level = 'district' AND l.lgd_code = ${lgdCode}
  `;
  return rows[0] ?? null;
}

/** Assembly constituencies whose seats lie in a district (cross-links). */
export async function getDistrictAcs(
  districtId: number,
): Promise<ConstituencyListItem[]> {
  return sql<ConstituencyListItem[]>`
    SELECT l.id, l.eci_code, l.name_en, l.name_ta,
           l.level::text AS level,
           d.name_en AS district_en, d.name_ta AS district_ta
    FROM localities l
    LEFT JOIN localities d ON d.id = l.district_id
    WHERE l.level = 'ac' AND l.district_id = ${districtId}
    ORDER BY (l.eci_code)::int
  `;
}

/**
 * /freshness is generated from the database, never by hand: last retrieval
 * time and row count per source, across localities, facts and news items.
 */
export async function getFreshness(): Promise<FreshnessRow[]> {
  return sql<FreshnessRow[]>`
    WITH usage AS (
      SELECT source_id, retrieved_at FROM localities
      UNION ALL
      SELECT source_id, retrieved_at FROM facts
      UNION ALL
      SELECT source_id, retrieved_at FROM news_items
      UNION ALL
      SELECT source_id, retrieved_at FROM news_clusters
    )
    SELECT s.name AS source_name, s.url AS source_url,
           s.publisher, s.license, s.access_mode, s.cadence,
           MAX(u.retrieved_at) AS last_retrieved,
           (EXTRACT(EPOCH FROM (now() - MAX(u.retrieved_at))) / 3600)::float
             AS age_hours,
           COUNT(*)::int AS record_count
    FROM usage u
    JOIN sources s ON s.id = u.source_id
    GROUP BY s.id, s.name, s.url, s.publisher, s.license, s.access_mode,
             s.cadence
    ORDER BY s.name
  `;
}
