"use client";

import { Home, Landmark, MoreHorizontal, Newspaper, Search } from "lucide-react";
import { Link, usePathname } from "@/i18n/navigation";

export interface TabItem {
  href: "/" | "/news" | "/constituencies" | "/government" | "/more";
  label: string;
}

const ICONS = {
  "/": Home,
  "/news": Newspaper,
  "/constituencies": Search,
  "/government": Landmark,
  "/more": MoreHorizontal,
} as const;

/**
 * Mobile bottom navigation (D-023). Thumb-reach, five tabs, active state
 * in peacock. Hidden on md+ where the header carries the same IA. Labels
 * arrive as props from the server — no client message catalogs.
 */
export function TabBar({ items }: { items: TabItem[] }) {
  const pathname = usePathname();
  const isActive = (href: TabItem["href"]) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/85 md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <ul
        className="mx-auto grid max-w-lg grid-cols-5"
        style={{ height: "var(--tabbar-h)" }}
      >
        {items.map((item) => {
          const Icon = ICONS[item.href];
          const active = isActive(item.href);
          return (
            <li key={item.href} className="flex">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`press flex flex-1 flex-col items-center justify-center gap-0.5 text-[10px] font-bold ${
                  active ? "text-primary" : "text-muted-foreground"
                }`}
              >
                <Icon
                  aria-hidden="true"
                  className="size-[21px]"
                  strokeWidth={active ? 2.4 : 1.8}
                />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
