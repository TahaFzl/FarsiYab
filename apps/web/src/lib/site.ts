/** The public address of the site, for canonical links and the sitemap. */
export function siteUrl(): string {
  return (process.env.FARSIYAB_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");
}

/** /fa/toronto/doctor/dentist: category slugs may contain a slash. */
export function cityPath(lang: string, city: string, category?: string): string {
  return category ? `/${lang}/${city}/${category}` : `/${lang}/${city}`;
}
