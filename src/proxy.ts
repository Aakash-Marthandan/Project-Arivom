import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // Skip Next.js internals and all static assets.
  matcher: "/((?!api|_next|_vercel|.*\\..*).*)",
};
