import type { Metadata } from "next";
import {
  getFormatter,
  getTranslations,
  setRequestLocale,
} from "next-intl/server";
import { Badge } from "@/components/ui/badge";
import {
  ProvenanceChip,
  type ProvenanceEntry,
} from "@/components/provenance-chip";
import { getCorrections } from "@/lib/queries";

export const revalidate = 3600;

const DECISIONS_URL =
  "https://github.com/Aakash-Marthandan/Project-Arivom/blob/main/docs/DECISIONS.md";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/corrections">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "corrections" });
  return { title: t("title"), description: t("intro") };
}

export default async function CorrectionsPage({
  params,
}: PageProps<"/[locale]/corrections">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, tp, format, rows] = await Promise.all([
    getTranslations("corrections"),
    getTranslations("provenance"),
    getFormatter(),
    getCorrections(),
  ]);
  const isTa = locale === "ta";

  const chipLabels = {
    publisher: tp("publisher"),
    retrievedOn: tp("retrievedOn"),
    method: tp("method"),
    license: tp("license"),
    viewSource: tp("viewSource"),
  };

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>

      {rows.length === 0 ? (
        <p className="mt-10 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-muted-foreground">
          {t("empty")}
        </p>
      ) : (
        <ol className="mt-8 space-y-4">
          {rows.map((row) => {
            const provenance: ProvenanceEntry[] = [
              {
                title: t("entryLabel"),
                sourceName: row.source_name,
                url: row.source_url,
                publisher: row.source_publisher,
                license: row.source_license,
                retrievedOn: format.dateTime(row.retrieved_at, {
                  dateStyle: "long",
                }),
                method: tp("methods.manual"),
              },
            ];
            return (
              <li
                key={`${row.corrected_on}-${row.field}`}
                className="rounded-lg border border-border bg-card p-5"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="font-heading text-lg font-bold leading-snug">
                    {isTa ? row.subject_ta : row.subject_en}
                  </h2>
                  <span className="shrink-0 text-sm tabular-nums text-muted-foreground">
                    {/* Date-only value: local-midnight parse, no day shift. */}
                    {format.dateTime(new Date(`${row.corrected_on}T00:00:00`), {
                      dateStyle: "long",
                    })}
                  </span>
                </div>
                <p className="mt-1">
                  <Badge variant="secondary">{row.field}</Badge>
                </p>
                <dl className="mt-3 space-y-1.5 text-sm leading-relaxed">
                  <div className="flex gap-2">
                    <dt className="shrink-0 font-medium text-muted-foreground">
                      {t("before")}:
                    </dt>
                    <dd>{isTa ? row.old_value_ta : row.old_value_en}</dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="shrink-0 font-medium text-muted-foreground">
                      {t("after")}:
                    </dt>
                    <dd>{isTa ? row.new_value_ta : row.new_value_en}</dd>
                  </div>
                </dl>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  {isTa ? row.note_ta : row.note_en}
                </p>
                <p className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                  {row.reference ? (
                    <a
                      href={DECISIONS_URL}
                      rel="noopener noreferrer"
                      target="_blank"
                      className="text-primary underline-offset-4 hover:underline"
                    >
                      {t("recordLink")}: {row.reference}
                    </a>
                  ) : null}
                  <ProvenanceChip
                    label={tp("chipLabel")}
                    heading={tp("title")}
                    fieldLabels={chipLabels}
                    entries={provenance}
                  />
                </p>
              </li>
            );
          })}
        </ol>
      )}

      <p className="mt-8 max-w-2xl rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
        {t("note")}
      </p>
    </div>
  );
}
