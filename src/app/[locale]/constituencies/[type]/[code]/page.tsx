import type { Metadata } from "next";
import { rankNewsItems } from "@/lib/civic-rank";
import { formatInrCompact, type InrDisplay } from "@/lib/inr";
import { cache } from "react";
import { notFound } from "next/navigation";
import { getFormatter, getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { FollowToggle } from "@/components/follow-toggle";
import { PlaceToggle } from "@/components/place-toggle";
import { buildNewsStrings } from "@/components/news-feed";
import { ClusterStoryCard, ItemStoryCard } from "@/components/story-card";
import {
  ProvenanceChip,
  type ProvenanceEntry,
} from "@/components/provenance-chip";
import { KnowledgeMap, type KnowledgeItem } from "@/components/knowledge-map";
import {
  getAssemblySegments,
  getConstituency,
  getLocalityFacts,
  getNewsClusters,
  getPersonFacts,
  getPersonNewsItems,
  getRepresentatives,
  getUnclusteredItems,
  type ConstituencyLevel,
} from "@/lib/queries";

export const revalidate = 3600;

const load = cache(async (level: ConstituencyLevel, code: string) => {
  return getConstituency(level, code);
});

function parseRouteParams(type: string, code: string) {
  if (type !== "ac" && type !== "pc") return null;
  if (!/^\d{1,3}$/.test(code)) return null;
  return { level: type as ConstituencyLevel, code };
}

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/constituencies/[type]/[code]">): Promise<Metadata> {
  const { locale, type, code } = await params;
  const route = parseRouteParams(type, code);
  if (!route) return {};
  const c = await load(route.level, route.code);
  if (!c) return {};
  const t = await getTranslations({ locale, namespace: "constituency" });
  const name = locale === "ta" ? c.name_ta : c.name_en;
  return {
    title: `${name} — ${t(`types.${c.level}`)}`,
    description: `${c.name_ta} · ${c.name_en} · ${t("numberLabel", { number: c.eci_code })}`,
  };
}

export default async function ConstituencyPage({
  params,
}: PageProps<"/[locale]/constituencies/[type]/[code]">) {
  const { locale, type, code } = await params;
  setRequestLocale(locale);
  const route = parseRouteParams(type, code);
  if (!route) notFound();

  const c = await load(route.level, route.code);
  if (!c) notFound();

  const [t, tp, tn, tk, tr, format, facts, segments, representatives] =
    await Promise.all([
      getTranslations("constituency"),
      getTranslations("provenance"),
      getTranslations("news"),
      getTranslations("knowledgeMap"),
      getTranslations("rightToKnow"),
      getFormatter(),
      getLocalityFacts(c.id),
      c.level === "pc" ? getAssemblySegments(c.id) : Promise.resolve([]),
      getRepresentatives(c.id),
    ]);
  const rep = representatives[0] ?? null;
  // News woven into the page (M7.5, D-023): the district's stories plus
  // stories that mention this seat's representatives by name.
  const newsLang = locale === "ta" ? ("ta" as const) : ("en" as const);
  const [repFacts, newsClusters, districtItems, personItems, newsStrings] =
    await Promise.all([
      rep ? getPersonFacts(rep.person_id) : Promise.resolve([]),
      c.district_id ? getNewsClusters(c.district_id, 2) : Promise.resolve([]),
      c.district_id
        ? getUnclusteredItems(newsLang, c.district_id, 8, 7, "any").then((r) => rankNewsItems(r).slice(0, 4))
        : Promise.resolve([]),
      getPersonNewsItems(
        representatives.map((r) => r.person_id),
        4,
      ),
      buildNewsStrings(),
    ]);
  const districtItemIds = new Set(districtItems.map((i) => i.id));
  const extraPersonItems = personItems.filter((i) => !districtItemIds.has(i.id));
  const hasNews =
    newsClusters.length + districtItems.length + extraPersonItems.length > 0;

  // Self-declared affidavit facts (M4/M5.5). Keys mirror the importer.
  const affidavitFacts = {
    assets: repFacts.find((f) => f.key === "declared_assets"),
    liabilities: repFacts.find((f) => f.key === "declared_liabilities"),
    cases: repFacts.find((f) => f.key === "criminal_cases"),
    education: repFacts.find((f) => f.key === "education"),
    age: repFacts.find((f) => f.key === "age"),
    profession: repFacts.find((f) => f.key === "profession"),
  };
  const contactFacts = repFacts.filter((f) => f.key === "contact");
  const hasAffidavit = Boolean(affidavitFacts.assets);

  const EDUCATION_KEYS: Record<string, string> = {
    Illiterate: "illiterate",
    Literate: "literate",
    "5th Pass": "pass5",
    "8th Pass": "pass8",
    "10th Pass": "pass10",
    "12th Pass": "pass12",
    Graduate: "graduate",
    "Graduate Professional": "graduateProfessional",
    "Post Graduate": "postGraduate",
    Doctorate: "doctorate",
    Others: "others",
  };

  interface StatusNote {
    note_en: string;
    note_ta: string;
    as_of: string;
  }
  const statusNoteFact = facts.find((f) => f.key === "status_note");
  const statusNote = statusNoteFact?.value as StatusNote | undefined;

  interface VacancyFact {
    reason: string;
    vacated_on: string;
    previous_member_en: string;
    previous_member_ta: string | null;
    by_election: string;
  }
  const vacancyFact = facts.find((f) => f.key === "vacancy");
  const vacancy = vacancyFact?.value as VacancyFact | undefined;

  interface ElectionResult {
    election: string;
    provisional?: boolean;
    votes: number;
    vote_pct?: number | null;
    margin?: number | null;
    runner_up_en?: string | null;
    runner_up_ta?: string | null;
    total_votes?: number | null;
    candidates?: number | null;
  }
  const electionResult = facts.find((f) => f.key === "election_result")?.value as
    | ElectionResult
    | undefined;

  const isTa = locale === "ta";
  const primaryName = isTa ? c.name_ta : c.name_en;
  const secondaryName = isTa ? c.name_en : c.name_ta;
  const districtName = isTa ? c.district_ta : c.district_en;
  const parentName = isTa ? c.parent_name_ta : c.parent_name_en;

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

  // The knowledge map (D-035): every journey a voter can take from this
  // page, named by the question it answers. Order: nearest first.
  const knowledgeItems: KnowledgeItem[] = [
    ...(c.district_lgd
      ? [
          {
            href: `/${locale}/d/${c.district_lgd}`,
            canonical: `/d/${c.district_lgd}`,
            label: tk("items.districtData.label", {
              district: districtName ?? "",
            }),
            answers: tk("items.districtData.answers"),
          },
          {
            href: `/${locale}/news/d/${c.district_lgd}`,
            canonical: `/news/d/${c.district_lgd}`,
            label: tk("items.districtNews.label", {
              district: districtName ?? "",
            }),
            answers: tk("items.districtNews.answers"),
          },
        ]
      : []),
    ...(c.level === "ac" && parentName && c.parent_eci_code
      ? [
          {
            href: `/${locale}/constituencies/pc/${c.parent_eci_code}`,
            canonical: `/constituencies/pc/${c.parent_eci_code}`,
            label: tk("items.pc.label", { name: parentName }),
            answers: tk("items.pc.answers"),
          },
        ]
      : []),
    {
      href: `/${locale}/government`,
      canonical: "/government",
      label: tk("items.government.label"),
      answers: tk("items.government.answers"),
    },
    {
      href: `/${locale}/vacancies`,
      canonical: "/vacancies",
      label: tk("items.vacancies.label"),
      answers: tk("items.vacancies.answers"),
    },
    {
      href: `/${locale}/methodology`,
      canonical: "/methodology",
      label: tk("items.methodology.label"),
      answers: tk("items.methodology.answers"),
    },
    {
      href: `/${locale}/right-to-know`,
      canonical: "/right-to-know",
      label: tk("items.rightToKnow.label"),
      answers: tk("items.rightToKnow.answers"),
    },
  ];

  const provenance: ProvenanceEntry[] = [
    {
      title: tp("entries.record"),
      sourceName: c.source_name,
      url: c.source_url,
      publisher: c.source_publisher,
      license: c.source_license,
      retrievedOn: formatDate(c.retrieved_at),
      method: methodLabel(c.source_access_mode),
    },
    ...facts
      .filter((f) => f.key === "name_ta")
      .map((f) => ({
        title: tp("entries.nameTa"),
        sourceName: f.source_name,
        url: f.source_url,
        publisher: f.source_publisher,
        license: f.source_license,
        retrievedOn: formatDate(f.retrieved_at),
        method: methodLabel(f.extraction_method),
      })),
    ...facts
      .filter((f) => f.key === "reservation")
      .map((f) => ({
        title: tp("entries.reservation"),
        sourceName: f.source_name,
        url: f.source_url,
        publisher: f.source_publisher,
        license: f.source_license,
        retrievedOn: formatDate(f.retrieved_at),
        method: methodLabel(f.extraction_method),
      })),
  ];

  const reservation = facts.find((f) => f.key === "reservation")?.value as
    | { status?: string }
    | undefined;
  const reservedStatus =
    reservation?.status && reservation.status !== "GEN" ? reservation.status : null;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href="/">{t("breadcrumb.home")}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href="/constituencies">{t("breadcrumb.constituencies")}</Link>
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
            fieldLabels={{
              publisher: tp("publisher"),
              retrievedOn: tp("retrievedOn"),
              method: tp("method"),
              license: tp("license"),
              viewSource: tp("viewSource"),
            }}
            entries={provenance}
          />
        </div>
        <p className="mt-1 text-lg text-muted-foreground" lang={isTa ? "en" : "ta"}>
          {secondaryName}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{t(`types.${c.level}`)}</Badge>
          <Badge variant="outline">{t("numberLabel", { number: c.eci_code })}</Badge>
          {reservedStatus ? (
            <Badge variant="outline">{t("reserved", { status: reservedStatus })}</Badge>
          ) : null}
        </div>
        {/* My-places toggle (M7.5, D-023): the home feed starts here. */}
        <div className="mt-4">
          <PlaceToggle
            level={c.level}
            code={c.eci_code}
            labels={{
              add: t("addPlace"),
              remove: t("removePlace"),
              full: t("placesFull"),
            }}
          />
        </div>
      </header>

      <dl className="mt-8 grid gap-4 sm:grid-cols-2">
        {districtName ? (
          <div className="rounded-lg border border-border bg-card p-4">
            <dt className="text-sm text-muted-foreground">{t("district")}</dt>
            <dd className="mt-1 font-medium">
              {c.district_lgd ? (
                <Link
                  href={`/d/${c.district_lgd}`}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  {districtName}
                </Link>
              ) : (
                districtName
              )}
            </dd>
            {c.district_lgd ? (
              <dd className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm">
                {/* The bridge from the civic spine to the district data:
                    both destinations spelled out, neither hidden behind
                    a bare name link. */}
                <Link
                  href={`/d/${c.district_lgd}`}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  {t("districtIndicatorsLink")} →
                </Link>
                <Link
                  href={`/news/d/${c.district_lgd}`}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  {tn("districtLink", { district: districtName })} →
                </Link>
              </dd>
            ) : null}
          </div>
        ) : null}
        {c.level === "ac" && parentName && c.parent_eci_code ? (
          <div className="rounded-lg border border-border bg-card p-4">
            <dt className="text-sm text-muted-foreground">{t("partOfPc")}</dt>
            <dd className="mt-1">
              <Link
                href={`/constituencies/pc/${c.parent_eci_code}`}
                className="font-medium text-primary underline-offset-4 hover:underline"
              >
                {parentName}
              </Link>
            </dd>
          </div>
        ) : null}
      </dl>

      {c.level === "pc" && segments.length > 0 ? (
        <section aria-labelledby="segments-title" className="mt-10">
          <h2 id="segments-title" className="font-heading text-xl font-bold">
            {t("assemblySegments")}
          </h2>
          <ul className="mt-3 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
            {segments.map((seg) => (
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

      <section aria-labelledby="reps-title" className="mt-10">
        <h2 id="reps-title" className="font-heading text-xl font-bold">
          {t("representatives.title")}
        </h2>
        {rep ? (
          <div className="mt-4 max-w-2xl rounded-lg border border-border bg-card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm text-muted-foreground">
                  {t(`representatives.offices.${rep.office_type}`)}
                </p>
                {/* No sourced Tamil rendering yet (D-014): show the sourced
                    English name with an honest pending note — never a
                    transliteration. */}
                <p
                  className="mt-1 font-heading text-2xl font-bold"
                  lang={isTa && !rep.name_ta ? "en" : undefined}
                >
                  {isTa ? (rep.name_ta ?? rep.name_en) : rep.name_en}
                </p>
                {rep.name_ta ? (
                  <p className="text-sm text-muted-foreground" lang={isTa ? "en" : "ta"}>
                    {isTa ? rep.name_en : rep.name_ta}
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {t("representatives.nameTaPending")}
                  </p>
                )}
                <div className="mt-2.5">
                  <FollowToggle
                    personId={rep.person_id}
                    labels={{
                      follow: t("follow"),
                      following: t("following"),
                    }}
                  />
                </div>
              </div>
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
                entries={[
                  {
                    title: t("representatives.title"),
                    sourceName: rep.source_name,
                    url: rep.source_url,
                    publisher: rep.source_publisher,
                    license: rep.source_license,
                    retrievedOn: formatDate(rep.retrieved_at),
                    method: methodLabel("scrape"),
                  },
                  ...repFacts
                    .filter((f) => f.key === "name_ta")
                    .map((f) => ({
                      title: tp("entries.nameTa"),
                      sourceName: f.source_name,
                      url: f.source_url,
                      publisher: f.source_publisher,
                      license: f.source_license,
                      retrievedOn: formatDate(f.retrieved_at),
                      method: methodLabel(f.extraction_method),
                    })),
                ]}
              />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {(isTa ? rep.party_ta : rep.party_en) ? (
                <Badge variant="secondary">
                  {isTa ? (rep.party_ta ?? rep.party_en) : rep.party_en}
                </Badge>
              ) : null}
              {rep.start_date ? (
                <span className="text-sm text-muted-foreground">
                  {t("representatives.electedOn", {
                    // Civil date, not a timestamp: parse at local midnight so
                    // the displayed day never shifts across timezones.
                    date: format.dateTime(new Date(`${rep.start_date}T00:00:00`), {
                      dateStyle: "long",
                    }),
                  })}
                </span>
              ) : null}
            </div>
            {/* Affidavit summary: ALWAYS framed as a self-declared filing
                (DESIGN.md pillar 2), never as verified fact. */}
            {hasAffidavit ? (
              <div className="mt-4 border-t border-border pt-4">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-heading text-base font-semibold">
                    {t("affidavit.title")}
                  </h3>
                  <Badge variant="outline">{t("affidavit.selfDeclaredBadge")}</Badge>
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
                    entries={[
                      {
                        title: t("affidavit.title"),
                        sourceName: affidavitFacts.assets!.source_name,
                        url: affidavitFacts.assets!.source_url,
                        publisher: affidavitFacts.assets!.source_publisher,
                        license: affidavitFacts.assets!.source_license,
                        retrievedOn: formatDate(affidavitFacts.assets!.retrieved_at),
                        method: methodLabel(affidavitFacts.assets!.extraction_method),
                      },
                    ]}
                  />
                </div>
                {(() => {
                  // Lakh/crore units with the exact figure kept beneath
                  // (owner directive; pillar 1).
                  const inr = (fact: typeof affidavitFacts.assets) => {
                    const v = fact?.value as { amount_inr?: number } | undefined;
                    return v?.amount_inr != null
                      ? formatInrCompact(v.amount_inr, locale)
                      : null;
                  };
                  const casesValue = (() => {
                    const v = affidavitFacts.cases?.value as
                      | { count?: number }
                      | undefined;
                    if (v?.count == null) return null;
                    return v.count === 0
                      ? t("affidavit.casesZero")
                      : format.number(v.count);
                  })();
                  const educationValue = (() => {
                    const v = affidavitFacts.education?.value as
                      | { category?: string }
                      | undefined;
                    if (!v?.category) return null;
                    const key = EDUCATION_KEYS[v.category];
                    return key
                      ? t(`affidavit.educationCategories.${key}`)
                      : v.category;
                  })();

                  const field = (key: string, value: string | null) =>
                    value == null ? null : (
                      <div key={key}>
                        <dt className="text-xs text-muted-foreground">
                          {t(`affidavit.${key}`)}
                        </dt>
                        <dd className="mt-0.5 text-sm font-medium tabular-nums">
                          {value}
                        </dd>
                      </div>
                    );

                  const moneyField = (key: string, value: InrDisplay | null) =>
                    value == null ? null : (
                      <div key={key}>
                        <dt className="text-xs text-muted-foreground">
                          {t(`affidavit.${key}`)}
                        </dt>
                        <dd className="mt-0.5 text-sm font-medium tabular-nums">
                          {value.primary}
                        </dd>
                        {value.exact ? (
                          <dd className="text-xs tabular-nums text-muted-foreground">
                            {value.exact}
                          </dd>
                        ) : null}
                      </div>
                    );

                  return (
                    <>
                      {/* Rational-citizen hierarchy (D-016): identity-adjacent
                          facts stay visible; sensitive facts (assets,
                          liabilities, cases) live one tap away under a
                          neutral label — de-emphasized, never buried.
                          Native <details>: works without JS. */}
                      <dl className="mt-3 grid grid-cols-2 gap-3">
                        {field(
                          "age",
                          (() => {
                            const v = affidavitFacts.age?.value as
                              | { years_at_nomination?: number }
                              | undefined;
                            return v?.years_at_nomination != null
                              ? format.number(v.years_at_nomination)
                              : null;
                          })(),
                        )}
                        {field("education", educationValue)}
                        {field(
                          "profession",
                          (() => {
                            const v = affidavitFacts.profession?.value as
                              | { profession?: string }
                              | undefined;
                            return v?.profession ?? null;
                          })(),
                        )}
                      </dl>
                      <details className="group mt-3">
                        <summary className="flex cursor-pointer list-none items-center gap-1 text-sm font-medium text-primary [&::-webkit-details-marker]:hidden">
                          <ChevronDown
                            className="size-4 transition-transform group-open:rotate-180"
                            aria-hidden="true"
                          />
                          {t("affidavit.moreInfo")}
                        </summary>
                        <dl className="mt-3 grid grid-cols-2 gap-3">
                          {moneyField("assets", inr(affidavitFacts.assets))}
                          {moneyField(
                            "liabilities",
                            inr(affidavitFacts.liabilities),
                          )}
                          {field("criminalCases", casesValue)}
                        </dl>
                      </details>
                    </>
                  );
                })()}
                <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                  {t("affidavit.framing")}
                </p>
              </div>
            ) : (
              <p className="mt-4 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
                {t("affidavit.pending")}
              </p>
            )}

            {/* Contact channels: officially published only, never personal
                numbers. Honest pending state until official directories
                are reachable (D-017 geo-block). */}
            <div className="mt-4 border-t border-border pt-4">
              <h3 className="font-heading text-base font-semibold">
                {t("contact.title")}
              </h3>
              {contactFacts.length > 0 ? (
                <dl className="mt-2 space-y-1">
                  {contactFacts.map((f, i) => {
                    const v = f.value as { label?: string; value?: string };
                    return v.value ? (
                      <div key={i} className="flex flex-wrap gap-2 text-sm">
                        {v.label ? (
                          <dt className="text-muted-foreground">{v.label}:</dt>
                        ) : null}
                        <dd className="font-medium">{v.value}</dd>
                      </div>
                    ) : null;
                  })}
                </dl>
              ) : (
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  {t("contact.pending")}{" "}
            <Link
              href="/right-to-know"
              className="text-primary underline-offset-4 hover:underline"
            >
              {tr("edgeLink")} →
            </Link>
                </p>
              )}
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                {t("contact.policy")}
              </p>
            </div>
          </div>
        ) : vacancy ? (
          <div className="mt-4 max-w-2xl rounded-lg border border-border bg-card p-5">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-heading text-lg font-semibold">
                {t("vacancy.title")}
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
                entries={[
                  {
                    title: t("vacancy.title"),
                    sourceName: vacancyFact!.source_name,
                    url: vacancyFact!.source_url,
                    publisher: vacancyFact!.source_publisher,
                    license: vacancyFact!.source_license,
                    retrievedOn: formatDate(vacancyFact!.retrieved_at),
                    method: methodLabel(vacancyFact!.extraction_method),
                  },
                ]}
              />
            </div>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              {t("vacancy.body", {
                member: isTa
                  ? (vacancy.previous_member_ta ?? vacancy.previous_member_en)
                  : vacancy.previous_member_en,
                date: format.dateTime(new Date(`${vacancy.vacated_on}T00:00:00`), {
                  dateStyle: "long",
                }),
              })}
            </p>
            <p className="mt-2 text-sm font-medium">{t("vacancy.byElection")}</p>
          </div>
        ) : (
          <p className="mt-3 max-w-xl rounded-md border border-dashed border-border bg-secondary/40 p-5 text-sm leading-relaxed text-muted-foreground">
            {t("representatives.emptyState")}
          </p>
        )}
        {/* Curated status note (D-016): civically important context such as
            a pending election petition, always cited. */}
        {statusNote ? (
          <div className="mt-4 flex max-w-2xl flex-wrap items-start gap-2 rounded-md border border-stale-foreground/30 bg-stale/60 p-4">
            <p className="min-w-0 flex-1 text-sm leading-relaxed text-stale-foreground">
              {isTa ? statusNote.note_ta : statusNote.note_en}
            </p>
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
              entries={[
                {
                  title: t("statusNote"),
                  sourceName: statusNoteFact!.source_name,
                  url: statusNoteFact!.source_url,
                  publisher: statusNoteFact!.source_publisher,
                  license: statusNoteFact!.source_license,
                  retrievedOn: formatDate(statusNoteFact!.retrieved_at),
                  method: methodLabel(statusNoteFact!.extraction_method),
                },
              ]}
            />
          </div>
        ) : null}
        {c.level === "ac" ? (
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            {t("representatives.wardEmpty")}{" "}
            <Link
              href="/right-to-know"
              className="text-primary underline-offset-4 hover:underline"
            >
              {tr("edgeLink")} →
            </Link>
          </p>
        ) : null}
      </section>

      {electionResult ? (
        <section aria-labelledby="result-title" className="mt-10">
          <div className="flex flex-wrap items-center gap-3">
            <h2 id="result-title" className="font-heading text-xl font-bold">
              {t("result.title")}
            </h2>
            <span className="text-sm text-muted-foreground">
              {electionResult.election.includes("2026")
                ? t("result.elections.assembly2026")
                : electionResult.election.includes("2024")
                  ? t("result.elections.ls2024")
                  : electionResult.election}
            </span>
          </div>
          <dl className="mt-4 grid max-w-2xl grid-cols-2 gap-4 sm:grid-cols-3">
            {[
              ["votes", format.number(electionResult.votes)],
              [
                "votePct",
                electionResult.vote_pct != null ? `${electionResult.vote_pct}%` : null,
              ],
              [
                "margin",
                electionResult.margin != null ? format.number(electionResult.margin) : null,
              ],
              [
                "runnerUp",
                isTa
                  ? (electionResult.runner_up_ta ?? electionResult.runner_up_en)
                  : electionResult.runner_up_en,
              ],
              [
                "totalVotes",
                electionResult.total_votes != null
                  ? format.number(electionResult.total_votes)
                  : null,
              ],
              [
                "candidates",
                electionResult.candidates != null
                  ? format.number(electionResult.candidates)
                  : null,
              ],
            ]
              .filter(([, v]) => v != null)
              .map(([key, value]) => (
                <div key={key as string} className="rounded-lg border border-border bg-card p-3">
                  <dt className="text-xs text-muted-foreground">
                    {t(`result.${key}`)}
                  </dt>
                  <dd className="mt-1 font-medium tabular-nums">{value}</dd>
                </div>
              ))}
          </dl>
          {/* The preliminary-figures note belongs to the vote counts, not to
              the representative: the outcome and government are settled. */}
          {electionResult.provisional ? (
            <p className="mt-3 max-w-2xl text-xs leading-relaxed text-muted-foreground">
              {t("result.figuresNote")}
            </p>
          ) : null}
        </section>
      ) : null}

      {hasNews ? (
        <section aria-labelledby="news-title" className="mt-10">
          <div className="flex items-baseline justify-between gap-2">
            <h2 id="news-title" className="font-heading text-xl font-bold">
              {t("inTheNews")}
            </h2>
            {c.district_lgd ? (
              <Link
                href={`/news/d/${c.district_lgd}`}
                className="text-sm font-semibold text-primary underline-offset-4 hover:underline"
              >
                {tn("moreNews")} →
              </Link>
            ) : null}
          </div>
          <div className="mt-4 max-w-2xl space-y-2.5">
            {newsClusters.map((cluster) => (
              <ClusterStoryCard
                key={`c${cluster.id}`}
                cluster={cluster}
                locale={locale}
                timeLabel={
                  cluster.event_time
                    ? format.relativeTime(new Date(cluster.event_time))
                    : null
                }
                s={newsStrings}
              />
            ))}
            {[...districtItems, ...extraPersonItems].slice(0, 5).map((item) => (
              <ItemStoryCard
                key={`i${item.id}`}
                item={item}
                locale={locale}
                timeLabel={
                  item.published_at
                    ? format.relativeTime(item.published_at)
                    : null
                }
                s={newsStrings}
              />
            ))}
          </div>
        </section>
      ) : null}

      <KnowledgeMap
        title={tk("title")}
        deviceNote={tk("deviceNote")}
        seenLabel={tk("seenLabel")}
        items={knowledgeItems}
      />

      <section aria-labelledby="about-title" className="mt-10">
        <h2 id="about-title" className="font-heading text-base font-semibold">
          {t("aboutData.title")}
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {t("aboutData.body")}
        </p>
      </section>
    </div>
  );
}
