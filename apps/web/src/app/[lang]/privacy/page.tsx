import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Prose } from "@/components/Prose";
import { hasLocale } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[lang]/privacy">): Promise<Metadata> {
  const { lang } = await params;
  return { title: lang === "fa" ? "حریم خصوصی" : "Privacy" };
}

export default async function Privacy({ params }: PageProps<"/[lang]/privacy">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  return (
    <Prose>
      {lang === "fa" ? (
        <>
          <h1>حریم خصوصی</h1>
          <h2>درباره‌ی کسب‌وکارها</h2>
          <ul>
            <li>فقط اطلاعات عمومی کسب‌وکارها را نمایش می‌دهیم: نام، آدرس کاری، تلفن، وب‌سایت و صفحه‌های عمومی.</li>
            <li>از پروفایل‌های شخصی، پست‌ها یا عکس‌ها چیزی جمع نمی‌کنیم.</li>
            <li>
              کسب‌وکاری را فقط وقتی «ایرانی» نشان می‌دهیم که خودش به‌صورت عمومی نشانه‌ای داده باشد. نام خانوادگی
              به‌تنهایی کافی نیست.
            </li>
            <li>
              <strong>درخواست حذف:</strong> صاحب هر کسب‌وکار می‌تواند با دکمه‌ی «گزارش اشتباه» و گزینه‌ی «می‌خواهم
              حذف شود» درخواست بدهد. درخواست ظرف ۷۲ ساعت بررسی می‌شود و کسب‌وکار دوباره فهرست نمی‌شود.
            </li>
          </ul>
          <h2>درباره‌ی شما</h2>
          <ul>
            <li>حساب کاربری وجود ندارد و کوکی ردیابی استفاده نمی‌کنیم.</li>
            <li>آدرس IP در دیتابیس ذخیره نمی‌شود. فقط در لاگ‌های وب‌سرور ثبت می‌شود و این لاگ‌ها حداکثر بعد از ۷ روز پاک می‌شوند.</li>
            <li>ایمیلی که در گزارش وارد می‌کنید فقط برای پیگیری همان گزارش استفاده می‌شود.</li>
          </ul>
        </>
      ) : (
        <>
          <h1>Privacy</h1>
          <h2>About businesses</h2>
          <ul>
            <li>We only show public business information: name, business address, phone, website and public pages.</li>
            <li>We do not collect personal profiles, posts or photos.</li>
            <li>
              A business is shown as Iranian only if it publicly signals it. A surname alone is never enough.
            </li>
            <li>
              <strong>Removal requests:</strong> owners can use “Report a problem” → “I own this business and want it
              removed”. Requests are handled within 72 hours and the business is not listed again.
            </li>
          </ul>
          <h2>About you</h2>
          <ul>
            <li>There are no user accounts and no tracking cookies.</li>
            <li>IP addresses are not stored in our database. They appear only in web server logs, which are deleted after at most 7 days.</li>
            <li>An email you enter in a report is used only to follow up on that report.</li>
          </ul>
        </>
      )}
    </Prose>
  );
}
