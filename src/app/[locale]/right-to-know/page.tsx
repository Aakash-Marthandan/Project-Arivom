import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";

export const revalidate = 86400;

const RTI_ACT_URL = "https://www.indiacode.nic.in/handle/123456789/1362";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/right-to-know">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "rightToKnow" });
  return { title: t("title"), description: t("intro") };
}

/**
 * The edge of the data, treated as a civic fact (D-035): where public
 * information stops, this page says who holds it and what the law says
 * about the citizen's right to it. Factual and legal only — the Act's
 * own requirements, never advocacy copy.
 */
export default async function RightToKnowPage({
  params,
}: PageProps<"/[locale]/right-to-know">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("rightToKnow");

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>

      <section aria-labelledby="rtk-law" className="mt-10">
        <h2 id="rtk-law" className="font-heading text-2xl font-bold">
          {t("law.title")}
        </h2>
        <div className="mt-2 space-y-3">
          {(["act", "proactive", "meaning"] as const).map((key) => (
            <p key={key} className="leading-relaxed text-muted-foreground">
              {t(`law.${key}`)}
            </p>
          ))}
        </div>
        <p className="mt-3 text-sm">
          <a
            href={RTI_ACT_URL}
            rel="noopener noreferrer"
            target="_blank"
            className="text-primary underline-offset-4 hover:underline"
          >
            {t("law.actLink")} ↗
          </a>
        </p>
      </section>

      <section aria-labelledby="rtk-edges" className="mt-10">
        <h2 id="rtk-edges" className="font-heading text-2xl font-bold">
          {t("edges.title")}
        </h2>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          {t("edges.intro")}
        </p>
        <ul className="mt-3 space-y-3">
          {(["wards", "contacts"] as const).map((key) => (
            <li
              key={key}
              className="rounded-lg border border-border bg-card p-4"
            >
              <h3 className="font-heading text-base font-bold">
                {t(`edges.${key}.title`)}
              </h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {t(`edges.${key}.body`)}
              </p>
            </li>
          ))}
        </ul>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {t("edges.tracking")}{" "}
          <Link
            href="/freshness"
            className="text-primary underline-offset-4 hover:underline"
          >
            {t("edges.freshnessLink")}
          </Link>
        </p>
      </section>

      <section aria-labelledby="rtk-ask" className="mt-10">
        <h2 id="rtk-ask" className="font-heading text-2xl font-bold">
          {t("ask.title")}
        </h2>
        <div className="mt-2 space-y-3">
          {(["how", "channels", "appeal"] as const).map((key) => (
            <p key={key} className="leading-relaxed text-muted-foreground">
              {t(`ask.${key}`)}
            </p>
          ))}
        </div>
        <p className="mt-3 text-sm">
          <a
            href="https://rtionline.gov.in/"
            rel="noopener noreferrer"
            target="_blank"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {t("ask.portalLink")} ↗
          </a>
        </p>
      </section>

      <p className="mt-10 max-w-2xl rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
        {t("note")}
      </p>
    </div>
  );
}
