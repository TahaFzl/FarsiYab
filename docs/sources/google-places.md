# Google Places API (New)

- **شناسه در کد:** `google_places`
- **وضعیت:** ✅ MVP با سقف سخت مصرف
- **نوع دسترسی:** API رسمی (همان داده‌ی Google Maps)
- **مستندات:** https://developers.google.com/maps/documentation/places/web-service/op-overview
- **قیمت و سهمیه:** https://developers.google.com/maps/documentation/places/web-service/usage-and-billing
- **قوانین:** https://cloud.google.com/maps-platform/terms/maps-service-terms
- **احراز هویت:** API key. **نیاز به حساب Google Cloud با کارت بانکی دارد**، حتی برای استفاده‌ی رایگان.

## هزینه و سهمیه (بررسی سپتامبر ۲۰۲۶)
از مارس ۲۰۲۵ اعتبار ثابت ۲۰۰ دلاری حذف شده و به‌جای آن **هر SKU سهمیه‌ی رایگان ماهانه‌ی جداگانه** دارد:

| رده‌ی SKU | سهمیه‌ی رایگان در ماه | مثال |
|---|---|---|
| Essentials | ۱۰٬۰۰۰ | Text Search با فقط `places.id` (IDs Only)، Place Details Essentials |
| Pro | ۵٬۰۰۰ | Text Search Pro (نام، آدرس، نوع و ...) |
| Enterprise | ۱٬۰۰۰ | فیلدهایی مثل `websiteUri` و شماره‌تلفن |

**هزینه با فیلدهای درخواستی (Field Mask) تعیین می‌شود.** بنابراین:
- جست‌وجو فقط با فیلدهای رده‌ی Pro انجام می‌شود (`places.id,places.displayName,places.formattedAddress,places.location,places.types,places.googleMapsUri`)
- فیلدهای Enterprise (وب‌سایت و تلفن) فقط برای کاندیدهایی گرفته می‌شوند که از قبل امتیاز ایرانی بودنشان حداقل «پایین» است

سقف‌ها در Quota Guard: Text Search Pro روی ۴٬۰۰۰ و Details Enterprise روی ۸۰۰ در ماه. علاوه بر این، در Google Cloud Console هم سقف روزانه تنظیم می‌شود.

## کوئری نمونه
```http
POST https://places.googleapis.com/v1/places:searchText
X-Goog-Api-Key: …
X-Goog-FieldMask: places.id,places.displayName,places.formattedAddress,places.location,places.types,places.googleMapsUri,nextPageToken

{
  "textQuery": "Persian restaurant",
  "locationRestriction": { "rectangle": { … bbox شهر … } },
  "languageCode": "en",
  "pageSize": 20
}
```
کوئری‌ها از ستون «کلیدواژه‌ی جست‌وجوی وب» در [06](../06-categories-and-locations.md) ساخته می‌شوند. برای هر دسته هم کوئری انگلیسی و هم کوئری فارسی اجرا می‌شود (مثلاً «رستوران ایرانی»)، چون گوگل نام‌های فارسی را هم ایندکس می‌کند.

## نشانه‌های ایرانی بودن
- `google_type_persian`: نوع `persian_restaurant` در `types` (در صورت وجود)
- `persian_script_name` و `explicit_keyword` و `iranian_place_name` در `displayName`
- اینکه گوگل برای کوئری «Persian restaurant» این نتیجه را برگردانده، **به‌تنهایی مدرک نیست**، چون گوگل نتایج مشابه (مثلاً رستوران‌های ترکی یا لبنانی) را هم برمی‌گرداند

## لینک نمایش‌داده‌شده به کاربر
`googleMapsUri` (لینک مستقیم به همان مکان در Google Maps)

## ⚠️ ذخیره‌سازی (مهم)
طبق قوانین Google Maps Platform:
- **`place_id` قابل ذخیره‌ی دائمی است.**
- **مختصات** حداکثر **۳۰ روز** قابل کش است.
- **بقیه‌ی محتوا** (نام، آدرس و ...) نباید به‌صورت دائمی ذخیره شود.

طراحی ما:
- در `source_record` فقط `external_id = place_id` و `url` ذخیره می‌شود و `raw` خالی می‌ماند.
- امتیاز و مدارک (evidence) خودمان ذخیره می‌شوند. متن snippet مدرک باید کوتاه باشد (مثلاً فقط نوع مکان) و در به‌روزرسانی ماهانه تازه شود.
- اگر کسب‌وکاری **فقط** در گوگل پیدا شده باشد، هنگام نمایش، جزئیاتش با Place Details (Essentials، با سهمیه‌ی ۱۰٬۰۰۰ در ماه) گرفته و موقتاً کش می‌شود.
- **داده‌ی Places نباید روی نقشه‌ی غیرگوگلی نمایش داده شود.** روی نقشه‌ی OSM (فاز ۴) فقط نتایجی نشان داده می‌شوند که مختصاتشان از سورس دیگری آمده باشد. این مورد قبل از پیاده‌سازی نقشه دوباره با متن قوانین چک شود.

## محدودیت‌ها و ریسک‌ها
- حداکثر ۶۰ نتیجه برای هر کوئری (۳ صفحه‌ی ۲۰تایی)؛ برای شهرهای بزرگ باید bbox را به چند بخش تقسیم کرد
- ریسک اصلی هزینه‌ی ناخواسته است که با Quota Guard و سقف کنسول کنترل می‌شود
- با سهمیه‌ی رایگان، هر شهر و دسته حدوداً ماهی یک بار به‌روزرسانی می‌شود

## ذکر منبع
لوگو یا متن «Google Maps» کنار داده‌های گوگل، طبق [راهنمای attribution](https://developers.google.com/maps/documentation/places/web-service/policies)
