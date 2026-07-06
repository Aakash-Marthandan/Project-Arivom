import { getFormatter, getTranslations } from "next-intl/server";
import { Badge } from "@/components/ui/badge";
import { CoverageDots } from "@/components/coverage-dots";
import {
  ProvenanceChip,
  type ProvenanceEntry,
} from "@/components/provenance-chip";
import { ItemStoryCard } from "@/components/story-card";
import type { NewsCluster, NewsSingleItem } from "@/lib/queries";

const KNOWN_OUTLETS = [
  "the-hindu",
  "times-of-india",
  "new-indian-express",
  "dt-next",
  "dinamani",
  "daily-thanthi",
  "maalaimalar",
  "puthiyathalaimurai",
  "polimer-news",
  "news7-tamil",
  "oneindia-tamil",
] as const;

const LOCK_CATEGORIES = ["communal", "sub_judice", "allegations"] as const;

type Formatter = Awaited<ReturnType<typeof getFormatter>>;

/**
 * Server-rendered news feed (M7): multi-outlet event clusters interleaved
 * with recent single-source items, newest first. All strings arrive
 * preformatted/translated from the page — no client message payloads.
 */

export interface NewsStrings {
  singleSource: string;
  aiNote: string;
  summaryPending: string;
  coverage: (covered: number, total: number) => string;
  coveredList: string;
  notCoveredList: string;
  sources: string;
  locked: string;
  lockedReason: (category: string | null) => string;
  outletName: (slug: string) => string;
  provenance: {
    chipLabel: string;
    title: string;
    summaryEntryTitle: string;
    method: string;
    fieldLabels: {
      publisher: string;
      retrievedOn: string;
      method: string;
      license: string;
      viewSource: string;
    };
  };
}

/** All feed strings, resolved server-side in one place for both pages. */
export async function buildNewsStrings(): Promise<NewsStrings> {
  const [t, tp] = await Promise.all([
    getTranslations("news"),
    getTranslations("provenance"),
  ]);
  return {
    singleSource: t("singleSource"),
    aiNote: t("aiNote"),
    summaryPending: t("summaryPending"),
    coverage: (covered, total) => t("coverage", { covered, total }),
    coveredList: t("coveredList"),
    notCoveredList: t("notCoveredList"),
    sources: t("sources"),
    locked: t("locked"),
    lockedReason: (category) => {
      const known = LOCK_CATEGORIES.find((c) => c === category);
      return t(`lockedReasons.${known ?? "allegations"}` as const);
    },
    outletName: (slug) => {
      const known = KNOWN_OUTLETS.find((o) => o === slug);
      return known ? t(`outlets.${known}` as const) : slug;
    },
    provenance: {
      chipLabel: tp("chipLabel"),
      title: tp("title"),
      summaryEntryTitle: t("summaryLabel"),
      method: tp("methods.llm_bulk"),
      fieldLabels: {
        publisher: tp("publisher"),
        retrievedOn: tp("retrievedOn"),
        method: tp("method"),
        license: tp("license"),
        viewSource: tp("viewSource"),
      },
    },
  };
}

type FeedEntry =
  | { kind: "cluster"; time: number; cluster: NewsCluster }
  | { kind: "item"; time: number; item: NewsSingleItem };

export function interleave(
  clusters: NewsCluster[],
  items: NewsSingleItem[],
): FeedEntry[] {
  const entries: FeedEntry[] = [
    ...clusters.map((cluster) => ({
      kind: "cluster" as const,
      time: cluster.event_time ? new Date(cluster.event_time).getTime() : 0,
      cluster,
    })),
    ...items.map((item) => ({
      kind: "item" as const,
      time: item.published_at ? new Date(item.published_at).getTime() : 0,
      item,
    })),
  ];
  return entries.sort((a, b) => b.time - a.time);
}

/** Render a summary, turning [n] markers into links to the cited items. */
function Summary({
  text,
  cluster,
}: {
  text: string;
  cluster: NewsCluster;
}) {
  const byId = new Map(cluster.members.map((m) => [m.id, m]));
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="mt-2 text-sm leading-relaxed">
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

function ClusterCard({
  cluster,
  trackedOutlets,
  locale,
  format,
  s,
}: {
  cluster: NewsCluster;
  trackedOutlets: string[];
  locale: string;
  format: Formatter;
  s: NewsStrings;
}) {
  const isTa = locale === "ta";
  const title = isTa
    ? (cluster.title_ta ?? cluster.title_en)
    : (cluster.title_en ?? cluster.title_ta);
  const summary = isTa
    ? (cluster.summary_ta ?? cluster.summary_en)
    : (cluster.summary_en ?? cluster.summary_ta);
  const covered = new Set(cluster.members.map((m) => m.outlet));
  const notCovered = trackedOutlets.filter((o) => !covered.has(o));

  const provenance: ProvenanceEntry[] = [
    {
      title: s.provenance.summaryEntryTitle,
      sourceName: cluster.source_name,
      url: cluster.source_url,
      publisher: cluster.source_publisher,
      license: cluster.source_license,
      retrievedOn: format.dateTime(cluster.retrieved_at, { dateStyle: "long" }),
      method: s.provenance.method,
    },
  ];

  return (
    <li className="rounded-lg border border-border bg-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-heading text-lg font-bold">
          {title ?? cluster.members[0]?.headline}
        </h2>
        {summary ? (
          <ProvenanceChip
            label={s.provenance.chipLabel}
            heading={s.provenance.title}
            fieldLabels={s.provenance.fieldLabels}
            entries={provenance}
          />
        ) : null}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {cluster.event_time
          ? format.dateTime(new Date(cluster.event_time), { dateStyle: "medium" })
          : null}
        {cluster.district_en ? (
          <> · {isTa ? cluster.district_ta : cluster.district_en}</>
        ) : null}
      </p>

      {cluster.discussion_locked ? (
        <div className="mt-3 rounded-md border border-stale-foreground/30 bg-stale p-3 text-xs leading-relaxed text-stale-foreground">
          <Badge variant="outline" className="mb-1 border-stale-foreground/40">
            {s.locked}
          </Badge>
          <p>{s.lockedReason(cluster.lock_category)}</p>
        </div>
      ) : null}

      {summary ? (
        <>
          <Summary text={summary} cluster={cluster} />
          <p className="mt-2 text-xs text-muted-foreground">{s.aiNote}</p>
        </>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">{s.summaryPending}</p>
      )}

      <details className="mt-3">
        <summary className="press flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-primary [&::-webkit-details-marker]:hidden">
          <CoverageDots
            covered={covered.size}
            total={trackedOutlets.length}
            label={s.coverage(covered.size, trackedOutlets.length)}
          />
          <span className="underline-offset-4 hover:underline">
            {s.coverage(covered.size, trackedOutlets.length)}
          </span>
        </summary>
        <div className="mt-2 grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {s.coveredList}
            </p>
            <ul className="mt-1 space-y-1">
              {cluster.members.map((m, i) => (
                <li key={m.id}>
                  <a
                    href={m.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    [{i + 1}] {s.outletName(m.outlet)}
                  </a>
                  <span className="block text-xs text-muted-foreground">
                    {m.headline}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {s.notCoveredList}
            </p>
            <ul className="mt-1 space-y-1 text-muted-foreground">
              {notCovered.map((o) => (
                <li key={o}>{s.outletName(o)}</li>
              ))}
            </ul>
          </div>
        </div>
      </details>
    </li>
  );
}

function ItemCard({
  item,
  totalOutlets,
  format,
  s,
}: {
  item: NewsSingleItem;
  totalOutlets: number;
  format: Formatter;
  s: NewsStrings;
}) {
  return (
    <li>
      <ItemStoryCard
        item={item}
        totalOutlets={totalOutlets}
        timeLabel={
          item.published_at ? format.relativeTime(item.published_at) : null
        }
        s={{
          singleSource: s.singleSource,
          coverageLabel: s.coverage,
          outletName: s.outletName,
        }}
      />
    </li>
  );
}

export function NewsFeed({
  clusters,
  items,
  trackedOutlets,
  locale,
  format,
  strings,
}: {
  clusters: NewsCluster[];
  items: NewsSingleItem[];
  trackedOutlets: string[];
  locale: string;
  format: Formatter;
  strings: NewsStrings;
}) {
  const entries = interleave(clusters, items);
  return (
    <ul className="mt-8 space-y-4">
      {entries.map((entry) =>
        entry.kind === "cluster" ? (
          <ClusterCard
            key={`c${entry.cluster.id}`}
            cluster={entry.cluster}
            trackedOutlets={trackedOutlets}
            locale={locale}
            format={format}
            s={strings}
          />
        ) : (
          <ItemCard
            key={`i${entry.item.id}`}
            item={entry.item}
            totalOutlets={trackedOutlets.length}
            format={format}
            s={strings}
          />
        ),
      )}
    </ul>
  );
}
