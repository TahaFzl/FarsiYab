from sqlalchemy import select

from farsiyab.adapters.telegram import TelegramResult, analyse_preview
from farsiyab.config import get_settings
from farsiyab.detection.signals import make
from farsiyab.indexer import check_telegram, recompute_scores, store_listing
from farsiyab.models import Business, City, SourceRecord
from tests.test_pipeline import listing

# Trimmed from live t.me pages (2026-09-26).
CHANNEL = """<html><head><meta property="og:title" content="Nan-e Barbari Toronto"></head><body>
<div class="tgme_page_title"><span dir="auto">Nan-e Barbari Toronto</span></div>
<div class="tgme_page_extra">1 234 subscribers</div>
<div class="tgme_page_description">نان بربری و سنگک تازه هر روز در ریچموند هیل</div>
</body></html>"""
MISSING = """<html><head><meta property="og:title" content="Telegram: Contact @nobody"></head>
<body><div class="tgme_page_extra">If you have Telegram, you can contact @nobody right away.</div>
</body></html>"""


def test_preview_in_persian_is_evidence():
    exists, title, description, signals = analyse_preview(CHANNEL, "https://t.me/barbari")
    assert exists and title == "Nan-e Barbari Toronto"
    assert description.startswith("نان بربری")
    assert "telegram_persian_content" in [s.signal for s in signals]


def test_unknown_channel_is_not_evidence():
    assert analyse_preview(MISSING, "https://t.me/nobody") == (False, None, None, [])


class FakeChecker:
    def __init__(self, results):
        self.results = results
        self.asked = []

    def check(self, name):
        self.asked.append(name)
        return self.results[name]


def test_check_telegram_adds_a_source_and_waits_a_month(db):
    city = db.scalar(select(City).where(City.slug == "toronto"))
    store_listing(db, city, listing(
        external_id="b1", name="Barbari Bakery", category="bakery",
        urls=["https://t.me/barbari"],
        signals=[make("persian_personal_name", "weak", None)],  # 0.2: a candidate
    ))
    store_listing(db, city, listing(external_id="b2", name="Gone Bakery", lat=43.6,
                                    urls=["https://t.me/gone"],
                                    signals=[make("persian_personal_name", "weak", None)]))
    recompute_scores(db, city.id)
    db.commit()
    signals = analyse_preview(CHANNEL, "https://t.me/barbari")[3]
    checker = FakeChecker({
        "barbari": TelegramResult("barbari", "https://t.me/barbari", ok=True, exists=True,
                                  title="Nan-e Barbari Toronto", signals=signals),
        "gone": TelegramResult("gone", "https://t.me/gone", ok=True, exists=False),
    })
    report = check_telegram(db, city, get_settings(), lambda: checker)
    assert report == {"checked": 2, "with_evidence": 1, "not_found": 1}
    record = db.scalar(select(SourceRecord).where(SourceRecord.source_id == "telegram"))
    assert record.external_id == "barbari" and record.url == "https://t.me/barbari"
    recompute_scores(db, city.id)
    barbari = db.get(Business, record.business_id)
    assert barbari.confidence_score >= 0.45

    # Both were checked; nothing is asked again within the month.
    assert check_telegram(db, city, get_settings(), lambda: checker) == {"checked": 0}
    assert sorted(checker.asked) == ["barbari", "gone"]
