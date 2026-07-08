"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

const KEY = "arivom_seen";

/**
 * Device-local footprints for the knowledge map (D-035): remembers which
 * pages this device has seen, in localStorage, like the browser's own
 * visited-link memory. Never sent anywhere, no account, no identifier —
 * the same posture as my-places (D-023).
 */
export function SeenTracker() {
  const pathname = usePathname();
  useEffect(() => {
    try {
      const seen: Record<string, number> = JSON.parse(
        localStorage.getItem(KEY) ?? "{}",
      );
      // Locale-free path: reading a page in Tamil or English is the same
      // journey.
      const canonical = pathname.replace(/^\/(ta|en)(?=\/|$)/, "") || "/";
      if (!seen[canonical]) {
        seen[canonical] = Date.now();
        localStorage.setItem(KEY, JSON.stringify(seen));
      }
    } catch {
      // Storage unavailable (private mode etc.): the map simply shows no
      // footprints. Nothing breaks.
    }
  }, [pathname]);
  return null;
}
