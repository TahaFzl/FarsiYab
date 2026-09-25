"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { browserApi, searchHref, type CategoryOption, type CityOption, type Country } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

export interface SearchFormText {
  country: string;
  city: string;
  chooseCountry: string;
  chooseCity: string;
  loadingCities: string;
  categories: string;
  categoriesHint: string;
  search: string;
  needCategory: string;
  needCity: string;
}

interface Props {
  lang: Locale;
  text: SearchFormText;
  countries: Country[];
  categories: CategoryOption[];
  initial?: { country: string; city: string; categories: string[]; cities: CityOption[] };
  compact?: boolean;
}

export function SearchForm({ lang, text, countries, categories, initial, compact }: Props) {
  const router = useRouter();
  const [country, setCountry] = useState(initial?.country ?? "");
  const [city, setCity] = useState(initial?.city ?? "");
  const [cities, setCities] = useState<CityOption[]>(initial?.cities ?? []);
  const [loadedFor, setLoadedFor] = useState(initial?.cities.length ? initial.country : "");
  const [selected, setSelected] = useState<string[]>(initial?.categories ?? []);
  const [error, setError] = useState("");

  const loadingCities = country !== "" && loadedFor !== country;

  useEffect(() => {
    if (!country || loadedFor === country) return;
    let cancelled = false;
    fetch(browserApi.cities(country, lang))
      .then((r) => (r.ok ? r.json() : []))
      .then((data: CityOption[]) => {
        if (cancelled) return;
        setCities(data);
        setLoadedFor(country);
        if (data.length === 1) setCity(data[0].slug);
      })
      .catch(() => {
        if (!cancelled) setLoadedFor(country);
      });
    return () => {
      cancelled = true;
    };
  }, [country, lang, loadedFor]);

  function toggle(slug: string) {
    setSelected((current) =>
      current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
    );
    setError("");
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!country || !city) return setError(text.needCity);
    if (selected.length === 0) return setError(text.needCategory);
    router.push(searchHref(lang, { country, city, categories: selected }));
  }

  const selectClass =
    "w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-base focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60";

  return (
    <form
      onSubmit={submit}
      className={`space-y-5 rounded-2xl border border-border bg-surface shadow-sm ${compact ? "p-4" : "p-5 sm:p-7"}`}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">{text.country}</span>
          <select
            className={selectClass}
            value={country}
            onChange={(e) => {
              setCountry(e.target.value);
              setCity("");
              setCities([]);
              setError("");
            }}
          >
            <option value="">{text.chooseCountry}</option>
            {countries.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">{text.city}</span>
          <select
            className={selectClass}
            value={city}
            disabled={!country || loadingCities}
            onChange={(e) => {
              setCity(e.target.value);
              setError("");
            }}
          >
            <option value="">{loadingCities ? text.loadingCities : text.chooseCity}</option>
            {cities.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset className="space-y-2.5">
        <legend className="text-sm font-medium">
          {text.categories} <span className="font-normal text-muted">({text.categoriesHint})</span>
        </legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {categories.map((c) => {
            const active = selected.includes(c.slug);
            return (
              <button
                key={c.slug}
                type="button"
                aria-pressed={active}
                onClick={() => toggle(c.slug)}
                className={`rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
                  active
                    ? "border-primary bg-primary text-white"
                    : "border-border bg-background hover:border-primary hover:text-primary"
                }`}
              >
                {c.name}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="flex flex-wrap items-center gap-4">
        <button
          type="submit"
          className="rounded-lg bg-primary px-8 py-2.5 font-semibold text-white hover:bg-primary-strong focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          {text.search}
        </button>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </form>
  );
}
