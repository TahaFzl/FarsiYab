import { notFound } from "next/navigation";

import { resolveReport, setBusinessStatus } from "@/app/[lang]/admin/actions";
import { ResultCard } from "@/components/ResultCard";
import { admin } from "@/lib/admin";
import { categoryNames } from "@/lib/categoryNames";
import { getDictionary } from "@/lib/dictionaries";
import { formatDate, hasLocale } from "@/lib/i18n";

const ACTIONS = ["dismiss", "hide", "close", "remove", "restore"] as const;

export default async function AdminReports({ params }: PageProps<"/[lang]/admin/reports">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const t = dict.admin.reports;
  const [groups, hidden, names] = await Promise.all([admin.reports(lang), admin.hidden(lang), categoryNames(lang)]);
  return (
    <div className="space-y-10">
      {groups.length === 0 ? (
        <p className="text-muted">{t.none}</p>
      ) : (
        <ol className="space-y-6">
          {groups.map(({ business, reports }) => (
            <li key={business.id} className="space-y-3">
              <p className="text-sm">
                <span className="font-medium">{business.city.name}</span> ·{" "}
                <span className="text-muted">{dict.admin.statuses[business.status]}</span>
              </p>
              <ResultCard result={business} lang={lang} dict={dict} categoryNames={names} actions={<span />} />
              <ul className="space-y-1 text-sm">
                {reports.map((r) => (
                  <li key={r.id}>
                    <strong>{t.reasons[r.reason]}</strong>
                    {r.message && <span>: {r.message}</span>}
                    {r.contact_email && <span className="text-muted" dir="ltr"> ({r.contact_email})</span>}
                    <span className="text-muted"> · {formatDate(lang, r.created_at)}</span>
                  </li>
                ))}
              </ul>
              <form action={resolveReport} className="flex flex-wrap items-end gap-2">
                <input type="hidden" name="lang" value={lang} />
                <input type="hidden" name="id" value={reports[0].id} />
                <label className="min-w-48 flex-1 space-y-1">
                  <span className="text-xs text-muted">{t.note}</span>
                  <input name="note" className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" />
                </label>
                {ACTIONS.map((action) => (
                  <button
                    key={action}
                    name="action"
                    value={action}
                    className={`rounded-lg border px-3 py-2 text-sm ${action === "remove" ? "border-danger text-danger" : "border-border hover:border-primary"}`}
                  >
                    {t.actions[action]}
                  </button>
                ))}
              </form>
              <p className="text-xs text-muted">{t.removeHint}</p>
            </li>
          ))}
        </ol>
      )}

      {hidden.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold">{t.hidden}</h2>
          <ul className="space-y-2 text-sm">
            {hidden.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center gap-3">
                <bdi className="font-medium">{b.name.latin ?? b.name.fa}</bdi>
                <span className="text-muted">{b.city.name}</span>
                <form action={setBusinessStatus}>
                  <input type="hidden" name="lang" value={lang} />
                  <input type="hidden" name="id" value={b.id} />
                  <input type="hidden" name="status" value="active" />
                  <button className="text-primary hover:underline">{t.actions.restore}</button>
                </form>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
