import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { getDictionary } from "@/lib/dictionaries";
import { direction, hasLocale, locales } from "@/lib/i18n";

import "../globals.css";

const vazirmatn = localFont({
  src: "../fonts/Vazirmatn-Variable.woff2",
  variable: "--font-vazirmatn",
  display: "swap",
  weight: "100 900",
});

export function generateStaticParams() {
  return locales.map((lang) => ({ lang }));
}

export async function generateMetadata({ params }: LayoutProps<"/[lang]">): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return {
    title: { default: `${dict.site.name} | ${dict.site.tagline}`, template: `%s | ${dict.site.name}` },
    description: dict.site.description,
    alternates: { languages: { fa: "/fa", en: "/en" } },
  };
}

export default async function RootLayout({ children, params }: LayoutProps<"/[lang]">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);

  return (
    <html lang={lang} dir={direction(lang)} className={`${vazirmatn.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="border-b border-border bg-surface">
          <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <Link href={`/${lang}`} className="text-xl font-extrabold text-primary">
              {dict.site.name}
            </Link>
            <div className="flex flex-1 flex-wrap items-center gap-x-5 gap-y-1 text-sm text-muted">
              <Link href={`/${lang}`} className="hover:text-foreground">
                {dict.nav.search}
              </Link>
              <Link href={`/${lang}/how-it-works`} className="hover:text-foreground">
                {dict.nav.howItWorks}
              </Link>
              <Link href={`/${lang}/about`} className="hover:text-foreground">
                {dict.nav.about}
              </Link>
              <Link href={`/${lang}/privacy`} className="hover:text-foreground">
                {dict.nav.privacy}
              </Link>
            </div>
            <Suspense>
              <LanguageSwitcher lang={lang} label={dict.nav.switchLanguage} />
            </Suspense>
          </nav>
        </header>

        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>

        <footer className="border-t border-border bg-surface text-xs leading-6 text-muted">
          <div className="mx-auto max-w-5xl space-y-1 px-4 py-5">
            <p>{dict.footer.disclaimer}</p>
            <p>{dict.footer.attribution}</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
