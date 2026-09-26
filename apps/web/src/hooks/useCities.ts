"use client";

import { useEffect, useState } from "react";

import { browserApi, type CityOption } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

/** Cities of the chosen country, fetched when the country changes. */
export function useCities(
  country: string,
  lang: Locale,
  initial: CityOption[] = [],
  onLoaded?: (cities: CityOption[]) => void,
) {
  const [cities, setCities] = useState<CityOption[]>(initial);
  const [loadedFor, setLoadedFor] = useState(initial.length ? country : "");

  useEffect(() => {
    if (!country || loadedFor === country) return;
    let cancelled = false;
    fetch(browserApi.cities(country, lang))
      .then((r) => (r.ok ? r.json() : []))
      .then((data: CityOption[]) => {
        if (cancelled) return;
        setCities(data);
        setLoadedFor(country);
        onLoaded?.(data);
      })
      .catch(() => {
        if (!cancelled) setLoadedFor(country);
      });
    return () => {
      cancelled = true;
    };
  }, [country, lang, loadedFor, onLoaded]);

  return { cities, loading: country !== "" && loadedFor !== country };
}
