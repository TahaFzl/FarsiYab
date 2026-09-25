# ۶. دسته‌بندی‌ها و مکان‌ها

## دسته‌بندی‌ها

هر دسته به نوع‌های معادل در هر سورس نگاشت می‌شود. این نگاشت در `data/categories.yaml` نگهداری می‌شود.

| slug | فارسی | OSM tags | Google Places (New) types | کلیدواژه‌ی جست‌وجوی وب |
|---|---|---|---|---|
| `restaurant` | رستوران و کافه | `amenity=restaurant\|cafe\|fast_food` | `restaurant`, `cafe`, `persian_restaurant`* | Persian restaurant, رستوران ایرانی |
| `grocery` | سوپرمارکت و فروشگاه مواد غذایی | `shop=supermarket\|convenience\|greengrocer\|deli` | `grocery_store`, `supermarket` | Persian grocery, سوپرمارکت ایرانی |
| `bakery` | نانوایی و شیرینی‌فروشی | `shop=bakery\|pastry\|confectionery` | `bakery` | Persian bakery, شیرینی ایرانی |
| `doctor` | پزشک | `amenity=doctors\|clinic`, `healthcare=*` | `doctor`, `medical_clinic` | Farsi speaking doctor, دکتر ایرانی |
| `doctor/dentist` | دندان‌پزشک | `amenity=dentist` | `dentist` | Farsi speaking dentist |
| `lawyer` | وکیل و مهاجرت | `office=lawyer` | `lawyer` | Iranian lawyer, وکیل ایرانی |
| `real_estate` | مشاور املاک | `office=estate_agent` | `real_estate_agency` | Persian realtor |
| `beauty` | آرایشگاه و زیبایی | `shop=hairdresser\|beauty` | `beauty_salon`, `hair_salon` | آرایشگاه ایرانی |
| `accounting` | حسابداری و مالیات | `office=accountant` | `accounting` | Iranian accountant |
| `education` | آموزش و کلاس فارسی | `amenity=school\|language_school` | `school` | Persian school, کلاس فارسی |
| `other` | سایر | — | — | — |

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
