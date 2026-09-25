# Common Crawl و Web Data Commons

دو دیتاست باز که از کل وب ساخته شده‌اند. هر دو **بدون حساب** قابل دانلود هستند.

---

## ۱. Common Crawl (Columnar Index)

- **شناسه در کد:** `common_crawl`
- **وضعیت:** ✅ فاز ۳ (کشف وب‌سایت‌های فارسی‌زبان)
- **حساب کاربری:** ❌ لازم نیست. دانلود از طریق HTTPS از `data.commoncrawl.org` انجام می‌شود و اعتبارنامه‌ی AWS نمی‌خواهد.
- **مستندات:** https://commoncrawl.org/columnar-index
- **قوانین:** https://commoncrawl.org/terms-of-use (استفاده‌ی آزاد با رعایت قوانین)
- **هزینه:** رایگان
- **تست‌شده؟** ⚠️ خیر. شبکه‌ی محیط توسعه به `data.commoncrawl.org` دسترسی ندارد. اطلاعات از مستندات رسمی است.

### ایده
Common Crawl هر ماه میلیاردها صفحه‌ی وب را کراول می‌کند. ایندکس ستونی آن (فایل‌های Parquet) برای هر صفحه ستون **`content_languages`** دارد (مثلاً `fas` یا `fas,eng`). با فیلتر این ستون روی دامنه‌های کشورهای هدف، **وب‌سایت‌های فارسی‌زبانی** پیدا می‌شوند که روی دامنه‌های `.ca`، `.de`، `.se`، `.co.uk`، `.com.au` و ... هستند یا hostشان به شهرهای هدف اشاره می‌کند.

```sql
-- روی فایل‌های Parquet یک crawl، مثلاً CC-MAIN-2026-xx
SELECT url_host_name, COUNT(*) AS pages
FROM ccindex
WHERE subset = 'warc'
  AND content_languages LIKE '%fas%'
  AND url_host_tld IN ('ca', 'de', 'se', 'uk', 'au', 'nl', 'at', 'ch')
GROUP BY url_host_name
```

خروجی این کوئری لیست **hostهای** فارسی‌زبان است. هر host به صف [بررسی وب‌سایت](business-websites.md) می‌رود تا نوع کسب‌وکار و شهرش از محتوای صفحه (آدرس، schema.org و ...) مشخص شود.

### محدودیت‌ها
- حجم زیاد: ایندکس هر crawl حدود ۳۰۰ فایل Parquet چندصدمگابایتی است. فقط ستون‌های لازم با range request خوانده می‌شوند. **این پردازش ماهی یک بار و به‌صورت آفلاین انجام می‌شود، نه در زمان جست‌وجوی کاربر.**
- دامنه‌های `.com` کشور مشخصی ندارند. برای آن‌ها شهر باید از محتوای صفحه استخراج شود.
- سایت‌های خبری، وبلاگ‌ها و رسانه‌های فارسی خیلی بیشتر از کسب‌وکارها هستند. فقط hostهایی نگه داشته می‌شوند که نشانه‌ی کسب‌وکار دارند (آدرس، تلفن، schema.org از نوع LocalBusiness).
- Common Crawl طبق `robots.txt` کار می‌کند. پس اینستاگرام و فیس‌بوک در آن نیستند، که برای ما مشکلی ندارد.

### نشانه‌ها
- `cc_persian_language_site`: وب‌سایتی که Common Crawl زبانش را فارسی تشخیص داده (وزن ۰٫۴). تأیید نهایی با [بررسی وب‌سایت](business-websites.md) انجام می‌شود.

---

## ۲. Web Data Commons (schema.org)

- **شناسه در کد:** `wdc_schemaorg`
- **وضعیت:** ✅ فاز ۳
- **حساب کاربری:** ❌ لازم نیست
- **مستندات:** https://webdatacommons.org/structureddata/schemaorg/
- **هزینه:** رایگان
- **تست‌شده؟** ⚠️ خیر. `webdatacommons.org` در شبکه‌ی محیط توسعه مسدود است.

### ایده
خیلی از وب‌سایت‌های کسب‌وکارها داده‌ی ساختاریافته‌ی schema.org دارند (مثلاً `Restaurant` با `servesCuisine: "Persian"`، به همراه `address` و `telephone`). پروژه‌ی Web Data Commons (دانشگاه مانهایم) این داده‌ها را از Common Crawl استخراج و برای حدود ۴۸ کلاس پرکاربرد schema.org، از جمله **LocalBusiness** و **Restaurant**، **زیرمجموعه‌های جداگانه** منتشر می‌کند (آخرین release بر اساس crawl اکتبر ۲۰۲۴).

### کوئری
از فایل‌های زیرمجموعه‌ی `Restaurant` و `LocalBusiness`:
- `servesCuisine` شامل Persian، Iranian یا «ایرانی» باشد، **یا**
- نام یا توضیحات با Detector امتیاز بگیرد
- `address.addressLocality` یا `addressCountry` در شهرها و کشورهای هدف باشد

### نشانه‌ها
- `schemaorg_serves_persian`: `servesCuisine = Persian/Iranian` که صاحب سایت **خودش** اعلام کرده (وزن ۰٫۷)

### محدودیت‌ها
- release ها سالانه‌اند و ممکن است قدیمی باشند. هر نتیجه باید با بررسی زنده‌ی وب‌سایت تأیید شود.
- فرمت پیش‌فرض N-Quads است و تبدیل آن کمی کار دارد (ابزار تبدیل به CSV را خود پروژه ارائه می‌دهد).

### ذکر منبع
«Web Data Commons, University of Mannheim» و «Common Crawl»
