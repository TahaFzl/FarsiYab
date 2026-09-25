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

### `POST /submissions` (فاز ۲)
پیشنهاد کسب‌وکار جدید. تا تأیید ادمین نمایش داده نمی‌شود.

## ادمین (با احراز هویت)

- `GET /admin/quota`: مصرف ماه جاری هر سورس
- `POST /admin/index`: `{ "city": "toronto", "categories": ["restaurant"] }` برای اجرای دستی ایندکس
- `PATCH /admin/sources/{id}`: فعال یا غیرفعال کردن سورس
- `GET /admin/review-queue`: نتایج با اطمینان پایین و گزارش‌ها

## محدودیت نرخ

- `/search`: ۳۰ درخواست در دقیقه برای هر IP
- ساخت job لایو: حداکثر ۵ job در ساعت برای هر IP (برای محافظت از سهمیه‌ی API ها)
