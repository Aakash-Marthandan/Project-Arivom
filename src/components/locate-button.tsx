"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LocateFixed, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Phase = "idle" | "locating" | "denied" | "failed";

/**
 * Geolocation entry point. Coordinates go only into the /locate URL for
 * one server-side point-in-polygon lookup — never persisted (the page
 * states this). Denial and failure keep the promise made in the copy:
 * a name-search form appears right where the message points, on every
 * surface this button lives on. All strings arrive as props (no client
 * message catalogs).
 */
export function LocateButton({
  targetPath,
  labels,
  fallback,
}: {
  targetPath: string; // e.g. "/ta/locate"
  labels: {
    button: string;
    locating: string;
    denied: string;
    failed: string;
  };
  fallback?: {
    action: string; // e.g. "/ta/constituencies"
    placeholder: string;
    submit: string;
  };
}) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");

  function locate() {
    if (!("geolocation" in navigator)) {
      setPhase("failed");
      return;
    }
    setPhase("locating");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude.toFixed(5);
        const lon = pos.coords.longitude.toFixed(5);
        router.push(`${targetPath}?lat=${lat}&lon=${lon}`);
      },
      (err) => {
        setPhase(err.code === err.PERMISSION_DENIED ? "denied" : "failed");
      },
      { enableHighAccuracy: false, timeout: 12000, maximumAge: 300000 },
    );
  }

  const message =
    phase === "denied" ? labels.denied : phase === "failed" ? labels.failed : null;

  return (
    <div className="space-y-2">
      <Button size="lg" onClick={locate} disabled={phase === "locating"}>
        <LocateFixed className="size-4" aria-hidden="true" />
        {phase === "locating" ? labels.locating : labels.button}
      </Button>
      {message ? (
        <p role="status" className="text-sm text-muted-foreground">
          {message}
        </p>
      ) : null}
      {message && fallback ? (
        <form
          method="get"
          action={fallback.action}
          role="search"
          className="flex max-w-md gap-2 pt-1"
        >
          <label htmlFor="locate-fallback-q" className="sr-only">
            {fallback.placeholder}
          </label>
          <Input
            id="locate-fallback-q"
            name="q"
            type="search"
            placeholder={fallback.placeholder}
            className="bg-card"
            /* The user just hit a wall; put them straight into the remedy. */
            autoFocus
          />
          <Button type="submit" variant="secondary" className="shrink-0">
            <Search className="size-4" aria-hidden="true" />
            {fallback.submit}
          </Button>
        </form>
      ) : null}
    </div>
  );
}
