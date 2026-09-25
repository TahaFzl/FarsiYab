import "server-only";

import type { Locale } from "./i18n";

const dictionaries = {
  fa: () => import("../dictionaries/fa.json").then((m) => m.default),
  en: () => import("../dictionaries/en.json").then((m) => m.default),
};

export type Dictionary = Awaited<ReturnType<(typeof dictionaries)["fa"]>>;

export const getDictionary = async (locale: Locale): Promise<Dictionary> =>
  dictionaries[locale]();
