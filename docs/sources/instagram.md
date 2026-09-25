# Instagram

- **شناسه در کد:** `instagram`
- **وضعیت:** ✅ MVP (فقط لینک، بدون حساب) · ⏸ Business Discovery اختیاری
- **نوع دسترسی:**
  1. **بدون حساب (MVP):** لینک‌های اینستاگرام که در سورس‌های باز ثبت شده‌اند
  2. **اختیاری:** Instagram Graph API، endpoint به نام **Business Discovery**
- **مستندات:** https://developers.facebook.com/docs/instagram-platform/overview/
- **قوانین:** https://help.instagram.com/581066165581870 (Terms of Use)، https://developers.facebook.com/terms (Platform Terms)
- **هزینه:** رایگان

## چرا اسکرپ نمی‌کنیم
قوانین اینستاگرام جمع‌آوری خودکار داده بدون اجازه را ممنوع می‌کند، Meta علیه اسکرپرها شکایت حقوقی کرده است و از نظر فنی هم IP ها سریع بلاک می‌شوند. ([ADR-002](../decisions/002-official-apis-only.md))

## MVP: پیدا کردن لینک اینستاگرام بدون حساب
هیچ درخواستی به instagram.com ارسال نمی‌شود. لینک پروفایل از این سورس‌ها جمع می‌شود:

| منبع | فیلد | تعداد در تست تورنتو |
|---|---|---|
| [Overture Maps](overture-maps.md) | `socials` و `websites` | حدود ۲٬۱۰۰ مکان |
| [OpenStreetMap](openstreetmap.md) | `contact:instagram` | — |
| [وب‌سایت کسب‌وکار](business-websites.md) | لینک‌های `instagram.com/...` در HTML | — |

این لینک به‌عنوان سورس «Instagram» و لینک مدرک نشان داده می‌شود. خود نام‌کاربری هم گاهی نشانه است (مثلاً `lmlawcpa.persian`).

**محدودیت:** بیوی پروفایل خوانده نمی‌شود و کسب‌وکارهایی که **فقط** اینستاگرام دارند پیدا نمی‌شوند.

## اختیاری: Business Discovery API

### Business Discovery چیست
با این endpoint، یک حساب Business یا Creator (که مال خودمان است) می‌تواند اطلاعات عمومی **یک حساب حرفه‌ای دیگر** را با داشتن نام‌کاربری‌اش بخواند. این endpoint قابلیت جست‌وجو ندارد؛ نام‌کاربری‌ها از همان لینک‌های بخش MVP می‌آیند. نتیجه این است که بیوی پروفایل هم به‌عنوان مدرک خوانده می‌شود.

```http
GET https://graph.facebook.com/v{N}/{our-ig-user-id}
  ?fields=business_discovery.username(shirazkitchen){username,name,biography,website,followers_count,media_count}
  &access_token=…
```

### پیش‌نیازها
- یک حساب Instagram Business یا Creator برای فارسی‌یاب
- یک Facebook Page متصل به آن حساب
- یک Meta App با دسترسی‌های `instagram_basic` و `pages_show_list` (و احتمالاً گذراندن App Review برای حالت Live)
- **این مراحل زمان‌بر هستند؛ بهتر است از همین الان شروع شوند** (در بخش سؤال‌های باز هم آمده است)

### سهمیه
Business Discovery جزو «Platform Rate Limits» است: **۲۰۰ درخواست در ساعت × تعداد کاربران فعال روزانه‌ی اپ**. برای اپ ما که یک کاربر فنی دارد، یعنی حدود ۲۰۰ درخواست در ساعت، که برای نیاز ما کافی است.

### محدودیت‌ها
- فقط حساب‌های **حرفه‌ای** (Business یا Creator) قابل خواندن هستند. حساب‌های شخصی قابل خواندن نیستند و ما هم نمی‌خواهیم بخوانیم ([07](../07-legal-and-privacy.md)).
- Meta ممکن است این endpoint را محدودتر کند. در این صورت سیستم به حالت «فقط لینک از جست‌وجوی وب» برمی‌گردد.

## نشانه‌های ایرانی بودن
- `persian_script_text` و `explicit_keyword` در `biography` (مثلاً «غذای اصیل ایرانی»)
- `persian_script_name` در `name`
- `website` برای ادغام با OSM و Google (کلید ادغام قوی)

## لینک نمایش‌داده‌شده به کاربر
`https://www.instagram.com/{username}/`

## ذخیره‌سازی
نام‌کاربری، نام، بیو و وب‌سایت ذخیره و ماهانه تازه می‌شوند. طبق Platform Terms، اگر حساب حذف یا خصوصی شد، داده‌اش را پاک می‌کنیم. **پست‌ها و عکس‌ها ذخیره نمی‌شوند.**
