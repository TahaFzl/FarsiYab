import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { LoginForm } from "@/components/admin/LoginForm";
import { getDictionary } from "@/lib/dictionaries";
import { hasLocale } from "@/lib/i18n";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function AdminLogin({ params, searchParams }: PageProps<"/[lang]/admin/login">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const error = (await searchParams).error;
  const initial = error === "wrong" || error === "disabled" ? error : null;
  return (
    <div className="mx-auto max-w-md space-y-4">
      <h1 className="text-2xl font-extrabold">{dict.admin.login.title}</h1>
      <LoginForm lang={lang} text={dict.admin.login} initialError={initial} />
    </div>
  );
}
