import { Link } from "@/i18n/navigation";
import { CoverageDots } from "@/components/coverage-dots";
import { StoryThumb } from "@/components/story-thumb";
import type { NewsCluster, NewsSingleItem } from "@/lib/queries";

/**
 * Ground-style story cards (M7.5 polish, D-024): image, title, summary
 * preview, coverage dots, source-count pill. Clusters route to their
 * dedicated story page; single-source items link out to the outlet.
 */

export interface StoryStrings {
  singleSource: string;
  coverageLabel: (covered: number, total: number) => string;
  sourcesCount: (count: number) => string;
  outletName: (slug: string) => string;
}

export function clusterImage(cluster: NewsCluster): string | null {
  return cluster.members.find((m) => m.image_url)?.image_url ?? null;
}

export function ClusterStoryCard({
  cluster,
  totalOutlets,
  locale,
  timeLabel,
  s,
}: {
  cluster: NewsCluster;
  totalOutlets: number;
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

  return (
    <Link
      href={`/news/s/${cluster.id}` as "/news"}
      className="press block rounded-xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(46,42,36,0.04)] transition-shadow hover:shadow-[0_6px_18px_-10px_rgba(46,42,36,0.25)]"
      style={{ viewTransitionName: `story-${cluster.id}` }}
    >
      <div className="flex gap-3.5">
        <div className="min-w-0 flex-1">
          <span className="inline-block rounded-full bg-accent px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wide text-accent-foreground">
            {s.sourcesCount(covered)}
          </span>
          <h3 className="mt-1.5 font-heading text-[16px] font-bold leading-snug">
            {title}
          </h3>
          {summary ? (
            <p className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">
              {summary.replace(/\[\d+\]/g, "")}
            </p>
          ) : null}
        </div>
        <StoryThumb
          src={clusterImage(cluster)}
          className="size-[76px] rounded-lg"
        />
      </div>
      <div className="mt-2.5 flex items-center justify-between gap-2">
        <CoverageDots
          covered={covered}
          total={totalOutlets}
          label={s.coverageLabel(covered, totalOutlets)}
        />
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
  totalOutlets,
  timeLabel,
  s,
}: {
  item: NewsSingleItem;
  totalOutlets: number;
  timeLabel: string | null;
  s: StoryStrings;
}) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="press block rounded-xl border border-border bg-card/60 p-4"
    >
      <div className="flex gap-3.5">
        <div className="min-w-0 flex-1">
          <h3
            lang={item.lang}
            className="font-heading text-[15px] font-bold leading-snug"
          >
            {item.headline} <span aria-hidden="true">↗</span>
          </h3>
          <p className="mt-1 text-[11.5px] font-semibold text-muted-foreground">
            {s.outletName(item.outlet)} · {s.singleSource}
          </p>
        </div>
        <StoryThumb src={item.image_url} className="size-[64px] rounded-lg" />
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <CoverageDots
          covered={1}
          total={totalOutlets}
          label={s.coverageLabel(1, totalOutlets)}
        />
        {timeLabel ? (
          <span className="text-[11px] font-medium text-muted-foreground">
            {timeLabel}
          </span>
        ) : null}
      </div>
    </a>
  );
}
