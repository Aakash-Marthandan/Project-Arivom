import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { ChevronRight } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { ForgetFootprints } from "@/components/forget-footprints";
import { removePlace } from "@/lib/places-actions";
import { getMyPlaces } from "@/lib/places";
import { getPlaceCards } from "@/lib/queries";

// The "More" tab (M7.5): my places management plus the trust surfaces.

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/more">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "more" });
  return { title: t("title") };
}

export default async function MorePage({
  params,
}: PageProps<"/[locale]/more">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const isTa = locale === "ta";

  const [t, tc, places] = await Promise.all([
    getTranslations("more"),
    getTranslations("common"),
    getMyPlaces(),
  ]);
  const cards = places.length ? await getPlaceCards(places) : [];

  const explore = [
    { href: "/constituencies" as const, label: tc("nav.search") },
    { href: "/government" as const, label: tc("nav.government") },
    { href: "/vacancies" as const, label: tc("nav.vacancies") },
  ];
  const trust = [
    { href: "/methodology" as const, label: tc("nav.methodology") },
    { href: "/freshness" as const, label: tc("nav.freshness") },
    { href: "/corrections" as const, label: tc("nav.corrections") },
    { href: "/right-to-know" as const, label: tc("nav.rightToKnow") },
    { href: "/about" as const, label: t("aboutLink") },
  ];

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>

      <section className="mt-8">
        <h2 className="text-xs font-bold uppercase tracking-widest text-primary">
          {t("placesTitle")}
        </h2>
        {cards.length === 0 ? (
          <div className="mt-3 rounded-xl border border-border bg-secondary/50 p-5">
            <p className="text-sm text-muted-foreground">{t("noPlaces")}</p>
            <Link
              href="/locate"
              className="press mt-3 inline-block rounded-lg bg-primary px-4 py-2 text-sm font-bold text-primary-foreground"
            >
              {t("locateCta")}
            </Link>
          </div>
        ) : (
          <>
            <ul className="mt-3 space-y-2">
              {cards.map((card) => (
                <li
                  key={`${card.level}:${card.eci_code}`}
                  className="flex items-center justify-between gap-3 rounded-xl border border-border bg-card p-3.5"
                >
                  <Link
                    href={`/constituencies/${card.level}/${card.eci_code}`}
                    className="min-w-0 font-heading text-[15px] font-bold underline-offset-4 hover:underline"
                  >
                    {isTa ? card.name_ta : card.name_en}
                    <span className="ms-2 text-xs font-medium text-muted-foreground">
                      {card.level.toUpperCase()} {card.eci_code}
                    </span>
                  </Link>
                  <form action={removePlace}>
                    <input type="hidden" name="level" value={card.level} />
                    <input type="hidden" name="code" value={card.eci_code} />
                    <button
                      type="submit"
                      className="press rounded-lg border border-border px-3 py-1.5 text-xs font-bold text-muted-foreground hover:text-destructive"
                    >
                      {t("remove")}
                    </button>
                  </form>
                </li>
              ))}
            </ul>
            {/* Discovery stays available after onboarding (audit): adding
                another place shouldn't require clearing the list. */}
            <p className="mt-3">
              <Link
                href="/locate"
                className="text-sm font-medium text-primary underline-offset-4 hover:underline"
              >
                {t("locateCta")} →
              </Link>
            </p>
          </>
        )}
        {/* The knowledge map's device memory is erasable where the rest
            of the device's data lives (D-035: forgetting must be as easy
            as remembering). */}
        <ForgetFootprints
          note={t("footprints.note")}
          action={t("footprints.forget")}
          done={t("footprints.done")}
        />
      </section>

      {[
        { heading: t("sections.explore"), links: explore },
        { heading: t("sections.trust"), links: trust },
      ].map((group) => (
        <section key={group.heading} className="mt-8">
          <h2 className="text-xs font-bold uppercase tracking-widest text-primary">
            {group.heading}
          </h2>
          <ul className="mt-3 divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
            {group.links.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="press flex items-center justify-between px-4 py-3.5 text-[15px] font-semibold"
                >
                  {link.label}
                  <ChevronRight
                    aria-hidden="true"
                    className="size-4 text-muted-foreground"
                  />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
