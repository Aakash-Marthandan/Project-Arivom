import { Link } from "@/i18n/navigation";
import { SourceDots } from "@/components/coverage-dots";
import { StoryThumb } from "@/components/story-thumb";
import type { NewsCluster, NewsSingleItem } from "@/lib/queries";

/**
 * Story cards (D-024/D-025): hero image when the outlet published one,
 * Arivom-voice title in the reader's language when available, in-card
 * summary preview, sources pill. Clusters route to their story page;
 * single-source items link out to the outlet.
 */

export interface StoryStrings {
  singleSource: string;
  sourcesCount: (count: number) => string;
  outletName: (slug: string) => string;
}

export function clusterImage(cluster: NewsCluster): string | null {
  return cluster.members.find((m) => m.image_url)?.image_url ?? null;
}

/** Arivom-voice title in the reader's language, else the original. */
export function itemTitle(
  item: NewsSingleItem,
  locale: string,
): { text: string; lang: "ta" | "en" } {
  const clean = locale === "ta" ? item.title_clean_ta : item.title_clean_en;
  if (clean) return { text: clean, lang: locale as "ta" | "en" };
  // Display-level tidy of feed escaping artifacts; the stored headline
  // stays verbatim (provenance).
  return { text: item.headline.replace(/\\(["'])/g, "$1"), lang: item.lang };
}

export function ClusterStoryCard({
  cluster,
  locale,
  timeLabel,
  s,
}: {
  cluster: NewsCluster;
  locale: string;
  timeLabel: string | null;
  s: StoryStrings;
}) {
  const isTa = locale === "ta";
  const title =
    (isTa ? cluster.title_ta : cluster.title_en) ??
    cluster.title_en ??
    cluster.title_ta ??
    cluster.members[0]?.headline;
  const summary = isTa
    ? (cluster.summary_ta ?? cluster.summary_en)
    : (cluster.summary_en ?? cluster.summary_ta);
  const covered = new Set(cluster.members.map((m) => m.outlet)).size;
  const image = clusterImage(cluster);

  return (
    <Link
      href={`/news/s/${cluster.id}` as "/news"}
      className="press block overflow-hidden rounded-2xl border border-border bg-card shadow-[0_1px_2px_rgba(46,42,36,0.04)] transition-shadow hover:shadow-[0_8px_22px_-12px_rgba(46,42,36,0.3)]"
      style={{ viewTransitionName: `story-${cluster.id}` }}
    >
      {image ? (
        <StoryThumb src={image} className="aspect-[16/9] w-full" />
      ) : null}
      <div className="p-4">
        <span className="inline-block rounded-full bg-accent px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wide text-accent-foreground">
          {s.sourcesCount(covered)}
        </span>
        <h3 className="mt-2 font-heading text-[17px] font-bold leading-snug">
          {title}
        </h3>
        {summary ? (
          <p className="mt-1.5 line-clamp-3 text-[13.5px] leading-relaxed text-muted-foreground">
            {summary.replace(/\[\d+\]/g, "")}
          </p>
        ) : null}
        <div className="mt-3 flex items-center justify-between gap-2">
          <SourceDots count={covered} label={s.sourcesCount(covered)} />
          {timeLabel ? (
            <span className="text-[11px] font-medium text-muted-foreground">
              {timeLabel}
            </span>
          ) : null}
        </div>
      </div>
    </Link>
  );
}

export function ItemStoryCard({
  item,
  locale,
  timeLabel,
  s,
}: {
  item: NewsSingleItem;
  locale: string;
  timeLabel: string | null;
  s: StoryStrings;
}) {
  const title = itemTitle(item, locale);
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="press block overflow-hidden rounded-2xl border border-border bg-card/70"
    >
      {item.image_url ? (
        <StoryThumb src={item.image_url} className="aspect-[16/9] w-full" />
      ) : null}
      <div className="p-4">
        <h3
          lang={title.lang}
          className="font-heading text-[16px] font-bold leading-snug"
        >
          {title.text} <span aria-hidden="true">↗</span>
        </h3>
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="text-[11.5px] font-semibold text-muted-foreground">
            {s.outletName(item.outlet)} · {s.singleSource}
          </span>
          {timeLabel ? (
            <span className="shrink-0 text-[11px] font-medium text-muted-foreground">
              {timeLabel}
            </span>
          ) : null}
        </div>
      </div>
    </a>
  );
}
