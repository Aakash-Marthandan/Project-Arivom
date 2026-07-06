import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Catamaran, Noto_Sans_Tamil } from "next/font/google";
import { routing } from "@/i18n/routing";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { SwRegister } from "@/components/sw-register";
import { TabBar } from "@/components/tab-bar";
import "../globals.css";

const bodyFont = Noto_Sans_Tamil({
  subsets: ["tamil", "latin"],
  variable: "--font-body",
  display: "swap",
});

const displayFont = Catamaran({
  subsets: ["tamil", "latin"],
  variable: "--font-display",
  display: "swap",
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "common" });
  return {
    title: {
      default: `${t("appName")} — ${t("tagline")}`,
      template: `%s · ${t("appName")}`,
    },
    description: t("footer.mission"),
  };
}

export const viewport = {
  themeColor: "#16646e",
};

export default async function LocaleLayout({
  children,
  params,
}: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  setRequestLocale(locale);

  const t = await getTranslations("common");
  const tabs = [
    { href: "/" as const, label: t("nav.home") },
    { href: "/news" as const, label: t("nav.news") },
    { href: "/constituencies" as const, label: t("nav.search") },
    { href: "/government" as const, label: t("nav.government") },
    { href: "/more" as const, label: t("nav.more") },
  ];

  return (
    <html lang={locale} className={`${bodyFont.variable} ${displayFont.variable}`}>
      <body className="has-tabbar flex min-h-svh flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
        >
          {t("skipToContent")}
        </a>
        {/* Client components receive strings via props; messages stay on the
            server to keep the HTML payload small on low-end connections. */}
        <NextIntlClientProvider messages={{}}>
          <SiteHeader />
          <main id="main" className="flex-1">
            {children}
          </main>
          <SiteFooter />
          <TabBar items={tabs} />
        </NextIntlClientProvider>
        <SwRegister />
      </body>
    </html>
  );
}
