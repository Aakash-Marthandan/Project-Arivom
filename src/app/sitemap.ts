import type { MetadataRoute } from "next";
import { siteOrigin } from "@/lib/site";
import { sql } from "@/lib/db";

export const revalidate = 86400;

/**
 * Sitemap with per-entry hreflang alternates (ta default, en second) —
 * the one place language alternates are declared, per M11 SEO scope.
 * Covers the stable civic spine; short-lived story pages are reachable
 * through feeds and are deliberately not enumerated here.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = siteOrigin();

  const entry = (
    path: string,
    changeFrequency: "hourly" | "daily" | "weekly" | "monthly",
    priority: number,
  ): MetadataRoute.Sitemap[number] => ({
    url: `${origin}/ta${path}`,
    changeFrequency,
    priority,
    alternates: {
      languages: {
        ta: `${origin}/ta${path}`,
        en: `${origin}/en${path}`,
        "x-default": `${origin}/ta${path}`,
      },
    },
  });

  const [constituencies, districts] = await Promise.all([
    sql<{ level: string; eci_code: string }[]>`
      SELECT level::text AS level, eci_code FROM localities
      WHERE level IN ('ac', 'pc') AND eci_code IS NOT NULL
      ORDER BY level, (eci_code)::int
    `,
    sql<{ lgd_code: string }[]>`
      SELECT lgd_code FROM localities
      WHERE level = 'district' AND lgd_code IS NOT NULL
      ORDER BY lgd_code
    `,
  ]);

  return [
    entry("", "hourly", 1),
    entry("/news", "hourly", 0.9),
    entry("/locate", "monthly", 0.9),
    entry("/vacancies", "daily", 0.8),
    entry("/government", "weekly", 0.8),
    entry("/constituencies", "weekly", 0.7),
    entry("/methodology", "monthly", 0.5),
    entry("/freshness", "daily", 0.5),
    entry("/corrections", "weekly", 0.5),
    entry("/right-to-know", "monthly", 0.5),
    entry("/about", "monthly", 0.4),
    entry("/more", "monthly", 0.3),
    ...constituencies.map((c) =>
      entry(`/constituencies/${c.level}/${c.eci_code}`, "daily", 0.8),
    ),
    ...districts.flatMap((d) => [
      entry(`/d/${d.lgd_code}`, "weekly", 0.7),
      entry(`/news/d/${d.lgd_code}`, "hourly", 0.6),
    ]),
  ];
}
