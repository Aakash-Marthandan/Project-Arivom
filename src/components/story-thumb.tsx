"use client";

import { useState } from "react";

/**
 * Hotlinked outlet story image (D-024): lazy, referrer-free, and it
 * disappears gracefully — a kolam-dot placeholder — when the outlet's CDN
 * blocks or breaks. We never copy or re-serve the asset.
 */
export function StoryThumb({
  src,
  className,
  eager = false,
}: {
  src: string | null;
  className: string;
  /** First in-viewport image: skip lazy-loading so LCP isn't delayed. */
  eager?: boolean;
}) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <span
        aria-hidden="true"
        className={`${className} grid shrink-0 place-items-center bg-accent/60`}
      >
        <svg viewBox="0 0 24 24" className="size-6 opacity-50" aria-hidden="true">
          {[
            [6, 6], [12, 6], [18, 6],
            [6, 12], [18, 12],
            [6, 18], [12, 18], [18, 18],
          ].map(([x, y]) => (
            <circle key={`${x}${y}`} cx={x} cy={y} r="1.3" fill="var(--primary)" />
          ))}
          <circle cx="12" cy="12" r="2.2" fill="var(--primary)" />
        </svg>
      </span>
    );
  }

  // Outlet CDNs are arbitrary hosts; we hotlink unoptimized by policy
  // (D-024) rather than proxy their assets through our infrastructure.
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      loading={eager ? "eager" : "lazy"}
      fetchPriority={eager ? "high" : "auto"}
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={`${className} shrink-0 object-cover`}
    />
  );
}
