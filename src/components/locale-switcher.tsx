"use client";

import { usePathname } from "next/navigation";
import { routing, type Locale } from "@/i18n/routing";

const LOCALE_PREFIX = new RegExp(`^/(${routing.locales.join("|")})(?=/|$)`);

/**
 * Deliberately provider-free: uses a plain anchor + pathname rewrite so we
 * avoid shipping NextIntlClientProvider (and message catalogs) to the client.
 * A full navigation on language switch is correct — the document language,
 * fonts, and metadata all change.
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
  const rest = pathname.replace(LOCALE_PREFIX, "");
  const href = `/${otherLocale}${rest}`;

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
