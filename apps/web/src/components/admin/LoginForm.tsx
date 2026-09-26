"use client";

import { useActionState } from "react";

import { login, type LoginState } from "@/app/[lang]/admin/actions";
import type { Locale } from "@/lib/i18n";

interface Text {
  token: string;
  submit: string;
  hint: string;
  wrong: string;
  disabled: string;
  down: string;
}

export function LoginForm({ lang, text, initialError }: { lang: Locale; text: Text; initialError: LoginState["error"] }) {
  const [state, action, pending] = useActionState(login, { error: initialError });
  return (
    <form action={action} className="space-y-4 rounded-2xl border border-border bg-surface p-6">
      <input type="hidden" name="lang" value={lang} />
      <label className="block space-y-1.5">
        <span className="text-sm font-medium">{text.token}</span>
        <input
          name="token"
          type="password"
          dir="ltr"
          required
          autoComplete="current-password"
          className="w-full rounded-lg border border-border bg-background px-3 py-2.5 focus:border-primary focus:outline-none"
        />
        <span className="text-xs text-muted">{text.hint}</span>
      </label>
      {state.error && (
        <p role="alert" className="text-sm text-danger">
          {text[state.error]}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="rounded-lg bg-primary px-8 py-2.5 font-semibold text-white hover:bg-primary-strong disabled:opacity-60"
      >
        {text.submit}
      </button>
    </form>
  );
}
