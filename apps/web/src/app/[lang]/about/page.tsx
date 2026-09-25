import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Prose } from "@/components/Prose";
import { hasLocale } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[lang]/about">): Promise<Metadata> {
  const { lang } = await params;
  return { title: lang === "fa" ? "درباره" : "About" };
}

export default async function About({ params }: PageProps<"/[lang]/about">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  return (
    <Prose>
      {lang === "fa" ? (
        <>
          <h1>درباره‌ی فارسی‌یاب</h1>
          <p>
            پیدا کردن دکتر فارسی‌زبان، رستوران ایرانی یا سوپرمارکت ایرانی در یک شهر تازه سخت است. این اطلاعات
            بین نقشه‌ها، اینستاگرام، فیس‌بوک و دایرکتوری‌های مختلف پخش شده و هیچ‌کدام فیلتر «ایرانی» ندارند.
          </p>
          <p>
            فارسی‌یاب این منابع را یک‌جا جمع می‌کند و با شفافیت کامل نشان می‌دهد هر نتیجه از کجا آمده. هدف این نیست
            که حرف ما را قبول کنید؛ هدف این است که خودتان بتوانید با یک کلیک بررسی کنید.
          </p>
          <p>
            فعلاً ۱۰ شهر در آمریکا، کانادا و آلمان پوشش داده می‌شوند و شهرهای بیشتری در راه است. جزئیات فنی در{" "}
            <Link href={`/${lang}/how-it-works`}>نحوه‌ی کار</Link> آمده است.
          </p>
        </>
      ) : (
        <>
          <h1>About FarsiYab</h1>
          <p>
            Finding a Farsi-speaking doctor, a Persian restaurant or an Iranian grocery in a new city is hard. The
            information is scattered across maps, Instagram, Facebook and directories, and none of them has an
            “Iranian” filter.
          </p>
          <p>
            FarsiYab brings these sources together and is fully transparent about where each result came from. The
            point is not to take our word for it, but to let you check with one click.
          </p>
          <p>
            Ten cities in the US, Canada and Germany are covered so far, with more on the way. See{" "}
            <Link href={`/${lang}/how-it-works`}>How it works</Link> for the details.
          </p>
        </>
      )}
    </Prose>
  );
}
