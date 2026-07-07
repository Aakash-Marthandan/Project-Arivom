import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getFormatter,
  getTranslations,
  setRequestLocale,
} from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { buildNewsStrings, NewsFeed } from "@/components/news-feed";
import {
  departmentList,
  departmentMatches,
  type StoredPortfolios,
} from "@/lib/departments";
import {
  getDepartmentTags,
  getMinisters,
  getNewsItemsByDepartmentTags,
} from "@/lib/queries";

export const revalidate = 600;

interface MinisterValue {
  position_ta: string;
  portfolios_ta: StoredPortfolios;
  portfolios_en: StoredPortfolios;
  is_chief_minister: boolean;
}

/** The department must be a real /government card name; anything else 404s. */
async function resolveDepartment(raw: string, isTa: boolean) {
  const dept = decodeURIComponent(raw);
  const ministers = await getMinisters();
  const holders = ministers.filter((m) => {
    const v = m.minister as MinisterValue;
    const portfolios = isTa
      ? v.portfolios_ta || v.portfolios_en
      : v.portfolios_en || v.portfolios_ta;
    return departmentList(portfolios).includes(dept);
  });
  return holders.length > 0 ? { dept, holders } : null;
}

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/government/news/[dept]">): Promise<Metadata> {
  const { locale, dept } = await params;
  const resolved = await resolveDepartment(dept, locale === "ta");
  if (!resolved) return {};
  const t = await getTranslations({ locale, namespace: "government" });
  return { title: t("deptNews.title", { department: resolved.dept }) };
}

export default async function DepartmentNewsPage({
  params,
}: PageProps<"/[locale]/government/news/[dept]">) {
  const { locale, dept } = await params;
  setRequestLocale(locale);
  const isTa = locale === "ta";
  const resolved = await resolveDepartment(dept, isTa);
  if (!resolved) notFound();

  const lang = isTa ? ("ta" as const) : ("en" as const);
  const [t, format, strings, allTags] = await Promise.all([
    getTranslations("government"),
    getFormatter(),
    buildNewsStrings(),
    getDepartmentTags(),
  ]);

  // Loose tag matching (D-019) against everything the extraction has
  // produced in either language; empty until cluster-news runs (M7 key).
  const matchedTags = allTags.filter((tag) =>
    departmentMatches(resolved.dept, tag),
  );
  const items = await getNewsItemsByDepartmentTags(matchedTags, lang);

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">
        {t("deptNews.title", { department: resolved.dept })}
      </h1>
      <p className="mt-2 text-sm">
        <Link
          href="/government"
          className="text-primary underline-offset-4 hover:underline"
        >
          ← {t("deptNews.back")}
        </Link>
      </p>
      <p className="mt-3 text-sm text-muted-foreground">
        {resolved.holders
          .map((m) => (isTa ? (m.name_ta ?? m.name_en) : m.name_en))
          .join(" · ")}
      </p>

      {items.length === 0 ? (
        <p className="mt-8 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-muted-foreground">
          {t("deptNews.empty")}
        </p>
      ) : (
        <NewsFeed
          clusters={[]}
          items={items}
          locale={locale}
          format={format}
          strings={strings}
        />
      )}

      <p className="mt-8 max-w-2xl rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
        {t("deptNews.note")}
      </p>
    </div>
  );
}
