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
import { Badge } from "@/components/ui/badge";
import {
  ProvenanceChip,
  type ProvenanceEntry,
} from "@/components/provenance-chip";
import { getDistrict, getDistrictAcs, getLocalityFacts } from "@/lib/queries";

export const revalidate = 3600;

// Series shapes mirror pipelines/arivom/import_udise.py (D-028).
type EnrollmentLevel =
  | "prePrimary"
  | "primary"
  | "upperPrimary"
  | "secondary"
  | "higherSecondary";

type EnrollmentPoint = {
  year: string;
  total: number;
  boys: number;
  girls: number;
} & Record<
  EnrollmentLevel | `${EnrollmentLevel}Boys` | `${EnrollmentLevel}Girls`,
  number
>;
interface SchoolsPoint {
  year: string;
  total: number;
}
interface TeachersPoint {
  year: string;
  total: number;
  female: number;
  male: number;
}
interface PtrPoint {
  year: string;
  primary: number | null;
  upperPrimary: number | null;
  secondary: number | null;
  higherSecondary: number | null;
}
interface InfraPoint {
  year: string;
  schools: number;
  functionalElectricity: number;
  functionalDrinkingWater: number;
  functionalGirlsToilet: number;
  functionalBoysToilet: number;
  library: number;
  playground: number;
  functionalComputers: number;
  internet: number;
  ramps: number;
  medicalCheckup: number;
}

const ENROLLMENT_LEVELS = [
  "prePrimary",
  "primary",
  "upperPrimary",
  "secondary",
  "higherSecondary",
] as const;

// Higher-secondary PTR is unpublished at district level (null across every
// district and year), so the table has no column for it.
const PTR_LEVELS = ["primary", "upperPrimary", "secondary"] as const;

// Mirrors pipelines/arivom/import_nfhs.py (D-030).
interface HealthFact {
  survey: string;
  period: string;
  indicators: Record<string, number>;
}

const HEALTH_GROUPS = {
  households: [
    "electricity",
    "improvedDrinkingWater",
    "improvedSanitation",
    "cleanFuel",
    "healthInsurance",
  ],
  births: ["institutionalBirth", "ancFourVisits"],
  nutrition: [
    "stunted",
    "wasted",
    "underweight",
    "anaemicChildren",
    "anaemicWomen",
  ],
} as const;

const FACILITIES = [
  "functionalElectricity",
  "functionalDrinkingWater",
  "functionalGirlsToilet",
  "functionalBoysToilet",
  "library",
  "playground",
  "functionalComputers",
  "internet",
  "ramps",
  "medicalCheckup",
] as const;

function series<T>(fact: { value: unknown } | undefined): T[] {
  const value = fact?.value as { series?: T[] } | undefined;
  return value?.series ?? [];
}

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/d/[lgd]">): Promise<Metadata> {
  const { locale, lgd } = await params;
  const [t, district] = await Promise.all([
    getTranslations({ locale, namespace: "district" }),
    getDistrict(lgd),
  ]);
  if (!district) return {};
  const name = locale === "ta" ? district.name_ta : district.name_en;
  return { title: t("metaTitle", { district: name }) };
}

export default async function DistrictPage({
  params,
}: PageProps<"/[locale]/d/[lgd]">) {
  const { locale, lgd } = await params;
  setRequestLocale(locale);
  const district = await getDistrict(lgd);
  if (!district) notFound();

  const [t, tp, tn, tc, format, facts, acs] = await Promise.all([
    getTranslations("district"),
    getTranslations("provenance"),
    getTranslations("news"),
    getTranslations("common"),
    getFormatter(),
    getLocalityFacts(district.id),
    getDistrictAcs(district.id),
  ]);

  const isTa = locale === "ta";
  const primaryName = isTa ? district.name_ta : district.name_en;
  const secondaryName = isTa ? district.name_en : district.name_ta;

  const formatDate = (d: Date) => format.dateTime(d, { dateStyle: "long" });
  const methodLabel = (m: string) =>
    (
      {
        api: tp("methods.api"),
        bulk: tp("methods.bulk"),
        scrape: tp("methods.scrape"),
        pdf: tp("methods.pdf"),
        parser: tp("methods.parser"),
        manual: tp("methods.manual"),
        llm_bulk: tp("methods.llm_bulk"),
      } as Record<string, string>
    )[m] ?? m;

  const educationFacts = facts.filter((f) => f.key.startsWith("education."));
  const enrollment = series<EnrollmentPoint>(
    educationFacts.find((f) => f.key === "education.enrollment"),
  );
  const schools = series<SchoolsPoint>(
    educationFacts.find((f) => f.key === "education.schools"),
  );
  const teachers = series<TeachersPoint>(
    educationFacts.find((f) => f.key === "education.teachers"),
  );
  const ptr = series<PtrPoint>(
    educationFacts.find((f) => f.key === "education.ptr"),
  );
  const infra = series<InfraPoint>(
    educationFacts.find((f) => f.key === "education.school_infrastructure"),
  );

  const latestEnrollment = enrollment.at(-1);
  const latestSchools = schools.at(-1);
  const latestTeachers = teachers.at(-1);
  const latestInfra = infra.at(-1);
  const hasEducation = Boolean(latestEnrollment);

  const recordProvenance: ProvenanceEntry[] = [
    {
      title: tp("entries.record"),
      sourceName: district.source_name,
      url: district.source_url,
      publisher: district.source_publisher,
      license: district.source_license,
      retrievedOn: formatDate(district.retrieved_at),
      method: methodLabel(district.source_access_mode),
    },
  ];
  const educationSource = educationFacts[0];
  const educationProvenance: ProvenanceEntry[] = educationSource
    ? [
        {
          title: tp("entries.education"),
          sourceName: educationSource.source_name,
          url: educationSource.source_url,
          publisher: educationSource.source_publisher,
          license: educationSource.source_license,
          retrievedOn: formatDate(educationSource.retrieved_at),
          method: methodLabel(educationSource.extraction_method),
        },
      ]
    : [];

  const healthFact = facts.find((f) => f.key === "health.nfhs5");
  const health = healthFact?.value as HealthFact | undefined;
  const healthProvenance: ProvenanceEntry[] = healthFact
    ? [
        {
          title: tp("entries.health"),
          sourceName: healthFact.source_name,
          url: healthFact.source_url,
          publisher: healthFact.source_publisher,
          license: healthFact.source_license,
          retrievedOn: formatDate(healthFact.retrieved_at),
          method: methodLabel(healthFact.extraction_method),
        },
      ]
    : [];

  const num = (n: number) => format.number(n);
  const pct = (count: number, total: number) =>
    format.number(total > 0 ? count / total : 0, {
      style: "percent",
      maximumFractionDigits: 1,
    });

  const chipLabels = {
    publisher: tp("publisher"),
    retrievedOn: tp("retrievedOn"),
    method: tp("method"),
    license: tp("license"),
    viewSource: tp("viewSource"),
  };

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
            <BreadcrumbPage>{primaryName}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <header className="mt-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-heading text-3xl font-bold sm:text-4xl">
            {primaryName}
          </h1>
          <ProvenanceChip
            label={tp("chipLabel")}
            heading={tp("title")}
            fieldLabels={chipLabels}
            entries={recordProvenance}
          />
        </div>
        <p className="mt-1 text-lg text-muted-foreground" lang={isTa ? "en" : "ta"}>
          {secondaryName}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{t("badge")}</Badge>
        </div>
        <p className="mt-4 text-sm">
          <Link
            href={`/news/d/${district.lgd_code}`}
            className="text-primary underline-offset-4 hover:underline"
          >
            {tn("districtLink", { district: primaryName })} →
          </Link>
        </p>
      </header>

      {/* One label over the whole indicators block (education + health). */}
      <p className="mt-10 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {t("education.sectionLabel")}
      </p>

      <section aria-labelledby="education-title" className="mt-1">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="education-title" className="font-heading text-xl font-bold">
            {t("education.title")}
          </h2>
          <Badge variant="outline">{t("education.selfReported")}</Badge>
          {educationProvenance.length > 0 ? (
            <ProvenanceChip
              label={tp("chipLabel")}
              heading={tp("title")}
              fieldLabels={chipLabels}
              entries={educationProvenance}
            />
          ) : null}
        </div>

        {!hasEducation ? (
          <p className="mt-4 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-muted-foreground">
            {t("education.unavailable")}
          </p>
        ) : (
          <>
            {/* Part 1 — the latest published year, all in one place. */}
            <h3 className="mt-5 font-heading text-lg font-bold">
              {t("education.snapshotTitle", { year: latestEnrollment!.year })}
            </h3>

            <dl className="mt-4 grid gap-4 sm:grid-cols-3">
              <div className="rounded-lg border border-border bg-card p-4">
                <dt className="text-sm text-muted-foreground">
                  {t("education.students")}
                </dt>
                <dd className="mt-1 font-heading text-2xl font-bold tabular-nums">
                  {num(latestEnrollment!.total)}
                </dd>
                <dd className="mt-1 text-sm text-muted-foreground">
                  {t("education.girlsBoys", {
                    girls: num(latestEnrollment!.girls),
                    boys: num(latestEnrollment!.boys),
                  })}
                </dd>
              </div>
              {latestSchools ? (
                <div className="rounded-lg border border-border bg-card p-4">
                  <dt className="text-sm text-muted-foreground">
                    {t("education.schools")}
                  </dt>
                  <dd className="mt-1 font-heading text-2xl font-bold tabular-nums">
                    {num(latestSchools.total)}
                  </dd>
                </div>
              ) : null}
              {latestTeachers ? (
                <div className="rounded-lg border border-border bg-card p-4">
                  <dt className="text-sm text-muted-foreground">
                    {t("education.teachers")}
                  </dt>
                  <dd className="mt-1 font-heading text-2xl font-bold tabular-nums">
                    {num(latestTeachers.total)}
                  </dd>
                  <dd className="mt-1 text-sm text-muted-foreground">
                    {t("education.womenTeachers", {
                      count: num(latestTeachers.female),
                    })}
                  </dd>
                </div>
              ) : null}
            </dl>

            <h4 className="mt-8 font-heading text-base font-bold">
              {t("education.byLevelTitle")}
            </h4>
            <div className="mt-3 overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full min-w-[26rem] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th scope="col" className="px-4 py-2 font-semibold">
                      {t("education.level")}
                    </th>
                    <th scope="col" className="px-4 py-2 text-right font-semibold">
                      {t("education.total")}
                    </th>
                    <th scope="col" className="px-4 py-2 text-right font-semibold">
                      {t("education.girls")}
                    </th>
                    <th scope="col" className="px-4 py-2 text-right font-semibold">
                      {t("education.boys")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {ENROLLMENT_LEVELS.map((level) => (
                    <tr key={level}>
                      <th scope="row" className="px-4 py-2 text-left font-medium">
                        {t(`education.levels.${level}`)}
                      </th>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {num(latestEnrollment![level])}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                        {num(latestEnrollment![`${level}Girls`])}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                        {num(latestEnrollment![`${level}Boys`])}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {latestInfra ? (
              <>
                <h4 className="mt-8 font-heading text-base font-bold">
                  {t("education.infraTitle")}
                </h4>
                <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                  {t("education.infraIntro", {
                    total: num(latestInfra.schools),
                  })}
                </p>
                <ul className="mt-3 grid gap-x-10 gap-y-3 md:grid-cols-2">
                  {FACILITIES.map((facility) => {
                    const count = latestInfra[facility];
                    const total = latestInfra.schools;
                    const share = total > 0 ? count / total : 0;
                    return (
                      <li key={facility} className="max-w-2xl">
                        <div className="flex items-baseline justify-between gap-4 text-sm">
                          <span>{t(`education.facilities.${facility}`)}</span>
                          <span className="shrink-0 tabular-nums text-muted-foreground">
                            {pct(count, total)} · {num(count)}
                          </span>
                        </div>
                        <div
                          className="mt-1 h-1.5 overflow-hidden rounded-full bg-secondary"
                          role="presentation"
                        >
                          <div
                            className="h-full rounded-full bg-primary/70"
                            style={{ width: `${Math.round(share * 1000) / 10}%` }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </>
            ) : null}

            {/* Part 2 — how the totals moved across published years. */}
            <h3 className="mt-10 font-heading text-lg font-bold">
              {t("education.changeTitle")}
            </h3>

            <h4 className="mt-4 font-heading text-base font-bold">
              {t("education.totalsTitle")}
            </h4>
            <div className="mt-3 overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full min-w-[26rem] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th scope="col" className="px-4 py-2 font-semibold">
                      {t("education.year")}
                    </th>
                    <th scope="col" className="px-4 py-2 text-right font-semibold">
                      {t("education.students")}
                    </th>
                    <th scope="col" className="px-4 py-2 text-right font-semibold">
                      {t("education.schools")}
                    </th>
                    <th scope="col" className="px-4 py-2 text-right font-semibold">
                      {t("education.teachers")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {enrollment.map((point) => {
                    const yearSchools = schools.find((s) => s.year === point.year);
                    const yearTeachers = teachers.find(
                      (s) => s.year === point.year,
                    );
                    return (
                      <tr key={point.year}>
                        <th scope="row" className="px-4 py-2 text-left font-medium">
                          {point.year}
                        </th>
                        <td className="px-4 py-2 text-right tabular-nums">
                          {num(point.total)}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">
                          {yearSchools ? num(yearSchools.total) : "—"}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">
                          {yearTeachers ? num(yearTeachers.total) : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {ptr.length > 0 ? (
              <>
                <h4 className="mt-8 font-heading text-base font-bold">
                  {t("education.ptrTitle")}
                </h4>
                <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                  {t("education.ptrNote")}
                </p>
                <div className="mt-3 overflow-x-auto rounded-lg border border-border bg-card">
                  <table className="w-full min-w-[26rem] text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th scope="col" className="px-4 py-2 font-semibold">
                          {t("education.year")}
                        </th>
                        {PTR_LEVELS.map((level) => (
                          <th
                            scope="col"
                            key={level}
                            className="px-4 py-2 text-right font-semibold"
                          >
                            {t(`education.levels.${level}`)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {ptr.map((point) => (
                        <tr key={point.year}>
                          <th scope="row" className="px-4 py-2 text-left font-medium">
                            {point.year}
                          </th>
                          {PTR_LEVELS.map((level) => (
                            <td
                              key={level}
                              className="px-4 py-2 text-right tabular-nums"
                            >
                              {point[level] != null ? num(point[level]) : "—"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}

            <p className="mt-8 max-w-2xl rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
              {t("education.sourceNote")}{" "}
              <Link
                href="/methodology"
                className="text-primary underline-offset-4 hover:underline"
              >
                {t("education.methodologyLink")}
              </Link>
            </p>
          </>
        )}
      </section>

      <section aria-labelledby="health-title" className="mt-10">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="health-title" className="font-heading text-xl font-bold">
            {t("health.title")}
          </h2>
          <Badge variant="outline">{t("health.badge")}</Badge>
          {healthProvenance.length > 0 ? (
            <ProvenanceChip
              label={tp("chipLabel")}
              heading={tp("title")}
              fieldLabels={chipLabels}
              entries={healthProvenance}
            />
          ) : null}
        </div>

        {!health ? (
          <p className="mt-4 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-muted-foreground">
            {t("health.unavailable")}
          </p>
        ) : (
          <>
            <p className="mt-2 text-sm text-muted-foreground">
              {t("health.surveyLine")}
            </p>
            {(Object.keys(HEALTH_GROUPS) as (keyof typeof HEALTH_GROUPS)[]).map(
              (group) => {
                // Coverage groups get progress bars (share of households /
                // births reached). Prevalence rows (nutrition, anaemia) get
                // plain figures: a filled bar would read as an achievement.
                const isPrevalence = group === "nutrition";
                return (
                  <div key={group}>
                    <h3 className="mt-6 font-heading text-base font-bold">
                      {t(`health.groups.${group}`)}
                    </h3>
                    {isPrevalence ? (
                      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                        {t("health.groupNotes.nutrition")}
                      </p>
                    ) : null}
                    <ul
                      className={
                        isPrevalence
                          ? "mt-3 max-w-2xl divide-y divide-border rounded-lg border border-border bg-card"
                          : "mt-3 space-y-3"
                      }
                    >
                      {HEALTH_GROUPS[group].map((key) => {
                        const value = health.indicators[key];
                        if (value == null) return null;
                        const pctLabel = format.number(value / 100, {
                          style: "percent",
                          maximumFractionDigits: 1,
                        });
                        return isPrevalence ? (
                          <li
                            key={key}
                            className="flex items-baseline justify-between gap-4 px-4 py-2.5 text-sm"
                          >
                            <span>{t(`health.indicators.${key}`)}</span>
                            <span className="shrink-0 tabular-nums">
                              {pctLabel}
                            </span>
                          </li>
                        ) : (
                          <li key={key} className="max-w-2xl">
                            <div className="flex items-baseline justify-between gap-4 text-sm">
                              <span>{t(`health.indicators.${key}`)}</span>
                              <span className="shrink-0 tabular-nums text-muted-foreground">
                                {pctLabel}
                              </span>
                            </div>
                            <div
                              className="mt-1 h-1.5 overflow-hidden rounded-full bg-secondary"
                              role="presentation"
                            >
                              <div
                                className="h-full rounded-full bg-primary/70"
                                style={{ width: `${value}%` }}
                              />
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              },
            )}
            <p className="mt-8 max-w-2xl rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
              {t("health.sourceNote")}{" "}
              <Link
                href="/methodology"
                className="text-primary underline-offset-4 hover:underline"
              >
                {t("health.methodologyLink")}
              </Link>
            </p>
          </>
        )}
      </section>

      {acs.length > 0 ? (
        <section aria-labelledby="acs-title" className="mt-10">
          <h2 id="acs-title" className="font-heading text-xl font-bold">
            {t("acsTitle")}
          </h2>
          <ul className="mt-3 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
            {acs.map((seg) => (
              <li key={seg.id}>
                <Link
                  href={`/constituencies/ac/${seg.eci_code}`}
                  className="flex items-baseline gap-3 rounded-md border border-transparent px-3 py-2 transition-colors hover:border-border hover:bg-card"
                >
                  <span className="w-8 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
                    {seg.eci_code}
                  </span>
                  <span className="truncate font-medium">
                    {isTa ? seg.name_ta : seg.name_en}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
