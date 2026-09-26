# ۵. API بک‌اند

پیشوند همه‌ی مسیرها `/api/v1` است. پاسخ‌ها JSON هستند. پارامتر `lang` (`fa` یا `en`) زبان نام‌ها را تعیین می‌کند.

## داده‌های پایه

### `GET /countries`
```json
[{ "code": "CA", "name": "کانادا", "city_count": 4 }]
```

### `GET /countries/{code}/cities?q=tor`
```json
[{ "slug": "toronto", "name": "تورنتو", "name_en": "Toronto" }]
```

### `GET /categories`
```json
[{ "slug": "doctor", "name": "پزشک", "children": [{ "slug": "doctor/dentist", "name": "دندان‌پزشک" }] }]
```

## جست‌وجو

### `GET /search`

| پارامتر | اجباری | توضیح |
|---|---|---|
| `country` | ✔ | کد ISO |
| `city` | ✔ | slug شهر |
| `categories` | ✔ | لیست slug ها با جداکننده‌ی کاما |
| `min_confidence` | | `low` (پیش‌فرض)، `medium` یا `high` |
| `sources` | | فیلتر بر اساس سورس |
| `sort` | | `confidence` (پیش‌فرض)، `name` یا `distance` |
| `lat`, `lng` | | برای مرتب‌سازی بر اساس فاصله |
| `page`, `page_size` | | صفحه‌بندی (پیش‌فرض ۲۰ نتیجه) |

پاسخ:
```json
{
  "results": [
    {
      "id": "7b1e…",
      "name": { "fa": "رستوران شیراز", "latin": "Shiraz Kitchen" },
      "categories": ["restaurant"],
      "address": "123 Yonge St, Toronto",
      "location": { "lat": 43.65, "lng": -79.38 },
      "contact": { "phone": "+14165550100", "website": "https://…" },
      "confidence": { "score": 0.86, "label": "high" },
      "sources": [
        { "id": "overture", "name": "Overture Maps", "url": "https://www.facebook.com/470792293411166", "via": ["meta"] },
        { "id": "osm", "name": "OpenStreetMap", "url": "https://www.openstreetmap.org/node/123" },
        { "id": "instagram", "name": "Instagram", "url": "https://www.instagram.com/shirazkitchen/" }
      ],
      "evidence": [
        {
          "signal": "osm_cuisine_tag",
          "label": "برچسب غذای ایرانی در OpenStreetMap",
          "snippet": "cuisine=persian",
          "url": "https://www.openstreetmap.org/node/123",
          "source": "osm",
          "weight": 0.7
        }
      ],
      "links": {
        "google_maps": "https://www.google.com/maps/search/?api=1&query=Shiraz%20Kitchen%2C%20123%20Yonge%20St",
        "apple_maps": "https://maps.apple.com/?q=Shiraz%20Kitchen&ll=43.65,-79.38",
        "openstreetmap": "https://www.openstreetmap.org/?mlat=43.65&mlon=-79.38#map=18/43.65/-79.38"
      },
      "last_verified_at": "2026-09-20T03:12:00Z"
    }
  ],
  "city": { "slug": "toronto", "country": "CA", "name": "تورنتو", "last_indexed_at": "2026-09-25T16:45:28Z" },
  "categories": ["restaurant"],
  "total": 37,
  "page": 1,
  "page_size": 20,
  "live_search": { "job_id": "c9f2…", "status": "running" }
}
```

اگر شهر تازه ایندکس شده باشد، `live_search` برابر `null` است. در غیر این صورت یک job ایندکس ساخته می‌شود (یا job در حال انجام برگردانده می‌شود).

نکته‌ها:
- `sources` هم رکوردهای سورس‌ها را شامل می‌شود و هم پروفایل‌های فیس‌بوک، اینستاگرام و تلگرام پیدا‌شده. `via` برای Overture سورس اصلی داده را نشان می‌دهد (مثلاً `meta` یعنی صفحه‌ی فیس‌بوک).
- اگر رکورد Overture نه صفحه‌ی فیس‌بوک داشته باشد نه وب‌سایت، `url` آن `null` است. Overture برای هر مکان صفحه‌ی عمومی ندارد، و لینک‌های `links` برای بررسی کاربر هستند.
- نتایج با امتیاز کمتر از ۰٫۲۵ هیچ‌وقت برگردانده نمی‌شوند. جست‌وجو در یک دسته‌ی والد (مثلاً `doctor`) زیردسته‌ها (`doctor/dentist`) را هم شامل می‌شود.

### `GET /search/jobs/{job_id}` ✅ فاز ۱
وضعیت job ایندکس:
```json
{ "id": "c9f2…", "kind": "index_city", "status": "done", "attempts": 1,
  "result": { "city": "toronto", "sources": { "overture": { "seen": 193872, "stored": 292 } } },
  "error": null, "created_at": "…", "finished_at": "…" }
```

### `GET /search/jobs/{job_id}/stream` (SSE) ✅ فاز ۲
پیشرفت job ایندکس به‌صورت Server-Sent Events:

```
event: progress
data: {"status": "running", "sources": {"overture": {"seen": 113630, "stored": 58, "release": "2026-09-23.1"}, "osm": {"error": "Overpass unreachable"}}, "error": null}

event: progress
data: {"status": "running", "sources": {…, "website": {"status": "running"}}, "error": null}

event: done
data: {"status": "done", "sources": {…}, "error": null}
```

- `progress` هر بار که وضعیت job تغییر کند ارسال می‌شود. Worker بعد از هر سورس، وضعیت را در `job.result.progress` می‌نویسد.
- رویداد پایانی یکی از `done`، `failed` یا `timeout` است (بعد از ۵ دقیقه).
- هر ۱۵ ثانیه یک comment به‌عنوان keep-alive فرستاده می‌شود.
- **تغییر نسبت به طرح اولیه:** به‌جای ارسال تک‌تک نتیجه‌ها با رویداد `result`، سایت بعد از تمام شدن هر سورس صفحه‌ی نتایج را از سرور دوباره می‌گیرد (`router.refresh()`). نتیجه برای کاربر یکی است، ولی مرتب‌سازی، فیلترها و صفحه‌بندی همیشه درست می‌مانند.

## گزارش و ثبت

### `POST /businesses/{id}/reports` ✅ فاز ۱
```json
{ "reason": "not_iranian", "message": "…", "contact_email": "owner@example.com" }
```
`reason` یکی از `not_iranian`، `closed`، `wrong_info` یا `remove_request` است. بعد از ۳ گزارش `not_iranian`، کسب‌وکار پنهان می‌شود (`status = hidden`) تا ادمین بررسی کند.

### `POST /submissions` ✅ فاز ۴
پیشنهاد کسب‌وکار جدید از فرم `/fa/submit`. تا تأیید ادمین نمایش داده نمی‌شود.
```json
{ "country": "CA", "city": "toronto", "name": "Kabab Sara", "category": "restaurant",
  "links": ["https://www.instagram.com/kababsara/"], "address": null, "phone": null,
  "is_owner": true, "contact_email": null, "note": null }
```
- حداقل یک لینک عمومی `http(s)` لازم است (حداکثر ۵).
- **ضد اسپم بدون حساب و بدون CAPTCHA شخص ثالث:** فیلد مخفی `company_website` (honeypot): اگر پر شود، پاسخ موفق برمی‌گردد ولی چیزی ذخیره نمی‌شود. به‌علاوه حداکثر `FARSIYAB_SUBMISSIONS_PER_DAY` (پیش‌فرض ۵) ثبت در روز برای هر کاربر، که با hash کلیددار آدرس IP به‌علاوه‌ی تاریخ روز شناخته می‌شود (`client_hash`). خود IP ذخیره نمی‌شود. پاسخ‌ها: `201`، `422` (شهر، دسته یا لینک نامعتبر) و `429` (سقف روزانه).

### `GET /cities` ✅ فاز ۴
همه‌ی شهرها با تعداد نتایج نمایش‌داده‌شده برای هر دسته‌ی اصلی (زیردسته‌ها داخل دسته‌ی اصلی شمرده می‌شوند). صفحه‌های شهر و sitemap از این استفاده می‌کنند.

### `GET /search/markers` ✅ فاز ۴
همان فیلترهای `/search` (بدون صفحه‌بندی): همه‌ی نتایجی که مکان دارند، حداکثر ۱۰۰۰ مورد. فقط شامل نام، برچسب اطمینان و مختصات است، به‌علاوه‌ی `bbox` شهر برای وقتی که نتیجه‌ای نیست. نقشه‌ی صفحه‌ی نتایج از این استفاده می‌کند.

### `GET /businesses/{id}` ✅ فاز ۵
یک کسب‌وکار نمایش‌داده‌شده، به همان شکل کارت نتیجه (صفحه‌ی ادعای مالکیت از این استفاده می‌کند). کسب‌وکار پنهان یا زیر آستانه، `404` برمی‌گرداند.

### ادعای مالکیت ✅ فاز ۵
| مسیر | کار |
|---|---|
| `POST /businesses/{id}/claims` | `{ "method": "website" \| "telegram" \| "manual", "contact_email", "note" }` → `{ id, token, where }`. اگر کسب‌وکار لینکی از آن نوع نداشته باشد، `422`؛ حداکثر ۵ درخواست در روز برای هر کاربر (`429`) |
| `POST /claims/{id}/verify` | صفحه‌ی `where` را می‌خواند و دنبال `token` می‌گردد → `{ owner_key }` (فقط یک بار). اگر کد پیدا نشود یا روش دستی باشد، `409` |
| `GET /owner/{claim_id}` | هدر `X-Owner-Key`؛ کارت کسب‌وکار و وضعیت آن |
| `PATCH /owner/{claim_id}` | هدر `X-Owner-Key`؛ `{ name_fa, name_latin, address, phone, website, status }`. فیلدهای خالی نادیده گرفته می‌شوند. `status` یکی از `active`، `closed` یا `hidden` است. کلید اشتباه `403` می‌گیرد |

ادمین: `GET /admin/claims`، `POST /admin/claims/{id}/verify` (برای روش دستی؛ کلید را برمی‌گرداند تا ادمین آن را برای مالک بفرستد) و `POST /admin/claims/{id}/reject`.

## ادمین ✅ فاز ۴

همه‌ی مسیرها زیر `/api/v1/admin` هستند و هدر `Authorization: Bearer <FARSIYAB_ADMIN_TOKEN>` می‌خواهند. اگر توکن تنظیم نشده باشد، پاسخ `503` است (پنل خاموش است)؛ توکن اشتباه `401` می‌گیرد. پنل وب در `/fa/admin` است: توکن فقط در یک کوکی httpOnly نگه داشته می‌شود و درخواست‌ها با Server Action از سرور Next.js فرستاده می‌شوند، پس کد مرورگر توکن را نمی‌بیند.

| مسیر | کار |
|---|---|
| `GET /overview` | تعداد ثبت‌های در انتظار، گزارش‌های باز، کسب‌وکارهای پنهان و برچسب‌ها؛ وضعیت هر شهر و سورس‌های ناموفق؛ دقت Detector |
| `GET /submissions?status=pending` | صف ثبت‌ها، همراه با کسب‌وکار موجودی که احتمالاً همان است (لینک مشترک) |
| `POST /submissions/{id}/approve` و `/reject` | تأیید: ثبت به‌عنوان یک رکورد `user_submission` با نشانه‌ی `user_submission_verified` ذخیره می‌شود و مثل هر سورس دیگری با کسب‌وکارهای موجود ادغام می‌شود. اگر لینکش در فهرست «ایندکس نکن» باشد، `409` برمی‌گردد |
| `GET /reports?status=open` | گزارش‌ها، گروه‌بندی‌شده بر اساس کسب‌وکار |
| `POST /reports/{id}/resolve` | `action`: یکی از `dismiss`، `hide`، `close`، `restore` یا `remove`. تصمیم برای همه‌ی گزارش‌های باز آن کسب‌وکار اعمال می‌شود. `remove` لینک‌های کسب‌وکار را به `do_not_index` اضافه می‌کند تا هیچ سورسی آن را برنگرداند |
| `GET /businesses/{id}`، `PATCH /businesses/{id}` | دیدن یا تغییر وضعیت یک کسب‌وکار، با هر امتیاز یا وضعیتی |
| `GET /hidden` | کسب‌وکارهای پنهان‌شده |
| `GET /labels/next?city=` | یک کسب‌وکار نمایش‌داده‌شده و بدون برچسب، از سطح اطمینانی که کمترین برچسب را دارد |
| `POST /businesses/{id}/label` | `{ "is_iranian": true, "by": "…", "note": "…" }` |
| `GET /precision` | دقت برای هر سطح با امتیازهای فعلی، به‌همراه بازه‌ی اطمینان ۹۵٪ (Wilson) |
| `GET /sources`، `PATCH /sources/{id}` | روشن و خاموش کردن سورس (با `farsiyab db load` برنمی‌گردد) و آخرین اجرای هر سورس در هر شهر |
| `POST /index` | `{ "city": "toronto" }`: ایندکس دستی از طریق صف |
| `GET /jobs` | job های ۷ روز اخیر |

## محدودیت نرخ

- `/search`: ۳۰ درخواست در دقیقه برای هر IP
- ساخت job لایو: حداکثر ۵ job در ساعت برای هر IP (برای محافظت از سهمیه‌ی API ها)
