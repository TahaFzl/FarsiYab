# فارسی‌یاب (FarsiYab)

موتور جست‌وجوی کسب‌وکارهای ایرانی و فارسی‌زبان در خارج از ایران.

کاربر کشور و شهر را انتخاب می‌کند، دسته‌بندی‌هایی مثل دکتر، رستوران یا فروشگاه را برمی‌گزیند و جست‌وجو می‌کند. فارسی‌یاب نتایج را از چند سورس جمع می‌کند و برای هر نتیجه نشان می‌دهد:

- **از کدام سورس پیدا شده** (مثلاً Facebook و Microsoft و Foursquare از طریق Overture Maps، OpenStreetMap، اینستاگرام، وب‌سایت خود کسب‌وکار) + لینک «دیدن روی Google Maps»
- **لینک مدرک**: صفحه‌ای که نشان می‌دهد این کسب‌وکار ایرانی یا فارسی‌زبان است
- **چرا ایرانی تشخیص داده شده** (مثلاً «نام فارسی دارد» یا «در توضیحات نوشته We speak Farsi»)
- **میزان اطمینان** (بالا، متوسط، پایین)

> وضعیت فعلی: **مرحله‌ی طراحی و مستندسازی**. هنوز کدی نوشته نشده است.

## مستندات

| فایل | موضوع |
|---|---|
| [docs/00-overview.md](docs/00-overview.md) | هدف، کاربران و جریان استفاده |
| [docs/01-requirements.md](docs/01-requirements.md) | نیازمندی‌های کارکردی و غیرکارکردی؛ محدوده‌ی MVP |
| [docs/02-architecture.md](docs/02-architecture.md) | معماری سیستم (ایندکس از قبل + جست‌وجوی لایو) |
| [docs/03-data-model.md](docs/03-data-model.md) | مدل داده و جدول‌های دیتابیس |
| [docs/04-iranian-detection.md](docs/04-iranian-detection.md) | الگوریتم تشخیص «ایرانی بودن» و امتیاز اطمینان |
| [docs/05-api.md](docs/05-api.md) | API بک‌اند |
| [docs/06-categories-and-locations.md](docs/06-categories-and-locations.md) | دسته‌بندی‌ها، کشورها و شهرها |
| [docs/07-legal-and-privacy.md](docs/07-legal-and-privacy.md) | قوانین سورس‌ها، حریم خصوصی، حذف اطلاعات |
| [docs/08-roadmap.md](docs/08-roadmap.md) | فازهای توسعه |
| [docs/sources/](docs/sources/README.md) | **کاتالوگ سورس‌ها**: یک فایل برای هر سورس |
| [data/sources.yaml](data/sources.yaml) | تعریف ماشین‌خوان ۲۷ سورس (کد از این فایل می‌خواند) |
| [docs/decisions/](docs/decisions/README.md) | تصمیم‌های معماری (ADR) |

## تکنولوژی (خلاصه)

- **فرانت‌اند:** Next.js (TypeScript)، دوزبانه‌ی فارسی (راست‌به‌چپ) و انگلیسی
- **بک‌اند و کراولرها:** Python با FastAPI
- **دیتابیس:** PostgreSQL به همراه PostGIS و جست‌وجوی متنی
- **صف کارها:** Redis
- **بودجه:** فقط سرویس‌های رایگان
- **بدون حساب کاربری:** MVP فقط با سورس‌هایی ساخته می‌شود که حساب، کلید یا کارت بانکی نمی‌خواهند ([ADR-005](docs/decisions/005-no-account-sources-first.md)). سورس اصلی [Overture Maps](docs/sources/overture-maps.md) است که روی داده‌ی واقعی تست شده.
