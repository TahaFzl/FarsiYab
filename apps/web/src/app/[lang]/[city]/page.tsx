import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type CityInfo } from "@/lib/api";
import { getDictionary } from "@/lib/dictionaries";
import { fill, formatDate, formatNumber, hasLocale, type Locale } from "@/lib/i18n";
import { cityPath } from "@/lib/site";

async function findCity(lang: Locale, slug: string): Promise<CityInfo | undefined> {
  return (await api.allCities(lang)).find((c) => c.slug === slug);
}

export async function generateMetadata({ params }: PageProps<"/[lang]/[city]">): Promise<Metadata> {
  const { lang, city } = await params;
  if (!hasLocale(lang)) return {};
  const [dict, info] = await Promise.all([getDictionary(lang), findCity(lang, city)]);
  if (!info) return {};
  return {
    title: fill(dict.seo.cityTitle, { city: info.name }),
    description: fill(dict.seo.cityIntro, { city: info.name }),
    alternates: {
      canonical: cityPath(lang, city),
      languages: { fa: cityPath("fa", city), en: cityPath("en", city) },
    },
  };
}

export default async function CityPage({ params }: PageProps<"/[lang]/[city]">) {
  const { lang, city } = await params;
  if (!hasLocale(lang)) notFound();
  const [dict, info, categories] = await Promise.all([
    getDictionary(lang),
    findCity(lang, city),
    api.categories(lang),
  ]);
  if (!info) notFound();
  const listed = categories.filter((c) => info.category_counts[c.slug]);
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-extrabold">{fill(dict.seo.cityTitle, { city: info.name })}</h1>
        <p className="leading-7 text-muted">{fill(dict.seo.cityIntro, { city: info.name })}</p>
        {info.last_indexed_at && (
          <p className="text-sm text-muted">
            {fill(dict.results.lastIndexed, { date: formatDate(lang, info.last_indexed_at) })}
          </p>
        )}
      </header>
      <section className="space-y-3">
        <h2 className="text-lg font-bold">{dict.seo.browse}</h2>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {listed.map((c) => (
            <li key={c.slug}>
              <Link
                href={cityPath(lang, city, c.slug)}
                className="flex items-center justify-between rounded-xl border border-border bg-surface px-4 py-3 hover:border-primary"
              >
                <span className="font-medium">{c.name}</span>
                <span className="text-sm text-muted">
                  {fill(dict.seo.results, { count: formatNumber(lang, info.category_counts[c.slug]) })}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
