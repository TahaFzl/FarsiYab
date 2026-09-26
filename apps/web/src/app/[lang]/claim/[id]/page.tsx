import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ClaimFlow } from "@/components/ClaimFlow";
import { api, ApiError } from "@/lib/api";
import { getDictionary } from "@/lib/dictionaries";
import { hasLocale } from "@/lib/i18n";

export const metadata: Metadata = { robots: { index: false } };

export default async function ClaimPage({ params }: PageProps<"/[lang]/claim/[id]">) {
  const { lang, id } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  let business;
  try {
    business = await api.business(lang, id);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    throw error;
  }
  const name = lang === "fa" ? business.name.fa ?? business.name.latin : business.name.latin ?? business.name.fa;
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <header className="space-y-2">
        <h1 className="text-2xl font-extrabold">{dict.claim.title}</h1>
        <p className="text-lg font-bold">
          <bdi>{name}</bdi> · <span className="text-muted">{business.city.name}</span>
        </p>
        <p className="leading-7 text-muted">{dict.claim.intro}</p>
      </header>
      <ClaimFlow lang={lang} businessId={business.id} text={dict.claim} />
    </div>
  );
}
