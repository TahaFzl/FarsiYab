"use client";

import { useActionState } from "react";

import { grantClaim } from "@/app/[lang]/admin/actions";
import type { Locale } from "@/lib/i18n";

export function GrantClaim({
  lang,
  id,
  text,
}: {
  lang: Locale;
  id: string;
  text: { verify: string; sendLink: string; failed: string };
}) {
  const [state, action, pending] = useActionState(grantClaim, { link: null, email: null, error: false });
  if (state.link) {
    return (
      <div role="status" className="space-y-1 text-sm">
        <p>
          {text.sendLink} {state.email && <span dir="ltr">({state.email})</span>}
        </p>
        <p dir="ltr" className="break-all rounded-lg bg-background p-2 font-mono text-xs">
          {state.link}
        </p>
      </div>
    );
  }
  return (
    <form action={action}>
      <input type="hidden" name="lang" value={lang} />
      <input type="hidden" name="id" value={id} />
      <button disabled={pending} className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white">
        {text.verify}
      </button>
      {state.error && <span className="ms-2 text-sm text-danger">{text.failed}</span>}
    </form>
  );
}
