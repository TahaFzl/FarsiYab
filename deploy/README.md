# راه‌اندازی روی سرور (بدون Docker)

این راهنما برای یک VPS با **Ubuntu 24.04** است. همه‌چیز مستقیم روی سیستم‌عامل نصب می‌شود.

```
اینترنت ──HTTPS──> Caddy ──┬── /api/*  ──> FastAPI (farsiyab-api، پورت 8000)
                           └── بقیه    ──> Next.js (farsiyab-web، پورت 3000)
                 farsiyab-worker: job های ایندکس را از جدول job برمی‌دارد
                 PostgreSQL + PostGIS: داده، صف کار، سهمیه
```

## ۱. نصب پیش‌نیازها

```bash
sudo apt update
sudo apt install -y git postgresql-16 postgresql-16-postgis-3 caddy
# Node.js 22 LTS (از مخزن رسمی NodeSource یا nvm)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash - && sudo apt install -y nodejs
# uv برای پایتون
curl -LsSf https://astral.sh/uv/install.sh | sudo env UV_INSTALL_DIR=/usr/local/bin sh
```

## ۲. کاربر و کد

```bash
sudo useradd --system --create-home --home-dir /opt/farsiyab --shell /usr/sbin/nologin farsiyab
sudo -u farsiyab git clone https://github.com/TahaFzl/FarsiYab.git /opt/farsiyab
```

## ۳. دیتابیس

```bash
cd /opt/farsiyab
sudo -u postgres env DB_PASSWORD='یک-رمز-قوی' bash < scripts/setup_db.sh
```

## ۴. تنظیمات

```bash
sudo mkdir -p /etc/farsiyab
sudo cp deploy/farsiyab.env.example /etc/farsiyab/farsiyab.env
sudo nano /etc/farsiyab/farsiyab.env      # رمز دیتابیس و دامنه
sudo chown root:farsiyab /etc/farsiyab/farsiyab.env && sudo chmod 640 /etc/farsiyab/farsiyab.env
```

مقادیری که باید حتماً عوض شوند:

| متغیر | توضیح |
|---|---|
| `FARSIYAB_DATABASE_URL` | رمز دیتابیس |
| `FARSIYAB_BOT_URL` | آدرس سایت؛ در User-Agent ربات فرستاده می‌شود |
| `FARSIYAB_SITE_URL` | آدرس عمومی سایت (مثلاً `https://farsiyab.example.com`) برای لینک‌های canonical، `sitemap.xml` و `robots.txt`. **موقع `npm run build` هم باید تنظیم باشد**، چون `robots.txt` در زمان build ساخته می‌شود |
| `FARSIYAB_ADMIN_TOKEN` | توکن پنل مدیریت (`/fa/admin`). با `openssl rand -hex 32` بسازید. اگر خالی باشد، پنل خاموش است |
| `FARSIYAB_SECRET_KEY` | کلید hash برای سقف روزانه‌ی فرم ثبت کسب‌وکار؛ مثل بالا بسازید |
| `NEXT_PUBLIC_MAP_TILES` (اختیاری) | آدرس tile های نقشه. پیش‌فرض tile های خود OpenStreetMap است که فقط برای ترافیک کم مجاز است ([سیاست استفاده](https://operations.osmfoundation.org/policies/tiles/)). با ترافیک زیاد، یک سرویس tile دیگر تنظیم کنید. این مقدار هم در زمان build خوانده می‌شود |

## ۵. نصب و ساخت

```bash
cd /opt/farsiyab/services/api
sudo -u farsiyab uv sync --locked --no-dev
sudo -u farsiyab bash -c 'set -a; . /etc/farsiyab/farsiyab.env; .venv/bin/farsiyab db init'

cd /opt/farsiyab/apps/web
sudo -u farsiyab npm ci
sudo -u farsiyab bash -c 'set -a; . /etc/farsiyab/farsiyab.env; npm run build'
```

## ۶. سرویس‌ها و Caddy

```bash
sudo cp /opt/farsiyab/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now farsiyab-api farsiyab-worker farsiyab-web
sudo systemctl enable --now farsiyab-schedule.timer   # هر شب شهرهای قدیمی را در صف می‌گذارد

sudo cp /opt/farsiyab/deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile            # farsiyab.example.com را با دامنه‌ی خودتان عوض کنید
sudo mkdir -p /var/log/caddy && sudo chown caddy:caddy /var/log/caddy
sudo systemctl reload caddy
```

دامنه باید با رکورد DNS به IP سرور اشاره کند. Caddy گواهی HTTPS را خودش می‌گیرد.

## ۷. اولین ایندکس

```bash
cd /opt/farsiyab/services/api
for city in toronto vancouver montreal los-angeles bay-area houston washington-dc hamburg berlin frankfurt; do
  sudo -u farsiyab bash -c "set -a; . /etc/farsiyab/farsiyab.env; .venv/bin/farsiyab index $city"
done
```

این اجرا با OSM و بررسی وب‌سایت‌ها کامل است. نتیجه‌اش را با [گزارش فاز ۱](../docs/reports/phase1-first-index.md) مقایسه کنید؛ آن گزارش بدون این دو گرفته شده بود.

بعد از این، هر جست‌وجو در شهری که ایندکسش قدیمی‌تر از ۷ روز باشد، خودکار یک job می‌سازد و `farsiyab-worker` اجرایش می‌کند.

## به‌روزرسانی

```bash
cd /opt/farsiyab && sudo -u farsiyab git pull
cd services/api && sudo -u farsiyab uv sync --locked --no-dev \
  && sudo -u farsiyab bash -c 'set -a; . /etc/farsiyab/farsiyab.env; .venv/bin/farsiyab db init'
cd ../../apps/web && sudo -u farsiyab npm ci \
  && sudo -u farsiyab bash -c 'set -a; . /etc/farsiyab/farsiyab.env; npm run build'
sudo systemctl restart farsiyab-api farsiyab-worker farsiyab-web
```

## حریم خصوصی در تنظیمات سرور
- API به‌صورت پیش‌فرض لاگ درخواست‌ها (که IP دارند) را نمی‌نویسد (`farsiyab serve --no-access-log`).
- Caddy لاگ‌ها را حداکثر ۷ روز نگه می‌دارد (`roll_keep_for 168h`). صفحه‌ی حریم خصوصی سایت همین را اعلام می‌کند؛ اگر تنظیم را تغییر دادید، آن متن را هم به‌روز کنید.

## بررسی سلامت
```bash
curl -s https://<دامنه>/api/v1/health          # {"status":"ok"}
systemctl status farsiyab-api farsiyab-worker farsiyab-web
journalctl -u farsiyab-worker -f               # پیشرفت ایندکس
```
