"use client";

import { useState } from "react";
import { Share2 } from "lucide-react";

/** Native share where available, clipboard fallback elsewhere (M7.5). */
export function ShareButton({
  title,
  labels,
}: {
  title: string;
  labels: { share: string; copied: string };
}) {
  const [copied, setCopied] = useState(false);

  const share = async () => {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // User dismissed the sheet; nothing to do.
    }
  };

  return (
    <button
      type="button"
      onClick={share}
      className="press inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-bold text-muted-foreground hover:border-primary hover:text-primary"
    >
      <Share2 aria-hidden="true" className="size-3.5" />
      {copied ? labels.copied : labels.share}
    </button>
  );
}
