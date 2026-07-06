import type { Metadata } from "next";
import {
  getFormatter,
  getTranslations,
  setRequestLocale,
} from "next-intl/server";
import { buildNewsStrings, NewsFeed } from "@/components/news-feed";
import { getNewsClusters, getUnclusteredItems } from "@/lib/queries";

export const revalidate = 600;

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/news">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "news" });
  return { title: t("title"), description: t("intro") };
}

export default async function NewsPage({
  params,
}: PageProps<"/[locale]/news">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const lang = locale === "ta" ? ("ta" as const) : ("en" as const);
  const [t, format, strings, clusters, items] = await Promise.all([
    getTranslations("news"),
    getFormatter(),
    buildNewsStrings(),
    getNewsClusters(),
    getUnclusteredItems(lang),
  ]);

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>

      {clusters.length === 0 && items.length === 0 ? (
        <p className="mt-10 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-muted-foreground">
          {t("empty")}
        </p>
      ) : (
        <NewsFeed
          clusters={clusters}
          items={items}
          locale={locale}
          format={format}
          strings={strings}
        />
      )}

      <p className="mt-8 max-w-2xl rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
        {t("methodNote")}
      </p>
    </div>
  );
}
