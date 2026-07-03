"use client";

import { Info } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

export interface ProvenanceEntry {
  /** What this entry sources, e.g. "Constituency list" / "Tamil name". */
  title: string;
  sourceName: string;
  url: string | null;
  publisher: string;
  license: string | null;
  retrievedOn: string; // preformatted, locale-aware
  method: string; // preformatted, localized label
}

/**
 * The provenance chip: pillar 1 made visible. Every displayed fact gets one,
 * opening the source, retrieval date, and collection method — one tap away.
 * All strings arrive preformatted from the server so no message catalog is
 * shipped to the client.
 */
export function ProvenanceChip({
  label,
  heading,
  fieldLabels,
  entries,
}: {
  label: string;
  heading: string;
  fieldLabels: { publisher: string; retrievedOn: string; method: string; license: string; viewSource: string };
  entries: ProvenanceEntry[];
}) {
  return (
    <Popover>
      <PopoverTrigger
        className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary/60 px-2.5 py-0.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-ring"
        aria-label={heading}
      >
        <Info className="size-3" aria-hidden="true" />
        {label}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 max-w-[calc(100vw-2rem)] p-0">
        <p className="border-b border-border px-4 py-2.5 text-sm font-semibold">
          {heading}
        </p>
        <ul className="divide-y divide-border">
          {entries.map((entry) => (
            <li key={entry.title + entry.sourceName} className="space-y-1 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {entry.title}
              </p>
              <p className="text-sm font-medium">{entry.sourceName}</p>
              <dl className="space-y-0.5 text-xs text-muted-foreground">
                <div className="flex gap-1">
                  <dt>{fieldLabels.publisher}:</dt>
                  <dd>{entry.publisher}</dd>
                </div>
                <div className="flex gap-1">
                  <dt>{fieldLabels.retrievedOn}:</dt>
                  <dd>{entry.retrievedOn}</dd>
                </div>
                <div className="flex gap-1">
                  <dt>{fieldLabels.method}:</dt>
                  <dd>{entry.method}</dd>
                </div>
                {entry.license ? (
                  <div className="flex gap-1">
                    <dt>{fieldLabels.license}:</dt>
                    <dd>{entry.license}</dd>
                  </div>
                ) : null}
              </dl>
              {entry.url ? (
                <a
                  href={entry.url}
                  rel="noopener noreferrer"
                  target="_blank"
                  className="inline-block text-xs font-medium text-primary underline underline-offset-4"
                >
                  {fieldLabels.viewSource} ↗
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
