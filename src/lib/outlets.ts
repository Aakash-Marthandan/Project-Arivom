import registry from "../../pipelines/data/outlets.json";

/**
 * The outlet registry is the single source of truth (pipelines/data,
 * D-020); the web derives coverage tiers from it at build time.
 * Outlets without a coverage field are Tamil Nadu outlets.
 */
interface RegistryOutlet {
  slug: string;
  coverage?: string;
}

const outlets = (registry as { outlets: RegistryOutlet[] }).outlets;

/** National + international outlets (D-036): shown only in the news
 *  feed's final tier, never on locality-first surfaces — except where
 *  an item carries a district tag, which makes it locally relevant. */
export const BEYOND_TN_OUTLETS: string[] = outlets
  .filter((o) => o.coverage === "national" || o.coverage === "international")
  .map((o) => o.slug);
