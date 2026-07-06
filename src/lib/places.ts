import { cookies } from "next/headers";
import {
  FOLLOWS_COOKIE,
  parseFollows,
  parsePlaces,
  PLACES_COOKIE,
  type Place,
} from "./places-shared";

/**
 * "My places" (M7.5, D-023): the constituencies a person follows. Device
 * cookie only — no account, no server-side profile. Capped small so the
 * home feed stays a considered read, not a doomscroll.
 */

export type { Place };

export async function getMyPlaces(): Promise<Place[]> {
  const jar = await cookies();
  return parsePlaces(jar.get(PLACES_COOKIE)?.value);
}

export async function getMyFollows(): Promise<number[]> {
  const jar = await cookies();
  return parseFollows(jar.get(FOLLOWS_COOKIE)?.value);
}
