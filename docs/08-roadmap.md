# ۸. نقشه‌ی راه

هر فاز یک **معیار اتمام** دارد که قابل تست است. سورس‌های هر فاز از [`data/sources.yaml`](../data/sources.yaml) (فیلد `phase`) می‌آیند. **فازهای ۰ تا ۵ هیچ حساب کاربری، کلید یا کارت بانکی لازم ندارند** ([ADR-005](decisions/005-no-account-sources-first.md)).

```mermaid
flowchart LR
    P0[۰. مستندات ✅] --> P1[۱. هسته‌ی بک‌اند<br/>Overture · OSM · وب‌سایت‌ها]
    P1 --> P2[۲. فرانت‌اند MVP<br/>+ لینک Google/Apple Maps]
    P2 --> P3[۳. سورس‌های بیشتر<br/>Common Crawl · دولتی · Wikidata<br/>دایرکتوری‌ها · رجیسترها]
    P3 --> P4[۴. جامعه و کیفیت<br/>ثبت کاربران · ادمین · نقشه · SEO]
    P4 --> P5[۵. گسترش<br/>کشورهای بیشتر · تلگرام]
    P5 -.اختیاری.-> P6[۶. سورس‌های با حساب<br/>Google Places · Brave · Instagram API]
```

## فاز ۰: مستندسازی ✅
- مستندات محصول، معماری و مدل داده
- کاتالوگ ۲۷ سورس ([sources/](sources/README.md) + [`data/sources.yaml`](../data/sources.yaml)) و سورس‌های ردشده با دلیل
- تصمیم‌های اصلی (ADR-001 تا ADR-005)
- تست واقعی Overture روی تورنتو ([`research/overture_probe.py`](../research/overture_probe.py))

## فاز ۱: هسته‌ی بک‌اند و سورس‌های MVP ✅
راهنمای اجرا: [`services/api/README.md`](../services/api/README.md)

**زیرساخت**
- [x] ساختار ریپو (`services/api`)، `scripts/setup_db.sh` (Postgres + PostGIS)، راهنمای نصب، CI (lint + test) در `.github/workflows/ci.yml`
- [x] مدل داده و migration ها (Alembic)
- [x] بارگذاری `data/sources.yaml` در جدول `source`، و `data/categories.yaml`
- [x] کشورها و ۱۰ شهر MVP از `data/cities.yaml` (GeoNames و Nominatim به فاز ۵ منتقل شدند)
- [x] صف کار و سهمیه در خود PostgreSQL (بدون Redis)

**سورس‌ها** (رابط `SourceAdapter`)
- [x] `overture`: خواندن bbox شهر از آخرین release (**تست‌شده روی داده‌ی واقعی**)
- [x] `osm`: کوئری Overpass (با تست روی داده‌ی ضبط‌شده؛ شبکه‌ی محیط توسعه به Overpass دسترسی ندارد)
- [x] `website`: بررسی صفحه‌ی اول وب‌سایت کاندیدها (robots.txt، محدودیت نرخ، تلاش دوباره فقط برای خطاهای شبکه)
- [x] استخراج لینک‌های `facebook`، `instagram` و `telegram`

**پردازش**
- [x] Iranian Detector، واژه‌نامه‌ها در `data/lexicons/` و تست با مثبت‌های کاذب واقعی (فرش‌فروشی‌ها، Shirazi، پشتو، اردو، Bastani، Caspian و ...)
- [x] Entity Resolver (رکورد یکسان، لینک مشترک، یا فاصله‌ی کمتر از ۱۵۰ متر + نام مشابه)
- [x] ذخیره‌ی `evidence` با snippet و لینک

**API و ابزار**
- [x] `GET /api/v1/search`، `/countries`، `/cities`، `/categories`، `/search/jobs/{id}`، `POST /businesses/{id}/reports`
- [x] CLI: `farsiyab db init`، `index <city>`، `worker`، `serve`، `cities`
- [x] ۱۱۱ تست (واحد + دیتابیس واقعی PostGIS)

**معیار اتمام:** دستور `farsiyab index toronto` بدون هیچ کلیدی اجرا شود و `GET /search?city=toronto&categories=restaurant` نتایجی با سورس، لینک مدرک و امتیاز اطمینان برگرداند. ✅ **انجام شد** (نتایج در [reports/phase1-first-index.md](reports/phase1-first-index.md)).

## فاز ۲: فرانت‌اند MVP
- [ ] Next.js با i18n (فارسی RTL و انگلیسی) و فونت Vazirmatn
- [ ] صفحه‌ی اصلی: انتخاب کشور، شهر و دسته‌ها و دکمه‌ی جست‌وجو
- [ ] صفحه‌ی نتایج: کارت نتیجه (سورس‌ها، مدارک، اطمینان، «دیدن روی Google Maps / Apple Maps»)
- [ ] اتصال SSE برای ایندکس لایو شهرهای جدید
- [ ] دکمه‌ی گزارش اشتباه
- [ ] صفحه‌های «درباره»، «نحوه‌ی جمع‌آوری داده» و «حریم خصوصی»
- [ ] استقرار اولیه روی VPS (systemd + Caddy، فایل‌ها در `deploy/`)

**معیار اتمام:** یک کاربر واقعی از موبایل، تورنتو و رستوران را انتخاب کند و نتایج را با مدرک و لینک ببیند.

## فاز ۳: سورس‌های بیشتر (بدون حساب)
- [ ] بررسی ToS و `robots.txt` **۱۹ دایرکتوری ایرانی** و ارسال ایمیل پیشنهاد همکاری
- [ ] آداپتر دایرکتوری‌های تأییدشده
- [ ] بررسی رجیسترها (CPSO، CalBar، Texas Bar، BDÜ و ...) و انتخاب حالت «داده» یا «لینک»
- [ ] `gov:*`: مجوزهای LA، تورنتو و ونکوور؛ IRS و CRA برای دسته‌ی `community`
- [ ] `common_crawl`: کشف ماهانه‌ی سایت‌های فارسی‌زبان
- [ ] `wdc_schemaorg`: رستوران‌های با `servesCuisine = Persian`
- [ ] `wikidata` و `wikivoyage`
- [ ] دسته‌های جدید: `accounting`، `education`، `community`، `translator`
- [ ] Scheduler: Overture ماهانه، OSM و وب‌سایت‌ها هفتگی، دایرکتوری‌ها هفتگی

**معیار اتمام:** برای هر شهر MVP، حداقل ۳ سورس مستقل نتیجه بدهند. گزارش مقایسه‌ی پوشش هر سورس در `docs/reports/` ثبت شود.

## فاز ۴: جامعه و کیفیت
- [ ] فرم ثبت کسب‌وکار و درخواست حذف یا اصلاح
- [ ] پنل ادمین: صف بررسی، گزارش‌ها، وضعیت سورس‌ها
- [ ] برچسب‌گذاری ۳۰۰ نمونه و تنظیم وزن‌های Detector
- [ ] نمایش روی نقشه (Leaflet + OSM)
- [ ] صفحه‌های SEO شهر و دسته

**معیار اتمام:** دقت (precision) Detector روی نمونه‌های برچسب‌خورده حداقل ۹۰٪ در برچسب‌های «بالا» و «متوسط».

## فاز ۵: گسترش
- [ ] کشورها و شهرهای بیشتر (انگلستان، سوئد، استرالیا، هلند، فرانسه، ترکیه، امارات و ...) با تنظیم آستانه‌های جدا
- [ ] دایرکتوری‌های کشورهای جدید (کاندیدهای انگلستان و استرالیا از قبل شناسایی شده‌اند)
- [ ] لینک کانال‌های تلگرام
- [ ] ادعای مالکیت کسب‌وکار (claim) توسط صاحبش

## فاز ۶: سورس‌های اختیاری با حساب
فقط در صورتی که حساب‌ها ساخته شوند؛ معماری تغییری نمی‌کند:
- [ ] Google Places API (با Quota Guard)
- [ ] Brave Search API
- [ ] Instagram Business Discovery
- [ ] UK Companies House
