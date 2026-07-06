import { Link } from "@/i18n/navigation";
import { CoverageDots } from "@/components/coverage-dots";
import type { NewsCluster, NewsSingleItem } from "@/lib/queries";

/**
 * Compact story cards for feed sectors (M7.5). Two shapes:
 * - cluster: multi-outlet event → dots show real coverage; links into the
 *   scope feed where the full card (summary, citations, table) lives.
 * - item: single-source story → external link, 1-dot coverage, honest label.
 */

export interface StoryStrings {
  singleSource: string;
  coverageLabel: (covered: number, total: number) => string;
  outletName: (slug: string) => string;
}

export function ClusterStoryCard({
  cluster,
  totalOutlets,
  locale,
  href,
  timeLabel,
  s,
}: {
  cluster: NewsCluster;
  totalOutlets: number;
  locale: string;
  href: string;
  timeLabel: string | null;
  s: StoryStrings;
}) {
  const isTa = locale === "ta";
  const title =
    (isTa ? cluster.title_ta : cluster.title_en) ??
    cluster.title_en ??
    cluster.title_ta ??
    cluster.members[0]?.headline;
  const covered = new Set(cluster.members.map((m) => m.outlet)).size;
  return (
    <Link
      href={href as "/news"}
      className="press block rounded-xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(46,42,36,0.04)]"
    >
      <h3 className="font-heading text-[15px] font-bold leading-snug">
        {title}
      </h3>
      <div className="mt-2 flex items-center justify-between gap-2">
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
      <h3
        lang={item.lang}
        className="font-heading text-[15px] font-bold leading-snug"
      >
        {item.headline} <span aria-hidden="true">↗</span>
      </h3>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] font-semibold text-muted-foreground">
          {s.outletName(item.outlet)} · {s.singleSource}
        </span>
        <span className="flex items-center gap-2">
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
        </span>
      </div>
    </a>
  );
}
