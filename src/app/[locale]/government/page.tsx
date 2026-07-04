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
  getMinisters,
  getVacantSeats,
  type Minister,
} from "@/lib/queries";

export const revalidate = 3600;

interface MinisterValue {
  position_ta: string;
  portfolios_ta: string;
  portfolios_en: string;
  is_chief_minister: boolean;
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
  const [t, tp, format, ministers, composition, vacantSeats] = await Promise.all([
    getTranslations("government"),
    getTranslations("provenance"),
    getFormatter(),
    getMinisters(),
    getAssemblyComposition(),
    getVacantSeats(),
  ]);
  const isTa = locale === "ta";

  const cm = ministers.find(
    (m) => (m.minister as MinisterValue).is_chief_minister,
  );
  const council = ministers.filter(
    (m) => !(m.minister as MinisterValue).is_chief_minister,
  );

  const provenanceFor = (m: Minister): ProvenanceEntry[] => [
    {
      title: t("ministers"),
      sourceName: m.source_name,
      url: m.source_url,
      publisher: m.source_publisher,
      license: m.source_license,
      retrievedOn: format.dateTime(m.retrieved_at, { dateStyle: "long" }),
      method: tp("methods.scrape"),
    },
  ];

  function ministerCard(m: Minister, big?: boolean) {
    const v = m.minister as MinisterValue;
    const portfolio = isTa
      ? v.portfolios_ta || v.portfolios_en
      : v.portfolios_en || v.portfolios_ta;
    return (
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p
              className={
                big
                  ? "font-heading text-2xl font-bold"
                  : "font-heading text-lg font-bold"
              }
            >
              {isTa ? (m.name_ta ?? m.name_en) : m.name_en}
            </p>
            {portfolio ? (
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {portfolio}
              </p>
            ) : null}
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
            entries={provenanceFor(m)}
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          {(isTa ? m.party_ta : m.party_en) ? (
            <Badge variant="secondary">
              {isTa ? (m.party_ta ?? m.party_en) : m.party_en}
            </Badge>
          ) : null}
          <span className="text-muted-foreground">{t("constituency")}:</span>
          <Link
            href={`/constituencies/ac/${m.seat_code}`}
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {isTa ? m.seat_ta : m.seat_en}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>

      {cm ? (
        <section aria-labelledby="cm-title" className="mt-8">
          <h2 id="cm-title" className="font-heading text-xl font-bold">
            {t("chiefMinister")}
          </h2>
          <div className="mt-3 max-w-2xl">{ministerCard(cm, true)}</div>
        </section>
      ) : null}

      {council.length > 0 ? (
        <section aria-labelledby="ministers-title" className="mt-10">
          <h2 id="ministers-title" className="font-heading text-xl font-bold">
            {t("ministers")}
          </h2>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {council.map((m) => (
              <div key={m.person_id}>{ministerCard(m)}</div>
            ))}
          </div>
        </section>
      ) : null}

      <section aria-labelledby="composition-title" className="mt-12">
        <h2 id="composition-title" className="font-heading text-xl font-bold">
          {t("composition")}
        </h2>
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
