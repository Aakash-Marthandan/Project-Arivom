"use client";

import { useEffect } from "react";

/** Registers the offline-shell service worker (PWA, D-023). */
export function SwRegister() {
  useEffect(() => {
    if (
      process.env.NODE_ENV === "production" &&
      "serviceWorker" in navigator
    ) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // Offline support is progressive enhancement; never break the page.
      });
    }
  }, []);
  return null;
}
