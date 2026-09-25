# OpenStreetMap (Overpass API)

- **شناسه در کد:** `osm`
- **وضعیت:** ✅ MVP (اولین سورسی که پیاده‌سازی می‌شود)
- **نوع دسترسی:** API باز و بدون کلید
- **مستندات:** https://wiki.openstreetmap.org/wiki/Overpass_API
- **سیاست استفاده:** https://dev.overpass-api.de/overpass-doc/en/preface/commons.html
- **لایسنس داده:** ODbL. استفاده، ذخیره و نمایش مجاز است، به شرط ذکر منبع.
- **هزینه و سهمیه (بررسی سپتامبر ۲۰۲۶):** رایگان. سرور عمومی `overpass-api.de` حدود **۱۰٬۰۰۰ درخواست در روز** را منصفانه می‌داند و درخواست‌ها باید **پشت سر هم** ارسال شوند، نه موازی. در صورت شلوغی، خطای 429 برمی‌گرداند.
- **احراز هویت:** ندارد

## چه داده‌ای می‌گیریم
نام (`name`، `name:fa`، `name:en`)، مختصات، آدرس (`addr:*`)، `cuisine`، `website`، `phone`، `contact:instagram`، `contact:facebook`، `opening_hours`، `description`

## کوئری نمونه
رستوران‌های تورنتو با نشانه‌ی ایرانی در یک کوئری:

```overpass
[out:json][timeout:60];
area["wikidata"="Q172"]->.city;          // Toronto
(
  nwr(area.city)["amenity"~"restaurant|cafe|fast_food"]["cuisine"~"persian|iranian",i];
  nwr(area.city)["amenity"~"restaurant|cafe|fast_food"]["name:fa"];
  nwr(area.city)["amenity"~"restaurant|cafe|fast_food"]["name"~"[پچژگ]"];
  nwr(area.city)["amenity"~"restaurant|cafe|fast_food"]["name"~"Persian|Iranian|Shiraz|Tehran|Isfahan|Tabriz|Pars|Persepolis",i];
);
out center tags;
```

برای دسته‌هایی مثل پزشک، OSM معمولاً برچسب زبان ندارد. در این دسته‌ها **همه‌ی** مکان‌های آن نوع در شهر گرفته می‌شوند (یک بار در هفته) و Detector روی نام‌ها اجرا می‌شود. این مکان‌ها به‌عنوان کاندید برای تکمیل از سورس‌های دیگر هم استفاده می‌شوند.

## نشانه‌های ایرانی بودن
- `osm_cuisine_tag`: `cuisine=persian` یا `cuisine=iranian`
- `persian_script_name`: وجود `name:fa` یا حروف فارسی در `name`
- `iranian_place_name` و `explicit_keyword` در `name` یا `description`
- لینک‌های `contact:instagram` و `website` برای ادغام با سورس‌های دیگر استفاده می‌شوند

## لینک نمایش‌داده‌شده به کاربر
`https://www.openstreetmap.org/{node|way|relation}/{id}`

## ذخیره‌سازی
کل تگ‌ها در `source_record.raw` بدون محدودیت زمانی ذخیره می‌شوند. به‌روزرسانی هفتگی انجام می‌شود.

## محدودیت‌ها و ریسک‌ها
- پوشش OSM برای کسب‌وکارها در بعضی شهرها ناقص است (در آلمان خوب، در آمریکای شمالی متوسط)
- برای ایندکس سنگین، استفاده از یک سرور Overpass شخصی یا فایل‌های Geofabrik (دانلود رایگان و روزانه‌ی داده‌ی هر کشور) بهتر است. **پیشنهاد فاز ۳:** ایمپورت extract کشورها در PostGIS خودمان با `osm2pgsql` تا کلاً به سرور عمومی وابسته نباشیم.

## ذکر منبع
«© OpenStreetMap contributors» با لینک به https://www.openstreetmap.org/copyright
