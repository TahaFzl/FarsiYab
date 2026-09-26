import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { ErrorNotice } from "@/components/ErrorNotice";
import { LiveSearch } from "@/components/LiveSearch";
import { ResultCard } from "@/components/ResultCard";
import { ResultsMap } from "@/components/ResultsMap";
import { SearchForm } from "@/components/SearchForm";
import {
  api,
  ApiError,
  browserApi,
  flattenCategories,
  searchHref,
  type Category,
  type CityOption,
  type Country,
  type ConfidenceLabel,
  type SearchParams,
  type SearchResponse,
} from "@/lib/api";
import { getDictionary } from "@/lib/dictionaries";
import { fill, formatDate, formatNumber, hasLocale, type Locale } from "@/lib/i18n";

type Query = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value) ?? "";
}

function parse(query: Query): SearchParams | null {
  const country = first(query.country).toUpperCase();
  const city = first(query.city);
  const categories = first(query.categories).split(",").filter(Boolean);
  if (!country || !city || categories.length === 0) return null;
  const sort = first(query.sort) === "name" ? "name" : "confidence";
  const min = first(query.min_confidence);
  const page = Math.max(1, Number(first(query.page)) || 1);
  return {
    country,
    city,
    categories,
    sort,
    min_confidence: (["low", "medium", "high"].includes(min) ? min : "low") as ConfidenceLabel,
    page,
  };
}

export async function generateMetadata({ params }: PageProps<"/[lang]/search">): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return { title: dict.nav.search, robots: { index: false } };
}

export default async function SearchPage({ params, searchParams }: PageProps<"/[lang]/search">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const query = parse(await searchParams);
  if (!query) redirect(`/${lang}`);
  const dict = await getDictionary(lang);

  let data: SearchResponse;
  let categories: Category[];
  let countries: Country[];
  let cities: CityOption[];
  try {
    [data, categories, countries, cities] = await Promise.all([
      api.search(lang, query),
      api.categories(lang),
      api.countries(lang),
      api.cities(query.country, lang),
    ]);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    return <ErrorNotice message={dict.results.error} />;
  }

  const flat = flattenCategories(categories);
  const categoryNames = Object.fromEntries(flat.map((c) => [c.slug, c.name]));
  const requested = query.categories.map((s) => categoryNames[s] ?? s).join(lang === "fa" ? "، " : ", ");
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  const link = (change: Partial<SearchParams>) => searchHref(lang, { ...query, page: 1, ...change });

  return (
    <div className="space-y-6">
      <SearchForm
        lang={lang}
        text={dict.form}
        countries={countries}
        categories={flat}
        initial={{ country: query.country, city: query.city, categories: query.categories, cities }}
        compact
      />

      <header className="space-y-1">
        <h1 className="text-2xl font-extrabold">{fill(dict.results.title, { categories: requested, city: data.city.name })}</h1>
        <p className="text-sm text-muted">
          {fill(dict.results.count, { count: formatNumber(lang, data.total) })}
          {" · "}
          {data.city.last_indexed_at
            ? fill(dict.results.lastIndexed, { date: formatDate(lang, data.city.last_indexed_at) })
            : dict.results.neverIndexed}
        </p>
      </header>

      {data.live_search && (
        <LiveSearch
          jobId={data.live_search.job_id}
          initialStatus={data.live_search.status}
          text={dict.live}
          sourceNames={dict.sources}
        />
      )}

      <Filters lang={lang} dict={dict} query={query} link={link} />

      {data.total > 0 && <ResultsMap markersUrl={browserApi.markers(query)} lang={lang} text={dict.map} />}

      {data.results.length === 0 ? (
        <EmptyState lang={lang} dict={dict} requested={requested} city={data.city.name} />
      ) : (
        <ol className="space-y-4">
          {data.results.map((r) => (
            <li key={r.id} id={`b-${r.id}`} className="scroll-mt-4">
              <ResultCard result={r} lang={lang} dict={dict} categoryNames={categoryNames} />
            </li>
          ))}
        </ol>
      )}

      {data.registry_links.length > 0 && (
        <aside className="space-y-2 rounded-2xl border border-border p-4 text-sm">
          <h2 className="font-bold">{dict.results.registries}</h2>
          <p className="text-muted">{dict.results.registriesHint}</p>
          <ul className="space-y-2">
            {data.registry_links.map((r) => (
              <li key={r.id}>
                <a href={r.url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary hover:underline">
                  {r.name} ↗
                </a>
                <p className="text-muted">{r.hint}</p>
              </li>
            ))}
          </ul>
        </aside>
      )}

      {pages > 1 && (
        <nav className="flex items-center justify-between text-sm">
          {query.page! > 1 ? (
            <Link href={link({ page: query.page! - 1 })} className="text-primary hover:underline">
              {dict.results.previous}
            </Link>
          ) : (
            <span />
          )}
          <span className="text-muted">
            {fill(dict.results.page, { page: formatNumber(lang, query.page!), pages: formatNumber(lang, pages) })}
          </span>
          {query.page! < pages ? (
            <Link href={link({ page: query.page! + 1 })} className="text-primary hover:underline">
              {dict.results.next}
            </Link>
          ) : (
            <span />
          )}
        </nav>
      )}
    </div>
  );
}

function Filters({
  lang,
  dict,
  query,
  link,
}: {
  lang: Locale;
  dict: Awaited<ReturnType<typeof getDictionary>>;
  query: SearchParams;
  link: (change: Partial<SearchParams>) => string;
}) {
  const pill = (active: boolean) =>
    `rounded-full px-3 py-1 ${active ? "bg-foreground text-background" : "border border-border hover:border-primary"}`;
  const levels: ConfidenceLabel[] = ["low", "medium", "high"];
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted">{dict.results.sort}:</span>
        <Link href={link({ sort: "confidence" })} className={pill(query.sort === "confidence")}>
          {dict.results.sortConfidence}
        </Link>
        <Link href={link({ sort: "name" })} className={pill(query.sort === "name")}>
          {dict.results.sortName}
        </Link>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted">{dict.results.minConfidence}:</span>
        {levels.map((level) => (
          <Link key={level} href={link({ min_confidence: level })} className={pill(query.min_confidence === level)} hrefLang={lang}>
            {dict.card.confidence[level]}
          </Link>
        ))}
      </div>
    </div>
  );
}

function EmptyState({
  lang,
  dict,
  requested,
  city,
}: {
  lang: Locale;
  dict: Awaited<ReturnType<typeof getDictionary>>;
  requested: string;
  city: string;
}) {
  const google = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`Persian ${requested} ${city}`)}`;
  return (
    <div className="space-y-2 rounded-2xl border border-dashed border-border p-8 text-center">
      <p className="font-medium">{dict.results.none}</p>
      <p className="text-sm text-muted">
        {dict.results.noneHint}{" "}
        <a href={google} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          Google Maps ↗
        </a>
      </p>
      <p className="text-sm">
        <Link href={`/${lang}/submit`} className="text-primary hover:underline">
          {dict.results.suggest}
        </Link>
      </p>
    </div>
  );
}
