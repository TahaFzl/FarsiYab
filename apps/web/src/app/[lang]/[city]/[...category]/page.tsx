import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ResultCard } from "@/components/ResultCard";
import { ResultsMap } from "@/components/ResultsMap";
import { api, browserApi, flattenCategories, searchHref, type SearchParams } from "@/lib/api";
import { getDictionary } from "@/lib/dictionaries";
import { fill, formatNumber, hasLocale, type Locale } from "@/lib/i18n";
import { cityPath } from "@/lib/site";

async function resolve(lang: Locale, city: string, segments: string[]) {
  const slug = segments.join("/");
  const [cities, categories] = await Promise.all([api.allCities(lang), api.categories(lang)]);
  const info = cities.find((c) => c.slug === city);
  const category = flattenCategories(categories).find((c) => c.slug === slug);
  if (!info || !category) return null;
  const query: SearchParams = { country: info.country, city, categories: [slug], sort: "confidence", page: 1 };
  return { info, category, query, names: Object.fromEntries(flattenCategories(categories).map((c) => [c.slug, c.name])) };
}

export async function generateMetadata({ params }: PageProps<"/[lang]/[city]/[...category]">): Promise<Metadata> {
  const { lang, city, category } = await params;
  if (!hasLocale(lang)) return {};
  const [dict, found] = await Promise.all([getDictionary(lang), resolve(lang, city, category)]);
  if (!found) return {};
  const slug = found.category.slug;
  const count = found.info.category_counts[slug] ?? 0;
  const values = { category: found.category.name, city: found.info.name, count: formatNumber(lang, count) };
  return {
    title: fill(dict.seo.categoryTitle, values),
    description: fill(dict.seo.categoryDescription, values),
    alternates: {
      canonical: cityPath(lang, city, slug),
      languages: { fa: cityPath("fa", city, slug), en: cityPath("en", city, slug) },
    },
    // A category with nothing to show is not worth a search engine's visit.
    robots: count ? undefined : { index: false },
  };
}

export default async function CategoryPage({ params }: PageProps<"/[lang]/[city]/[...category]">) {
  const { lang, city, category } = await params;
  if (!hasLocale(lang)) notFound();
  const [dict, found] = await Promise.all([getDictionary(lang), resolve(lang, city, category)]);
  if (!found) notFound();
  const { info, query, names } = found;
  const data = await api.search(lang, query);
  const values = { category: found.category.name, city: info.name };
  return (
    <div className="space-y-6">
      <nav className="text-sm text-muted">
        <Link href={cityPath(lang, city)} className="hover:text-foreground">
          {info.name}
        </Link>
        {" / "}
        <span>{found.category.name}</span>
      </nav>
      <header className="space-y-2">
        <h1 className="text-2xl font-extrabold">{fill(dict.seo.categoryTitle, values)}</h1>
        <p className="text-sm text-muted">
          {fill(dict.results.count, { count: formatNumber(lang, data.total) })} ·{" "}
          <Link href={searchHref(lang, query)} className="text-primary hover:underline">
            {dict.seo.seeAll}
          </Link>
        </p>
      </header>
      {data.total > 0 && <ResultsMap markersUrl={browserApi.markers(query)} lang={lang} text={dict.map} />}
      {data.results.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-8 text-center">{dict.seo.empty}</p>
      ) : (
        <ol className="space-y-4">
          {data.results.map((r) => (
            <li key={r.id} id={`b-${r.id}`} className="scroll-mt-4">
              <ResultCard result={r} lang={lang} dict={dict} categoryNames={names} />
            </li>
          ))}
        </ol>
      )}
      {data.total > data.results.length && (
        <p className="text-center">
          <Link href={searchHref(lang, { ...query, page: 2 })} className="text-primary hover:underline">
            {dict.seo.seeAll}
          </Link>
        </p>
      )}
    </div>
  );
}
