"use client";

import { useState, type FormEvent } from "react";

import { browserApi } from "@/lib/api";
import type { Dictionary } from "@/lib/dictionaries";
import { fill, type Locale } from "@/lib/i18n";

type Method = "website" | "telegram" | "manual";
type Started = { id: string; token: string; method: Method; where: string | null };

const input =
  "w-full rounded-lg border border-border bg-surface px-3 py-2.5 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30";
const button =
  "rounded-lg bg-primary px-6 py-2.5 font-semibold text-white hover:bg-primary-strong disabled:opacity-60";

export function ClaimFlow({ lang, businessId, text }: { lang: Locale; businessId: string; text: Dictionary["claim"] }) {
  const [method, setMethod] = useState<Method>("website");
  const [started, setStarted] = useState<Started | null>(null);
  const [ownerLink, setOwnerLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const response = await fetch(browserApi.claims(businessId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          method,
          contact_email: String(form.get("email") || "") || null,
          note: String(form.get("note") || "") || null,
        }),
      });
      if (response.ok) setStarted(await response.json());
      else if (response.status === 429) setError(text.tooMany);
      else if (response.status === 422 && method !== "manual") setError(text.noLink);
      else setError(text.failed);
    } catch {
      setError(text.failed);
    } finally {
      setBusy(false);
    }
  }

  async function check() {
    if (!started) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(browserApi.verifyClaim(started.id), { method: "POST" });
      if (response.ok) {
        const { owner_key } = await response.json();
        // The key goes in the fragment, which browsers never send to a server.
        setOwnerLink(`${window.location.origin}/${lang}/owner/${started.id}#key=${owner_key}`);
      } else setError(response.status === 409 ? text.notFound : text.failed);
    } catch {
      setError(text.failed);
    } finally {
      setBusy(false);
    }
  }

  if (ownerLink) {
    return (
      <div role="status" className="space-y-3 rounded-2xl border border-primary bg-surface p-5">
        <p>{text.verified}</p>
        <p dir="ltr" className="break-all rounded-lg bg-background p-3 font-mono text-sm">
          {ownerLink}
        </p>
        <a href={ownerLink} className="text-primary hover:underline">
          {text.openOwner}
        </a>
      </div>
    );
  }

  if (started) {
    return (
      <div className="space-y-4 rounded-2xl border border-border bg-surface p-5">
        {started.method === "manual" ? (
          <p role="status">
            {text.manualWait} <code dir="ltr">{started.token}</code>
          </p>
        ) : (
          <>
            <p>{fill(text.putToken, { where: started.where ?? "" })}</p>
            <p dir="ltr" className="rounded-lg bg-background p-3 font-mono">
              {started.token}
            </p>
            {started.where && (
              <a href={started.where} target="_blank" rel="noopener noreferrer" dir="ltr" className="text-sm text-primary">
                {started.where}
              </a>
            )}
            <div>
              <button type="button" onClick={check} disabled={busy} className={button}>
                {busy ? text.checking : text.check}
              </button>
            </div>
          </>
        )}
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <form onSubmit={start} className="space-y-4 rounded-2xl border border-border bg-surface p-5">
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">{text.method}</legend>
        {(["website", "telegram", "manual"] as const).map((m) => (
          <label key={m} className="flex items-start gap-2">
            <input
              type="radio"
              name="method"
              value={m}
              checked={method === m}
              onChange={() => setMethod(m)}
              className="mt-1 accent-primary"
            />
            <span>{text.methods[m]}</span>
          </label>
        ))}
      </fieldset>
      <label className="block space-y-1.5">
        <span className="text-sm font-medium">{text.email}</span>
        <input name="email" type="email" dir="ltr" required={method === "manual"} className={input} />
        <span className="text-xs text-muted">{text.emailHint}</span>
      </label>
      <label className="block space-y-1.5">
        <span className="text-sm font-medium">{text.note}</span>
        <textarea name="note" rows={2} maxLength={2000} className={input} />
      </label>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy} className={button}>
        {text.start}
      </button>
    </form>
  );
}
