# Wikidata، Wikipedia و Wikivoyage

- **شناسه در کد:** `wikidata`، `wikipedia`، `wikivoyage`
- **وضعیت:** ✅ فاز ۳ (پوشش کم، ولی کیفیت بالا)
- **حساب کاربری:** ❌ لازم نیست
- **هزینه:** رایگان
- **لایسنس:** Wikidata: CC0 · Wikipedia و Wikivoyage: CC BY-SA 4.0
- **سیاست استفاده:** User-Agent با اطلاعات تماس الزامی است: https://meta.wikimedia.org/wiki/User-Agent_policy
- **تست‌شده؟** ⚠️ خیر. `query.wikidata.org` در شبکه‌ی محیط توسعه مسدود است.

## Wikidata (SPARQL)
Endpoint: `https://query.wikidata.org/sparql`

کاربرد: **سازمان‌ها، انجمن‌ها، مراکز فرهنگی، مدارس فارسی و رسانه‌های** ایرانیان خارج از کشور، که در OSM و Overture کمتر ثبت شده‌اند. همچنین رستوران‌ها و کسب‌وکارهای معروف.

```sparql
# ساختار کوئری؛ شناسه‌های <...> قبل از پیاده‌سازی از خود Wikidata استخراج شوند
SELECT ?item ?itemLabel ?website ?instagram WHERE {
  ?item wdt:P131* <CITY_QID> .                          # located in the administrative territorial entity
  { ?item <CUISINE_PROPERTY> <IRANIAN_CUISINE_QID> }    # رستوران با غذای ایرانی
  UNION { ?item rdfs:label ?l FILTER(LANG(?l) = "fa") } # برچسب فارسی دارد
  OPTIONAL { ?item wdt:P856 ?website }                  # official website
  OPTIONAL { ?item wdt:P2003 ?instagram }               # Instagram username
  SERVICE wikibase:label { bd:serviceParam wikibase:language "fa,en". }
}
```
(P131، P856 و P2003 شناسه‌های استاندارد هستند. بقیه‌ی شناسه‌ها در زمان پیاده‌سازی بررسی می‌شوند.)

نشانه‌ها: `wikidata_iran_related` (وزن ۰٫۵)، و `persian_script_name` برای برچسب فارسی.

لینک به کاربر: `https://www.wikidata.org/wiki/Q…` یا مقاله‌ی Wikipedia

## Wikipedia
کاربرد: مقاله‌هایی مثل «Iranian Canadians»، «Tehrangeles» و «Iranians in Germany» بخش‌هایی درباره‌ی محله‌ها، سازمان‌ها و کسب‌وکارهای شاخص دارند. این مقاله‌ها برای **ساخت لیست اولیه‌ی شهرها و محله‌های پرجمعیت** مفیدند (مثلاً Westwood در لس‌آنجلس و North York در تورنتو)، نه برای ایندکس انبوه.

## Wikivoyage
Endpoint: `https://en.wikivoyage.org/w/api.php`

صفحه‌ی شهرها بخش «Eat» دارد که در آن رستوران‌ها با قالب `{{eat | name= | address= | url= | content=…Persian…}}` ثبت شده‌اند. این قالب **ساختاریافته** است و راحت parse می‌شود.

نشانه: `explicit_keyword` در فیلد `content`. لینک به کاربر: صفحه‌ی Wikivoyage شهر.

## محدودیت‌ها
- پوشش کم است: فقط موارد شناخته‌شده ثبت می‌شوند
- Wikidata کند است؛ کوئری‌ها باید ساده و کش‌شده باشند (هر شهر ماهی یک بار)
