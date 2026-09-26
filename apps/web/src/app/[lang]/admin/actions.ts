"use server";

import { revalidatePath } from "next/cache";
import { redirect, unstable_rethrow } from "next/navigation";

import { adminFetch, clearAdminToken, setAdminToken, tokenStatus } from "@/lib/admin";
import { hasLocale, type Locale } from "@/lib/i18n";
import { siteUrl } from "@/lib/site";

function field(form: FormData, key: string): string {
  return String(form.get(key) ?? "").trim();
}

function localeOf(form: FormData): Locale {
  const lang = field(form, "lang");
  return hasLocale(lang) ? lang : "fa";
}

function refresh(lang: Locale) {
  revalidatePath(`/${lang}/admin`, "layout");
}

export type LoginState = { error: "wrong" | "disabled" | "down" | null };

export async function login(_state: LoginState, form: FormData): Promise<LoginState> {
  const lang = localeOf(form);
  const status = await tokenStatus(field(form, "token"));
  if (status !== "ok") return { error: status };
  await setAdminToken(field(form, "token"));
  redirect(`/${lang}/admin`);
}

export async function logout(form: FormData) {
  await clearAdminToken();
  redirect(`/${localeOf(form)}/admin/login`);
}

async function post(form: FormData, path: string, body: object, method = "POST") {
  const lang = localeOf(form);
  await adminFetch(lang, path, { method, body: JSON.stringify(body) });
  refresh(lang);
}

export async function reviewSubmission(form: FormData) {
  const decision = field(form, "decision") === "approve" ? "approve" : "reject";
  await post(form, `/submissions/${field(form, "id")}/${decision}`, {
    note: field(form, "note") || null,
  });
}

export async function resolveReport(form: FormData) {
  await post(form, `/reports/${field(form, "id")}/resolve`, {
    action: field(form, "action"),
    note: field(form, "note") || null,
  });
}

export async function setBusinessStatus(form: FormData) {
  await post(form, `/businesses/${field(form, "id")}`, { status: field(form, "status") }, "PATCH");
}

export async function labelBusiness(form: FormData) {
  await post(form, `/businesses/${field(form, "id")}/label`, {
    is_iranian: field(form, "verdict") === "yes",
    note: field(form, "note") || null,
    by: field(form, "by") || "admin",
  });
}

export async function setSource(form: FormData) {
  await post(form, `/sources/${encodeURIComponent(field(form, "id"))}`, {
    enabled: field(form, "enabled") === "true",
  }, "PATCH");
}

export async function indexCity(form: FormData) {
  await post(form, "/index", { city: field(form, "city") });
}

export type GrantState = { link: string | null; email: string | null; error: boolean };

export async function grantClaim(_state: GrantState, form: FormData): Promise<GrantState> {
  const lang = localeOf(form);
  const id = field(form, "id");
  try {
    const { owner_key, contact_email } = await adminFetch<{ owner_key: string; contact_email: string }>(
      lang,
      `/claims/${id}/verify`,
      { method: "POST" },
    );
    // No refresh here: the claim would leave the pending list and take the link, which is
    // shown only once, with it. The admin sends this link to the owner.
    return { link: `${siteUrl()}/${lang}/owner/${id}#key=${owner_key}`, email: contact_email, error: false };
  } catch (error) {
    unstable_rethrow(error); // let the redirect to the login page through
    return { link: null, email: null, error: true };
  }
}

export async function rejectClaim(form: FormData) {
  await post(form, `/claims/${field(form, "id")}/reject`, {});
}
