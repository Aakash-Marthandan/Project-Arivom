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
  last_retrieved: Date;
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

/**
 * /freshness is generated from the database, never by hand: last retrieval
 * time and row count per source, across localities and facts.
 */
export async function getFreshness(): Promise<FreshnessRow[]> {
  return sql<FreshnessRow[]>`
    WITH usage AS (
      SELECT source_id, retrieved_at FROM localities
      UNION ALL
      SELECT source_id, retrieved_at FROM facts
    )
    SELECT s.name AS source_name, s.url AS source_url,
           s.publisher, s.license, s.access_mode,
           MAX(u.retrieved_at) AS last_retrieved,
           COUNT(*)::int AS record_count
    FROM usage u
    JOIN sources s ON s.id = u.source_id
    GROUP BY s.id, s.name, s.url, s.publisher, s.license, s.access_mode
    ORDER BY s.name
  `;
}
