import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getFormatter,
  getTranslations,
  setRequestLocale,
} from "next-intl/server";
import { cache } from "react";
import { Link } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { SourceDots } from "@/components/coverage-dots";
import { buildNewsStrings } from "@/components/news-feed";
import {
  ProvenanceChip,
  type ProvenanceEntry,
} from "@/components/provenance-chip";
import { ShareButton } from "@/components/share-button";
import { StoryThumb } from "@/components/story-thumb";
import { clusterImage } from "@/components/story-card";
import { getNewsClusterById, getTrackedOutlets } from "@/lib/queries";

export const revalidate = 600;

/**
 * The dedicated story page (M7.5 polish, D-024), Ground-style: checked
 * bilingual summary, then "what each outlet covers" — neutral,
 * content-descriptive notes on how each outlet's reporting differs,
 * possible only because we read all tracked outlets at once. No ratings,
 * no bias labels, ever (pillar 2).
 */

const load = cache(getNewsClusterById);

function parseId(raw: string): number | null {
  return /^\d{1,12}$/.test(raw) ? Number(raw) : null;
}

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/news/s/[id]">): Promise<Metadata> {
  const { locale, id } = await params;
  const clusterId = parseId(id);
  const cluster = clusterId ? await load(clusterId) : null;
  // 404 here, before streaming starts, so the status code is honest even
  // with the loading boundary in place.
  if (!cluster) notFound();
  const title =
    (locale === "ta" ? cluster.title_ta : cluster.title_en) ??
    cluster.title_en ??
    cluster.members[0]?.headline;
  const summary =
    (locale === "ta" ? cluster.summary_ta : cluster.summary_en) ?? undefined;
  return { title: title ?? undefined, description: summary?.replace(/\[\d+\]/g, "") };
}

/** Render [n] markers as superscript links to the cited member items. */
function CitedText({
  text,
  cluster,
  className,
}: {
  text: string;
  cluster: NonNullable<Awaited<ReturnType<typeof getNewsClusterById>>>;
  className: string;
}) {
  const byId = new Map(cluster.members.map((m) => [m.id, m]));
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className={className}>
      {parts.map((part, i) => {
        const marker = /^\[(\d+)\]$/.exec(part);
        if (!marker) return <span key={i}>{part}</span>;
        const n = Number(marker[1]);
        const itemId = cluster.citations?.[n - 1];
        const member = itemId ? byId.get(itemId) : undefined;
        if (!member) return <sup key={i}>{part}</sup>;
        return (
          <a
            key={i}
            href={member.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline-offset-2 hover:underline"
          >
            <sup>[{n}]</sup>
          </a>
        );
      })}
    </p>
  );
}

export default async function StoryPage({
  params,
}: PageProps<"/[locale]/news/s/[id]">) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const clusterId = parseId(id);
  if (!clusterId) notFound();
  const cluster = await load(clusterId);
  if (!cluster) notFound();

  const [t, format, strings, trackedOutlets] = await Promise.all([
    getTranslations("news"),
    getFormatter(),
    buildNewsStrings(),
    getTrackedOutlets(),
  ]);
  const isTa = locale === "ta";

  const title =
    (isTa ? cluster.title_ta : cluster.title_en) ??
    cluster.title_en ??
    cluster.title_ta ??
    cluster.members[0]?.headline ??
    "";
  const summaryShort = isTa
    ? (cluster.summary_ta ?? cluster.summary_en)
    : (cluster.summary_en ?? cluster.summary_ta);
  const summaryLong = isTa
    ? (cluster.summary_long_ta ?? cluster.summary_long_en)
    : (cluster.summary_long_en ?? cluster.summary_long_ta);
  const summary = summaryLong ?? summaryShort;

  const covered = new Set(cluster.members.map((m) => m.outlet));
  const notCovered = trackedOutlets.filter((o) => !covered.has(o));
  const noteByItem = new Map(
    (cluster.coverage_notes ?? []).map((n) => [n.news_item_id, n]),
  );
  const image = clusterImage(cluster);

  const provenance: ProvenanceEntry[] = [
    {
      title: strings.provenance.summaryEntryTitle,
      sourceName: cluster.source_name,
      url: cluster.source_url,
      publisher: cluster.source_publisher,
      license: cluster.source_license,
      retrievedOn: format.dateTime(cluster.retrieved_at, { dateStyle: "long" }),
      method: strings.provenance.method,
    },
  ];

  return (
    <article
      className="mx-auto w-full max-w-2xl px-4 py-6"
      style={{ viewTransitionName: `story-${cluster.id}` }}
    >
      <p className="text-sm">
        <Link
          href="/news"
          className="font-semibold text-primary underline-offset-4 hover:underline"
        >
          ← {t("title")}
        </Link>
      </p>

      <header className="mt-4">
        <span className="inline-block rounded-full bg-accent px-2.5 py-0.5 text-[11px] font-extrabold uppercase tracking-wide text-accent-foreground">
          {strings.sourcesCount(covered.size)}
        </span>
        <h1 className="mt-2 font-heading text-2xl font-extrabold leading-snug sm:text-3xl">
          {title}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          {cluster.event_time ? (
            <time dateTime={new Date(cluster.event_time).toISOString()}>
              {format.dateTime(new Date(cluster.event_time), {
                dateStyle: "long",
              })}
            </time>
          ) : null}
          {cluster.district_en && cluster.district_lgd ? (
            <Link
              href={`/news/d/${cluster.district_lgd}`}
              className="text-primary underline-offset-4 hover:underline"
            >
              {isTa ? cluster.district_ta : cluster.district_en}
            </Link>
          ) : null}
          <span className="ms-auto flex items-center gap-2">
            <ShareButton
              title={title}
              labels={{ share: t("share"), copied: t("linkCopied") }}
            />
            <ProvenanceChip
              label={strings.provenance.chipLabel}
              heading={strings.provenance.title}
              fieldLabels={strings.provenance.fieldLabels}
              entries={provenance}
            />
          </span>
        </div>
      </header>

      {image ? (
        <StoryThumb
          src={image}
          className="mt-4 h-52 w-full rounded-xl sm:h-64"
        />
      ) : null}

      {cluster.discussion_locked ? (
        <div className="mt-4 rounded-xl border border-stale-foreground/30 bg-stale p-4 text-sm leading-relaxed text-stale-foreground">
          <Badge variant="outline" className="mb-1 border-stale-foreground/40">
            {strings.locked}
          </Badge>
          <p>{strings.lockedReason(cluster.lock_category)}</p>
        </div>
      ) : null}

      {summary ? (
        <section className="mt-5">
          <CitedText
            text={summary}
            cluster={cluster}
            className="text-[15.5px] leading-relaxed [&_sup]:font-bold"
          />
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            {strings.aiNote}
          </p>
        </section>
      ) : (
        <p className="mt-5 rounded-xl border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
          {t("detailPending")}
        </p>
      )}

      <section className="mt-8" aria-labelledby="coverage-heading">
        <h2
          id="coverage-heading"
          className="font-heading text-lg font-extrabold tracking-tight"
        >
          {t("coverageHeading")}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("coverageIntro")}
        </p>
        <div className="mt-2.5">
          <SourceDots
            count={covered.size}
            label={strings.sourcesCount(covered.size)}
          />
        </div>

        <ul className="mt-4 space-y-2.5">
          {cluster.members.map((member, i) => {
            const note = noteByItem.get(member.id);
            const noteText = note ? (isTa ? note.note_ta : note.note_en) : null;
            return (
              <li
                key={member.id}
                className="rounded-xl border border-border bg-card p-4"
              >
                <div className="flex items-center gap-3">
                  <span
                    aria-hidden="true"
                    className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent font-heading text-sm font-extrabold text-accent-foreground"
                  >
                    {strings.outletName(member.outlet).slice(0, 1)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-heading text-sm font-bold">
                      {strings.outletName(member.outlet)}{" "}
                      <sup className="font-sans text-primary">[{i + 1}]</sup>
                    </p>
                    <p
                      lang={member.lang}
                      className="truncate text-xs text-muted-foreground"
                    >
                      {member.headline}
                    </p>
                  </div>
                  {member.published_at ? (
                    <span className="shrink-0 text-[11px] font-medium tabular-nums text-muted-foreground">
                      {format.relativeTime(new Date(member.published_at))}
                    </span>
                  ) : null}
                </div>
                {noteText ? (
                  <p className="mt-2.5 border-s-2 border-accent ps-3 text-[13.5px] leading-relaxed">
                    {noteText}
                  </p>
                ) : null}
                <a
                  href={member.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="press mt-2.5 inline-block text-xs font-bold text-primary underline-offset-4 hover:underline"
                >
                  {t("readAtOutlet", {
                    outlet: strings.outletName(member.outlet),
                  })}{" "}
                  ↗
                </a>
              </li>
            );
          })}
        </ul>

        {notCovered.length > 0 ? (
          <div className="mt-4 rounded-xl border border-border bg-secondary/40 p-4">
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
              {t("notCoveredHeading")}
            </p>
            <p className="mt-1.5 text-sm text-muted-foreground">
              {notCovered.map((o) => strings.outletName(o)).join(" · ")}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              {t("coverageNote")}
            </p>
          </div>
        ) : null}
      </section>

      <p className="mt-8 rounded-xl border border-border bg-secondary/40 p-4 text-xs leading-relaxed text-muted-foreground">
        {t("methodNote")}
      </p>
    </article>
  );
}
