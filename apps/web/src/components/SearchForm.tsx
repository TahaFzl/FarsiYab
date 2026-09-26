"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { CityPicker, type KnownCity, type PickedCity } from "@/components/CityPicker";
import { searchHref, type CategoryOption } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

export interface SearchFormText {
  city: string;
  cityPlaceholder: string;
  searchingCities: string;
  noCity: string;
  cityFailed: string;
  addingCity: string;
  categories: string;
  categoriesHint: string;
  search: string;
  needCategory: string;
  needCity: string;
}

interface Props {
  lang: Locale;
  text: SearchFormText;
  known: KnownCity[];
  countryNames: Record<string, string>;
  categories: CategoryOption[];
  initial?: { country: string; city: string; name: string; categories: string[] };
  compact?: boolean;
}

export function SearchForm({ lang, text, known, countryNames, categories, initial, compact }: Props) {
  const router = useRouter();
  const [picked, setPicked] = useState<PickedCity | null>(
    initial ? { country: initial.country, city: initial.city, name: initial.name } : null,
  );
  const [selected, setSelected] = useState<string[]>(initial?.categories ?? []);
  const [error, setError] = useState("");
  const [preparing, setPreparing] = useState(false);

  function toggle(slug: string) {
    setSelected((current) =>
      current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
    );
    setError("");
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!picked) return setError(text.needCity);
    if (selected.length === 0) return setError(text.needCategory);
    router.push(searchHref(lang, { country: picked.country, city: picked.city, categories: selected }));
  }

  return (
    <form
      onSubmit={submit}
      className={`space-y-5 rounded-2xl border border-border bg-surface shadow-sm ${compact ? "p-4" : "p-5 sm:p-7"}`}
    >
      <CityPicker
        lang={lang}
        text={{
          city: text.city,
          cityPlaceholder: text.cityPlaceholder,
          searching: text.searchingCities,
          noMatch: text.noCity,
          failed: text.cityFailed,
          adding: text.addingCity,
        }}
        known={known}
        countryNames={countryNames}
        value={picked}
        onChange={(city) => {
          setPicked(city);
          setError("");
        }}
        onBusy={setPreparing}
      />

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
          disabled={preparing}
          className="rounded-lg bg-primary px-8 py-2.5 font-semibold text-white hover:bg-primary-strong focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-60"
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
