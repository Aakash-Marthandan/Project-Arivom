/**
 * "My places" primitives shared by server and client code (M7.5, D-023).
 * No next/headers here — the client place-toggle imports this module.
 */

export const PLACES_COOKIE = "arivom_places";
export const MAX_PLACES = 5;

export interface Place {
  level: "ac" | "pc";
  code: string;
}

export const FOLLOWS_COOKIE = "arivom_follows";
export const MAX_FOLLOWS = 10;

/** Person follows (D-026): device-only, like places. */
export function parseFollows(raw: string | undefined): number[] {
  if (!raw) return [];
  try {
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return value
      .filter((id): id is number => typeof id === "number" && Number.isInteger(id) && id > 0)
      .slice(0, MAX_FOLLOWS);
  } catch {
    return [];
  }
}

export function parsePlaces(raw: string | undefined): Place[] {
  if (!raw) return [];
  try {
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return value
      .filter(
        (p): p is Place =>
          typeof p === "object" &&
          p !== null &&
          ((p as Place).level === "ac" || (p as Place).level === "pc") &&
          typeof (p as Place).code === "string" &&
          /^\d{1,3}$/.test((p as Place).code),
      )
      .slice(0, MAX_PLACES);
  } catch {
    return [];
  }
}
