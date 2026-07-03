import { getLocale, getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { LocaleSwitcher } from "@/components/locale-switcher";

export async function SiteHeader() {
  const t = await getTranslations("common");
  const locale = await getLocale();
  const otherLocale = locale === "ta" ? "en" : "ta";

  const nav = [
    { href: "/constituencies", label: t("nav.constituencies") },
    { href: "/methodology", label: t("nav.methodology") },
    { href: "/freshness", label: t("nav.freshness") },
  ] as const;

  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="font-heading text-2xl font-bold tracking-tight text-primary">
            {t("appName")}
          </span>
          <span className="hidden text-sm text-muted-foreground sm:inline">
            {t("tagline")}
          </span>
        </Link>
        <LocaleSwitcher
          label={t("localeSwitcher.label")}
          switchTo={t("localeSwitcher.switchTo")}
          otherLocale={otherLocale}
        />
      </div>
      <nav
        aria-label={t("nav.home")}
        className="mx-auto w-full max-w-5xl overflow-x-auto px-4"
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
