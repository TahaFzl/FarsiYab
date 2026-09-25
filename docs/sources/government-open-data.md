# داده‌های باز دولتی (مجوز کسب‌وکار، شرکت‌ها، مؤسسات غیرانتفاعی)

- **شناسه در کد:** `gov:<slug>` (مثلاً `gov:la_business`)
- **وضعیت:** ✅ پیاده‌سازی و تست‌شده روی داده‌ی واقعی (فاز ۳): `gov:la_business`، `gov:vancouver_business`، `gov:toronto_business`، `gov:irs_eo_bmf`، `gov:cra_charities`
- **حساب کاربری:** ❌ لازم نیست. همه‌ی موارد زیر دانلود یا API بدون کلید دارند. در Socrata، app token اختیاری است و فقط محدودیت نرخ را بالا می‌برد.
- **هزینه:** رایگان
- **لایسنس:** لایسنس‌های داده‌ی باز دولتی (Open Government Licence و مشابه) که استفاده‌ی تجاری را مجاز می‌دانند
- **تست‌شده؟** ✅ بله (۲۰۲۶-۰۹-۲۵). کد در `services/api/farsiyab/adapters/government.py`.

## چرا
شهرداری‌ها و دولت‌ها لیست **همه‌ی** کسب‌وکارهای دارای مجوز را منتشر می‌کنند. این لیست‌ها کامل‌تر از نقشه‌ها هستند، به‌خصوص برای کسب‌وکارهای کوچک و خانگی. در اکثرشان فیلدی درباره‌ی زبان وجود ندارد، ولی **نام تجاری** وجود دارد (مثلاً «Tehran Market Inc» یا «Pars Auto Repair»). Detector روی این نام‌ها اجرا می‌شود.

## کاتالوگ

### مجوز کسب‌وکار شهرها
| شهر | دیتاست | پلتفرم | لینک |
|---|---|---|---|
| لس‌آنجلس | Listing of Active Businesses (ماهانه) | Socrata | https://data.lacity.org/Administration-Finance/Listing-of-Active-Businesses/6rrh-rzua |
| تورنتو | Business Licences and Permits (ML&S) | CKAN | https://open.toronto.ca/dataset/municipal-licensing-and-standards-business-licences-and-permits/ |
| ونکوور | Business licences (به‌روزرسانی روزانه) | Opendatasoft | https://opendata.vancouver.ca/explore/dataset/business-licences/ |
| سن‌فرانسیسکو | Registered Business Locations | Socrata | data.sfgov.org (بررسی شود) |
| سایر شهرهای MVP | بررسی شود (Houston، DC، San Jose، Montreal) | | |

آلمان مجوز کسب‌وکار باز ندارد. Handelsregister هم دانلود انبوه آزاد ندارد.

### مؤسسات غیرانتفاعی (دسته‌ی جدید `community`)
انجمن‌های فرهنگی، کانون‌ها، مدارس فارسی و هیئت‌ها:

| کشور | دیتاست | لینک |
|---|---|---|
| آمریکا | IRS Exempt Organizations Business Master File (CSV برای هر ایالت) | https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf |
| کانادا | CRA List of Charities (سالانه، روی پورتال داده‌ی باز) | https://open.canada.ca/data/en/organization/cra-arc |

نام‌هایی مثل «Iranian American …»، «Persian Cultural …» یا «Pars …» با Detector پیدا می‌شوند.

### ثبت شرکت‌ها
| کشور | دیتاست | وضعیت |
|---|---|---|
| کانادا (فدرال) | Corporations Canada open data (دانلود انبوه) | ✅ بدون حساب؛ فقط نام و آدرس ثبت‌شده |
| انگلستان | Companies House | ⏸ اختیاری؛ API key رایگان می‌خواهد (= حساب) |

## نشانه‌ها
- فقط نشانه‌های مبتنی بر نام (`persian_script_name`، `explicit_keyword`، `iranian_place_name`). **وزن اضافه‌ای برای خود سورس وجود ندارد**، چون داشتن مجوز چیزی درباره‌ی ایرانی بودن نمی‌گوید.
- ارزش اصلی این سورس‌ها **کشف کاندید** و **تأیید فعال بودن** است (`status = active`).

## ⚠️ حریم خصوصی
در این دیتاست‌ها گاهی **نام شخص** صاحب کسب‌وکار یا آدرس خانه (برای کسب‌وکار خانگی) ثبت شده است. قوانین ما:
- نام شخص ذخیره یا نمایش داده **نمی‌شود**؛ فقط نام تجاری
- آدرسی که مسکونی به نظر می‌رسد (کسب‌وکار خانگی) نمایش داده **نمی‌شود**؛ فقط شهر
- **مختصات این سورس‌ها هرگز ذخیره یا نمایش داده نمی‌شود** (`private_location`). آدرس فقط geocode می‌شود تا با رکورد همان کسب‌وکار در سورس‌های دیگر (OSM، Overture) ادغام شود. کسب‌وکاری که فقط از این سورس آمده باشد بدون آدرس و بدون نقشه، فقط با نام تجاری و شهر نمایش داده می‌شود
- قبل از geocode، نام با Detector بررسی می‌شود (`looks_iranian`) تا فقط کاندیدهای واقعی به Nominatim فرستاده شوند

## پیاده‌سازی
| شناسه | دیتاست | نکات |
|---|---|---|
| `gov:la_business` | LA Listing of Active Businesses (Socrata) | فیلتر `where` در خود API با کلمات لاتین لغت‌نامه (`latin_hint_terms`)؛ نام حقوقی فقط وقتی استفاده می‌شود که پسوند شرکت داشته باشد (Inc، LLC، ...) تا نام شخص وارد نشود؛ دسته از کد NAICS |
| `gov:vancouver_business` | Business licences (Opendatasoft) | فقط `status = Issued` در دو سال اخیر؛ نام‌های داخل پرانتز (نام شخص در کسب‌وکار انفرادی) کنار گذاشته می‌شوند |
| `gov:toronto_business` | ML&S Business Licences (CKAN) | جدیدترین CSV؛ فقط `Operating Name`، نه `Client Name` |
| `gov:irs_eo_bmf` | IRS EO BMF (`eo_{state}.csv`) | ایالت‌ها از `regions` شهر در `cities.yaml`؛ ستون ICO هرگز استفاده نمی‌شود |
| `gov:cra_charities` | CRA List of Charities | جدیدترین CSV «Identification» |

آدرس‌ها با `farsiyab/geocode.py` به مختصات تبدیل می‌شوند: اول Nominatim، اگر نشد Photon، و اگر باز هم نشد فقط کد پستی. واحد و طبقه قبل از جست‌وجو حذف می‌شوند (`clean_address`). حداکثر ۱ درخواست در ثانیه، و نتیجه‌ها در جدول `geocode_cache` نگه داشته می‌شوند (خطاها ذخیره نمی‌شوند).

سن‌فرانسیسکو، هیوستون، DC، سن‌خوزه و مونترال هنوز آداپتر مجوز شهرداری ندارند (فقط IRS یا CRA).

## لینک به کاربر
صفحه‌ی دیتاست در پورتال، به همراه برچسب «ثبت در مجوزهای شهرداری {شهر}»
