# ۶. دسته‌بندی‌ها و مکان‌ها

## دسته‌بندی‌ها

هر دسته به نوع‌های معادل در هر سورس نگاشت می‌شود. این نگاشت در `data/categories.yaml` نگهداری می‌شود.

| slug | فارسی | Overture `basic_category` | OSM tags | Google Places (New) types (اختیاری) | کلیدواژه‌ی جست‌وجوی وب (اختیاری) |
|---|---|---|---|---|---|
| `restaurant` | رستوران و کافه | `restaurant`, `fast_food_restaurant`, `cafe`, `food_service` | `amenity=restaurant\|cafe\|fast_food` | `restaurant`, `cafe`, `persian_restaurant`* | Persian restaurant, رستوران ایرانی |
| `grocery` | سوپرمارکت و فروشگاه مواد غذایی | `food_and_beverage_store`, `superstore` | `shop=supermarket\|convenience\|greengrocer\|deli` | `grocery_store`, `supermarket` | Persian grocery, سوپرمارکت ایرانی |
| `bakery` | نانوایی و شیرینی‌فروشی | `food_and_beverage_store` (+ taxonomy `bakery`) | `shop=bakery\|pastry\|confectionery` | `bakery` | Persian bakery, شیرینی ایرانی |
| `doctor` | پزشک | `medical_service`, `health_care`, `primary_care_or_general_clinic`, `specialized_health_care`, `walk_in_clinic`, `pediatric_clinic`, `behavioral_or_mental_health_clinic` | `amenity=doctors\|clinic`, `healthcare=*` | `doctor`, `medical_clinic` | Farsi speaking doctor, دکتر ایرانی |
| `doctor/dentist` | دندان‌پزشک | `dental_clinic` | `amenity=dentist` | `dentist` | Farsi speaking dentist |
| `lawyer` | وکیل و مهاجرت | `attorney_or_law_firm` | `office=lawyer` | `lawyer` | Iranian lawyer, وکیل ایرانی |
| `real_estate` | مشاور املاک | `real_estate_service` | `office=estate_agent` | `real_estate_agency` | Persian realtor |
| `beauty` | آرایشگاه و زیبایی | `personal_or_beauty_service`, `personal_care_and_beauty_store` | `shop=hairdresser\|beauty` | `beauty_salon`, `hair_salon` | آرایشگاه ایرانی |
| `accounting` | حسابداری و مالیات | `financial_service` | `office=accountant` | `accounting` | Iranian accountant |
| `education` | آموزش و کلاس فارسی | `specialty_school`, `tutoring_service` | `amenity=school\|language_school` | `school` | Persian school, کلاس فارسی |
| `other` | سایر | بقیه | — | — | — |

مقادیر `basic_category` از داده‌ی واقعی تورنتو (release `2026-08-19.0`) استخراج شده‌اند. برای رستوران‌ها، `taxonomy.primary = persian_restaurant` در release `2026-09-23.1` وجود دارد (۵۴ مورد در تورنتو). قبل از پیاده‌سازی، لیست کامل taxonomy از مستندات Overture گرفته شود.

\* قبل از استفاده، وجود نوع `persian_restaurant` در لیست رسمی types نسخه‌ی New بررسی شود. اگر وجود نداشت، از `restaurant` به همراه `textQuery="Persian restaurant"` استفاده می‌شود.

دسته‌های MVP: ۸ دسته‌ی اول (بدون `accounting` و `education`).

## کشورها و شهرها

- **منبع داده:** [GeoNames](https://www.geonames.org/) (فایل `cities15000`، رایگان با لایسنس CC BY 4.0). مختصات مرکز شهرها و نام‌های جایگزین از همین فایل می‌آید.
- **محدوده‌ی شهر (bbox):** از Nominatim (OpenStreetMap) و فقط یک بار برای هر شهر گرفته و ذخیره می‌شود (با رعایت سقف ۱ درخواست در ثانیه).
- **نام فارسی شهرها:** از `alternateNames` در GeoNames یا برچسب `name:fa` در OSM؛ در صورت نبودن، به‌صورت دستی وارد می‌شود.

### شهرهای MVP

انتخاب بر اساس جمعیت شناخته‌شده‌ی ایرانیان:

| کشور | شهرها |
|---|---|
| آمریکا (US) | لس‌آنجلس، سن‌خوزه / بی‌اریا، هیوستون، واشنگتن دی‌سی |
| کانادا (CA) | تورنتو، ونکوور، مونترال |
| آلمان (DE) | هامبورگ، برلین، فرانکفورت |

(بعد از MVP: انگلستان، سوئد، استرالیا، ترکیه، امارات، هلند، فرانسه و ...)

توجه: در کشورهایی مثل ترکیه، امارات و عراق، متن فارسی و نام‌های ایرانی زیاد دیده می‌شود ولی لزوماً نشانه‌ی کسب‌وکار ایرانی نیست. آستانه‌ها در این کشورها بعداً جداگانه تنظیم می‌شوند.
