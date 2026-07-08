import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";

const GITHUB_URL = "https://github.com/Aakash-Marthandan/Project-Arivom";

export async function SiteFooter() {
  const t = await getTranslations("common");

  return (
    <footer className="mt-16 border-t border-border bg-secondary/60">
      <div className="mx-auto grid w-full max-w-5xl gap-8 px-4 py-10 sm:grid-cols-3">
        <div className="space-y-2 sm:col-span-1">
          <p className="font-heading text-lg font-bold text-primary">
            {t("appName")}
          </p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t("footer.mission")}
          </p>
        </div>
        <div className="space-y-2">
          <p className="text-sm font-semibold">{t("footer.sections.explore")}</p>
          <ul className="space-y-1 text-sm text-muted-foreground">
            <li>
              <Link href="/constituencies" className="hover:text-primary hover:underline">
                {t("nav.search")}
              </Link>
            </li>
            <li>
              <Link href="/right-to-know" className="hover:text-primary hover:underline">
                {t("nav.rightToKnow")}
              </Link>
            </li>
            <li>
              <Link href="/corrections" className="hover:text-primary hover:underline">
                {t("nav.corrections")}
              </Link>
            </li>
            <li>
              <Link href="/methodology" className="hover:text-primary hover:underline">
                {t("nav.methodology")}
              </Link>
            </li>
            <li>
              <Link href="/freshness" className="hover:text-primary hover:underline">
                {t("nav.freshness")}
              </Link>
            </li>
          </ul>
        </div>
        <div className="space-y-2">
          <p className="text-sm font-semibold">{t("footer.sections.trust")}</p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t("footer.neutrality")}
          </p>
          <p className="text-sm text-muted-foreground">
            <a
              href={GITHUB_URL}
              rel="noopener noreferrer"
              className="hover:text-primary hover:underline"
            >
              {t("footer.sourceCode")}
            </a>
          </p>
          <p className="text-xs text-muted-foreground">{t("footer.license")}</p>
        </div>
      </div>
    </footer>
  );
}
