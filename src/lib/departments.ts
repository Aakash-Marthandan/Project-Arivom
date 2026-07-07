/**
 * Loose department-name matching (D-019): /government cards carry
 * source-verbatim portfolio names that differ per locale, and the
 * extraction tags stories with one department name per language. Until
 * the official tn.gov.in directory becomes the canonical list, a tag
 * matches a card when either normalized form contains the other.
 */

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
