"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";

// Real subscription: one tick after mount (so hydration picks up the
// device's footprints) and live storage events from other tabs.
const subscribeSeen = (onChange: () => void) => {
  queueMicrotask(onChange);
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
};
const readSeen = () => {
  try {
    return localStorage.getItem("arivom_seen") ?? "{}";
  } catch {
    return "{}";
  }
};
const serverSnapshot = () => null;

export interface KnowledgeItem {
  href: string; // locale-prefixed target
  canonical: string; // locale-free path, matches SeenTracker keys
  label: string;
  answers: string; // the question this journey answers
}

/**
 * The knowledge map (D-035): the landscape of what a voter can know from
 * here, each row a real journey named by the question it answers. A quiet
 * dot marks where this device has already been — orientation like a
 * museum floor plan, never a score.
 *
 * Hard boundaries, by design (never loosen these): no counts, no
 * percentages, no completion states, no praise, no streaks. The unvisited
 * arrow is the only invitation; the visited dot is the only memory.
 */
export function KnowledgeMap({
  title,
  deviceNote,
  seenLabel,
  items,
}: {
  title: string;
  deviceNote: string;
  seenLabel: string;
  items: KnowledgeItem[];
}) {
  // Footprints are a device fact, not a server fact: read them like
  // PlaceToggle reads the places cookie. SSR (server snapshot null)
  // shows every row as an invitation.
  const raw = useSyncExternalStore(subscribeSeen, readSeen, serverSnapshot);
  let seen: Record<string, number> | null = null;
  if (raw !== null) {
    try {
      seen = JSON.parse(raw);
    } catch {
      seen = {};
    }
  }

  return (
    <section aria-label={title} className="mt-10">
      <h2 className="font-heading text-xl font-bold">{title}</h2>
      <ul className="mt-3 divide-y divide-border overflow-hidden rounded-lg border border-border bg-card">
        {items.map((item) => {
          const visited = Boolean(seen?.[item.canonical]);
          return (
            <li key={item.canonical}>
              <Link
                href={item.href}
                className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-secondary/50"
              >
                <span className="min-w-0">
                  <span className="block font-medium">{item.label}</span>
                  <span className="mt-0.5 block text-sm text-muted-foreground">
                    {item.answers}
                  </span>
                </span>
                {visited ? (
                  <span
                    className="h-2 w-2 shrink-0 rounded-full bg-primary/50"
                    role="img"
                    aria-label={seenLabel}
                  />
                ) : (
                  <span aria-hidden className="shrink-0 text-primary">
                    →
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">{deviceNote}</p>
    </section>
  );
}
