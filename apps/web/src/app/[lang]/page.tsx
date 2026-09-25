import { notFound } from "next/navigation";

import { ErrorNotice } from "@/components/ErrorNotice";
import { SearchForm } from "@/components/SearchForm";
import { api, flattenCategories, type Category, type Country } from "@/lib/api";
import { getDictionary } from "@/lib/dictionaries";
import { hasLocale } from "@/lib/i18n";

export default async function Home({ params }: PageProps<"/[lang]">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);

  let countries: Country[] = [];
  let categories: Category[] = [];
  try {
    [countries, categories] = await Promise.all([api.countries(lang), api.categories(lang)]);
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
        countries={countries}
        categories={flattenCategories(categories)}
      />
    </div>
  );
}
