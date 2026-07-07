/**
 * Loose department-name matching (D-019): /government cards carry
 * source-verbatim portfolio names that differ per locale, and the
 * extraction tags stories with one department name per language. Until
 * the official tn.gov.in directory becomes the canonical list, a tag
 * matches a card when either normalized form contains the other.
 */

/** One department card: name is the department's identity (the source's
 *  link target when it has one, D-033); subjects is the allocation text
 *  shown under it when the two differ. */
export interface DepartmentEntry {
  name: string;
  subjects: string | null;
}

export type StoredPortfolios = DepartmentEntry[] | string[] | string;

/** The ministers importer stores one entry per source-listed department
 *  (D-032/D-033). Older rows are flat strings or plain string arrays;
 *  normalization keeps prod rendering until its re-import lands. */
export function departmentEntries(
  portfolios: StoredPortfolios,
): DepartmentEntry[] {
  if (Array.isArray(portfolios)) {
    return portfolios.map((p) =>
      typeof p === "string" ? { name: p, subjects: null } : p,
    );
  }
  return portfolios
    .split(",")
    .map((d) => d.trim().replace(/\s+/g, " "))
    .filter((d) => d.length > 1)
    .map((name) => ({ name, subjects: null }));
}

export function departmentList(portfolios: StoredPortfolios): string[] {
  return departmentEntries(portfolios).map((e) => e.name);
}

const STRIP_WORDS = /\b(department|dept|of|and|the)\b|துறை|மற்றும்/g;

export function normalizeDepartment(name: string): string {
  return name
    .normalize("NFKC")
    .toLowerCase()
    .replace(STRIP_WORDS, " ")
    .replace(/[^\p{L}\p{N} ]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function departmentMatches(cardName: string, tag: string): boolean {
  const a = normalizeDepartment(cardName);
  const b = normalizeDepartment(tag);
  if (!a || !b) return false;
  return a.includes(b) || b.includes(a);
}
