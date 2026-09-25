# سورس‌های «فقط لینک» (بدون گرفتن داده)

- **وضعیت:** ✅ MVP
- **حساب کاربری:** ❌ لازم نیست
- **هزینه:** رایگان

## ایده
از بعضی سرویس‌ها نمی‌شود بدون حساب یا بدون نقض قوانین داده گرفت. ولی **ساختن لینک جست‌وجو** به آن‌ها همیشه مجاز است. این لینک‌ها کاربر را به همان سرویس می‌برند تا خودش نتیجه را ببیند و بررسی کند. **هیچ درخواستی از سرور ما به این سرویس‌ها ارسال نمی‌شود.**

این لینک‌ها در بخش «سورس‌ها» (یعنی جایی که نتیجه پیدا شده) نمایش داده **نمی‌شوند**. جایشان در بخش جداگانه‌ای به اسم **«بررسی در ...»** است.

## لینک‌های هر نتیجه
| سرویس | الگوی لینک | مستندات | ارزش برای کاربر |
|---|---|---|---|
| **Google Maps** | `https://www.google.com/maps/search/?api=1&query={name}, {address}` | [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started) (رسمی، بدون کلید) | نظرات، عکس‌ها، ساعت کاری |
| **Apple Maps** | `https://maps.apple.com/?q={name}&ll={lat},{lng}` | [Apple Map Links](https://developer.apple.com/library/archive/featuredarticles/iPhoneURLScheme_Reference/MapLinks/MapLinks.html) | کاربران آیفون |
| **مسیریابی** | `https://www.google.com/maps/dir/?api=1&destination={lat},{lng}` | Maps URLs | |
| **OpenStreetMap** | `https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=18/{lat}/{lng}` | | |

## لینک‌های صفحه‌ی نتایج (برای هر شهر و دسته)
وقتی نتایج ما برای یک شهر و دسته کم است، به کاربر پیشنهاد داده می‌شود که **خودش** در این سرویس‌ها بگردد:

| سرویس | الگوی لینک |
|---|---|
| Google Maps | `https://www.google.com/maps/search/?api=1&query=Persian+{category}+{city}` |
| Instagram (هشتگ) | `https://www.instagram.com/explore/tags/{city}ایرانی/` (مثلاً `#تورنتو_ایرانی`)؛ الگوی هشتگ‌ها در `data/hashtags.yaml` |
| Google Search | `https://www.google.com/search?q=…` |
| رجیسترهای رسمی | لینک جست‌وجوی زبان در [رجیسترهای حرفه‌ای](professional-registries.md) (مثلاً پزشکان فارسی‌زبان در CPSO) |
| دایرکتوری‌های ایرانی | لینک صفحه‌ی همان شهر و دسته در [دایرکتوری‌ها](community-directories.md) |

## نشانه‌ها
هیچ نشانه‌ای از این سورس‌ها گرفته نمی‌شود، چون داده‌ای دریافت نمی‌کنیم.
