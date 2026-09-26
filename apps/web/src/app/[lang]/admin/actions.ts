"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { adminFetch, clearAdminToken, setAdminToken, tokenStatus } from "@/lib/admin";
import { hasLocale, type Locale } from "@/lib/i18n";

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
