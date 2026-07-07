import { Suspense } from "react";
import { getLocale, getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { LocaleSwitcher } from "@/components/locale-switcher";

export async function SiteHeader() {
  const t = await getTranslations("common");
  const locale = await getLocale();
  const otherLocale = locale === "ta" ? "en" : "ta";

  const nav = [
    // One name for one destination (owner, audit round): the tab bar,
    // header and /more all say "Search" for /constituencies.
    { href: "/constituencies", label: t("nav.search") },
    { href: "/government", label: t("nav.government") },
    { href: "/news", label: t("nav.news") },
    { href: "/vacancies", label: t("nav.vacancies") },
    { href: "/methodology", label: t("nav.methodology") },
    { href: "/freshness", label: t("nav.freshness") },
  ] as const;

  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="flex items-center gap-2.5">
          {/* The D-027 mark; the ink-field variant when the system is dark
              (D-029) — a <picture> swap, no client JS. */}
          <picture>
            <source
              media="(prefers-color-scheme: dark)"
              srcSet="/logo-dark.svg"
            />
            <img
              src="/logo.svg"
              alt=""
              width={30}
              height={30}
              className="h-[30px] w-[30px]"
            />
          </picture>
          <span className="flex items-baseline gap-2">
            <span className="font-heading text-2xl font-bold tracking-tight text-primary">
              {t("appName")}
            </span>
            <span className="hidden text-sm text-muted-foreground sm:inline">
              {t("tagline")}
            </span>
          </span>
        </Link>
        {/* Suspense: useSearchParams requires it during static prerender. */}
        <Suspense>
          <LocaleSwitcher
            label={t("localeSwitcher.label")}
            switchTo={t("localeSwitcher.switchTo")}
            otherLocale={otherLocale}
          />
        </Suspense>
      </div>
      {/* Desktop nav; on mobile the bottom tab bar carries the IA (D-023). */}
      <nav
        aria-label={t("nav.home")}
        className="mx-auto hidden w-full max-w-5xl overflow-x-auto px-4 md:block"
      >
        <ul className="flex gap-6 pb-2 text-sm font-medium">
          {nav.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                className="whitespace-nowrap text-foreground/80 underline-offset-8 hover:text-primary hover:underline"
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
