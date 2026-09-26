import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { OwnerEditor } from "@/components/OwnerEditor";
import { getDictionary } from "@/lib/dictionaries";
import { hasLocale } from "@/lib/i18n";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function OwnerPage({ params }: PageProps<"/[lang]/owner/[claim]">) {
  const { lang, claim } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <h1 className="text-2xl font-extrabold">{dict.claim.ownerTitle}</h1>
      <OwnerEditor lang={lang} claimId={claim} text={dict.claim} />
    </div>
  );
}
