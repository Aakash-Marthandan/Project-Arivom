import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default async function HomePage({ params }: PageProps<"/[locale]">) {
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
      <section className="py-16 sm:py-24">
        <h1 className="max-w-3xl font-heading text-4xl font-extrabold leading-snug tracking-tight sm:text-5xl sm:leading-snug">
          {t("hero.title")}
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
          {t("hero.subtitle")}
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link href="/constituencies">{t("hero.browseCta")}</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/methodology">{t("hero.methodologyCta")}</Link>
          </Button>
        </div>
      </section>

      <section aria-labelledby="pillars-title" className="py-8">
        <h2 id="pillars-title" className="sr-only">
          {t("pillars.title")}
        </h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {pillars.map(({ key, accent }) => (
            <Card key={key} className={`border-t-4 ${accent} shadow-none`}>
              <CardHeader>
                <CardTitle className="font-heading text-lg">
                  {t(`pillars.${key}.title`)}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {t(`pillars.${key}.body`)}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section aria-labelledby="status-title" className="py-12">
        <div className="rounded-lg border border-border bg-secondary/50 p-6">
          <h2 id="status-title" className="font-heading text-xl font-bold">
            {t("status.title")}
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted-foreground">
            {t("status.body")}
          </p>
          <p className="mt-3 text-sm text-muted-foreground">
            {t.rich("status.note", {
              link: (chunks) => (
                <Link
                  href="/freshness"
                  className="font-medium text-primary underline underline-offset-4"
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
