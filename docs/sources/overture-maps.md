# Overture Maps (Places)

- **شناسه در کد:** `overture` (در هر ردیف، سورس اصلی هم نگه داشته می‌شود: `meta`، `Microsoft`، `Foursquare`، `AllThePlaces` و ...)
- **وضعیت:** ✅ **MVP، سورس اصلی** ([ADR-005](../decisions/005-no-account-sources-first.md))
- **نوع دسترسی:** دیتاست باز. فایل‌های GeoParquet روی S3 عمومی آمازون (و Azure) قرار دارند.
- **حساب کاربری یا کلید:** ❌ **لازم نیست** (دسترسی ناشناس به S3)
- **هزینه:** رایگان
- **مستندات:** https://docs.overturemaps.org/guides/places/
- **لایسنس:** https://docs.overturemaps.org/attribution/. داده‌هایی که از Foursquare آمده‌اند Apache 2.0 هستند و بقیه CDLA Permissive 2.0. هر دو استفاده‌ی تجاری و ذخیره را مجاز می‌دانند.
- **به‌روزرسانی:** تقریباً ماهانه (release هایی مثل `2026-09-23.1`)

## چرا سورس اصلی است
Overture داده‌ی مکان‌ها را از چند شرکت بزرگ (Meta یعنی صفحات کسب‌وکار فیس‌بوک، Microsoft یعنی داده‌های Bing Maps، Foursquare و ...) در یک دیتاست باز جمع کرده است. بنابراین **بخش بزرگی از همان داده‌ای که در فیس‌بوک و نقشه‌ها هست، بدون ساخت حساب و بدون اسکرپینگ در دسترس است.**

## ✅ نتیجه‌ی تست واقعی (۲۰۲۶-۰۹-۲۵، تورنتو)

از داخل همین محیط توسعه، بدون هیچ کلیدی:

| مورد | عدد |
|---|---|
| کل مکان‌ها در محدوده‌ی تورنتو | حدود ۱۶۵٬۰۰۰ |
| زمان کوئری با فیلتر bbox (بدون دانلود کل فایل) | حدود ۲ ثانیه |
| مکان‌هایی که داده‌شان از **Meta (فیس‌بوک)** آمده | حدود ۱۰۸٬۰۰۰ |
| مکان‌های دارای **لینک صفحه‌ی فیس‌بوک** | حدود ۱۱۵٬۰۰۰ |
| مکان‌های دارای **لینک اینستاگرام** (در `socials` یا `websites`) | حدود ۲٬۱۰۰ |
| مکان‌های دسته‌ی `persian_restaurant` | ۵۴ |
| نتایجی که فقط با فیلتر ساده‌ی نام پیدا شدند (Persian، Tehran، Shiraz یا حروف پ چ ژ گ) | ۶۶ |

نمونه‌هایی از خروجی: *Sina Persian Grill*، *Deedar Persian Restaurant*، *Tehran Supermarket*، *Narges Shiraz Food*، *Diplomat Exchange | صرافی دیپلمات*، *Dorostkar Persian Translation Services*. اکثر این‌ها لینک صفحه‌ی فیس‌بوک و وب‌سایت هم دارند.

مثبت‌های کاذب هم دیده شد که در [04](../04-iranian-detection.md) بررسی شده است. برای مثال، یک نام پشتو که حرف «چ» دارد و فیلتر ساده آن را فارسی تشخیص داد، و «Cars With Shirazi» که کلمه‌ی Shirazi در آن فقط نام یک شخص است.

## فیلدهای مهم
| فیلد | کاربرد |
|---|---|
| `id` | شناسه‌ی پایدار Overture؛ به‌عنوان `external_id` استفاده می‌شود |
| `names.primary`، `names.common` | نام، که گاهی به چند زبان است |
| `taxonomy.primary`، `taxonomy.hierarchy`، `basic_category` | دسته. **فیلد `categories` از release سپتامبر ۲۰۲۶ حذف شده است.** |
| `websites`، `socials`، `phones`، `emails` | لینک‌ها؛ `socials` معمولاً لینک فیس‌بوک است و گاهی اینستاگرام |
| `addresses`، `geometry` | آدرس و مختصات |
| `sources[].dataset` | سورس اصلی (`meta`، `Microsoft`، `Foursquare` و ...) |
| `confidence` | اطمینان Overture از **وجود داشتن** مکان (ربطی به ایرانی بودن ندارد) |
| `operating_status` | باز یا بسته بودن |

## روش دریافت داده
فایل‌ها Parquet هستند و با HTTP range request فقط بخش لازم خوانده می‌شود:

```python
import pyarrow.dataset as ds, pyarrow.fs as fs, pyarrow.compute as pc

s3 = fs.S3FileSystem(anonymous=True, region="us-west-2")
places = ds.dataset(
    "overturemaps-us-west-2/release/2026-09-23.1/theme=places/type=place/",
    filesystem=s3, format="parquet")

in_bbox = ((pc.field("bbox", "xmin") > W) & (pc.field("bbox", "xmin") < E) &
           (pc.field("bbox", "ymin") > S) & (pc.field("bbox", "ymin") < N))
table = places.to_table(filter=in_bbox, columns=[...])
```

(DuckDB هم راه رایج دیگری است. در این محیط توسعه، دانلود افزونه‌ی `httpfs` آن مسدود بود و برای همین از pyarrow استفاده شد.)

**جریان در فارسی‌یاب:**
1. بعد از هر release جدید (ماهانه)، **همه‌ی** مکان‌های bbox هر شهر فعال گرفته می‌شوند.
2. Detector روی نام، دسته و لینک‌ها اجرا می‌شود.
3. مکان‌هایی که امتیاز حداقل «پایین» دارند، در `business` و `source_record` ذخیره می‌شوند.
4. وب‌سایت این کاندیدها به صف [بررسی وب‌سایت](business-websites.md) می‌رود تا مدرک بیشتری پیدا شود.

نسخه‌ی release در تنظیمات نگهداری می‌شود و آخرین release از لیست `release/` در باکت خوانده می‌شود.

## نشانه‌های ایرانی بودن
- `overture_persian_category`: `taxonomy.primary = persian_restaurant` (وزن ۰٫۷)
- `persian_script_name`، `explicit_keyword` و `iranian_place_name` در نام
- لینک‌های `socials` و `websites` هم برای ادغام با سورس‌های دیگر و هم به‌عنوان «لینک مدرک» استفاده می‌شوند

## لینک نمایش‌داده‌شده به کاربر
Overture صفحه‌ی عمومی برای هر مکان ندارد. بنابراین به کاربر این‌ها نشان داده می‌شود:
- **لینک سورس اصلی:** صفحه‌ی فیس‌بوک (از `socials`) یا وب‌سایت و اینستاگرام. برچسب سورس هم مثلاً «Facebook (از طریق Overture Maps)» است.
- لینک [Google Maps URL](google-places.md#google-maps-urls-بدون-کلید) برای اینکه کاربر خودش نتیجه را روی گوگل‌مپ ببیند

## ذخیره‌سازی
طبق لایسنس، ذخیره‌ی کامل داده مجاز است. ردیف خام در `source_record.raw` ذخیره می‌شود.

## محدودیت‌ها و ریسک‌ها
- پوشش در هر کشور متفاوت است؛ باید برای هر شهر MVP بررسی شود
- بخشی از داده قدیمی است (کسب‌وکارهای بسته‌شده)؛ از `operating_status` و بررسی وب‌سایت کمک گرفته می‌شود
- نام‌ها بیشتر لاتین هستند و نام فارسی کمتر ثبت شده است
- اسکیما در حال تغییر است (مثلاً حذف فیلد `categories` در سپتامبر ۲۰۲۶). نسخه‌ی release باید در کد ثابت و با تست به‌روز شود.

## ذکر منبع
«Overture Maps Foundation» با لینک به https://overturemaps.org، به همراه ذکر سورس‌های اصلی‌ای که لایسنسشان لازم می‌داند (طبق صفحه‌ی attribution)
