/**
 * Server-side access to the admin API (docs/05-api.md, "ادمین").
 *
 * The admin token lives only in an httpOnly cookie and is sent to the API from
 * the Next.js server; browser code never sees it.
 */
import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, serverBase, type Result } from "./api";
import type { Locale } from "./i18n";

export const ADMIN_COOKIE = "farsiyab_admin";
const COOKIE_DAYS = 7;

export type BusinessStatus = "active" | "hidden" | "closed" | "removed_by_request";

export interface AdminBusiness extends Result {
  status: BusinessStatus;
  city: { slug: string; country: string; name: string };
  label: { is_iranian: boolean; note: string | null; by: string } | null;
}

export interface LevelStats {
  labeled: number;
  iranian: number;
  precision: number | null;
  ci95: [number, number];
}

export interface Precision {
  levels: Record<"high" | "medium" | "low", LevelStats>;
  high_and_medium: number | null;
  goal: number;
  met: boolean;
  target_per_level: number;
}

export interface Overview {
  pending_submissions: number;
  open_reports: number;
  hidden_businesses: number;
  labels: number;
  cities: {
    slug: string;
    country: string;
    name: string;
    last_indexed_at: string | null;
    shown: number;
    failed_sources: Record<string, string>;
  }[];
  precision: Precision;
}

export interface AdminSubmission {
  id: string;
  name: string;
  city: string;
  category: string;
  address: string | null;
  phone: string | null;
  links: string[];
  is_owner: boolean;
  contact_email: string | null;
  note: string | null;
  detected_score: number;
  status: "pending" | "approved" | "rejected";
  created_at: string;
  possible_duplicate: AdminBusiness | null;
  business_id: string | null;
}

export interface ReportGroup {
  business: AdminBusiness;
  reports: {
    id: string;
    reason: "not_iranian" | "closed" | "wrong_info" | "remove_request";
    message: string | null;
    contact_email: string | null;
    created_at: string;
    review_note: string | null;
  }[];
}

export interface AdminSource {
  id: string;
  name: string;
  kind: string;
  status: string;
  phase: number;
  enabled: boolean;
  account_required: boolean;
  last_runs: Record<string, { seen?: number; stored?: number; error?: string; at?: string }>;
}

export interface AdminJob {
  id: string;
  kind: string;
  city: string | null;
  status: "queued" | "running" | "done" | "failed";
  attempts: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export async function setAdminToken(token: string) {
  (await cookies()).set(ADMIN_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: COOKIE_DAYS * 24 * 60 * 60,
  });
}

export async function clearAdminToken() {
  (await cookies()).delete(ADMIN_COOKIE);
}

/** Checks a token against the API without storing it. */
export async function tokenStatus(token: string): Promise<"ok" | "wrong" | "disabled" | "down"> {
  try {
    const response = await fetch(`${serverBase()}/api/v1/admin/overview`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (response.ok) return "ok";
    if (response.status === 503) return "disabled";
    return "wrong";
  } catch {
    return "down";
  }
}

export async function adminFetch<T>(lang: Locale, path: string, init?: RequestInit): Promise<T> {
  const token = (await cookies()).get(ADMIN_COOKIE)?.value;
  if (!token) redirect(`/${lang}/admin/login`);
  const response = await fetch(`${serverBase()}/api/v1/admin${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (response.status === 401) redirect(`/${lang}/admin/login?error=wrong`);
  if (response.status === 503) redirect(`/${lang}/admin/login?error=disabled`);
  if (!response.ok) throw new ApiError(response.status, await response.text());
  return response.json() as Promise<T>;
}

export const admin = {
  overview: (lang: Locale) => adminFetch<Overview>(lang, `/overview?lang=${lang}`),
  submissions: (lang: Locale, status = "pending") =>
    adminFetch<AdminSubmission[]>(lang, `/submissions?status=${status}&lang=${lang}`),
  reports: (lang: Locale, status = "open") =>
    adminFetch<ReportGroup[]>(lang, `/reports?status=${status}&lang=${lang}`),
  hidden: (lang: Locale) => adminFetch<AdminBusiness[]>(lang, `/hidden?lang=${lang}`),
  nextLabel: (lang: Locale, city?: string) =>
    adminFetch<{ business: AdminBusiness | null; precision: Precision }>(
      lang,
      `/labels/next?lang=${lang}${city ? `&city=${encodeURIComponent(city)}` : ""}`,
    ),
  sources: (lang: Locale) => adminFetch<AdminSource[]>(lang, `/sources?lang=${lang}`),
  jobs: (lang: Locale) => adminFetch<AdminJob[]>(lang, "/jobs"),
};
