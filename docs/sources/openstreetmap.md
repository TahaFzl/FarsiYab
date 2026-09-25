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

## کوئری (پیاده‌سازی: `services/api/farsiyab/adapters/osm.py`)
برای هر شهر **یک** کوئری روی bbox شهر ([`data/cities.yaml`](../../data/cities.yaml)) ارسال می‌شود. این کوئری فقط مکان‌هایی را برمی‌گرداند که از قبل نشانه‌ی ایرانی دارند. به این ترتیب مصرف خیلی کمتر از سقف سرور عمومی می‌ماند (سقف Quota Guard: ۳۰۰۰ کوئری در ماه).

```overpass
[out:json][timeout:120];
(
  nwr["cuisine"~"persian|iranian",i](S,W,N,E);
  nwr["name:fa"](S,W,N,E);
  nwr["language:fa"="yes"](S,W,N,E);
  nwr["name"~"[پچژگ]"](S,W,N,E);
  nwr["name"~"persian|iranian|farsi|tehran|shiraz|isfahan|esfahan|tabriz|mashhad|persepolis",i](S,W,N,E);
  nwr["description"~"persian|iranian|farsi",i](S,W,N,E);
);
out center tags;
```

عناصری که هیچ کلید مکان تجاری (`amenity`، `shop`، `office`، `healthcare`، `craft`، `club`، `tourism` یا `leisure`) ندارند، مثل نام خیابان‌ها، کنار گذاشته می‌شوند.

> تغییر نسبت به طرح اولیه: گرفتن «همه‌ی پزشکان شهر» حذف شد. نام پزشکان به‌تنهایی مدرک کافی نیست ([04](../04-iranian-detection.md)) و پزشکانی که برچسب `language:fa=yes` دارند با همین کوئری پیدا می‌شوند.

## نشانه‌های ایرانی بودن
- `osm_cuisine_tag`: `cuisine=persian` یا `cuisine=iranian`
- `osm_language_fa`: `language:fa=yes` (کسب‌وکاری که در OSM ثبت کرده فارسی صحبت می‌کند؛ وزن ۰٫۷)
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
