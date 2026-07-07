"use client";

import { useState, useSyncExternalStore, useTransition } from "react";
import { addPlace, removePlace } from "@/lib/places-actions";
import { MAX_PLACES } from "@/lib/places-shared";

/**
 * Add/remove a constituency from "my places" (M7.5, D-023). Client-side so
 * ISR-cached constituency pages stay static: the state comes from the
 * (non-httpOnly) places cookie after hydration; the mutation is a server
 * action with an optimistic flip for app-grade feedback.
 */

const subscribeNoop = () => () => {};
const readCookie = () =>
  document.cookie.split("; ").find((c) => c.startsWith("arivom_places=")) ??
  "";
const serverSnapshot = () => null;

function parseState(
  cookie: string | null,
  level: string,
  code: string,
): "unknown" | "in" | "out" | "full" {
  if (cookie === null) return "unknown";
  try {
    const raw = cookie.split("=")[1];
    const places: { level: string; code: string }[] = raw
      ? JSON.parse(decodeURIComponent(raw))
      : [];
    if (places.some((p) => p.level === level && p.code === code)) return "in";
    return places.length >= MAX_PLACES ? "full" : "out";
  } catch {
    return "out";
  }
}

export function PlaceToggle({
  level,
  code,
  labels,
}: {
  level: "ac" | "pc";
  code: string;
  labels: { add: string; remove: string; full: string };
}) {
  const cookie = useSyncExternalStore(subscribeNoop, readCookie, serverSnapshot);
  const [override, setOverride] = useState<"in" | "out" | null>(null);
  const [, startTransition] = useTransition();

  const state = override ?? parseState(cookie, level, code);

  if (state === "unknown") {
    // Stable footprint pre-hydration; a button-shaped shimmer reads as
    // "loading", never as an empty hole in the page.
    return (
      <div
        className="h-9 w-40 animate-pulse rounded-lg bg-secondary"
        aria-hidden="true"
      />
    );
  }
  if (state === "full") {
    return <p className="text-sm text-muted-foreground">{labels.full}</p>;
  }

  const inPlaces = state === "in";
  const toggle = () => {
    const data = new FormData();
    data.set("level", level);
    data.set("code", code);
    setOverride(inPlaces ? "out" : "in");
    startTransition(async () => {
      await (inPlaces ? removePlace(data) : addPlace(data));
    });
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={inPlaces}
      className={
        inPlaces
          ? "press rounded-lg border border-border bg-card px-4 py-2 text-sm font-bold text-muted-foreground"
          : "press rounded-lg bg-primary px-4 py-2 text-sm font-bold text-primary-foreground shadow-[0_6px_14px_-8px_rgba(22,100,110,0.7)]"
      }
    >
      {inPlaces ? `✓ ${labels.remove}` : `★ ${labels.add}`}
    </button>
  );
}
