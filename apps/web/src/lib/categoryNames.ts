import { api, flattenCategories } from "./api";
import type { Locale } from "./i18n";

/** slug -> display name, for labeling category chips. */
export async function categoryNames(lang: Locale): Promise<Record<string, string>> {
  return Object.fromEntries(flattenCategories(await api.categories(lang)).map((c) => [c.slug, c.name]));
}
