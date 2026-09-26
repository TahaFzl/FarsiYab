"use client";

import { useState, type FormEvent } from "react";

import { useCities } from "@/hooks/useCities";
import { browserApi, type CategoryOption, type Country } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

export interface SubmitFormText {
  country: string;
  city: string;
  chooseCountry: string;
  chooseCity: string;
  loadingCities: string;
  name: string;
  nameHint: string;
  category: string;
  chooseCategory: string;
  address: string;
  addressHint: string;
  phone: string;
  links: string;
  linksHint: string;
  addLink: string;
  owner: string;
  email: string;
  emailHint: string;
  note: string;
  consent: string;
  send: string;
  sending: string;
  sent: string;
  sendAnother: string;
  failed: string;
  tooMany: string;
  invalid: string;
}

const MAX_LINKS = 5;

export function SubmitForm({
  lang,
  text,
  countries,
  categories,
}: {
  lang: Locale;
  text: SubmitFormText;
  countries: Country[];
  categories: CategoryOption[];
}) {
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const { cities, loading } = useCities(country, lang);
  const [links, setLinks] = useState([""]);
  const [state, setState] = useState<"idle" | "sending" | "sent" | "failed" | "tooMany" | "invalid">(
    "idle",
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const value = (key: string) => {
      const v = String(form.get(key) ?? "").trim();
      return v || null;
    };
    setState("sending");
    try {
      const response = await fetch(browserApi.submissions, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          country,
          city,
          name: value("name"),
          category: value("category"),
          address: value("address"),
          phone: value("phone"),
          links: links.map((l) => l.trim()).filter(Boolean),
          is_owner: form.get("is_owner") === "on",
          contact_email: value("contact_email"),
          note: value("note"),
          company_website: value("company_website"),
        }),
      });
      if (response.ok) setState("sent");
      else if (response.status === 429) setState("tooMany");
      else if (response.status === 422) setState("invalid");
      else setState("failed");
    } catch {
      setState("failed");
    }
  }

  const input =
    "w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-base focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60";
  const label = "block space-y-1.5";
  const caption = "text-sm font-medium";
  const hint = "text-xs text-muted";

  if (state === "sent") {
    return (
      <div role="status" className="space-y-4 rounded-2xl border border-border bg-surface p-6">
        <p className="font-medium">{text.sent}</p>
        <button
          type="button"
          className="text-primary hover:underline"
          onClick={() => {
            setLinks([""]);
            setState("idle");
          }}
        >
          {text.sendAnother}
        </button>
      </div>
    );
  }

  const error = { failed: text.failed, tooMany: text.tooMany, invalid: text.invalid }[
    state as "failed" | "tooMany" | "invalid"
  ];

  return (
    <form onSubmit={submit} className="space-y-5 rounded-2xl border border-border bg-surface p-5 shadow-sm sm:p-7">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={label}>
          <span className={caption}>{text.country}</span>
          <select
            className={input}
            value={country}
            required
            onChange={(e) => {
              setCountry(e.target.value);
              setCity("");
            }}
          >
            <option value="">{text.chooseCountry}</option>
            {countries.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className={label}>
          <span className={caption}>{text.city}</span>
          <select
            className={input}
            value={city}
            required
            disabled={!country || loading}
            onChange={(e) => setCity(e.target.value)}
          >
            <option value="">{loading ? text.loadingCities : text.chooseCity}</option>
            {cities.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className={label}>
        <span className={caption}>{text.name}</span>
        <input name="name" className={input} required minLength={2} maxLength={200} />
        <span className={hint}>{text.nameHint}</span>
      </label>

      <label className={label}>
        <span className={caption}>{text.category}</span>
        <select name="category" className={input} required defaultValue="">
          <option value="">{text.chooseCategory}</option>
          {categories.map((c) => (
            <option key={c.slug} value={c.slug}>
              {c.name}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="space-y-2">
        <legend className={caption}>{text.links}</legend>
        {links.map((link, i) => (
          <input
            key={i}
            type="url"
            dir="ltr"
            aria-label={`${text.links} ${i + 1}`}
            className={input}
            required={i === 0}
            placeholder="https://instagram.com/…"
            value={link}
            onChange={(e) => setLinks((all) => all.map((l, j) => (j === i ? e.target.value : l)))}
          />
        ))}
        <p className={hint}>{text.linksHint}</p>
        {links.length < MAX_LINKS && (
          <button type="button" className="text-sm text-primary hover:underline" onClick={() => setLinks([...links, ""])}>
            + {text.addLink}
          </button>
        )}
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className={label}>
          <span className={caption}>{text.address}</span>
          <input name="address" className={input} maxLength={300} />
          <span className={hint}>{text.addressHint}</span>
        </label>
        <label className={label}>
          <span className={caption}>{text.phone}</span>
          <input name="phone" type="tel" dir="ltr" className={input} maxLength={40} />
        </label>
      </div>

      <label className="flex items-center gap-2">
        <input name="is_owner" type="checkbox" className="size-4 accent-primary" />
        <span className="text-sm">{text.owner}</span>
      </label>

      <label className={label}>
        <span className={caption}>{text.email}</span>
        <input name="contact_email" type="email" dir="ltr" className={input} />
        <span className={hint}>{text.emailHint}</span>
      </label>

      <label className={label}>
        <span className={caption}>{text.note}</span>
        <textarea name="note" rows={3} maxLength={2000} className={input} />
      </label>

      {/* Honeypot: hidden from people and screen readers; bots fill it in. */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-0 overflow-hidden">
        <label>
          Company website
          <input name="company_website" tabIndex={-1} autoComplete="off" />
        </label>
      </div>

      <p className={hint}>{text.consent}</p>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={state === "sending"}
        className="rounded-lg bg-primary px-8 py-2.5 font-semibold text-white hover:bg-primary-strong focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-60"
      >
        {state === "sending" ? text.sending : text.send}
      </button>
    </form>
  );
}
