import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getFormatter,
  getTranslations,
  setRequestLocale,
} from "next-intl/server";
import { Link } from "@/i18n/navigation";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { buildNewsStrings, NewsFeed } from "@/components/news-feed";
import {
  getDistrictByLgd,
  getNewsClusters,
  getUnclusteredItems,
} from "@/lib/queries";

export const revalidate = 600;

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/news/d/[lgd]">): Promise<Metadata> {
  const { locale, lgd } = await params;
  const [t, district] = await Promise.all([
    getTranslations({ locale, namespace: "news" }),
    getDistrictByLgd(lgd),
  ]);
  if (!district) return { title: t("title") };
  const name = locale === "ta" ? district.name_ta : district.name_en;
  return { title: t("districtTitle", { district: name }) };
}

export default async function DistrictNewsPage({
  params,
}: PageProps<"/[locale]/news/d/[lgd]">) {
  const { locale, lgd } = await params;
  setRequestLocale(locale);
  const district = await getDistrictByLgd(lgd);
  if (!district) notFound();

  const lang = locale === "ta" ? ("ta" as const) : ("en" as const);
  const [t, td, tc, format, strings, clusters, items] = await Promise.all([
    getTranslations("news"),
    getTranslations("district"),
    getTranslations("common"),
    getFormatter(),
    buildNewsStrings(),
    getNewsClusters(district.id),
    getUnclusteredItems(lang, district.id),
  ]);
  const districtName = locale === "ta" ? district.name_ta : district.name_en;
  const isEmpty = clusters.length === 0 && items.length === 0;

  // Empty district feeds fall back to the statewide feed (M7 exit criteria).
  const [fallbackClusters, fallbackItems] = isEmpty
    ? await Promise.all([getNewsClusters(), getUnclusteredItems(lang)])
    : [[], []];

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href="/">{tc("nav.home")}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href="/news">{tc("nav.news")}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{districtName}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <h1 className="mt-6 font-heading text-3xl font-bold">
        {t("districtTitle", { district: districtName })}
      </h1>
      <p className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <Link
          href="/news"
          className="text-primary underline-offset-4 hover:underline"
        >
          ← {t("backToAll")}
        </Link>
        <Link
          href={`/d/${lgd}`}
          className="text-primary underline-offset-4 hover:underline"
        >
          {td("metaTitle", { district: districtName })} →
        </Link>
      </p>

      {isEmpty ? (
        <>
          <p className="mt-8 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-muted-foreground">
            {t("emptyDistrict")}
          </p>
          <NewsFeed
            clusters={fallbackClusters}
            items={fallbackItems}
            locale={locale}
            format={format}
            strings={strings}
          />
        </>
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
