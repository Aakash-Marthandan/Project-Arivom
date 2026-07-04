import type { Metadata } from "next";
import { getFormatter, getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import {
  ProvenanceChip,
  type ProvenanceEntry,
} from "@/components/provenance-chip";
import { getMonitorLastChecked, getVacantSeats } from "@/lib/queries";

export const revalidate = 3600;

interface VacancyValue {
  reason: string;
  vacated_on: string;
  previous_member_en: string;
  previous_member_ta: string | null;
  by_election: string;
  note?: string;
}

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/vacancies">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "vacancies" });
  return { title: t("title"), description: t("intro") };
}

export default async function VacanciesPage({
  params,
}: PageProps<"/[locale]/vacancies">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, tp, format, seats, lastChecked] = await Promise.all([
    getTranslations("vacancies"),
    getTranslations("provenance"),
    getFormatter(),
    getVacantSeats(),
    getMonitorLastChecked(),
  ]);
  const isTa = locale === "ta";

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

  const reasonLabel = (reason: string) => {
    const known = ["resigned", "deceased", "disqualified"];
    return known.includes(reason)
      ? t(`reasons.${reason as "resigned" | "deceased" | "disqualified"}`)
      : reason;
  };
  const byElectionLabel = (status: string) => {
    const known = ["awaiting_notification", "notified", "scheduled"];
    return known.includes(status)
      ? t(
          `byElectionStatus.${status as "awaiting_notification" | "notified" | "scheduled"}`,
        )
      : status;
  };

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        {seats.length > 0 ? (
          <Badge variant="secondary" className="text-sm">
            {t("count", { count: seats.length })}
          </Badge>
        ) : null}
        {lastChecked ? (
          <span>
            {t("lastChecked", {
              datetime: format.dateTime(lastChecked, {
                dateStyle: "medium",
                timeStyle: "short",
              }),
            })}
          </span>
        ) : null}
      </div>

      {seats.length === 0 ? (
        <p className="mt-10 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-muted-foreground">
          {t("quietState")}
        </p>
      ) : (
        <ul className="mt-8 space-y-4">
          {seats.map((seat) => {
            const v = seat.vacancy as VacancyValue;
            const provenance: ProvenanceEntry[] = [
              {
                title: t("table.reason"),
                sourceName: seat.source_name,
                url: seat.source_url,
                publisher: seat.source_publisher,
                license: seat.source_license,
                retrievedOn: format.dateTime(seat.retrieved_at, {
                  dateStyle: "long",
                }),
                method: methodLabel(seat.extraction_method),
              },
            ];
            return (
              <li
                key={seat.locality_id}
                className="rounded-lg border border-border bg-card p-5"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Link
                    href={`/constituencies/ac/${seat.eci_code}`}
                    className="font-heading text-xl font-bold text-primary underline-offset-4 hover:underline"
                  >
                    {isTa ? seat.name_ta : seat.name_en}
                  </Link>
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
                <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div>
                    <dt className="text-xs text-muted-foreground">
                      {t("table.previousMember")}
                    </dt>
                    <dd className="mt-0.5 text-sm font-medium">
                      {isTa
                        ? (v.previous_member_ta ?? v.previous_member_en)
                        : v.previous_member_en}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">
                      {t("table.vacatedOn")}
                    </dt>
                    <dd className="mt-0.5 text-sm font-medium tabular-nums">
                      {format.dateTime(new Date(`${v.vacated_on}T00:00:00`), {
                        dateStyle: "medium",
                      })}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">
                      {t("table.reason")}
                    </dt>
                    <dd className="mt-0.5 text-sm font-medium">
                      {reasonLabel(v.reason)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">
                      {t("table.byElection")}
                    </dt>
                    <dd className="mt-0.5">
                      <Badge
                        variant="outline"
                        className="h-auto whitespace-normal border-stale-foreground/40 bg-stale text-left text-stale-foreground"
                      >
                        {byElectionLabel(v.by_election)}
                      </Badge>
                    </dd>
                  </div>
                </dl>
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-8 max-w-2xl rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
        {t("methodNote")}
      </p>
    </div>
  );
}
