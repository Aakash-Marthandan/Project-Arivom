"use client";

import { useState, useSyncExternalStore, useTransition } from "react";
import { followPerson, unfollowPerson } from "@/lib/places-actions";
import { MAX_FOLLOWS } from "@/lib/places-shared";

/**
 * Follow a representative (D-026): device cookie, no account, capped.
 * Client-side so ISR pages stay static; optimistic flip.
 */

const subscribeNoop = () => () => {};
const readCookie = () =>
  document.cookie.split("; ").find((c) => c.startsWith("arivom_follows=")) ??
  "";
const serverSnapshot = () => null;

function parseState(
  cookie: string | null,
  personId: number,
): "unknown" | "in" | "out" | "full" {
  if (cookie === null) return "unknown";
  try {
    const raw = cookie.split("=")[1];
    const ids: number[] = raw ? JSON.parse(decodeURIComponent(raw)) : [];
    if (ids.includes(personId)) return "in";
    return ids.length >= MAX_FOLLOWS ? "full" : "out";
  } catch {
    return "out";
  }
}

export function FollowToggle({
  personId,
  labels,
}: {
  personId: number;
  labels: { follow: string; following: string };
}) {
  const cookie = useSyncExternalStore(subscribeNoop, readCookie, serverSnapshot);
  const [override, setOverride] = useState<"in" | "out" | null>(null);
  const [, startTransition] = useTransition();

  const state = override ?? parseState(cookie, personId);
  if (state === "unknown" || state === "full") {
    return <span className="inline-block h-8 w-24" aria-hidden="true" />;
  }

  const inFollows = state === "in";
  const toggle = () => {
    const data = new FormData();
    data.set("person_id", String(personId));
    setOverride(inFollows ? "out" : "in");
    startTransition(async () => {
      await (inFollows ? unfollowPerson(data) : followPerson(data));
    });
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={inFollows}
      className={
        inFollows
          ? "press rounded-full border border-border bg-card px-3 py-1.5 text-xs font-bold text-muted-foreground"
          : "press rounded-full border border-primary/50 bg-accent px-3 py-1.5 text-xs font-bold text-accent-foreground"
      }
    >
      {inFollows ? labels.following : labels.follow}
    </button>
  );
}
