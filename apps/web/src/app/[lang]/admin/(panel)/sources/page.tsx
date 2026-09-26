import { notFound } from "next/navigation";

import { setSource } from "@/app/[lang]/admin/actions";
import { admin } from "@/lib/admin";
import { getDictionary } from "@/lib/dictionaries";
import { formatNumber, hasLocale } from "@/lib/i18n";

export default async function AdminSources({ params }: PageProps<"/[lang]/admin/sources">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const t = dict.admin.sources;
  const sources = await admin.sources(lang);
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] border-collapse text-sm">
        <thead className="text-muted">
          <tr>
            <th className="py-1 text-start font-medium">{t.name}</th>
            <th className="py-1 text-start font-medium">{t.status}</th>
            <th className="py-1 text-start font-medium">{t.enabled}</th>
            <th className="py-1 text-start font-medium">{t.lastRuns}</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.id} className="border-t border-border align-top">
              <td className="py-2">
                <div className="font-medium">{s.name}</div>
                <div className="text-xs text-muted" dir="ltr">
                  {s.id}
                </div>
              </td>
              <td className="py-2">
                {s.status} · {formatNumber(lang, s.phase)}
                {s.account_required && <div className="text-xs text-muted">{t.accountRequired}</div>}
              </td>
              <td className="py-2">
                <form action={setSource} className="flex items-center gap-2">
                  <input type="hidden" name="lang" value={lang} />
                  <input type="hidden" name="id" value={s.id} />
                  <input type="hidden" name="enabled" value={String(!s.enabled)} />
                  <span className={s.enabled ? "text-primary" : "text-muted"}>{s.enabled ? t.on : t.off}</span>
                  {!(s.account_required || s.status === "rejected") && (
                    <button className="text-xs text-primary hover:underline">{s.enabled ? t.disable : t.enable}</button>
                  )}
                </form>
              </td>
              <td className="py-2 text-xs" dir="ltr">
                {Object.entries(s.last_runs).map(([city, run]) => (
                  <div key={city} className={run.error ? "text-danger" : ""}>
                    {city}: {run.error ?? `${run.stored ?? 0}/${run.seen ?? 0}`}
                  </div>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
