"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import type { Locale } from "@/lib/i18n";

/** Same page and query, other language. */
export function LanguageSwitcher({ lang, label }: { lang: Locale; label: string }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const other: Locale = lang === "fa" ? "en" : "fa";
  const path = pathname.replace(/^\/(fa|en)(?=\/|$)/, `/${other}`);
  const query = searchParams.toString();

  return (
    <Link
      href={query ? `${path}?${query}` : path}
      hrefLang={other}
      className="rounded-full border border-border px-3 py-1 text-sm hover:border-primary hover:text-primary"
    >
      {label}
    </Link>
  );
}
