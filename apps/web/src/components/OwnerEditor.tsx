"use client";

import { useEffect, useState, type FormEvent } from "react";

import { browserApi, type Result } from "@/lib/api";
import type { Dictionary } from "@/lib/dictionaries";
import type { Locale } from "@/lib/i18n";

type Status = "active" | "closed" | "hidden";

const input =
  "w-full rounded-lg border border-border bg-surface px-3 py-2.5 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30";

export function OwnerEditor({ lang, claimId, text }: { lang: Locale; claimId: string; text: Dictionary["claim"] }) {
  const [key, setKey] = useState<string | null>(null);
  const [business, setBusiness] = useState<Result | null>(null);
  const [status, setStatus] = useState<Status>("active");
  const [state, setState] = useState<"loading" | "ready" | "badKey" | "saving" | "saved" | "invalid" | "failed">(
    "loading",
  );

  useEffect(() => {
    // The key lives in the URL fragment, which is never sent to a server.
    const found = new URLSearchParams(window.location.hash.slice(1)).get("key");
    async function load() {
      if (!found) throw new Error("no key");
      const response = await fetch(browserApi.owner(claimId, lang), { headers: { "X-Owner-Key": found } });
      if (!response.ok) throw new Error(String(response.status));
      const data = await response.json();
      setKey(found);
      setBusiness(data.business);
      setStatus(data.status);
      setState("ready");
    }
    load().catch(() => setState("badKey"));
  }, [claimId, lang]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!key) return;
    const form = new FormData(event.currentTarget);
    const value = (k: string) => String(form.get(k) ?? "").trim() || null;
    setState("saving");
    const response = await fetch(browserApi.owner(claimId, lang), {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-Owner-Key": key },
      body: JSON.stringify({
        name_fa: value("name_fa"),
        name_latin: value("name_latin"),
        address: value("address"),
        phone: value("phone"),
        website: value("website"),
        status,
      }),
    }).catch(() => null);
    setState(response?.ok ? "saved" : response?.status === 422 ? "invalid" : "failed");
  }

  if (state === "loading") return null;
  if (state === "badKey" || !business) {
    return (
      <p role="alert" className="text-danger">
        {text.badKey}
      </p>
    );
  }

  const field = (name: string, label: string, placeholder: string | null, dir?: "ltr") => (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium">{label}</span>
      <input name={name} dir={dir} placeholder={placeholder ?? ""} className={input} />
    </label>
  );

  return (
    <form onSubmit={save} className="space-y-4 rounded-2xl border border-border bg-surface p-5">
      <p className="text-sm text-muted">{text.ownerIntro}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {field("name_fa", text.nameFa, business.name.fa)}
        {field("name_latin", text.nameLatin, business.name.latin, "ltr")}
      </div>
      {field("address", text.address, business.address)}
      <div className="grid gap-4 sm:grid-cols-2">
        {field("phone", text.phone, business.contact.phone, "ltr")}
        {field("website", text.website, business.contact.website, "ltr")}
      </div>
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">{text.status}</legend>
        {(["active", "closed", "hidden"] as const).map((s) => (
          <label key={s} className="flex items-center gap-2">
            <input type="radio" name="status" checked={status === s} onChange={() => setStatus(s)} className="accent-primary" />
            <span>{text.statuses[s]}</span>
          </label>
        ))}
      </fieldset>
      {state === "saved" && <p role="status" className="text-sm text-primary">{text.saved}</p>}
      {(state === "invalid" || state === "failed") && (
        <p role="alert" className="text-sm text-danger">
          {state === "invalid" ? text.invalid : text.failed}
        </p>
      )}
      <button
        type="submit"
        disabled={state === "saving"}
        className="rounded-lg bg-primary px-6 py-2.5 font-semibold text-white hover:bg-primary-strong disabled:opacity-60"
      >
        {text.save}
      </button>
    </form>
  );
}
