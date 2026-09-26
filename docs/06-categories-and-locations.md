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
| `community` | انجمن‌ها، مراکز فرهنگی، مدارس فارسی | `specialty_school`, `religious_organization`, `social_service_organization` (بررسی شود) | `amenity=community_centre\|place_of_worship`, `club=*` | — | Iranian community centre, کانون ایرانیان |
| `translator` | ترجمه و دارالترجمه | `b2b_office_and_professional_service` (+ taxonomy `translation_service`؛ بررسی شود) | `office=translator` | — | Farsi translator, مترجم رسمی فارسی |
| `other` | سایر | بقیه | — | — | — |

نگاشت در [`data/categories.yaml`](../data/categories.yaml) است و مقادیرش با داده‌ی واقعی تورنتو (release `2026-09-23.1`) تطبیق داده شده‌اند. ترتیب تطبیق: اول `taxonomy.hierarchy` (از جزئی‌ترین سطح)، بعد `basic_category`. ستون Overture در جدول بالا خلاصه است؛ مرجع اصلی همان فایل YAML است.

\* قبل از استفاده، وجود نوع `persian_restaurant` در لیست رسمی types نسخه‌ی New بررسی شود. اگر وجود نداشت، از `restaurant` به همراه `textQuery="Persian restaurant"` استفاده می‌شود.

دسته‌های MVP: ۸ دسته‌ی اول. `accounting`، `education`، `community` (سورس اصلی: مؤسسات غیرانتفاعی IRS و CRA و Wikidata) و `translator` (سورس اصلی: رجیسترهای BDÜ و ATIO) در فاز ۳ اضافه می‌شوند.

## کشورها و شهرها

- **MVP:** شهرها در [`data/cities.yaml`](../data/cities.yaml) به‌صورت دستی تعریف شده‌اند، با bbox که **کل منطقه‌ی شهری** را می‌پوشاند و فقط محدوده‌ی رسمی شهر نیست (مثلاً North York و Richmond Hill برای تورنتو، یا Irvine برای لس‌آنجلس). اضافه کردن شهر: یک ردیف در این فایل و اجرای `farsiyab db load`.
- **گسترش (فاز ۵):** [GeoNames](https://www.geonames.org/) (فایل `cities15000`، رایگان با لایسنس CC BY 4.0) برای مختصات و نام‌های جایگزین.
- **محدوده‌ی شهر (bbox) در فاز ۵:** از Nominatim (OpenStreetMap)، فقط یک بار برای هر شهر و با رعایت سقف ۱ درخواست در ثانیه.
- **نام فارسی شهرها:** از `alternateNames` در GeoNames یا برچسب `name:fa` در OSM؛ در صورت نبودن، به‌صورت دستی وارد می‌شود.

### هر شهری در دنیا ✅ (فاز ۵)

فهرست ثابتی از کشورها و شهرها وجود ندارد. کاربر نام **هر شهری** را می‌نویسد و از پیشنهادها انتخاب می‌کند:

1. **پیشنهادها** در حین تایپ از [Photon](https://photon.komoot.io) می‌آیند (داده‌ی OpenStreetMap، بدون کلید، ساخته‌شده برای جست‌وجوی هم‌زمان با تایپ). درخواست‌ها از سرور ما فرستاده می‌شوند (`GET /api/v1/places`)، پس IP کاربر به سرویس بیرونی نمی‌رسد، و نتیجه‌ها در حافظه cache می‌شوند. فقط مکان‌های مسکونی (شهر، شهرک، روستا، ...) نگه داشته می‌شوند و شهرها قبل از روستاها می‌آیند. Nominatim برای این کار مناسب نیست، چون سیاست استفاده‌اش جست‌وجوی هم‌زمان با تایپ را ممنوع کرده است.
2. **ساخت شهر در اولین استفاده** (`POST /api/v1/cities`): دو درخواست به Nominatim `lookup` (انگلیسی و فارسی، با ۱ ثانیه فاصله):
   - bbox شهر ۲۵٪ از هر طرف بزرگ‌تر می‌شود تا حومه‌ها را هم بگیرد. حداقل ۰٫۱۸ درجه از مرکز فاصله دارد (برای شهرهایی که فقط یک نقطه‌اند) و حداکثر ۱٫۲ درجه است (تا یک شهر معادل ایندکس کل یک استان نشود).
   - نام فارسی از `name:fa`، و نام فارسی کشور از پاسخ فارسی Nominatim گرفته می‌شود.
   - `regions` از کد ISO 3166-2 گرفته می‌شود (`US-CA` → `CA`، `GB-ENG` → `ENG`، و برای فرانسه département، یعنی `FR-75` → `75`). پس ثبت‌های IRS، CRA، ACNC، Charity Commission و SIRENE برای شهرهای جدید هم کار می‌کنند.
   - اگر نقطه‌ی انتخاب‌شده داخل bbox یک شهر موجود در همان کشور باشد (مثلاً Irvine داخل لس‌آنجلس)، همان شهر برگردانده می‌شود.
3. **ایندکس:** اولین جست‌وجو در شهر جدید یک job ایندکس در صف می‌گذارد و «جست‌وجوی زنده» پیشرفت آن را نشان می‌دهد ([ADR-001](decisions/001-indexed-plus-live-search.md)). برای این کار **worker باید روشن باشد** (`farsiyab-worker.service`).
4. **محدودیت‌ها:** حداکثر ۱۰ شهر جدید در روز برای هر کاربر و ۲۰۰ شهر جدید در روز در کل، چون هر شهر یک ایندکس کامل لازم دارد.
5. **ایران، افغانستان و تاجیکستان** در پیشنهادها نیستند. در این کشورها تقریباً همه‌ی کسب‌وکارها فارسی‌زبان هستند و فارسی‌یاب برای پیدا کردن فارسی‌زبان‌ها در خارج از این کشورهاست.

`data/cities.yaml` حالا فقط **شهرهای منتخب** است. این شهرها در صفحه‌ی اول به‌عنوان «مرور بر اساس شهر» نمایش داده می‌شوند و bbox و منابع آن‌ها دستی تنظیم شده است. شهرهایی که کاربران اضافه می‌کنند در دیتابیس با `added_by = 'visitor'` ذخیره می‌شوند. کد: `farsiyab/places.py`.

### شهرهای منتخب (MVP)

انتخاب بر اساس جمعیت شناخته‌شده‌ی ایرانیان:

| کشور | شهرها |
|---|---|
| آمریکا (US) | لس‌آنجلس، سن‌خوزه / بی‌اریا، هیوستون، واشنگتن دی‌سی |
| کانادا (CA) | تورنتو، ونکوور، مونترال |
| آلمان (DE) | هامبورگ، برلین، فرانکفورت |

### شهرهای فاز ۵ ✅

| کشور | شهرها | آستانه‌ی نمایش |
|---|---|---|
| بریتانیا (GB) | لندن، منچستر | ۰٫۲۵ (پیش‌فرض) |
| سوئد (SE) | استکهلم، گوتنبرگ | ۰٫۲۵ |
| هلند (NL) | آمستردام | ۰٫۲۵ |
| فرانسه (FR) | پاریس | ۰٫۲۵ |
| استرالیا (AU) | سیدنی، ملبورن | ۰٫۲۵ |
| ترکیه (TR) | استانبول | **۰٫۴۵** |
| امارات (AE) | دبی | **۰٫۴۵** |

- bbox هر شهر یک بار از Nominatim گرفته شد و بعد دستی تا کل منطقه‌ی شهری گسترش داده شد. مثلاً «Greater Sydney» در Nominatim به یک خیابان رسید، و مرز «Dubai» کل امیرنشین را با بیابان‌هایش پوشش می‌داد. نام فارسی شهرها از `name:fa` در OSM گرفته شد.
- **آستانه‌ی جدا برای هر کشور:** فیلد `min_display_score` در بخش `countries` فایل `cities.yaml`. در ترکیه و امارات خط فارسی، نام‌های ایرانی و مسافران ایرانی آن‌قدر زیاد است که یک نشانه‌ی ضعیف (مثل «Tehran» در نام) کافی نیست. پس فقط نتایج «متوسط» و «بالا» نمایش داده می‌شوند. این آستانه در جست‌وجو، نقشه، صفحه‌های شهر، sitemap، گزارش پوشش و نمونه‌گیری برچسب اعمال می‌شود (`farsiyab/display.py`).
- **زبان‌های جدید در Detector:** سوئدی (persisk، iransk)، هلندی (Perzisch، Iraans)، ترکی (İranlı، Farsça، İran mutfağı) و املای عربی (إيراني، فارسي). یکسان‌سازی متن حالا حرف به حرف است، چون `"İ".lower()` در پایتون دو کاراکتر برمی‌گرداند و جای بریده شدن snippet را جابه‌جا می‌کرد.

توجه: در کشورهایی مثل ترکیه، امارات و عراق، متن فارسی و نام‌های ایرانی زیاد دیده می‌شود ولی لزوماً نشانه‌ی کسب‌وکار ایرانی نیست. آستانه‌ها در این کشورها بعداً جداگانه تنظیم می‌شوند.
