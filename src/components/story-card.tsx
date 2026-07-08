import { Link } from "@/i18n/navigation";
import { SourceDots } from "@/components/coverage-dots";
import { StoryThumb } from "@/components/story-thumb";
import type { NewsCluster, NewsSingleItem } from "@/lib/queries";

/**
 * Story cards v3 (D-026): content-first. A side thumbnail supports the
 * text (the full-width hero lives on story pages); extended summary
 * preview; a markers row of FACTS — civic priority, sources-differ,
 * locked — never judgments or scores (pillar 2).
 */

export interface StoryStrings {
  /** Null until the first cluster exists (D-037): with nothing to
   *  contrast against, "one outlet so far" is noise on every card. */
  singleSource: string | null;
  sourcesCount: (count: number) => string;
  outletName: (slug: string) => string;
  markers: { priority: string; sourcesDiffer: string; locked: string };
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

function Marker({
  tone,
  children,
}: {
  tone: "priority" | "differ" | "locked";
  children: React.ReactNode;
}) {
  const tones = {
    priority: "bg-accent text-accent-foreground",
    differ: "bg-stale text-stale-foreground",
    locked: "bg-stale text-stale-foreground",
  } as const;
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wide ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function ClusterStoryCard({
  cluster,
  locale,
  timeLabel,
  s,
  eager = false,
}: {
  cluster: NewsCluster;
  locale: string;
  timeLabel: string | null;
  s: StoryStrings;
  eager?: boolean;
}) {
  const isTa = locale === "ta";
  const title =
    (isTa ? cluster.title_ta : cluster.title_en) ??
    cluster.title_en ??
    cluster.title_ta ??
    cluster.members[0]?.headline;
  const summary = isTa
    ? (cluster.summary_long_ta ?? cluster.summary_ta ?? cluster.summary_long_en ?? cluster.summary_en)
    : (cluster.summary_long_en ?? cluster.summary_en ?? cluster.summary_long_ta ?? cluster.summary_ta);
  const covered = new Set(cluster.members.map((m) => m.outlet)).size;
  const image = clusterImage(cluster);

  return (
    <Link
      href={`/news/s/${cluster.id}` as "/news"}
      className="press block rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(46,42,36,0.04)] transition-shadow hover:shadow-[0_8px_22px_-12px_rgba(46,42,36,0.3)]"
      style={{ viewTransitionName: `story-${cluster.id}` }}
    >
      <div className="flex items-center gap-1.5">
        <span className="inline-block rounded-full bg-secondary px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wide text-secondary-foreground">
          {s.sourcesCount(covered)}
        </span>
        {cluster.priority_high ? (
          <Marker tone="priority">{s.markers.priority}</Marker>
        ) : null}
        {cluster.sources_disagree ? (
          <Marker tone="differ">{s.markers.sourcesDiffer}</Marker>
        ) : null}
        {cluster.discussion_locked ? (
          <Marker tone="locked">{s.markers.locked}</Marker>
        ) : null}
      </div>
      <div className="mt-2 flex gap-3.5">
        <div className="min-w-0 flex-1">
          <h3 className="font-heading text-[16.5px] font-bold leading-snug">
            {title}
          </h3>
          {summary ? (
            <p className="mt-1.5 line-clamp-4 text-[13.5px] leading-relaxed text-muted-foreground">
              {summary.replace(/\[\d+\]/g, "")}
            </p>
          ) : null}
        </div>
        {image ? (
          <StoryThumb
            src={image}
            eager={eager}
            className="mt-0.5 size-[104px] rounded-xl sm:size-[118px]"
          />
        ) : null}
      </div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <SourceDots count={covered} label={s.sourcesCount(covered)} />
          {cluster.district_en ? (
            <span className="text-[11px] font-semibold text-muted-foreground">
              {isTa ? cluster.district_ta : cluster.district_en}
            </span>
          ) : null}
        </span>
        {timeLabel ? (
          <span className="text-[11px] font-medium text-muted-foreground">
            {timeLabel}
          </span>
        ) : null}
      </div>
    </Link>
  );
}

export function ItemStoryCard({
  item,
  locale,
  timeLabel,
  s,
  eager = false,
}: {
  item: NewsSingleItem;
  locale: string;
  timeLabel: string | null;
  s: StoryStrings;
  eager?: boolean;
}) {
  const title = itemTitle(item, locale);
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="press block rounded-2xl border border-border bg-card/70 p-4"
    >
      <div className="flex gap-3.5">
        <div className="min-w-0 flex-1">
          {item.civic_priority === "high" ? (
            <div className="mb-1">
              <Marker tone="priority">{s.markers.priority}</Marker>
            </div>
          ) : null}
          <h3
            lang={title.lang}
            className="font-heading text-[15.5px] font-bold leading-snug"
          >
            {title.text} <span aria-hidden="true">↗</span>
          </h3>
          <p className="mt-1.5 text-[11.5px] font-semibold text-muted-foreground">
            {s.outletName(item.outlet)}
            {s.singleSource ? <> · {s.singleSource}</> : null}
          </p>
        </div>
        {item.image_url ? (
          <StoryThumb
            src={item.image_url}
            eager={eager}
            className="mt-0.5 size-[88px] rounded-xl"
          />
        ) : null}
      </div>
      {timeLabel ? (
        <p className="mt-2 text-right text-[11px] font-medium text-muted-foreground">
          {timeLabel}
        </p>
      ) : null}
    </a>
  );
}
