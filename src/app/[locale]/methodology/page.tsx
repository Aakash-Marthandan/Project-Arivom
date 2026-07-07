import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/methodology">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "methodology" });
  return { title: t("title"), description: t("intro") };
}

export default async function MethodologyPage({
  params,
}: PageProps<"/[locale]/methodology">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("methodology");

  const principles = ["transparency", "neutrality", "craft"] as const;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10">
      <h1 className="font-heading text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 text-lg leading-relaxed text-muted-foreground">
        {t("intro")}
      </p>

      <section aria-labelledby="principles-title" className="mt-10">
        <h2 id="principles-title" className="font-heading text-2xl font-bold">
          {t("principles.title")}
        </h2>
        <div className="mt-4 space-y-6">
          {principles.map((key) => (
            <div key={key}>
              <h3 className="font-heading text-lg font-semibold">
                {t(`principles.${key}.title`)}
              </h3>
              <p className="mt-1 leading-relaxed text-muted-foreground">
                {t(`principles.${key}.body`)}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="data-title" className="mt-10">
        <h2 id="data-title" className="font-heading text-2xl font-bold">
          {t("currentData.title")}
        </h2>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          {t("currentData.body")}
        </p>
      </section>

      <section aria-labelledby="education-method-title" className="mt-10">
        <h2 id="education-method-title" className="font-heading text-2xl font-bold">
          {t("education.title")}
        </h2>
        <div className="mt-2 space-y-3">
          {(["source", "computed", "withheld", "facilities"] as const).map(
            (key) => (
              <p key={key} className="leading-relaxed text-muted-foreground">
                {t(`education.${key}`)}
              </p>
            ),
          )}
        </div>
      </section>

      <section aria-labelledby="stories-method-title" className="mt-10">
        <h2 id="stories-method-title" className="font-heading text-2xl font-bold">
          {t("stories.title")}
        </h2>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          {t("stories.intro")}
        </p>
        <div className="mt-3 space-y-3">
          {(
            [
              "pool",
              "classification",
              "priority",
              "differ",
              "titles",
              "actorBlind",
              "interim",
            ] as const
          ).map((key) => (
            <p key={key} className="leading-relaxed text-muted-foreground">
              {t(`stories.${key}`)}
            </p>
          ))}
        </div>
      </section>

      <section aria-labelledby="corrections-title" className="mt-10">
        <h2 id="corrections-title" className="font-heading text-2xl font-bold">
          {t("corrections.title")}
        </h2>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          {t("corrections.body")}
        </p>
      </section>

      <p className="mt-12 rounded-md border border-border bg-secondary/50 p-4 text-sm leading-relaxed text-muted-foreground">
        {t("wip")}
      </p>
    </div>
  );
}
