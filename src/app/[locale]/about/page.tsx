import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

// The former marketing home (M1) lives on as /about (M7.5, D-023):
// mission, pillars, and build status, unchanged in substance.

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/about">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "home" });
  return { title: t("hero.title") };
}

export default async function AboutPage({
  params,
}: PageProps<"/[locale]/about">) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("home");

  const pillars = [
    { key: "transparency", accent: "border-t-primary" },
    { key: "neutrality", accent: "border-t-primary/70" },
    { key: "craft", accent: "border-t-primary/40" },
  ] as const;

  return (
    <div className="mx-auto w-full max-w-5xl px-4">
      <section className="py-14 sm:py-20">
        <h1 className="max-w-3xl font-heading text-4xl font-extrabold leading-snug tracking-tight sm:text-5xl sm:leading-snug">
          {t("hero.title")}
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
          {t("hero.subtitle")}
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild size="lg" className="press">
            <Link href="/constituencies">{t("hero.browseCta")}</Link>
          </Button>
          <Button asChild size="lg" variant="outline" className="press">
            <Link href="/methodology">{t("hero.methodologyCta")}</Link>
          </Button>
        </div>
      </section>

      <section className="grid gap-4 pb-14 sm:grid-cols-3">
        {pillars.map((pillar) => (
          <Card key={pillar.key} className={`border-t-4 ${pillar.accent}`}>
            <CardHeader>
              <CardTitle className="font-heading text-lg">
                {t(`pillars.${pillar.key}.title`)}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm leading-relaxed text-muted-foreground">
              {t(`pillars.${pillar.key}.body`)}
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="pb-16">
        <div className="max-w-2xl rounded-md border border-border bg-secondary/50 p-5 text-sm leading-relaxed text-muted-foreground">
          <h2 className="font-heading text-base font-bold text-foreground">
            {t("status.title")}
          </h2>
          <p className="mt-2">{t("status.body")}</p>
          <p className="mt-2">
            {t.rich("status.note", {
              link: (chunks) => (
                <Link
                  href="/freshness"
                  className="text-primary underline underline-offset-4"
                >
                  {chunks}
                </Link>
              ),
            })}
          </p>
        </div>
      </section>
    </div>
  );
}
