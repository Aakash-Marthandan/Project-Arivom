import type { Metadata } from "next";
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
import { Badge } from "@/components/ui/badge";
import {
  ProvenanceChip,
  type ProvenanceEntry,
} from "@/components/provenance-chip";
import {
  getAssemblySegments,
  getConstituency,
  getLocalityFacts,
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

  const [t, tp, format, facts, segments] = await Promise.all([
    getTranslations("constituency"),
    getTranslations("provenance"),
    getFormatter(),
    getLocalityFacts(c.id),
    c.level === "pc" ? getAssemblySegments(c.id) : Promise.resolve([]),
  ]);

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
      </header>

      <dl className="mt-8 grid gap-4 sm:grid-cols-2">
        {districtName ? (
          <div className="rounded-lg border border-border bg-card p-4">
            <dt className="text-sm text-muted-foreground">{t("district")}</dt>
            <dd className="mt-1 font-medium">{districtName}</dd>
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
        {/* Honest empty state: representative data arrives in a later
            milestone; we never show placeholder people. */}
        <p className="mt-3 max-w-xl rounded-md border border-dashed border-border bg-secondary/40 p-5 text-sm leading-relaxed text-muted-foreground">
          {t("representatives.emptyState")}
        </p>
      </section>

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
