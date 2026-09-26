import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ErrorNotice } from "@/components/ErrorNotice";
import { SubmitForm } from "@/components/SubmitForm";
import { api, flattenCategories, type Category, type CityInfo, type Country } from "@/lib/api";
import { getDictionary } from "@/lib/dictionaries";
import { hasLocale } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[lang]/submit">): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return { title: dict.submit.title, description: dict.submit.intro };
}

export default async function SubmitPage({ params }: PageProps<"/[lang]/submit">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  let countries: Country[];
  let categories: Category[];
  let cities: CityInfo[];
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
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-extrabold">{dict.submit.title}</h1>
        <p className="text-muted">{dict.submit.intro}</p>
      </header>
      <SubmitForm
        lang={lang}
        text={dict.submit}
        cityText={dict.form}
        known={cities}
        countryNames={Object.fromEntries(countries.map((c) => [c.code, c.name]))}
        categories={flattenCategories(categories)}
      />
    </div>
  );
}
