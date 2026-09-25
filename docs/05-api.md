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
        { "id": "osm", "name": "OpenStreetMap", "url": "https://www.openstreetmap.org/node/123" },
        { "id": "instagram", "name": "Instagram", "url": "https://www.instagram.com/shirazkitchen" }
      ],
      "evidence": [
        {
          "signal": "osm_cuisine_tag",
          "label": "برچسب غذای ایرانی در OpenStreetMap",
          "snippet": "cuisine=persian",
          "url": "https://www.openstreetmap.org/node/123",
          "source": "osm"
        }
      ],
      "last_verified_at": "2026-09-20T03:12:00Z"
    }
  ],
  "total": 37,
  "live_search": { "job_id": "c9f2…", "status": "running" }
}
```

اگر جست‌وجوی لایو لازم نباشد، `live_search` برابر `null` است.

### `GET /search/jobs/{job_id}/stream` (SSE)

```
event: source_started
data: {"source": "google_places"}

event: result
data: { …مثل آیتم‌های results… }

event: source_finished
data: {"source": "google_places", "count": 12}

event: source_failed
data: {"source": "brave_search", "reason": "quota_exhausted"}

event: done
data: {"total_new": 9}
```

## گزارش و ثبت

### `POST /businesses/{id}/reports`
```json
{ "reason": "not_iranian", "message": "…" }
```

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
