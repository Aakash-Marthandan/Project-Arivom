import type { Metadata } from "next";
import {
  getFormatter,
  getTranslations,
  setRequestLocale,
} from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { buildNewsStrings, NewsFeed } from "@/components/news-feed";
import { rankNewsItems } from "@/lib/civic-rank";
import { getMyPlaces } from "@/lib/places";
import {
  getNewsClusters,
  getPlaceCards,
  getUnclusteredItems,
} from "@/lib/queries";

/**
 * The finite feed (D-036). Three bounded tiers behind honest "more"
 * links, then a deliberate end: no endless scroll, ever. Depth lives in
 * the URL (?d=2, ?d=3) so the whole experience is server-rendered
 * plain links — no client state, works without JS, and each step is a
 * page a reader chose, not one that slid under their thumb.
 */

const TIER1_LIMIT = 12;
const TIER2_LIMIT = 15;
const TIER3_LIMIT = 15;

const FEEDBACK_URL =
  "https://github.com/Aakash-Marthandan/Project-Arivom/issues/new?title=" +
  encodeURIComponent("Feed feedback: what I was looking for") +
  "&body=" +
  encodeURIComponent(
    [
      "You pressed 'More news' to the end. Thank you for telling us why.",
      "",
      "- Were you looking for a story we missed? Which one?",
      "- Should some topic get more priority? Which?",
      "- Anything else?",
      "",
      "(Write in Tamil or English.)",
    ].join("\n"),
  );

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/news">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "news" });
  return { title: t("title"), description: t("intro") };
}

function Nudge({ children }: { children: React.ReactNode }) {
  return (
    <p className="mx-auto mt-10 max-w-md text-center text-sm leading-relaxed text-muted-foreground">
      {children}
    </p>
  );
}

function MoreLink({ href, label }: { href: string; label: string }) {
  return (
    <p className="mt-4 text-center">
      <Link
        href={href}
        scroll={false}
        className="press inline-block rounded-lg border border-border bg-card px-5 py-2.5 text-sm font-bold text-primary"
      >
        {label}
      </Link>
    </p>
  );
}

export default async function NewsPage({
  params,
  searchParams,
}: PageProps<"/[locale]/news">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const lang = locale === "ta" ? ("ta" as const) : ("en" as const);
  const sp = await searchParams;
  const depth = sp.d === "3" ? 3 : sp.d === "2" ? 2 : 1;

  const places = await getMyPlaces();
  const [t, format, strings, clusters, tnItems, placeCards] =
    await Promise.all([
      getTranslations("news"),
      getFormatter(),
      buildNewsStrings(),
      getNewsClusters(),
      getUnclusteredItems(lang, undefined, TIER1_LIMIT + TIER2_LIMIT),
      places.length ? getPlaceCards(places) : Promise.resolve([]),
    ]);

  // Civic-context order (D-037): consequential subjects first, then the
  // reader's own districts, then the newest. Tier 1 is the top of that
  // order — the set we think a reader needs — not merely the latest.
  const placeDistrictLgds = new Set(
    placeCards.flatMap((c) => (c.district_lgd ? [c.district_lgd] : [])),
  );
  // Ranking can only lift what the pool contains: guarantee each saved
  // district a few of its own recent stories before ordering.
  const placeDistrictIds = [
    ...new Set(
      placeCards.flatMap((c) => (c.district_id ? [c.district_id] : [])),
    ),
  ].slice(0, 3);
  const districtPools = await Promise.all(
    placeDistrictIds.map((id) => getUnclusteredItems(lang, id, 5, 3, "any")),
  );
  const seenIds = new Set(tnItems.map((i) => i.id));
  const pool = [...tnItems];
  for (const extra of districtPools) {
    for (const item of extra) {
      if (!seenIds.has(item.id)) {
        seenIds.add(item.id);
        pool.push(item);
      }
    }
  }
  const ranked = rankNewsItems(pool, { placeDistrictLgds });
  const tier1 = ranked.slice(0, TIER1_LIMIT);
  const tier2 = ranked.slice(TIER1_LIMIT);
  const tier3 =
    depth >= 3
      ? rankNewsItems(
          await getUnclusteredItems(lang, undefined, TIER3_LIMIT, 3, "beyond"),
        )
      : [];

  // The life-doors at the finite end: the reader's own district when we
  // know it, the locate flow when we do not.
  const districtLgd = placeCards.find((c) => c.district_lgd)?.district_lgd;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>
      <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
        {t("tiers.orderNote")}
      </p>

      {clusters.length === 0 && tier1.length === 0 ? (
        <p className="mt-10 max-w-xl rounded-md border border-border bg-secondary/50 p-6 text-muted-foreground">
          {t("empty")}
        </p>
      ) : (
        <NewsFeed
          clusters={clusters}
          items={tier1}
          locale={locale}
          format={format}
          strings={strings}
          order="given"
        />
      )}

      {depth === 1 && tier2.length > 0 ? (
        <>
          <Nudge>{t("tiers.tier1End")}</Nudge>
          <MoreLink href="?d=2#t2" label={t("tiers.moreNews")} />
        </>
      ) : null}

      {depth >= 2 && tier2.length > 0 ? (
        <section id="t2" aria-label={t("tiers.moreNews")} className="mt-10">
          <Nudge>{t("tiers.tier2Intro")}</Nudge>
          <NewsFeed
            clusters={[]}
            items={tier2}
            locale={locale}
            format={format}
            strings={strings}
            order="given"
          />
        </section>
      ) : null}

      {depth === 2 ? (
        <>
          <Nudge>{t("tiers.tier2End")}</Nudge>
          <MoreLink href="?d=3#t3" label={t("tiers.moreNews")} />
        </>
      ) : null}

      {depth >= 3 ? (
        <section id="t3" aria-label={t("tiers.tier3Intro")} className="mt-10">
          <Nudge>{t("tiers.tier3Intro")}</Nudge>
          {tier3.length > 0 ? (
            <NewsFeed
              clusters={[]}
              items={tier3}
              locale={locale}
              format={format}
              strings={strings}
              order="given"
            />
          ) : (
            <p className="mt-6 text-center text-sm text-muted-foreground">
              {t("empty")}
            </p>
          )}

          {/* The deliberate end (D-036): a proud stop, a listening door,
              and two lasting places that outlive any headline. */}
          <div className="mx-auto mt-12 max-w-md rounded-2xl border border-border bg-card p-6 text-center">
            <h2 className="font-heading text-xl font-bold">
              {t("tiers.finiteTitle")}
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              {t("tiers.finiteBody")}
            </p>
            <p className="mt-5 text-sm text-muted-foreground">
              {t("tiers.feedbackPrompt")}
            </p>
            <p className="mt-2">
              <a
                href={FEEDBACK_URL}
                rel="noopener noreferrer"
                target="_blank"
                className="press inline-block rounded-lg border border-border px-4 py-2 text-sm font-bold text-primary"
              >
                {t("tiers.feedbackCta")} ↗
              </a>
            </p>
            <p className="mt-6 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t("tiers.doorsTitle")}
            </p>
            <p className="mt-2 flex flex-col items-center gap-1.5 text-sm">
              {districtLgd ? (
                <Link
                  href={`/d/${districtLgd}`}
                  className="font-medium text-primary underline-offset-4 hover:underline"
                >
                  {t("tiers.doorDistrict")}
                </Link>
              ) : (
                <Link
                  href="/locate"
                  className="font-medium text-primary underline-offset-4 hover:underline"
                >
                  {t("tiers.doorLocate")}
                </Link>
              )}
              <Link
                href="/methodology#stories-method-title"
                className="font-medium text-primary underline-offset-4 hover:underline"
              >
                {t("tiers.doorMethod")}
              </Link>
            </p>
          </div>
        </section>
      ) : null}

      <p className="mt-8 max-w-2xl rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
        {t("methodNote")}
      </p>
    </div>
  );
}
