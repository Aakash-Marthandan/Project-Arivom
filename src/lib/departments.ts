/**
 * Loose department-name matching (D-019): /government cards carry
 * source-verbatim portfolio names that differ per locale, and the
 * extraction tags stories with one department name per language. Until
 * the official tn.gov.in directory becomes the canonical list, a tag
 * matches a card when either normalized form contains the other.
 */

/** The ministers importer stores one entry per source-listed department
 *  (D-032). Legacy rows are flat strings; comma-splitting them is
 *  best-effort until the re-import lands everywhere. */
export function departmentList(portfolios: string[] | string): string[] {
  if (Array.isArray(portfolios)) return portfolios;
  return portfolios
    .split(",")
    .map((d) => d.trim().replace(/\s+/g, " "))
    .filter((d) => d.length > 1);
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
