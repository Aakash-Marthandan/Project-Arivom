import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Input } from "@/components/ui/input";
import {
  listConstituencies,
  searchPersons,
  searchStories,
  type ConstituencyListItem,
} from "@/lib/queries";
import type { Locale } from "@/i18n/routing";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/constituencies">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "constituencies" });
  return { title: t("title"), description: t("subtitle") };
}

function ConstituencyCard({
  item,
  locale,
}: {
  item: ConstituencyListItem;
  locale: Locale;
}) {
  const primary = locale === "ta" ? item.name_ta : item.name_en;
  const secondary = locale === "ta" ? item.name_en : item.name_ta;
  const district = locale === "ta" ? item.district_ta : item.district_en;

  return (
    <li>
      <Link
        href={`/constituencies/${item.level}/${item.eci_code}`}
        className="flex items-baseline gap-3 rounded-md border border-transparent px-3 py-2 transition-colors hover:border-border hover:bg-card"
      >
        <span className="w-8 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
          {item.eci_code}
        </span>
        <span className="min-w-0">
          <span className="block truncate font-medium">{primary}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {secondary}
            {district ? ` · ${district}` : null}
          </span>
        </span>
      </Link>
    </li>
  );
}

export default async function ConstituenciesPage({
  params,
  searchParams,
}: PageProps<"/[locale]/constituencies">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("constituencies");

  const { q } = (await searchParams) as { q?: string };
  const query = typeof q === "string" ? q.slice(0, 100) : undefined;
  const lang = locale === "ta" ? ("ta" as const) : ("en" as const);
  const [items, persons, stories] = await Promise.all([
    listConstituencies(query),
    query ? searchPersons(query) : Promise.resolve([]),
    query ? searchStories(query, lang) : Promise.resolve([]),
  ]);
  const acs = items.filter((item) => item.level === "ac");
  const pcs = items.filter((item) => item.level === "pc");

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-1 text-muted-foreground">{t("subtitle")}</p>

      {/* Server-rendered search: works with JavaScript disabled. */}
      <form method="get" role="search" className="mt-6 max-w-md">
        <label htmlFor="q" className="sr-only">
          {t("searchLabel")}
        </label>
        <Input
          id="q"
          name="q"
          type="search"
          defaultValue={query ?? ""}
          placeholder={t("searchPlaceholder")}
          className="bg-card"
        />
      </form>

      {items.length === 0 && !query ? (
        <p className="mt-12 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-sm text-muted-foreground">
          {t("emptyState")}
        </p>
      ) : null}

      {items.length === 0 && persons.length === 0 && stories.length === 0 && query ? (
        <p className="mt-12 text-sm text-muted-foreground">{t("noResults")}</p>
      ) : null}

      {persons.length > 0 ? (
        <section aria-labelledby="people-title" className="mt-10">
          <div className="flex items-baseline justify-between gap-4 border-b border-border pb-2">
            <h2 id="people-title" className="font-heading text-xl font-bold">
              {t("groupPeople")}
            </h2>
          </div>
          <ul className="mt-3 grid gap-x-6 sm:grid-cols-2">
            {persons.map((person) => (
              <li key={person.person_id}>
                <Link
                  href={`/constituencies/${person.seat_level}/${person.seat_code}`}
                  className="press flex flex-col rounded-md border border-transparent px-3 py-2 transition-colors hover:border-border hover:bg-card"
                >
                  <span className="truncate font-medium">
                    {locale === "ta"
                      ? (person.name_ta ?? person.name_en)
                      : person.name_en}
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    {locale === "ta" ? person.seat_ta : person.seat_en}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {stories.length > 0 ? (
        <section aria-labelledby="stories-title" className="mt-10">
          <div className="flex items-baseline justify-between gap-4 border-b border-border pb-2">
            <h2 id="stories-title" className="font-heading text-xl font-bold">
              {t("groupStories")}
            </h2>
          </div>
          <ul className="mt-3 space-y-1">
            {stories.map((story) =>
              story.kind === "cluster" ? (
                <li key={`c${story.id}`}>
                  <Link
                    href={`/news/s/${story.id}`}
                    className="press block rounded-md border border-transparent px-3 py-2 font-medium transition-colors hover:border-border hover:bg-card"
                  >
                    {story.title}
                  </Link>
                </li>
              ) : (
                <li key={`i${story.id}`}>
                  <a
                    href={story.url ?? "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    lang={story.lang}
                    className="press block rounded-md border border-transparent px-3 py-2 font-medium transition-colors hover:border-border hover:bg-card"
                  >
                    {story.title} ↗
                  </a>
                </li>
              ),
            )}
          </ul>
        </section>
      ) : null}

      {acs.length > 0 ? (
        <section aria-labelledby="acs-title" className="mt-10">
          <div className="flex items-baseline justify-between gap-4 border-b border-border pb-2">
            <h2 id="acs-title" className="font-heading text-xl font-bold">
              {t("assembly")}
            </h2>
            <span className="text-sm text-muted-foreground">
              {t("assemblyCount", { count: acs.length })}
            </span>
          </div>
          <ul className="mt-3 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
            {acs.map((item) => (
              <ConstituencyCard key={item.id} item={item} locale={locale as Locale} />
            ))}
          </ul>
        </section>
      ) : null}

      {pcs.length > 0 ? (
        <section aria-labelledby="pcs-title" className="mt-12">
          <div className="flex items-baseline justify-between gap-4 border-b border-border pb-2">
            <h2 id="pcs-title" className="font-heading text-xl font-bold">
              {t("parliamentary")}
            </h2>
            <span className="text-sm text-muted-foreground">
              {t("assemblyCount", { count: pcs.length })}
            </span>
          </div>
          <ul className="mt-3 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
            {pcs.map((item) => (
              <ConstituencyCard key={item.id} item={item} locale={locale as Locale} />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
