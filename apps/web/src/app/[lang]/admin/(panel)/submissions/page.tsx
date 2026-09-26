import { notFound } from "next/navigation";

import { reviewSubmission } from "@/app/[lang]/admin/actions";
import { ResultCard } from "@/components/ResultCard";
import { admin } from "@/lib/admin";
import { categoryNames } from "@/lib/categoryNames";
import { getDictionary } from "@/lib/dictionaries";
import { formatDate, formatNumber, hasLocale } from "@/lib/i18n";

export default async function AdminSubmissions({ params }: PageProps<"/[lang]/admin/submissions">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const t = dict.admin.submissions;
  const [items, names] = await Promise.all([admin.submissions(lang), categoryNames(lang)]);
  if (items.length === 0) return <p className="text-muted">{t.none}</p>;
  return (
    <ol className="space-y-6">
      {items.map((s) => (
        <li key={s.id} className="space-y-3 rounded-2xl border border-border bg-surface p-5">
          <header className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-bold">
              <bdi>{s.name}</bdi>
            </h2>
            <span className="text-sm text-muted">
              {s.city} · {s.category} · {s.is_owner ? t.owner : t.community} · {formatDate(lang, s.created_at)}
            </span>
          </header>
          <ul className="space-y-1 text-sm" dir="ltr">
            {s.links.map((link) => (
              <li key={link}>
                <a href={link} target="_blank" rel="noopener noreferrer nofollow" className="text-primary hover:underline">
                  {link}
                </a>
              </li>
            ))}
          </ul>
          <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
            {s.address && <><dt className="text-muted">{dict.submit.address}</dt><dd>{s.address}</dd></>}
            {s.phone && <><dt className="text-muted">{dict.submit.phone}</dt><dd dir="ltr" className="text-start">{s.phone}</dd></>}
            {s.contact_email && <><dt className="text-muted">{t.contact}</dt><dd dir="ltr" className="text-start">{s.contact_email}</dd></>}
            {s.note && <><dt className="text-muted">{t.noteFrom}</dt><dd>{s.note}</dd></>}
            <dt className="text-muted">{t.score}</dt>
            <dd>{formatNumber(lang, s.detected_score)}</dd>
          </dl>
          {s.possible_duplicate && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-accent">{t.duplicate}</p>
              <ResultCard result={s.possible_duplicate} lang={lang} dict={dict} categoryNames={names} actions={<span />} />
            </div>
          )}
          <form action={reviewSubmission} className="flex flex-wrap items-end gap-3">
            <input type="hidden" name="lang" value={lang} />
            <input type="hidden" name="id" value={s.id} />
            <label className="min-w-48 flex-1 space-y-1">
              <span className="text-xs text-muted">{t.note}</span>
              <input name="note" className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" />
            </label>
            <button name="decision" value="approve" className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-strong">
              {t.approve}
            </button>
            <button name="decision" value="reject" className="rounded-lg border border-border px-4 py-2 text-sm hover:border-danger hover:text-danger">
              {t.reject}
            </button>
          </form>
        </li>
      ))}
    </ol>
  );
}
