import type { Precision } from "@/lib/admin";
import { fill, formatNumber, type Locale } from "@/lib/i18n";

interface Text {
  level: string;
  labeled: string;
  iranian: string;
  precision: string;
  ci: string;
  goal: string;
  combined: string;
  met: string;
  notMet: string;
}

export function PrecisionTable({
  lang,
  precision,
  text,
  levelNames,
}: {
  lang: Locale;
  precision: Precision;
  text: Text;
  levelNames: Record<"high" | "medium" | "low", string>;
}) {
  const percent = (v: number | null) =>
    v === null ? "—" : `${formatNumber(lang, Math.round(v * 100))}${lang === "fa" ? "٪" : "%"}`;
  return (
    <div className="space-y-2 text-sm">
      <table className="w-full border-collapse text-start">
        <thead className="text-muted">
          <tr>
            <th className="py-1 text-start font-medium">{text.level}</th>
            <th className="py-1 text-start font-medium">{text.labeled}</th>
            <th className="py-1 text-start font-medium">{text.iranian}</th>
            <th className="py-1 text-start font-medium">{text.precision}</th>
            <th className="py-1 text-start font-medium">{text.ci}</th>
          </tr>
        </thead>
        <tbody>
          {(["high", "medium", "low"] as const).map((level) => {
            const s = precision.levels[level];
            return (
              <tr key={level} className="border-t border-border">
                <td className="py-1">{levelNames[level]}</td>
                <td className="py-1">
                  {formatNumber(lang, s.labeled)} / {formatNumber(lang, precision.target_per_level)}
                </td>
                <td className="py-1">{formatNumber(lang, s.iranian)}</td>
                <td className="py-1 font-semibold">{percent(s.precision)}</td>
                <td className="py-1 text-muted" dir="ltr">
                  {s.labeled ? `${percent(s.ci95[0])} – ${percent(s.ci95[1])}` : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p>
        {text.combined}: <strong>{percent(precision.high_and_medium)}</strong> ·{" "}
        {precision.met ? text.met : text.notMet}
      </p>
      <p className="text-xs text-muted">
        {fill(text.goal, { goal: percent(precision.goal), target: formatNumber(lang, precision.target_per_level) })}
      </p>
    </div>
  );
}
