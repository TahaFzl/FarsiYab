# ADR-004: Next.js + Python (FastAPI) + PostgreSQL، دوزبانه

- **وضعیت:** پذیرفته (۲۰۲۶-۰۹-۲۵)

## تصمیم
| لایه | انتخاب | دلیل |
|---|---|---|
| فرانت‌اند | Next.js (App Router، TypeScript)، `next-intl`، Tailwind با پشتیبانی RTL | رندر سمت سرور برای SEO، پشتیبانی خوب از i18n |
| فونت | Vazirmatn | فونت فارسی متن‌باز و رایگان |
| بک‌اند | Python 3.11+، FastAPI، SQLAlchemy 2، Alembic | اکوسیستم قوی برای کراول، پردازش متن و تشخیص زبان |
| صف کار | جدول `job` در خود PostgreSQL (`FOR UPDATE SKIP LOCKED`)؛ **بدون Redis** | یک سرویس کمتر برای نصب؛ برای حجم این پروژه کافی است |
| دیتابیس | PostgreSQL 16 + PostGIS + `pg_trgm` | جست‌وجوی مکانی و شباهت نام در یک دیتابیس |
| HTTP | `httpx` (async) | درخواست موازی به سورس‌ها |
| تست | pytest + داده‌های ضبط‌شده (VCR / fixtures) | تست آداپترها بدون مصرف سهمیه |
| استقرار | نصب مستقیم روی یک VPS (Ubuntu) با systemd و Caddy؛ **بدون Docker** | ساده، بدون لایه‌ی اضافه؛ جزئیات در [02](../02-architecture.md#استقرار-بدون-docker) |

## زبان‌ها
رابط کاربری فارسی (پیش‌فرض، RTL) و انگلیسی. مسیرها: `/fa/...` و `/en/...`.
