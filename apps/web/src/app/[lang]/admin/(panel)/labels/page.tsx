import { notFound } from "next/navigation";

import { labelBusiness } from "@/app/[lang]/admin/actions";
import { PrecisionTable } from "@/components/admin/PrecisionTable";
import { ResultCard } from "@/components/ResultCard";
import { admin } from "@/lib/admin";
import { categoryNames } from "@/lib/categoryNames";
import { getDictionary } from "@/lib/dictionaries";
import { hasLocale } from "@/lib/i18n";

export default async function AdminLabels({ params, searchParams }: PageProps<"/[lang]/admin/labels">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const query = await searchParams;
  const city = typeof query.city === "string" && query.city ? query.city : undefined;
  const by = typeof query.by === "string" ? query.by : "";
  const dict = await getDictionary(lang);
  const t = dict.admin.labels;
  const [{ business, precision }, overview, names] = await Promise.all([
    admin.nextLabel(lang, city),
    admin.overview(lang),
    categoryNames(lang),
  ]);
  const input = "rounded-lg border border-border bg-background px-3 py-2 text-sm";
  return (
    <div className="space-y-6">
      <form className="flex flex-wrap items-end gap-3 text-sm">
        <label className="space-y-1">
          <span className="block text-xs text-muted">{t.city}</span>
          <select name="city" defaultValue={city ?? ""} className={input}>
            <option value="">{t.allCities}</option>
            {overview.cities.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="block text-xs text-muted">{t.by}</span>
          <input name="by" defaultValue={by} className={input} />
        </label>
        <button className="rounded-lg border border-border px-4 py-2 hover:border-primary">{t.filter}</button>
      </form>

      <p className="text-sm text-muted">{t.hint}</p>

      {business ? (
        <ResultCard
          result={business}
          lang={lang}
          dict={dict}
          categoryNames={names}
          actions={
            <form action={labelBusiness} className="flex flex-wrap items-center gap-2">
              <input type="hidden" name="lang" value={lang} />
              <input type="hidden" name="id" value={business.id} />
              <input type="hidden" name="by" value={by || "admin"} />
              <input name="note" placeholder={t.note} className={`${input} w-40`} />
              <button
                name="verdict"
                value="yes"
                className="rounded-lg bg-primary px-3 py-2 font-semibold text-white hover:bg-primary-strong"
              >
                {t.yes}
              </button>
              <button name="verdict" value="no" className="rounded-lg border border-danger px-3 py-2 text-danger">
                {t.no}
              </button>
            </form>
          }
        />
      ) : (
        <p className="rounded-2xl border border-dashed border-border p-8 text-center">{t.done}</p>
      )}

      <PrecisionTable lang={lang} precision={precision} text={t} levelNames={dict.card.confidence} />
    </div>
  );
}
