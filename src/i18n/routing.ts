import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  // Tamil is the default locale; both locales are first-class (full parity).
  locales: ["ta", "en"],
  defaultLocale: "ta",
  localePrefix: "always",
});

export type Locale = (typeof routing.locales)[number];
