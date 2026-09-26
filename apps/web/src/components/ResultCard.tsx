import type { Result } from "@/lib/api";
import type { Dictionary } from "@/lib/dictionaries";
import { fill, formatDate, type Locale } from "@/lib/i18n";

import { ReportButton } from "./ReportButton";

const DOTS = { high: 3, medium: 2, low: 1 } as const;

function ConfidenceBadge({ label, text }: { label: Result["confidence"]["label"]; text: string }) {
  if (!label) return null;
  const dots = DOTS[label];
  const tone =
    label === "high"
      ? "bg-primary-soft text-primary-strong"
      : label === "medium"
        ? "bg-accent-soft text-accent"
        : "bg-background text-muted border border-border";
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${tone}`}>
      <span aria-hidden className="tracking-tighter">
        {"●".repeat(dots)}
        {"○".repeat(3 - dots)}
      </span>
      {text}
    </span>
  );
}

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="text-primary hover:underline">
      {children}
    </a>
  );
}

interface Props {
  result: Result;
  lang: Locale;
  dict: Dictionary;
  categoryNames: Record<string, string>;
  /** Replaces the report button (the admin panel puts its review buttons here). */
  actions?: React.ReactNode;
}

export function ResultCard({ result, lang, dict, categoryNames, actions }: Props) {
  const t = dict.card;
  const title = lang === "fa" ? result.name.fa ?? result.name.latin : result.name.latin ?? result.name.fa;
  const subtitle = title === result.name.fa ? result.name.latin : result.name.fa;
  const label = result.confidence.label;

  return (
    <article className="space-y-4 rounded-2xl border border-border bg-surface p-5 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h2 className="text-lg font-bold leading-7">
            <bdi>{title}</bdi>
          </h2>
          {subtitle && (
            <p className="text-sm text-muted">
              <bdi>{subtitle}</bdi>
            </p>
          )}
          <p className="flex flex-wrap gap-1.5 pt-1">
            {result.categories.map((slug) => (
              <span key={slug} className="rounded-md bg-background px-2 py-0.5 text-xs text-muted">
                {categoryNames[slug] ?? slug}
              </span>
            ))}
          </p>
        </div>
        {label && <ConfidenceBadge label={label} text={t.confidence[label]} />}
      </header>

      <div className="space-y-1 text-sm leading-6">
        {result.address && (
          <p>
            <span aria-hidden>📍 </span>
            <bdi>{result.address}</bdi>
          </p>
        )}
        <p className="flex flex-wrap gap-x-4 gap-y-1">
          {result.contact.phone && (
            <a href={`tel:${result.contact.phone}`} className="text-primary hover:underline">
              <span aria-hidden>☎ </span>
              <span className="ltr-embed">{result.contact.phone}</span>
            </a>
          )}
          {result.contact.website && <ExternalLink href={result.contact.website}>{t.website}</ExternalLink>}
        </p>
      </div>

      <section className="space-y-2 rounded-xl bg-background p-4">
        <h3 className="text-sm font-bold">{t.whyIranian}</h3>
        <ul className="space-y-2 text-sm leading-6">
          {result.evidence.map((e, i) => (
            <li key={`${e.signal}-${i}`} className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
              <span className="font-medium">• {e.label}</span>
              <span className="text-muted">
                <bdi className="rounded bg-surface px-1.5 py-0.5 text-xs">{e.snippet}</bdi>
                {e.url && (
                  <>
                    {" "}
                    <ExternalLink href={e.url}>↗</ExternalLink>
                  </>
                )}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-sm">
        <span className="font-bold">{t.sources}:</span>
        {result.sources.map((s) => {
          const via = s.via?.length ? ` (${fill(t.via, { via: s.via.join("، ") })})` : "";
          return (
            <span key={s.id} className="rounded-full border border-border px-2.5 py-0.5">
              {s.url ? <ExternalLink href={s.url}>{s.name}</ExternalLink> : s.name}
              <span className="text-muted">{via}</span>
            </span>
          );
        })}
      </section>

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3 text-xs text-muted">
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>{t.checkOn}:</span>
          <ExternalLink href={result.links.google_maps}>{t.googleMaps}</ExternalLink>
          <ExternalLink href={result.links.apple_maps}>{t.appleMaps}</ExternalLink>
          {result.links.openstreetmap && (
            <ExternalLink href={result.links.openstreetmap}>{t.openstreetmap}</ExternalLink>
          )}
        </span>
        <span className="flex items-center gap-3">
          <span>{fill(t.verified, { date: formatDate(lang, result.last_verified_at) })}</span>
          {actions ?? (
            <ReportButton businessId={result.id} name={title ?? ""} text={dict.report} buttonLabel={t.report} />
          )}
        </span>
      </footer>
    </article>
  );
}
