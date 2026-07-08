"use client";

import { useSyncExternalStore, useState } from "react";

const KEY = "arivom_seen";

// Same read-after-mount pattern as the knowledge map: SSR shows nothing,
// the device's own state appears on hydration.
const subscribe = (onChange: () => void) => {
  queueMicrotask(onChange);
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
};
const read = () => {
  try {
    return window.localStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
};
const serverSnapshot = () => null;

/**
 * One-tap erasure for the knowledge map's device memory (D-035). The
 * footprints never leave the device; this makes forgetting as easy as
 * remembering was. Renders nothing when there is nothing to forget.
 */
export function ForgetFootprints({
  note,
  action,
  done,
}: {
  note: string;
  action: string;
  done: string;
}) {
  const raw = useSyncExternalStore(subscribe, read, serverSnapshot);
  const [cleared, setCleared] = useState(false);

  const hasPrints = raw !== null && raw !== "" && raw !== "{}";
  if (!hasPrints && !cleared) return null;

  return (
    <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
      {cleared ? (
        done
      ) : (
        <>
          {note}{" "}
          <button
            type="button"
            onClick={() => {
              try {
                window.localStorage.removeItem(KEY);
              } catch {
                // Nothing stored or storage blocked; either way it is gone.
              }
              setCleared(true);
            }}
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {action}
          </button>
        </>
      )}
    </p>
  );
}
