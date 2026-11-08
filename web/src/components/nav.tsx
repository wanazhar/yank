"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "New" },
  { href: "/queue/", label: "Queue" },
  { href: "/history/", label: "History" },
  { href: "/settings/", label: "Settings" },
] as const;

export function Nav() {
  const path = usePathname();

  return (
    <nav className="glass-nav inline-flex text-[11px] font-medium tracking-tight" aria-label="Main">
      {links.map((l) => {
        const active =
          path === l.href || path === l.href.replace(/\/$/, "") || (l.href === "/" && path === "");
        return (
          <Link
            key={l.href}
            href={l.href}
            className={cn(
              "relative z-[1] rounded-full px-2.5 py-1.5 transition-all duration-300",
              active
                ? "glass-nav-active"
                : "text-muted-foreground hover:text-foreground/90",
            )}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
