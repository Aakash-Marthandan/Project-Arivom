"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LocateFixed } from "lucide-react";
import { Button } from "@/components/ui/button";

type Phase = "idle" | "locating" | "denied" | "failed";

/**
 * Geolocation entry point. Coordinates go only into the /locate URL for
 * one server-side point-in-polygon lookup — never persisted (the page
 * states this). Denial and failure degrade to the always-present manual
 * search. All strings arrive as props (no client message catalogs).
 */
export function LocateButton({
  targetPath,
  labels,
}: {
  targetPath: string; // e.g. "/ta/locate"
  labels: {
    button: string;
    locating: string;
    denied: string;
    failed: string;
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

  return (
    <div className="space-y-2">
      <Button size="lg" onClick={locate} disabled={phase === "locating"}>
        <LocateFixed className="size-4" aria-hidden="true" />
        {phase === "locating" ? labels.locating : labels.button}
      </Button>
      {phase === "denied" ? (
        <p role="status" className="text-sm text-muted-foreground">
          {labels.denied}
        </p>
      ) : null}
      {phase === "failed" ? (
        <p role="status" className="text-sm text-muted-foreground">
          {labels.failed}
        </p>
      ) : null}
    </div>
  );
}
