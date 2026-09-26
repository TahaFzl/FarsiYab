import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { logout } from "@/app/[lang]/admin/actions";
import { admin } from "@/lib/admin";
import { getDictionary } from "@/lib/dictionaries";
import { formatNumber, hasLocale } from "@/lib/i18n";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function AdminLayout({ children, params }: LayoutProps<"/[lang]/admin">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const t = dict.admin;
  const overview = await admin.overview(lang);
  const badge = (n: number) =>
    n > 0 ? (
      <span className="ms-1 rounded-full bg-danger px-1.5 text-xs text-white">{formatNumber(lang, n)}</span>
    ) : null;
  const links = [
    { href: "", label: t.nav.overview },
    { href: "/submissions", label: t.nav.submissions, badge: badge(overview.pending_submissions) },
    { href: "/reports", label: t.nav.reports, badge: badge(overview.open_reports) },
    { href: "/labels", label: t.nav.labels },
    { href: "/sources", label: t.nav.sources },
  ];
  return (
    <div className="space-y-6">
      <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border pb-3 text-sm">
        <span className="font-bold">{t.title}</span>
        {links.map((l) => (
          <Link key={l.href} href={`/${lang}/admin${l.href}`} className="text-muted hover:text-foreground">
            {l.label}
            {l.badge}
          </Link>
        ))}
        <form action={logout} className="ms-auto">
          <input type="hidden" name="lang" value={lang} />
          <button type="submit" className="text-muted hover:text-danger">
            {t.nav.logout}
          </button>
        </form>
      </nav>
      {children}
    </div>
  );
}
