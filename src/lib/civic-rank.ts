import type { NewsSingleItem } from "./queries";

/**
 * Civic-context ordering for news feeds (D-037).
 *
 * The reader sees the most civically consequential stories first, then
 * stories from their own saved places, then the newest. Three rules,
 * all published on the methodology page:
 *
 * 1. The checked classification wins when it exists: civic_priority
 *    "high" (set by the analysis pipeline from key day) outranks
 *    everything below.
 * 2. Until then, an interim SUBJECT rubric stands in: bilingual
 *    keyword classes for elections, courts, the legislature and
 *    government decisions, public-safety alerts, and household prices.
 *    Subjects only — party and person names never appear here, and
 *    never will (pillar 2).
 * 3. A story tagged to one of the reader's saved districts matters
 *    more to them; it gets a boost. This uses only the device's
 *    my-places cookie, on surfaces that are already per-reader.
 *
 * Ties break by recency. Nothing is hidden by ranking: every story
 * stays in the feed, later in it.
 */
const CIVIC_SUBJECTS: RegExp[] = [
  // Elections and by-elections
  /தேர்தல்|வாக்குப்பதிவு|வாக்காளர்|வேட்பாளர்|by-?election|election|polling|voter/iu,
  // Courts and their orders
  /நீதிமன்ற|தீர்ப்பு|சிபிஐ|அமலாக்க|supreme court|high court|verdict|judgment|tribunal/iu,
  // Legislature and government decisions
  /சட்டமன்ற|சட்டப்பேரவை|மசோதா|அரசாணை|அமைச்சரவை|assembly|legislature|ordinance|cabinet|government order/iu,
  // Public safety and weather alerts
  /வெள்ளம்|புயல்|கனமழை|எச்சரிக்கை|வெப்பஅலை|வெடிவிபத்து|flood|cyclone|heavy rain|red alert|heatwave|outbreak/iu,
  // Household economics
  /விலை உயர்வு|ரேஷன்|மின்கட்டண|சொத்துவரி|price hike|ration|tariff|fuel price|property tax/iu,
];

export function matchesCivicSubject(headline: string): boolean {
  return CIVIC_SUBJECTS.some((re) => re.test(headline));
}

export interface RankContext {
  /** lgd codes of the reader's saved districts (my-places cookie). */
  placeDistrictLgds?: ReadonlySet<string>;
}

function score(item: NewsSingleItem, ctx: RankContext): number {
  let s = 0;
  if (item.civic_priority === "high") {
    s += 3; // checked classification (key day onward)
  } else if (item.civic_priority === null && matchesCivicSubject(item.headline)) {
    s += 2; // interim subject rubric, published above
  }
  if (
    item.district_lgd &&
    ctx.placeDistrictLgds?.has(item.district_lgd)
  ) {
    s += 1.5;
  }
  return s;
}

/** Stable order: score desc, then published_at desc. Returns a copy. */
export function rankNewsItems(
  items: NewsSingleItem[],
  ctx: RankContext = {},
): NewsSingleItem[] {
  return items
    .map((item, i) => ({ item, i, s: score(item, ctx) }))
    .sort(
      (a, b) =>
        b.s - a.s ||
        new Date(b.item.published_at ?? 0).getTime() -
          new Date(a.item.published_at ?? 0).getTime() ||
        a.i - b.i,
    )
    .map(({ item }) => item);
}
