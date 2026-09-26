import Link from "next/link";
import { notFound } from "next/navigation";

import { ErrorNotice } from "@/components/ErrorNotice";
import { SearchForm } from "@/components/SearchForm";
import { api, flattenCategories, type Category, type CityInfo, type Country } from "@/lib/api";
import { getDictionary } from "@/lib/dictionaries";
import { hasLocale } from "@/lib/i18n";
import { cityPath } from "@/lib/site";

export default async function Home({ params }: PageProps<"/[lang]">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);

  let countries: Country[] = [];
  let categories: Category[] = [];
  let cities: CityInfo[] = [];
  try {
    [countries, categories, cities] = await Promise.all([
      api.countries(lang),
      api.categories(lang),
      api.allCities(lang),
    ]);
  } catch {
    return <ErrorNotice message={dict.results.error} />;
  }

  return (
    <div className="space-y-8">
      <section className="space-y-3 pt-4 text-center">
        <h1 className="text-3xl font-extrabold leading-tight sm:text-4xl">{dict.site.tagline}</h1>
        <p className="mx-auto max-w-2xl leading-7 text-muted">{dict.site.description}</p>
      </section>
      <SearchForm
        lang={lang}
        text={dict.form}
        known={cities}
        countryNames={Object.fromEntries(countries.map((c) => [c.code, c.name]))}
        categories={flattenCategories(categories)}
      />
      <section className="space-y-3">
        <h2 className="text-lg font-bold">{dict.seo.browseCities}</h2>
        {countries.map((country) => (
          <div key={country.code} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted">{country.name}:</span>
            {cities
              .filter((c) => c.country === country.code)
              .map((c) => (
                <Link
                  key={c.slug}
                  href={cityPath(lang, c.slug)}
                  className="rounded-full border border-border px-3 py-1 hover:border-primary"
                >
                  {c.name}
                </Link>
              ))}
          </div>
        ))}
      </section>
    </div>
  );
}
