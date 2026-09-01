import type { Metadata } from "next";
import { getFormatter, getTranslations, setRequestLocale } from "next-intl/server";
import {
  ProvenanceChip,
  type ProvenanceEntry,
} from "@/components/provenance-chip";
import { getOutlets, type OutletOwnership } from "@/lib/queries";

export const revalidate = 3600;

/**
 * Who owns the news (D-042).
 *
 * The answer a reader wants from a "political lean" label — who is telling me
 * this, and what are their interests — delivered as sourced fact instead of a
 * score we would have to author. Every claim carries its provenance chip, and
 * an outlet we could not document says so plainly rather than looking checked.
 */

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/outlets">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "outlets" });
  return { title: t("title"), description: t("intro") };
}

const TYPE_KEYS = [
  "media_conglomerate", "private_equity", "individual", "government",
  "telecom", "corporation", "independent", "other",
] as const;

function typeLabel(
  value: string | null,
  t: Awaited<ReturnType<typeof getTranslations<"outlets">>>,
): string | null {
  const known = TYPE_KEYS.find((k) => k === value);
  return known ? t(`types.${known}`) : null;
}

export default async function OutletsPage({
  params,
}: PageProps<"/[locale]/outlets">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, format, outlets] = await Promise.all([
    getTranslations("outlets"),
    getFormatter(),
    getOutlets(),
  ]);
  const isTa = locale === "ta";

  // Concentration is the finding, so it leads. Computed from the same
  // owner_group facts the individual rows show, never a separate number.
  const groups = new Map<string, OutletOwnership[]>();
  for (const o of outlets) {
    if (!o.owner_group) continue;
    const list = groups.get(o.owner_group) ?? [];
    list.push(o);
    groups.set(o.owner_group, list);
  }
  const shared = [...groups.entries()]
    .filter(([, list]) => list.length > 1)
    .sort((a, b) => b[1].length - a[1].length);

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        {t("outletCount", { count: outlets.length })}
      </p>

      {shared.length > 0 ? (
        <section aria-labelledby="concentration-title" className="mt-8">
          <h2
            id="concentration-title"
            className="font-heading text-xl font-bold"
          >
            {t("concentrationTitle")}
          </h2>
          <p className="mt-2 leading-relaxed text-muted-foreground">
            {t("concentrationBody")}
          </p>
          <ul className="mt-4 space-y-2">
            {shared.map(([group, list]) => (
              <li
                key={group}
                className="flex flex-wrap items-baseline gap-x-2 rounded-md border border-border bg-secondary/40 px-3 py-2"
              >
                <span className="font-semibold">{group}</span>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {t("concentration", { count: list.length })}
                </span>
                <span className="w-full text-sm text-muted-foreground">
                  {list.map((o) => o.name).join(" · ")}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="outlets-title" className="mt-10">
        <h2 id="outlets-title" className="sr-only">
          {t("title")}
        </h2>
        <ul className="space-y-3">
          {outlets.map((o) => {
            const affiliation = isTa
              ? (o.affiliation_ta ?? o.affiliation_en)
              : o.affiliation_en;
            const provenance: ProvenanceEntry[] = o.source_name
              ? [
                  {
                    title: t("ownerLabel"),
                    sourceName: o.source_name,
                    url: o.source_url,
                    publisher: o.source_publisher ?? o.source_name,
                    license: null,
                    retrievedOn: o.retrieved_at
                      ? format.dateTime(o.retrieved_at, { dateStyle: "long" })
                      : "",
                    method: t("typeLabel"),
                  },
                ]
              : [];
            return (
              <li
                key={o.slug}
                className="rounded-xl border border-border bg-card p-4"
              >
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <h3 className="font-heading text-base font-bold">{o.name}</h3>
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {o.lang === "ta" ? "தமிழ்" : "English"}
                  </span>
                  {o.status !== "active" ? (
                    <span className="rounded-full bg-stale px-2 py-0.5 text-[11px] font-semibold text-stale-foreground">
                      {t("statusPending")}
                    </span>
                  ) : null}
                  {provenance.length > 0 ? (
                    <span className="ms-auto">
                      <ProvenanceChip
                        label={t("ownerLabel")}
                        heading={t("title")}
                        fieldLabels={{
                          publisher: t("groupLabel"),
                          retrievedOn: t("typeLabel"),
                          method: t("typeLabel"),
                          license: t("typeLabel"),
                          viewSource: t("visit"),
                        }}
                        entries={provenance}
                      />
                    </span>
                  ) : null}
                </div>

                {o.owner ? (
                  <dl className="mt-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
                    <dt className="text-muted-foreground">{t("ownerLabel")}</dt>
                    <dd className="font-medium">{o.owner}</dd>
                    {o.owner_group && o.owner_group !== o.owner ? (
                      <>
                        <dt className="text-muted-foreground">
                          {t("groupLabel")}
                        </dt>
                        <dd>
                          {o.owner_group}
                          {o.group_size > 1 ? (
                            <span className="ms-2 text-muted-foreground tabular-nums">
                              {t("concentration", { count: o.group_size })}
                            </span>
                          ) : null}
                        </dd>
                      </>
                    ) : null}
                    {typeLabel(o.ownership_type, t) ? (
                      <>
                        <dt className="text-muted-foreground">
                          {t("typeLabel")}
                        </dt>
                        <dd>{typeLabel(o.ownership_type, t)}</dd>
                      </>
                    ) : null}
                  </dl>
                ) : (
                  <p className="mt-2 text-sm text-muted-foreground">
                    <span className="font-medium">{t("unknown")}.</span>{" "}
                    {t("unknownBody")}
                  </p>
                )}

                {affiliation ? (
                  <div className="mt-3 rounded-md border border-accent bg-accent/40 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-accent-foreground">
                      {t("affiliationTitle")}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed">
                      {affiliation}
                    </p>
                    {o.affiliation_note ? (
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        {o.affiliation_note}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      </section>

      <section
        aria-labelledby="no-labels-title"
        className="mt-10 rounded-md border border-border bg-secondary/50 p-4"
      >
        <h2 id="no-labels-title" className="font-heading text-base font-bold">
          {t("noLabels")}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {t("noLabelsBody")}
        </p>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {t("taxonomyNote")}
        </p>
      </section>
    </div>
  );
}
