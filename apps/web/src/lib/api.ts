/**
 * Types and fetch helpers for the FarsiYab API (docs/05-api.md).
 *
 * Server components call the API directly (FARSIYAB_API_URL); the browser uses
 * relative /api/... URLs, which next.config.ts rewrites to the same server
 * (and which Caddy routes straight to the API in production).
 */
import type { Locale } from "./i18n";

export type ConfidenceLabel = "high" | "medium" | "low";

export interface Country {
  code: string;
  name: string;
  name_en: string;
  city_count: number;
}

export interface CityOption {
  slug: string;
  name: string;
  name_en: string;
}

export interface Category {
  slug: string;
  name: string;
  mvp: boolean;
  children: { slug: string; name: string }[];
}

export interface SourceRef {
  id: string;
  name: string;
  url: string | null;
  via?: string[];
}

export interface EvidenceItem {
  signal: string;
  label: string;
  snippet: string;
  url: string | null;
  source: string;
  weight: number;
}

export interface Result {
  id: string;
  name: { fa: string | null; latin: string | null };
  categories: string[];
  address: string | null;
  location: { lat: number; lng: number } | null;
  contact: {
    phone: string | null;
    website: string | null;
    facebook?: string;
    instagram?: string;
    telegram?: string;
  };
  confidence: { score: number; label: ConfidenceLabel | null };
  sources: SourceRef[];
  evidence: EvidenceItem[];
  links: { google_maps: string; apple_maps: string; openstreetmap?: string };
  last_verified_at: string;
}

export interface SearchResponse {
  city: { slug: string; country: string; name: string; last_indexed_at: string | null };
  categories: string[];
  results: Result[];
  total: number;
  page: number;
  page_size: number;
  live_search: { job_id: string; status: string } | null;
  registry_links: RegistryLink[];
}

/** An official registry to check the user can search themselves (link only, never crawled). */
export interface RegistryLink {
  id: string;
  name: string;
  url: string;
  hint: string;
}

export interface SearchParams {
  country: string;
  city: string;
  categories: string[];
  sort?: "confidence" | "name";
  min_confidence?: ConfidenceLabel;
  page?: number;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export function serverBase(): string {
  return process.env.FARSIYAB_API_URL ?? "http://127.0.0.1:8000";
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${serverBase()}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  return response.json() as Promise<T>;
}

export const api = {
  countries: (lang: Locale) => get<Country[]>(`/api/v1/countries?lang=${lang}`),
  categories: (lang: Locale) => get<Category[]>(`/api/v1/categories?lang=${lang}`),
  cities: (country: string, lang: Locale) =>
    get<CityOption[]>(`/api/v1/countries/${encodeURIComponent(country)}/cities?lang=${lang}`),
  search: (lang: Locale, params: SearchParams) => {
    const query = new URLSearchParams({
      country: params.country,
      city: params.city,
      categories: params.categories.join(","),
      lang,
      sort: params.sort ?? "confidence",
      min_confidence: params.min_confidence ?? "low",
      page: String(params.page ?? 1),
    });
    return get<SearchResponse>(`/api/v1/search?${query}`);
  },
};

/** Browser-side URLs (relative, rewritten or proxied to the API). */
export const browserApi = {
  cities: (country: string, lang: Locale) => `/api/v1/countries/${country}/cities?lang=${lang}`,
  jobStream: (jobId: string) => `/api/v1/search/jobs/${jobId}/stream`,
  report: (businessId: string) => `/api/v1/businesses/${businessId}/reports`,
  submissions: "/api/v1/submissions",
};

export type CategoryOption = { slug: string; name: string };

/** Parents followed by their children (e.g. doctor, dentist) for pickers and labels. */
export function flattenCategories(categories: Category[]): CategoryOption[] {
  return categories.flatMap((c) => [{ slug: c.slug, name: c.name }, ...c.children]);
}

export function searchHref(lang: Locale, params: SearchParams): string {
  const query = new URLSearchParams({
    country: params.country,
    city: params.city,
    categories: params.categories.join(","),
  });
  if (params.sort && params.sort !== "confidence") query.set("sort", params.sort);
  if (params.min_confidence && params.min_confidence !== "low") {
    query.set("min_confidence", params.min_confidence);
  }
  if (params.page && params.page > 1) query.set("page", String(params.page));
  return `/${lang}/search?${query}`;
}
