"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import { browserApi } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

/** A city the site already knows (indexed or added earlier). */
export interface KnownCity {
  slug: string;
  country: string;
  name: string;
  name_en: string;
}

export interface PickedCity {
  country: string;
  city: string;
  name: string;
}

interface Suggestion {
  osm_id: string;
  name: string;
  state: string | null;
  country: string | null;
  country_code: string | null;
}

type Option =
  | { kind: "known"; key: string; label: string; detail: string; city: KnownCity }
  | { kind: "place"; key: string; label: string; detail: string; place: Suggestion };

export interface CityPickerText {
  city: string;
  cityPlaceholder: string;
  searching: string;
  noMatch: string;
  failed: string;
  adding: string;
}

const MIN_CHARS = 2;
const DEBOUNCE_MS = 300;

function matches(city: KnownCity, query: string): boolean {
  const q = query.toLowerCase();
  return city.name.toLowerCase().includes(q) || city.name_en.toLowerCase().includes(q);
}

export function CityPicker({
  lang,
  text,
  known,
  countryNames,
  value,
  onChange,
  onBusy,
}: {
  lang: Locale;
  text: CityPickerText;
  known: KnownCity[];
  countryNames: Record<string, string>;
  value: PickedCity | null;
  onChange: (city: PickedCity | null) => void;
  /** True while a new city is being prepared, so forms can wait before submitting. */
  onBusy?: (busy: boolean) => void;
}) {
  const id = useId();
  const [query, setQuery] = useState(value?.name ?? "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [places, setPlaces] = useState<Suggestion[]>([]);
  const [state, setState] = useState<"idle" | "searching" | "failed" | "adding">("idle");
  const request = useRef(0);

  const typed = query.trim();
  const searchable = open && typed.length >= MIN_CHARS && typed !== value?.name;

  useEffect(() => {
    if (!searchable) return;
    const mine = ++request.current;
    const timer = setTimeout(() => {
      setState("searching");
      fetch(`/api/v1/places?q=${encodeURIComponent(typed)}&lang=${lang}`)
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((data: Suggestion[]) => {
          if (mine !== request.current) return;
          setPlaces(data);
          setState("idle");
        })
        .catch(() => {
          if (mine === request.current) setState("failed");
        });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchable, typed, lang]);

  const knownOptions: Option[] = (typed && typed !== value?.name ? known.filter((c) => matches(c, typed)) : known)
    .slice(0, 8)
    .map((c) => ({ kind: "known", key: c.slug, label: c.name, detail: countryNames[c.country] ?? c.country, city: c }));
  const knownNames = new Set(known.map((c) => `${c.name_en.toLowerCase()}|${c.country}`));
  const placeOptions: Option[] = searchable
    ? places
        .filter((p) => !knownNames.has(`${p.name.toLowerCase()}|${p.country_code}`))
        .map((p) => ({
          kind: "place",
          key: p.osm_id,
          label: p.name,
          detail: [p.state, p.country].filter(Boolean).join("، "),
          place: p,
        }))
    : [];
  const options = [...knownOptions, ...placeOptions];

  async function pick(option: Option) {
    setOpen(false);
    if (option.kind === "known") {
      setQuery(option.city.name);
      onChange({ country: option.city.country, city: option.city.slug, name: option.city.name });
      return;
    }
    setQuery(option.label);
    setState("adding");
    onBusy?.(true);
    try {
      const response = await fetch(browserApi.addCity(lang), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ osm_id: option.place.osm_id }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const city: { slug: string; country: string; name: string } = await response.json();
      setQuery(city.name);
      setState("idle");
      onChange({ country: city.country, city: city.slug, name: city.name });
    } catch {
      setState("failed");
      onChange(null);
    } finally {
      onBusy?.(false);
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((a) => (options.length ? (a + step + options.length) % options.length : 0));
    } else if (event.key === "Enter" && open && options[active]) {
      event.preventDefault();
      pick(options[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const status =
    state === "adding"
      ? text.adding
      : state === "failed"
        ? text.failed
        : state === "searching"
          ? text.searching
          : searchable && options.length === 0
            ? text.noMatch
            : "";

  return (
    <div className="relative space-y-1.5">
      <label htmlFor={`${id}-input`} className="block text-sm font-medium">
        {text.city}
      </label>
      <input
        id={`${id}-input`}
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        aria-activedescendant={open && options[active] ? `${id}-${options[active].key}` : undefined}
        autoComplete="off"
        placeholder={text.cityPlaceholder}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActive(0);
          if (value) onChange(null);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKeyDown}
        className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-base focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
      />
      {open && options.length > 0 && (
        <ul
          id={`${id}-list`}
          role="listbox"
          className="absolute z-20 max-h-72 w-full overflow-auto rounded-lg border border-border bg-surface py-1 shadow-lg"
        >
          {options.map((option, i) => (
            <li
              key={`${option.kind}-${option.key}`}
              id={`${id}-${option.key}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(option)}
              onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-baseline justify-between gap-3 px-3 py-2 ${i === active ? "bg-primary-soft" : ""}`}
            >
              <bdi className="font-medium">{option.label}</bdi>
              <span className="text-xs text-muted">{option.detail}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="min-h-4 text-xs text-muted" aria-live="polite">
        {status}
      </p>
    </div>
  );
}
