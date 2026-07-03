"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { routing, type Locale } from "@/i18n/routing";

const LOCALE_PREFIX = new RegExp(`^/(${routing.locales.join("|")})(?=/|$)`);

/**
 * Deliberately provider-free: uses a plain anchor + pathname rewrite so we
 * avoid shipping NextIntlClientProvider (and message catalogs) to the client.
 * A full navigation on language switch is correct — the document language,
 * fonts, and metadata all change. Query params are preserved (e.g. the
 * coordinates on /locate results).
 */
export function LocaleSwitcher({
  label,
  switchTo,
  otherLocale,
}: {
  label: string;
  switchTo: string;
  otherLocale: Locale;
}) {
  const pathname = usePathname() ?? "/";
  const search = useSearchParams()?.toString();
  const rest = pathname.replace(LOCALE_PREFIX, "");
  const href = `/${otherLocale}${rest}${search ? `?${search}` : ""}`;

  return (
    <a
      href={href}
      lang={otherLocale}
      aria-label={label}
      className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground/80 hover:border-primary hover:text-primary"
    >
      {switchTo}
    </a>
  );
}
