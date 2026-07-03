import type { Metadata } from "next";
import { getFormatter, getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ProvenanceChip,
  type ProvenanceEntry,
} from "@/components/provenance-chip";
import { resolveLocation, type ResolvedLocality } from "@/lib/queries";
import { sql } from "@/lib/db";

// Coordinates are per-user: always resolved at request time, never cached.
export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/locate">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "locate" });
  // Coordinate URLs are unbounded — keep them out of search indexes.
  return { title: t("title"), robots: { index: false } };
}

function parseCoord(value: unknown, min: number, max: number): number | null {
  if (typeof value !== "string") return null;
  const n = Number(value);
  if (!Number.isFinite(n) || n < min || n > max) return null;
  return n;
}

async function boundarySource() {
  const rows = await sql<
    { name: string; url: string | null; publisher: string; license: string | null; retrieved_at: Date }[]
  >`
    SELECT s.name, s.url, s.publisher, s.license, MAX(f.retrieved_at) AS retrieved_at
    FROM facts f
    JOIN sources s ON s.id = f.source_id
    JOIN localities l ON l.id = f.subject_id AND f.subject_type = 'locality'
    WHERE f.key = 'geometry' AND l.level = 'ac'
    GROUP BY s.id, s.name, s.url, s.publisher, s.license
    LIMIT 1
  `;
  return rows[0] ?? null;
}

export default async function LocatePage({
  params,
  searchParams,
}: PageProps<"/[locale]/locate">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, tc, tp, format] = await Promise.all([
    getTranslations("locate"),
    getTranslations("constituency"),
    getTranslations("provenance"),
    getFormatter(),
  ]);

  const sp = await searchParams;
  const lat = parseCoord(sp.lat, -90, 90);
  const lon = parseCoord(sp.lon, -180, 180);
  const isTa = locale === "ta";

  let resolved: ResolvedLocality[] = [];
  if (lat !== null && lon !== null) {
    resolved = await resolveLocation(lon, lat);
  }
  const ac = resolved.find((r) => r.level === "ac");
  const pc = resolved.find((r) => r.level === "pc");
  const district = resolved.find((r) => r.level === "district");

  const source = ac ? await boundarySource() : null;
  const provenance: ProvenanceEntry[] = source
    ? [
        {
          title: t("provenanceTitle"),
          sourceName: source.name,
          url: source.url,
          publisher: source.publisher,
          license: source.license,
          retrievedOn: format.dateTime(source.retrieved_at, { dateStyle: "long" }),
          method: tp("methods.bulk"),
        },
      ]
    : [];

  const name = (r: ResolvedLocality) => (isTa ? r.name_ta : r.name_en);

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>

      {ac ? (
        <section aria-labelledby="result-title" className="mt-6">
          <div className="flex flex-wrap items-center gap-3">
            <h2 id="result-title" className="font-heading text-xl font-bold">
              {t("resultTitle")}
            </h2>
            {provenance.length > 0 ? (
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
            ) : null}
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Card className="border-t-4 border-t-primary shadow-none">
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {tc("types.ac")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Link
                  href={`/constituencies/ac/${ac.eci_code}`}
                  className="font-heading text-2xl font-bold text-primary underline-offset-4 hover:underline"
                >
                  {name(ac)}
                </Link>
                {district ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    {tc("district")}: {name(district)}
                  </p>
                ) : null}
              </CardContent>
            </Card>
            {pc ? (
              <Card className="border-t-4 border-t-primary/50 shadow-none">
                <CardHeader>
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {tc("types.pc")}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Link
                    href={`/constituencies/pc/${pc.eci_code}`}
                    className="font-heading text-2xl font-bold text-primary underline-offset-4 hover:underline"
                  >
                    {name(pc)}
                  </Link>
                </CardContent>
              </Card>
            ) : null}
          </div>

          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            {t("accuracyNote")}
          </p>
        </section>
      ) : lat !== null && lon !== null ? (
        <p className="mt-6 max-w-xl rounded-md border border-border bg-secondary/50 p-5 text-sm leading-relaxed text-muted-foreground">
          {t("outside")}
        </p>
      ) : (
        <p className="mt-4 max-w-2xl text-muted-foreground">{t("intro")}</p>
      )}

      <p className="mt-6 text-sm text-muted-foreground">{t("privacyNote")}</p>

      {/* Manual fallback: always present, works without JavaScript. */}
      <section aria-labelledby="picker-title" className="mt-10">
        <h2 id="picker-title" className="font-heading text-xl font-bold">
          {t("pickerTitle")}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("pickerHint")}</p>
        <form
          method="get"
          action={`/${locale}/constituencies`}
          role="search"
          className="mt-4 max-w-md"
        >
          <label htmlFor="locate-q" className="sr-only">
            {t("pickerTitle")}
          </label>
          <Input
            id="locate-q"
            name="q"
            type="search"
            placeholder={t("pickerPlaceholder")}
            className="bg-card"
          />
        </form>
      </section>
    </div>
  );
}
