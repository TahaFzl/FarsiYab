import type { MetadataRoute } from "next";

import { api } from "@/lib/api";
import { locales } from "@/lib/i18n";
import { cityPath, siteUrl } from "@/lib/site";

// Rebuilt at most once an hour; cities are re-indexed weekly.
export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteUrl();
  const both = (path: (lang: string) => string) =>
    ({ languages: Object.fromEntries(locales.map((l) => [l, `${base}${path(l)}`])) });
  const pages: MetadataRoute.Sitemap = ["", "/how-it-works", "/about", "/privacy", "/submit"].flatMap((p) =>
    locales.map((lang) => ({ url: `${base}/${lang}${p}`, alternates: both((l) => `/${l}${p}`) })),
  );
  let cities: Awaited<ReturnType<typeof api.allCities>> = [];
  try {
    cities = await api.allCities("en");
  } catch {
    return pages; // API down during a build: still publish the static pages
  }
  for (const city of cities) {
    const lastModified = city.last_indexed_at ?? undefined;
    for (const lang of locales) {
      pages.push({ url: `${base}${cityPath(lang, city.slug)}`, lastModified, alternates: both((l) => cityPath(l, city.slug)) });
      for (const [category, count] of Object.entries(city.category_counts)) {
        if (!count) continue;
        pages.push({
          url: `${base}${cityPath(lang, city.slug, category)}`,
          lastModified,
          alternates: both((l) => cityPath(l, city.slug, category)),
        });
      }
    }
  }
  return pages;
}
