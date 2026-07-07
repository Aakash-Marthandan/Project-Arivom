/**
 * Canonical site origin for absolute URLs (sitemap, canonicals, JSON-LD).
 * Resolution order: explicit NEXT_PUBLIC_SITE_URL (set this when a custom
 * domain lands) → Vercel's production domain (automatic on deploys) →
 * localhost for local work. Never hardcode a domain elsewhere.
 */
export function siteOrigin(): string {
  const configured = process.env.NEXT_PUBLIC_SITE_URL;
  if (configured) return configured.replace(/\/+$/, "");
  const vercel = process.env.VERCEL_PROJECT_PRODUCTION_URL;
  if (vercel) return `https://${vercel}`;
  return "http://localhost:3000";
}
