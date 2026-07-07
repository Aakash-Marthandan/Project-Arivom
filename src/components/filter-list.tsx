"use client";

import { useId, useRef, useState } from "react";
import { Input } from "@/components/ui/input";

/**
 * Progressive find-as-you-type over a server-rendered list: children carry
 * data-filter text; typing hides non-matches. Without JS the full list
 * simply shows (nothing is gated on the filter). Built for long civic
 * lists like the 100+ department cards on /government.
 */
export function FilterList({
  placeholder,
  emptyLabel,
  children,
}: {
  placeholder: string;
  emptyLabel: string;
  children: React.ReactNode;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [empty, setEmpty] = useState(false);
  const inputId = useId();

  function apply(query: string) {
    const norm = query.trim().toLowerCase();
    let visible = 0;
    containerRef.current
      ?.querySelectorAll<HTMLElement>("[data-filter]")
      .forEach((el) => {
        const hit = !norm || (el.dataset.filter ?? "").includes(norm);
        el.hidden = !hit;
        if (hit) visible += 1;
      });
    setEmpty(visible === 0);
  }

  return (
    <div>
      <label htmlFor={inputId} className="sr-only">
        {placeholder}
      </label>
      <Input
        id={inputId}
        type="search"
        placeholder={placeholder}
        onChange={(e) => apply(e.target.value)}
        className="max-w-md bg-card"
      />
      <div ref={containerRef}>{children}</div>
      {empty ? (
        <p className="mt-4 text-sm text-muted-foreground" role="status">
          {emptyLabel}
        </p>
      ) : null}
    </div>
  );
}
