import {
  getFormatter,
  getTranslations,
  setRequestLocale,
} from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { LocateButton } from "@/components/locate-button";
import { buildNewsStrings } from "@/components/news-feed";
import { ClusterStoryCard, ItemStoryCard } from "@/components/story-card";
import { getMyFollows, getMyPlaces } from "@/lib/places";
import {
  getDailyBrief,
  getNewsClusters,
  getNewsLastChecked,
  getPersonNewsItems,
  getPlaceCards,
  getUnclusteredItems,
  getVacantSeats,
  type NewsCluster,
  type NewsSingleItem,
  type PlaceCard,
} from "@/lib/queries";

/**
 * Home = the news-first civic feed (M7.5, D-023): sectioned by the
 * reader's geographies — their places' districts, then statewide — each
 * sector limited and ending in an explicit "caught up" moment. Ranking is
 * civic (seat status above stories, D-016/D-021), never engagement.
 */

const PER_SECTOR = 5;

interface Sector {
  districtId: number;
  districtName: string;
  districtLgd: string | null;
  places: PlaceCard[];
  clusters: NewsCluster[];
  items: NewsSingleItem[];
}

export default async function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const isTa = locale === "ta";

  const lang = locale === "ta" ? ("ta" as const) : ("en" as const);
  const [places, follows] = await Promise.all([getMyPlaces(), getMyFollows()]);
  const [t, tn, tl, tc, format, strings, lastChecked, brief, followItems] =
    await Promise.all([
      getTranslations("home.feed"),
      getTranslations("news"),
      getTranslations("locate"),
      getTranslations("common"),
      getFormatter(),
      buildNewsStrings(),
      getNewsLastChecked(),
      getDailyBrief(),
      getPersonNewsItems(follows, 4),
    ]);

  const cards = places.length ? await getPlaceCards(places) : [];
  const vacantSeats = cards.length ? await getVacantSeats() : [];

  // One sector per unique district across the reader's places.
  const districtOrder: number[] = [];
  const byDistrict = new Map<number, PlaceCard[]>();
  for (const card of cards) {
    if (card.district_id === null) continue;
    if (!byDistrict.has(card.district_id)) {
      byDistrict.set(card.district_id, []);
      districtOrder.push(card.district_id);
    }
    byDistrict.get(card.district_id)?.push(card);
  }
  const sectors: Sector[] = await Promise.all(
    districtOrder.map(async (districtId) => {
      const sectorPlaces = byDistrict.get(districtId) ?? [];
      const [clusters, items] = await Promise.all([
        getNewsClusters(districtId, 3),
        getUnclusteredItems(lang, districtId, PER_SECTOR, 7),
      ]);
      const first = sectorPlaces[0]; // districts only enter via a place
      return {
        districtId,
        districtName:
          (isTa ? first?.district_ta : first?.district_en) ??
          String(districtId),
        districtLgd: first?.district_lgd ?? null,
        places: sectorPlaces,
        clusters,
        items: items.slice(0, Math.max(0, PER_SECTOR - clusters.length)),
      };
    }),
  );

  const [stateClusters, stateItems] = await Promise.all([
    getNewsClusters(undefined, 3),
    getUnclusteredItems(lang, undefined, PER_SECTOR),
  ]);

  const timeLabel = (d: Date | string | null) =>
    d ? format.relativeTime(new Date(d)) : null;

  const vacantByLocality = new Map(
    vacantSeats.map((seat) => [seat.locality_id, seat]),
  );

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-6">
      {brief.length > 0 ? (
        <section className="mb-8">
          <h2 className="font-heading text-lg font-extrabold tracking-tight text-primary">
            {tn("brief.title")}
          </h2>
          <ol className="mt-3 space-y-2 rounded-2xl border border-border bg-card p-4">
            {brief.map((cluster, i) => (
              <li key={cluster.id} className="flex gap-3">
                <span
                  aria-hidden="true"
                  className="font-heading text-sm font-extrabold tabular-nums text-primary"
                >
                  {i + 1}
                </span>
                <Link
                  href={`/news/s/${cluster.id}`}
                  className="press min-w-0 flex-1 font-heading text-[14.5px] font-bold leading-snug underline-offset-4 hover:underline"
                >
                  {(locale === "ta"
                    ? (cluster.title_ta ?? cluster.title_en)
                    : (cluster.title_en ?? cluster.title_ta)) ??
                    cluster.members[0]?.headline}
                </Link>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {followItems.length > 0 ? (
        <section className="mb-8">
          <h2 className="font-heading text-lg font-extrabold tracking-tight text-primary">
            {t("followedSection")}
          </h2>
          <div className="mt-3 space-y-2.5">
            {followItems.map((item) => (
              <ItemStoryCard
                key={`f${item.id}`}
                item={item}
                locale={locale}
                timeLabel={timeLabel(item.published_at)}
                s={strings}
              />
            ))}
          </div>
        </section>
      ) : null}

      {cards.length === 0 ? (
        <section className="py-10 sm:py-16">
          <h1 className="max-w-xl font-heading text-3xl font-extrabold leading-snug sm:text-4xl">
            {t("onboardTitle")}
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
            {t("onboardSub")}
          </p>
          <div className="mt-6 flex flex-wrap items-start gap-3">
            <LocateButton
              targetPath={`/${locale}/locate`}
              labels={{
                button: tl("button"),
                locating: tl("locating"),
                denied: tl("denied"),
                failed: tl("failed"),
              }}
              fallback={{
                action: `/${locale}/constituencies`,
                placeholder: tl("pickerPlaceholder"),
                submit: tc("nav.search"),
              }}
            />
            <Button asChild size="lg" variant="outline" className="press">
              <Link href="/constituencies">{t("browse")}</Link>
            </Button>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            {tl("privacyNote")}
          </p>
        </section>
      ) : (
        sectors.map((sector, sectorIndex) => (
          <section key={sector.districtId} className="mb-8">
            <div className="flex items-baseline justify-between gap-2">
              <h2 className="font-heading text-lg font-extrabold tracking-tight text-primary">
                {t("districtSection", { district: sector.districtName })}
              </h2>
              {sector.districtLgd ? (
                <Link
                  href={`/news/d/${sector.districtLgd}`}
                  className="text-sm font-semibold text-primary underline-offset-4 hover:underline"
                >
                  {t("showMore")} →
                </Link>
              ) : null}
            </div>

            <div className="mt-3 space-y-2.5">
              {sector.places.map((place) => {
                const vacancy = vacantByLocality.get(place.id);
                const repName = isTa
                  ? (place.rep_ta ?? place.rep_en)
                  : place.rep_en;
                const party = isTa ? place.party_ta : place.party_en;
                return (
                  <Link
                    key={`${place.level}:${place.eci_code}`}
                    href={`/constituencies/${place.level}/${place.eci_code}`}
                    className="press flex items-center gap-3 rounded-xl border border-border bg-card p-3.5"
                  >
                    <span
                      aria-hidden="true"
                      className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent font-heading text-sm font-extrabold text-accent-foreground"
                    >
                      {(repName ?? (isTa ? place.name_ta : place.name_en)).slice(0, 1)}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-heading text-[15px] font-bold leading-tight">
                        {vacancy
                          ? (isTa ? place.name_ta : place.name_en)
                          : (repName ?? (isTa ? place.name_ta : place.name_en))}
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {vacancy
                          ? t("seatVacant")
                          : `${place.level === "ac" ? t("myMla") : t("myMp")} · ${
                              isTa ? place.name_ta : place.name_en
                            }${party ? ` · ${party}` : ""}`}
                      </span>
                    </span>
                    {vacancy ? (
                      <span className="ms-auto shrink-0 rounded-full bg-stale px-2.5 py-1 text-[10px] font-bold text-stale-foreground">
                        {t("vacantCta")}
                      </span>
                    ) : null}
                  </Link>
                );
              })}
            </div>

            <div className="mt-2.5 space-y-2.5">
              {sector.clusters.map((cluster, ci) => (
                <ClusterStoryCard
                  key={`c${cluster.id}`}
                  cluster={cluster}
                  locale={locale}
                  timeLabel={timeLabel(cluster.event_time)}
                  s={strings}
                  eager={sectorIndex === 0 && ci === 0}
                />
              ))}
              {sector.items.map((item, ii) => (
                <ItemStoryCard
                  key={`i${item.id}`}
                  item={item}
                  locale={locale}
                  timeLabel={timeLabel(item.published_at)}
                  s={strings}
                  eager={
                    sectorIndex === 0 && sector.clusters.length === 0 && ii === 0
                  }
                />
              ))}
              {sector.clusters.length === 0 && sector.items.length === 0 ? (
                <p className="rounded-xl border border-border bg-secondary/50 p-4 text-sm text-muted-foreground">
                  {t("quiet")}
                </p>
              ) : null}
            </div>
          </section>
        ))
      )}

      <section className="mb-6">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="font-heading text-lg font-extrabold tracking-tight text-primary">
            {t("statewide")}
          </h2>
          <Link
            href="/news"
            className="text-sm font-semibold text-primary underline-offset-4 hover:underline"
          >
            {t("showMore")} →
          </Link>
        </div>
        <div className="mt-3 space-y-2.5">
          {stateClusters.map((cluster) => (
            <ClusterStoryCard
              key={`c${cluster.id}`}
              cluster={cluster}
              locale={locale}
              timeLabel={timeLabel(cluster.event_time)}
              s={strings}
            />
          ))}
          {stateItems
            .slice(0, Math.max(0, PER_SECTOR - stateClusters.length))
            .map((item, ii) => (
              <ItemStoryCard
                key={`i${item.id}`}
                item={item}
                locale={locale}
                timeLabel={timeLabel(item.published_at)}
                s={strings}
                eager={cards.length === 0 && stateClusters.length === 0 && ii === 0}
              />
            ))}
        </div>
      </section>

      <footer className="pb-4 pt-6 text-center">
        <p aria-hidden="true" className="text-base tracking-[6px] text-primary">
          · · ●
        </p>
        <p className="mt-1 text-sm font-semibold text-foreground">
          {t("caughtUp")}
        </p>
        {lastChecked ? (
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t("lastChecked", {
              time: format.dateTime(lastChecked, {
                dateStyle: "medium",
                timeStyle: "short",
              }),
            })}
          </p>
        ) : null}
        {cards.length > 0 ? (
          <p className="mt-3 text-xs text-muted-foreground">{t("manageHint")}</p>
        ) : null}
      </footer>
    </div>
  );
}
