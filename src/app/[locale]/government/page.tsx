import type { Metadata } from "next";
import { getFormatter, getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import {
  ProvenanceChip,
  type ProvenanceEntry,
} from "@/components/provenance-chip";
import {
  getAssemblyComposition,
  getCompositionSources,
  getMinisters,
  getVacantSeats,
  type Minister,
} from "@/lib/queries";
import {
  departmentEntries,
  type StoredPortfolios,
} from "@/lib/departments";
import { FilterList } from "@/components/filter-list";

export const revalidate = 3600;

interface MinisterValue {
  position_ta: string;
  portfolios_ta: StoredPortfolios;
  portfolios_en: StoredPortfolios;
  is_chief_minister: boolean;
}

/** One department card: the department (its identity from the source's
 *  link target, D-033), the allocation subjects under it when they
 *  differ, and the minister who holds it. */
interface DepartmentCard {
  department: string;
  subjects: string | null;
  positionKey: "cm" | "deputyCm" | "minister";
  minister: Minister;
}


function positionKeyOf(v: MinisterValue): DepartmentCard["positionKey"] {
  if (v.is_chief_minister) return "cm";
  if (/துணை\s*முதல்?வமைச்சர்|துணை\s*முதலமைச்சர்/.test(v.position_ta)) return "deputyCm";
  return "minister";
}

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/government">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "government" });
  return { title: t("title"), description: t("intro") };
}

export default async function GovernmentPage({
  params,
}: PageProps<"/[locale]/government">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, tp, format, ministers, composition, compositionSources, vacantSeats] =
    await Promise.all([
      getTranslations("government"),
      getTranslations("provenance"),
      getFormatter(),
      getMinisters(),
      getAssemblyComposition(),
      getCompositionSources(),
      getVacantSeats(),
    ]);
  const isTa = locale === "ta";

  const cm = ministers.find(
    (m) => (m.minister as MinisterValue).is_chief_minister,
  );

  // Department-first: one card per source-listed department entry,
  // sorted by department name in the reader's language.
  const entries: DepartmentCard[] = ministers.flatMap((m) => {
    const v = m.minister as MinisterValue;
    const portfolios = isTa
      ? v.portfolios_ta || v.portfolios_en
      : v.portfolios_en || v.portfolios_ta;
    return departmentEntries(portfolios).map((entry) => ({
      department: entry.name,
      subjects: entry.subjects,
      positionKey: positionKeyOf(v),
      minister: m,
    }));
  });
  entries.sort((a, b) =>
    a.department.localeCompare(b.department, isTa ? "ta" : "en"),
  );

  const provenanceFor = (m: Minister): ProvenanceEntry[] => [
    {
      title: t("departments"),
      sourceName: m.source_name,
      url: m.source_url,
      publisher: m.source_publisher,
      license: m.source_license,
      retrievedOn: format.dateTime(m.retrieved_at, { dateStyle: "long" }),
      method: tp("methods.scrape"),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>

      {/* Slim head-of-government line: identity without duplicating the
          department list below. */}
      {cm ? (
        <p className="mt-6 flex flex-wrap items-baseline gap-2 rounded-lg border border-border bg-card px-5 py-4">
          <span className="text-sm text-muted-foreground">
            {t("positions.cm")}:
          </span>
          <span className="font-heading text-xl font-bold">
            {isTa ? (cm.name_ta ?? cm.name_en) : cm.name_en}
          </span>
          <Link
            href={`/constituencies/ac/${cm.seat_code}`}
            className="text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            {isTa ? cm.seat_ta : cm.seat_en}
          </Link>
        </p>
      ) : null}

      <section aria-labelledby="departments-title" className="mt-10">
        <h2 id="departments-title" className="font-heading text-xl font-bold">
          {t("departments")}
        </h2>
        <div className="mt-3">
        <FilterList
          placeholder={t("filterPlaceholder")}
          emptyLabel={t("filterEmpty")}
        >
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {entries.map((entry, i) => {
            const m = entry.minister;
            return (
              <div
                key={`${entry.department}-${m.person_id}-${i}`}
                id={entry.department.replace(/\s+/g, "-")}
                data-filter={`${entry.department} ${entry.subjects ?? ""} ${m.name_en ?? ""} ${m.name_ta ?? ""}`.toLowerCase()}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-heading text-base font-semibold leading-snug">
                    {entry.department}
                  </h3>
                  <ProvenanceChip
                    label={tp("chipLabel")}
                    heading={tp("title")}
                    fieldLabels={{
                      publisher: tp("publisher"),
                      retrievedOn: tp("retrievedOn"),
                      method: tp("method"),
                      license: tp("license"),
                      viewSource: tp("viewSource"),
                    }}
                    entries={provenanceFor(m)}
                  />
                </div>
                {entry.subjects ? (
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    {entry.subjects}
                  </p>
                ) : null}
                <p className="mt-2 text-sm">
                  <span
                    className={
                      entry.positionKey === "cm"
                        ? "font-medium text-primary"
                        : "text-muted-foreground"
                    }
                  >
                    {t(`positions.${entry.positionKey}`)}
                  </span>
                  <span className="mx-1.5 text-muted-foreground">·</span>
                  <span className="font-medium">
                    {isTa ? (m.name_ta ?? m.name_en) : m.name_en}
                  </span>
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-2 text-sm">
                  {(isTa ? m.party_ta : m.party_en) ? (
                    <Badge variant="secondary">
                      {isTa ? (m.party_ta ?? m.party_en) : m.party_en}
                    </Badge>
                  ) : null}
                  <Link
                    href={`/constituencies/ac/${m.seat_code}`}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    {isTa ? m.seat_ta : m.seat_en}
                  </Link>
                </p>
                <p className="mt-2 text-sm">
                  <Link
                    href={`/government/news/${encodeURIComponent(entry.department)}`}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    {t("deptNewsLink")} →
                  </Link>
                </p>
              </div>
            );
          })}
        </div>
        </FilterList>
        </div>
        <p className="mt-3 max-w-2xl text-xs leading-relaxed text-muted-foreground">
          {t("departmentsNote")}
        </p>
      </section>

      <section aria-labelledby="composition-title" className="mt-12">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="composition-title" className="font-heading text-xl font-bold">
            {t("composition")}
          </h2>
          <ProvenanceChip
            label={tp("chipLabel")}
            heading={tp("title")}
            fieldLabels={{
              publisher: tp("publisher"),
              retrievedOn: tp("retrievedOn"),
              method: tp("method"),
              license: tp("license"),
              viewSource: tp("viewSource"),
            }}
            entries={compositionSources.map((src) => ({
              title: t("composition"),
              sourceName: src.source_name,
              url: src.source_url,
              publisher: src.source_publisher,
              license: src.source_license,
              retrievedOn: format.dateTime(src.retrieved_at, {
                dateStyle: "long",
              }),
              method: tp("methods.scrape"),
            }))}
          />
        </div>
        <ul className="mt-3 max-w-md space-y-1">
          {composition.map((row) => (
            <li
              key={row.party_en ?? "unknown"}
              className="flex items-baseline justify-between gap-4 rounded-md border border-border bg-card px-4 py-2"
            >
              <span className="font-medium">
                {isTa ? (row.party_ta ?? row.party_en) : row.party_en}
              </span>
              <span className="tabular-nums text-muted-foreground">
                {t("seats", { count: row.seats })}
              </span>
            </li>
          ))}
          {vacantSeats.length > 0 ? (
            <li className="flex items-baseline justify-between gap-4 rounded-md border border-dashed border-border px-4 py-2">
              <Link
                href="/vacancies"
                className="font-medium text-primary underline-offset-4 hover:underline"
              >
                {t("vacantSeats")}
              </Link>
              <span className="tabular-nums text-muted-foreground">
                {t("seats", { count: vacantSeats.length })}
              </span>
            </li>
          ) : null}
        </ul>
        <p className="mt-3 max-w-2xl text-xs leading-relaxed text-muted-foreground">
          {t("compositionNote")}
        </p>
      </section>

      <p className="mt-10 max-w-2xl rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
        {t("officialNote")}
      </p>
    </div>
  );
}
