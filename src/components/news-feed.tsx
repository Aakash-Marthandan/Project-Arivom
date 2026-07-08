import { getFormatter, getTranslations } from "next-intl/server";
import {
  ClusterStoryCard,
  ItemStoryCard,
  type StoryStrings,
} from "@/components/story-card";
import type { NewsCluster, NewsSingleItem } from "@/lib/queries";

/**
 * Feed assembly (M7.5, D-024): Ground-style story cards, newest first,
 * clusters routing to their dedicated story pages. All strings resolved
 * server-side; no client message payloads.
 */

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
  // Beyond-TN outlets (D-036): the news feed's final tier only.
  "the-hindu-national",
  "indian-express-india",
  "bbc-tamil",
  "bbc-world",
] as const;

const LOCK_CATEGORIES = ["communal", "sub_judice", "allegations"] as const;

type Formatter = Awaited<ReturnType<typeof getFormatter>>;

export interface NewsStrings extends StoryStrings {
  aiNote: string;
  summaryPending: string;
  locked: string;
  lockedReason: (category: string | null) => string;
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

/** All feed strings, resolved server-side in one place for every surface. */
export async function buildNewsStrings(): Promise<NewsStrings> {
  const [t, tp] = await Promise.all([
    getTranslations("news"),
    getTranslations("provenance"),
  ]);
  return {
    singleSource: t("singleSource"),
    aiNote: t("aiNote"),
    summaryPending: t("summaryPending"),
    sourcesCount: (count) => t("sourcesCount", { count }),
    markers: {
      priority: t("markers.priority"),
      sourcesDiffer: t("markers.sourcesDiffer"),
      locked: t("locked"),
    },
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

export function NewsFeed({
  clusters,
  items,
  locale,
  format,
  strings,
}: {
  clusters: NewsCluster[];
  items: NewsSingleItem[];
  locale: string;
  format: Formatter;
  strings: NewsStrings;
}) {
  const entries = interleave(clusters, items);
  return (
    <ul className="mt-8 space-y-3">
      {entries.map((entry, index) => (
        <li key={entry.kind === "cluster" ? `c${entry.cluster.id}` : `i${entry.item.id}`}>
          {entry.kind === "cluster" ? (
            <ClusterStoryCard
              cluster={entry.cluster}
              locale={locale}
              eager={index === 0}
              timeLabel={
                entry.cluster.event_time
                  ? format.relativeTime(new Date(entry.cluster.event_time))
                  : null
              }
              s={strings}
            />
          ) : (
            <ItemStoryCard
              item={entry.item}
              locale={locale}
              eager={index === 0}
              timeLabel={
                entry.item.published_at
                  ? format.relativeTime(entry.item.published_at)
                  : null
              }
              s={strings}
            />
          )}
        </li>
      ))}
    </ul>
  );
}
