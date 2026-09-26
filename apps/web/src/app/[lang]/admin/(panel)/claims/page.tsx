import { notFound } from "next/navigation";

import { rejectClaim } from "@/app/[lang]/admin/actions";
import { GrantClaim } from "@/components/admin/GrantClaim";
import { ResultCard } from "@/components/ResultCard";
import { admin } from "@/lib/admin";
import { categoryNames } from "@/lib/categoryNames";
import { getDictionary } from "@/lib/dictionaries";
import { formatDate, hasLocale } from "@/lib/i18n";

export default async function AdminClaims({ params }: PageProps<"/[lang]/admin/claims">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const t = dict.admin.claims;
  const [items, names] = await Promise.all([admin.claims(lang), categoryNames(lang)]);
  if (items.length === 0) return <p className="text-muted">{t.none}</p>;
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">{t.manualHint}</p>
      <ol className="space-y-6">
        {items.map((c) => (
          <li key={c.id} className="space-y-3">
            <p className="text-sm">
              <strong>{dict.claim.methods[c.method]}</strong> · {t.token}: <code dir="ltr">{c.token}</code>
              {c.contact_email && <span dir="ltr"> · {c.contact_email}</span>}
              <span className="text-muted"> · {formatDate(lang, c.created_at)}</span>
            </p>
            {c.note && <p className="text-sm">{c.note}</p>}
            {c.business && <ResultCard result={c.business} lang={lang} dict={dict} categoryNames={names} actions={<span />} />}
            <div className="flex flex-wrap items-start gap-3">
              {c.method === "manual" && <GrantClaim lang={lang} id={c.id} text={t} />}
              <form action={rejectClaim}>
                <input type="hidden" name="lang" value={lang} />
                <input type="hidden" name="id" value={c.id} />
                <button className="rounded-lg border border-border px-3 py-2 text-sm hover:border-danger hover:text-danger">
                  {t.reject}
                </button>
              </form>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
