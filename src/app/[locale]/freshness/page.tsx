import type { Metadata } from "next";
import { getFormatter, getTranslations, setRequestLocale } from "next-intl/server";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getFreshness, getNewsPoolStats } from "@/lib/queries";
import type { FreshnessRow } from "@/lib/queries";

export const revalidate = 3600;

/** SLA per checking cadence (M10): late/stalled thresholds in hours.
 *  The exact numbers are printed on the page — no hidden judgment. */
const SLA: Record<
  NonNullable<FreshnessRow["cadence"]>,
  { late: number; stalled: number } | null
> = {
  "half-hourly": { late: 3, stalled: 24 },
  hourly: { late: 6, stalled: 24 },
  daily: { late: 48, stalled: 96 },
  monthly: { late: 45 * 24, stalled: 75 * 24 },
  manual: null,
};

type SlaStatus = "current" | "late" | "stalled" | "onDemand";

/** age_hours comes from the query's now() — clock reads stay out of render. */
function slaStatus(row: FreshnessRow): SlaStatus {
  const sla = row.cadence ? SLA[row.cadence] : null;
  if (!sla) return "onDemand";
  if (row.age_hours >= sla.stalled) return "stalled";
  if (row.age_hours >= sla.late) return "late";
  return "current";
}

const STATUS_DOT: Record<SlaStatus, string> = {
  current: "bg-emerald-600 dark:bg-emerald-500",
  late: "bg-amber-500 dark:bg-amber-400",
  stalled: "bg-red-600 dark:bg-red-500",
  onDemand: "bg-muted-foreground/40",
};

// Problems surface first: a reader checking "is anything broken?"
// should not scroll past thirty healthy rows to find out.
const STATUS_ORDER: Record<SlaStatus, number> = {
  stalled: 0,
  late: 1,
  current: 2,
  onDemand: 3,
};

type Translator = Awaited<ReturnType<typeof getTranslations<"freshness">>>;
type Formatter = Awaited<ReturnType<typeof getFormatter>>;

function SourceTable({
  rows,
  caption,
  t,
  format,
}: {
  rows: FreshnessRow[];
  caption: string;
  t: Translator;
  format: Formatter;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <Table className="min-w-[44rem]">
        <TableCaption className="sr-only">{caption}</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>{t("table.source")}</TableHead>
            <TableHead>{t("table.status")}</TableHead>
            <TableHead>{t("table.retrieved")}</TableHead>
            <TableHead className="text-right">{t("table.records")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const status = slaStatus(row);
            return (
              <TableRow key={row.source_name}>
                <TableCell className="w-2/5 max-w-xs whitespace-normal break-words">
                  {row.source_url ? (
                    <a
                      href={row.source_url}
                      rel="noopener noreferrer"
                      target="_blank"
                      className="font-medium text-primary underline-offset-4 hover:underline"
                    >
                      {row.source_name}
                    </a>
                  ) : (
                    <span className="font-medium">{row.source_name}</span>
                  )}
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {row.publisher}
                    {row.license ? ` · ${row.license}` : null}
                  </span>
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  <span className="inline-flex items-center gap-1.5 text-sm">
                    <span
                      aria-hidden
                      className={`h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[status]}`}
                    />
                    {t(`sla.${status}`)}
                  </span>
                  {row.cadence && row.cadence !== "manual" ? (
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {t(`cadence.${row.cadence}`)}
                    </span>
                  ) : null}
                </TableCell>
                <TableCell className="whitespace-nowrap tabular-nums">
                  {format.dateTime(row.last_retrieved, { dateStyle: "medium" })}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {format.number(row.record_count)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/freshness">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "freshness" });
  return { title: t("title"), description: t("intro") };
}

export default async function FreshnessPage({
  params,
}: PageProps<"/[locale]/freshness">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, format, rows, pool] = await Promise.all([
    getTranslations("freshness"),
    getFormatter(),
    getFreshness(),
    getNewsPoolStats(),
  ]);

  const sorted = [...rows].sort(
    (a, b) =>
      STATUS_ORDER[slaStatus(a)] - STATUS_ORDER[slaStatus(b)] ||
      a.source_name.localeCompare(b.source_name),
  );
  const scheduled = sorted.filter((r) => slaStatus(r) !== "onDemand");
  const onDemand = sorted.filter((r) => slaStatus(r) === "onDemand");

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>

      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        {t("sla.legend")}
      </p>
      <details className="group mt-2 max-w-2xl">
        <summary className="cursor-pointer list-none text-sm font-medium text-primary [&::-webkit-details-marker]:hidden">
          <span
            aria-hidden
            className="mr-1 inline-block transition-transform group-open:rotate-90"
          >
            ›
          </span>
          {t("sla.thresholds")}
        </summary>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {t("sla.thresholdsBody")}
        </p>
      </details>

      {rows.length === 0 ? (
        <p className="mt-10 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-sm text-muted-foreground">
          {t("emptyState")}
        </p>
      ) : (
        <>
          <SourceTable
            rows={scheduled}
            caption={t("table.caption")}
            t={t}
            format={format}
          />
          {/* On-demand sources rarely change; folded so the schedule-
              checked rows (the ones that can go stale) stay in view. */}
          <details className="group mt-4 rounded-lg border border-border bg-card">
            <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground [&::-webkit-details-marker]:hidden">
              <span
                aria-hidden
                className="mr-2 inline-block transition-transform group-open:rotate-90"
              >
                ›
              </span>
              {t("onDemandGroup", { count: onDemand.length })}
            </summary>
            <SourceTable
              rows={onDemand}
              caption={t("onDemandGroup", { count: onDemand.length })}
              t={t}
              format={format}
            />
          </details>
        </>
      )}

      {/* The story pool (D-025): stored vs excluded-by-classification. */}
      <section aria-labelledby="pool-title" className="mt-10">
        <h2 id="pool-title" className="font-heading text-xl font-bold">
          {t("pool.title")}
        </h2>
        <p className="mt-2 max-w-2xl leading-relaxed text-muted-foreground">
          {t("pool.body", {
            total: format.number(pool.total),
            soft: format.number(pool.soft),
            unclassified: format.number(pool.unclassified),
          })}
        </p>
      </section>

    </div>
  );
}
