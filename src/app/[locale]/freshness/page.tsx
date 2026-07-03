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
import { getFreshness } from "@/lib/queries";

export const revalidate = 3600;

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
  const [t, format, rows] = await Promise.all([
    getTranslations("freshness"),
    getFormatter(),
    getFreshness(),
  ]);

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>

      {rows.length === 0 ? (
        <p className="mt-10 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-sm text-muted-foreground">
          {t("emptyState")}
        </p>
      ) : (
        <div className="mt-8 overflow-x-auto rounded-lg border border-border bg-card">
          <Table>
            <TableCaption className="sr-only">{t("table.caption")}</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>{t("table.source")}</TableHead>
                <TableHead>{t("table.retrieved")}</TableHead>
                <TableHead className="text-right">{t("table.records")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.source_name}>
                  <TableCell className="max-w-xs">
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
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {format.dateTime(row.last_retrieved, { dateStyle: "medium" })}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {format.number(row.record_count)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <p className="mt-8 max-w-2xl rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
        {t("slaNote")}
      </p>
    </div>
  );
}
