import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Prose } from "@/components/Prose";
import { hasLocale } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[lang]/how-it-works">): Promise<Metadata> {
  const { lang } = await params;
  return { title: lang === "fa" ? "نحوه‌ی کار" : "How it works" };
}

export default async function HowItWorks({ params }: PageProps<"/[lang]/how-it-works">) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  return <Prose>{lang === "fa" ? <Fa /> : <En />}</Prose>;
}

function Fa() {
  return (
    <>
      <h1>فارسی‌یاب چطور کار می‌کند؟</h1>
      <p>
        فارسی‌یاب هیچ داده‌ای را از پشت صحنه‌ی سایت‌ها برنمی‌دارد. فقط از داده‌های باز و صفحه‌های عمومی
        استفاده می‌کند و برای هر نتیجه نشان می‌دهد <strong>از کجا</strong> آمده و <strong>چرا</strong> ایرانی تشخیص
        داده شده است.
      </p>

      <h2>منابع</h2>
      <ul>
        <li>
          <strong>Overture Maps:</strong> دیتاست باز مکان‌ها، شامل داده‌ی صفحه‌های کسب‌وکار فیس‌بوک (Meta)،
          Microsoft و Foursquare.
        </li>
        <li>
          <strong>OpenStreetMap:</strong> نقشه‌ی آزاد. برچسب‌هایی مثل «غذای ایرانی» یا «فارسی صحبت می‌کنیم» از
          اینجا می‌آیند.
        </li>
        <li>
          <strong>وب‌سایت خود کسب‌وکار:</strong> صفحه‌ی اول سایت را (با رعایت robots.txt) می‌خوانیم تا متن فارسی،
          اسم غذاهای ایرانی یا لینک اینستاگرام و تلگرام را پیدا کنیم.
        </li>
      </ul>
      <p>
        اینستاگرام و فیس‌بوک را مستقیماً نمی‌گردیم؛ لینک صفحه‌ها از همین منابع باز پیدا می‌شود. برای هر نتیجه
        لینک Google Maps و Apple Maps هم هست تا خودتان نظرات و عکس‌ها را ببینید.
      </p>

      <h2>ایرانی بودن را چطور تشخیص می‌دهیم؟</h2>
      <p>از چند نشانه، که هر کدام وزنی دارند:</p>
      <ul>
        <li>ذکر صریح، مثل «Persian»، «Iranian»، «ایرانی» یا «We speak Farsi»</li>
        <li>دسته‌ی «رستوران ایرانی» در نقشه‌ها</li>
        <li>نام یا وب‌سایت به خط فارسی (فارسی از عربی، پشتو و اردو جدا تشخیص داده می‌شود)</li>
        <li>اسم غذاهای ایرانی، شهرهای ایران، نوروز و یلدا</li>
      </ul>
      <p>
        نشانه‌ها با هم جمع می‌شوند و یک میزان اطمینان می‌سازند. نام خانوادگی ایرانی به‌تنهایی هیچ‌وقت کافی
        نیست. «فرش ایرانی» هم به‌معنای ایرانی بودن صاحب مغازه حساب نمی‌شود.
      </p>
      <table>
        <thead>
          <tr>
            <th>برچسب</th>
            <th>یعنی</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>●●● اطمینان بالا</td>
            <td>چند نشانه‌ی قوی و مستقل</td>
          </tr>
          <tr>
            <td>●●○ اطمینان متوسط</td>
            <td>حداقل یک نشانه‌ی قوی</td>
          </tr>
          <tr>
            <td>●○○ احتمالاً ایرانی</td>
            <td>نشانه‌ی ضعیف، مثلاً فقط اسم یک شهر ایران در نام</td>
          </tr>
        </tbody>
      </table>

      <h2>اشتباه دیدید؟</h2>
      <p>
        روی «گزارش اشتباه» در هر نتیجه بزنید. نتیجه‌ای که چند گزارش «ایرانی نیست» بگیرد، تا بررسی پنهان
        می‌شود.
      </p>
    </>
  );
}

function En() {
  return (
    <>
      <h1>How FarsiYab works</h1>
      <p>
        FarsiYab does not scrape websites. It only uses open data and public pages, and every result shows{" "}
        <strong>where</strong> it came from and <strong>why</strong> it is considered Iranian.
      </p>

      <h2>Sources</h2>
      <ul>
        <li>
          <strong>Overture Maps:</strong> an open places dataset that includes business-page data from Meta
          (Facebook), Microsoft and Foursquare.
        </li>
        <li>
          <strong>OpenStreetMap:</strong> the free map. Tags such as “Persian cuisine” or “Farsi spoken” come from
          here.
        </li>
        <li>
          <strong>The business’s own website:</strong> we read the front page (respecting robots.txt) to find
          Persian text, Iranian dishes, or Instagram and Telegram links.
        </li>
      </ul>
      <p>
        We never crawl Instagram or Facebook directly; profile links come from the open sources above. Every
        result also links to Google Maps and Apple Maps so you can check reviews and photos yourself.
      </p>

      <h2>How is “Iranian” detected?</h2>
      <p>From several signals, each with a weight:</p>
      <ul>
        <li>Explicit mentions such as “Persian”, “Iranian”, “ایرانی” or “We speak Farsi”</li>
        <li>A “Persian restaurant” category on maps</li>
        <li>A name or website in Persian script (told apart from Arabic, Pashto and Urdu)</li>
        <li>Iranian dishes, Iranian city names, Nowruz and Yalda</li>
      </ul>
      <p>
        Signals combine into a confidence level. An Iranian-sounding surname alone is never enough, and “Persian
        rugs” does not make the shop owner Iranian.
      </p>
      <table>
        <thead>
          <tr>
            <th>Label</th>
            <th>Means</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>●●● High confidence</td>
            <td>Several strong, independent signals</td>
          </tr>
          <tr>
            <td>●●○ Medium confidence</td>
            <td>At least one strong signal</td>
          </tr>
          <tr>
            <td>●○○ Possibly Iranian</td>
            <td>A weak signal, e.g. only an Iranian city in the name</td>
          </tr>
        </tbody>
      </table>

      <h2>Found a mistake?</h2>
      <p>Use “Report a problem” on the result. Results with several “not Iranian” reports are hidden for review.</p>
    </>
  );
}
