import { notFound } from "next/navigation";

import { indexCity } from "@/app/[lang]/admin/actions";
import { PrecisionTable } from "@/components/admin/PrecisionTable";
import { admin } from "@/lib/admin";
import { getDictionary } from "@/lib/dictionaries";
import { formatDate, formatNumber, hasLocale } from "@/lib/i18n";

export default async function AdminOverview({ params }: PageProps<"/[lang]/admin">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const t = dict.admin;
  const [overview, jobs] = await Promise.all([admin.overview(lang), admin.jobs(lang)]);
  const stats = [
    [t.overview.pending, overview.pending_submissions],
    [t.overview.reports, overview.open_reports],
    [t.overview.hidden, overview.hidden_businesses],
    [t.overview.labels, overview.labels],
  ] as const;
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-border bg-surface p-4">
            <div className="text-2xl font-extrabold">{formatNumber(lang, value)}</div>
            <div className="text-sm text-muted">{label}</div>
          </div>
        ))}
      </div>

      <section className="space-y-2">
        <h2 className="text-lg font-bold">{t.overview.precision}</h2>
        <PrecisionTable lang={lang} precision={overview.precision} text={t.labels} levelNames={dict.card.confidence} />
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-bold">{t.overview.cities}</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] border-collapse text-sm">
            <thead className="text-muted">
              <tr>
                <th className="py-1 text-start font-medium">{t.overview.city}</th>
                <th className="py-1 text-start font-medium">{t.overview.lastIndexed}</th>
                <th className="py-1 text-start font-medium">{t.overview.shown}</th>
                <th className="py-1 text-start font-medium">{t.overview.failed}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {overview.cities.map((c) => (
                <tr key={c.slug} className="border-t border-border align-top">
                  <td className="py-1.5">{c.name}</td>
                  <td className="py-1.5">{c.last_indexed_at ? formatDate(lang, c.last_indexed_at) : t.overview.never}</td>
                  <td className="py-1.5">{formatNumber(lang, c.shown)}</td>
                  <td className="py-1.5 text-danger" dir="ltr">
                    {Object.keys(c.failed_sources).join(", ") || <span className="text-muted">—</span>}
                  </td>
                  <td className="py-1.5 text-end">
                    <form action={indexCity}>
                      <input type="hidden" name="lang" value={lang} />
                      <input type="hidden" name="city" value={c.slug} />
                      <button type="submit" className="text-primary hover:underline">
                        {t.overview.indexNow}
                      </button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-bold">{t.overview.jobs}</h2>
        {jobs.length === 0 ? (
          <p className="text-sm text-muted">{t.overview.none}</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {jobs.map((j) => (
              <li key={j.id}>
                <span className="font-medium">{j.city}</span> · {t.jobStatuses[j.status]} ·{" "}
                <span className="text-muted">{formatDate(lang, j.created_at)}</span>
                {j.error && <span className="text-danger"> · {j.error}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
