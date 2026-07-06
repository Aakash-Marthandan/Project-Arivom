"use server";

import { cookies } from "next/headers";
import {
  MAX_PLACES,
  PLACES_COOKIE,
  parsePlaces,
  type Place,
} from "./places-shared";

// Not httpOnly: the client-side place toggle on ISR-cached constituency
// pages reads it to show add/remove state without forcing those pages
// dynamic (performance pillar). It holds nothing but the user's own list.
const COOKIE_OPTS = {
  httpOnly: false,
  sameSite: "lax" as const,
  path: "/",
  maxAge: 60 * 60 * 24 * 365,
};

function readPlace(formData: FormData): Place | null {
  const level = formData.get("level");
  const code = formData.get("code");
  if (
    (level === "ac" || level === "pc") &&
    typeof code === "string" &&
    /^\d{1,3}$/.test(code)
  ) {
    return { level, code };
  }
  return null;
}

export async function addPlace(formData: FormData): Promise<void> {
  const place = readPlace(formData);
  if (!place) return;
  const jar = await cookies();
  const places = parsePlaces(jar.get(PLACES_COOKIE)?.value);
  if (
    !places.some((p) => p.level === place.level && p.code === place.code) &&
    places.length < MAX_PLACES
  ) {
    jar.set(PLACES_COOKIE, JSON.stringify([...places, place]), COOKIE_OPTS);
  }
}

export async function removePlace(formData: FormData): Promise<void> {
  const place = readPlace(formData);
  if (!place) return;
  const jar = await cookies();
  const places = parsePlaces(jar.get(PLACES_COOKIE)?.value).filter(
    (p) => !(p.level === place.level && p.code === place.code),
  );
  jar.set(PLACES_COOKIE, JSON.stringify(places), COOKIE_OPTS);
}
