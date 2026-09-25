"""Indexer, entity resolution, job queue and quota against a real PostGIS database."""

import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from farsiyab import jobs
from farsiyab.adapters.base import RawListing, SourceUnavailable
from farsiyab.adapters.website import WebsiteResult
from farsiyab.config import Settings
from farsiyab.detection.detector import TextField
from farsiyab.detection.signals import make
from farsiyab.indexer import index_city, store_listing
from farsiyab.links import Link
from farsiyab.models import (
    Business,
    BusinessCategory,
    BusinessLink,
    City,
    DoNotIndex,
    Evidence,
    IndexStatus,
    Job,
    Source,
    SourceRecord,
)
from farsiyab.quota import QuotaExhausted, consume
from farsiyab.resolution import name_similarity, normalize_name

SETTINGS = Settings(website_min_interval_seconds=0)


def listing(source="overture", external_id="o1", name="Shiraz Kitchen", lat=43.70, lng=-79.40,
            category="restaurant", urls=(), phones=(), signals=(), texts=None):
    return RawListing(
        source_id=source, external_id=external_id, name=name,
        url=f"https://example.org/{source}/{external_id}", lat=lat, lng=lng,
        category=category, urls=list(urls), phones=list(phones),
        texts=texts if texts is not None else [TextField("name", name)],
        signals=list(signals),
    )


class FakeAdapter:
    def __init__(self, source_id, listings, error=None):
        self.id = source_id
        self.listings = listings
        self.error = error

    def fetch(self, city):
        if self.error:
            raise SourceUnavailable(self.error)
        yield from self.listings


class FakeChecker:
    def __init__(self, results):
        self.results = results

    async def check_many(self, urls):
        return [self.results[u] for u in urls]

    async def aclose(self):
        pass


def toronto(db):
    return db.scalar(select(City).where(City.slug == "toronto"))


def test_name_normalization():
    assert normalize_name("The Shiraz Kitchen Inc.") == "shiraz"
    assert name_similarity("Shiraz Restaurant", "SHIRAZ") == 100
    assert name_similarity("Shiraz Grill", "Tehran Grill") < 80


class TestStoreListing:
    def test_non_iranian_places_are_not_stored(self, db):
        assert not store_listing(db, toronto(db), listing(name="Joe's Pizza"))
        assert db.scalar(select(func.count(Business.id))) == 0

    def test_same_place_from_two_sources_is_merged_by_shared_link(self, db):
        city = toronto(db)
        insta = "https://instagram.com/shirazkitchen"
        store_listing(db, city, listing(urls=[insta]))
        store_listing(db, city, listing(
            # ~250 m away and a Persian-only name: only the shared link can match them.
            source="osm", external_id="node/1", name="آشپزخانه شیراز", lat=43.7022, lng=-79.4005,
            urls=[insta], signals=[make("osm_cuisine_tag", "cuisine=persian")],
        ))
        db.commit()
        business = db.scalar(select(Business))
        assert db.scalar(select(func.count(Business.id))) == 1
        assert {r.source_id for r in business.records} == {"overture", "osm"}
        assert (business.name_latin, business.name_fa) == ("Shiraz Kitchen", "آشپزخانه شیراز")

    def test_chain_branches_sharing_a_website_stay_separate(self, db):
        city = toronto(db)
        site = ["https://mrzagros.example/"]
        store_listing(db, city, listing(external_id="z1", name="Mr Zagros", urls=site))
        store_listing(db, city, listing(external_id="z2", name="Mr Zagros", urls=site, lat=43.80))
        store_listing(db, city, listing(external_id="z3", name="Zagros Kebab", urls=site,
                                        lat=43.7003))  # same corner, different name
        db.commit()
        assert db.scalar(select(func.count(Business.id))) == 2

    def test_nearby_place_with_similar_name_is_merged(self, db):
        city = toronto(db)
        store_listing(db, city, listing(name="Shiraz Kitchen"))
        store_listing(db, city, listing(source="osm", external_id="n2",
                                        name="Shiraz Kitchen Restaurant", lat=43.7005))
        store_listing(db, city, listing(source="osm", external_id="n3",
                                        name="Shiraz Kitchen", lat=43.80))  # 11 km away
        db.commit()
        assert db.scalar(select(func.count(Business.id))) == 2

    def test_reindex_is_idempotent_and_drops_stale_evidence(self, db):
        city = toronto(db)
        store_listing(db, city, listing(name="Tehran Market"))
        store_listing(db, city, listing(name="Tehran Market"))
        db.commit()
        assert db.scalar(select(func.count(SourceRecord.id))) == 1
        assert db.scalar(select(func.count(Evidence.id))) == 1

        # The source renamed the place and it no longer looks Iranian.
        assert not store_listing(db, city, listing(name="Market 24"), known={"o1"})
        db.commit()
        assert db.scalar(select(func.count(Evidence.id))) == 0

    def test_do_not_index_blocks_the_business(self, db):
        db.add(DoNotIndex(kind="instagram", value="shirazkitchen", note="owner asked"))
        db.commit()
        kept = store_listing(db, toronto(db), listing(urls=["https://instagram.com/shirazkitchen"]))
        assert not kept

    def test_real_category_replaces_other(self, db):
        city = toronto(db)
        store_listing(db, city, listing(category="other"))
        store_listing(db, city, listing(source="osm", external_id="n1", category="restaurant"))
        db.commit()
        assert list(db.scalars(select(BusinessCategory.category_slug))) == ["restaurant"]


class TestIndexCity:
    def test_full_run_with_failing_source_and_websites(self, db):
        adapters = [
            FakeAdapter("overture", [
                listing(urls=["https://shirazkitchen.example/"]),
                listing(external_id="o2", name="Joe's Pizza", lat=43.8),
            ]),
            FakeAdapter("osm", [], error="Overpass unreachable"),
        ]
        page_signals = [make("website_persian_content", "رستوران شیراز", "https://shirazkitchen.example/")]
        checker = FakeChecker({
            "https://shirazkitchen.example/": WebsiteResult(
                "https://shirazkitchen.example/", ok=True,
                final_url="https://shirazkitchen.example/", lang="fa", signals=page_signals,
                links=[Link("telegram", "shiraz_kitchen", "https://t.me/shiraz_kitchen")],
            ),
        })
        report = index_city(db, "toronto", adapters, settings=SETTINGS,
                            checker_factory=lambda: checker)

        assert report["sources"]["overture"] == {**report["sources"]["overture"],
                                                 "seen": 2, "stored": 1}
        assert report["sources"]["osm"]["error"] == "Overpass unreachable"
        assert report["sources"]["website"]["with_evidence"] == 1

        business = db.scalar(select(Business))
        assert business.website_checked_at is not None
        assert business.confidence_label == "medium"  # 1 - (1-0.3)(1-0.5) = 0.65
        assert {link.kind for link in business.links} >= {"website", "telegram"}

        status = db.get(IndexStatus, business.city_id)
        assert status.category_counts == {"restaurant": 1}

    def test_records_the_source_dropped_are_removed(self, db):
        first = [listing(external_id="a", name="Tehran Market"),
                 listing(external_id="b", name="Shiraz Grill", lat=43.8)]
        index_city(db, "toronto", [FakeAdapter("overture", first)], check_sites=False,
                   settings=SETTINGS)
        assert db.scalar(select(func.count(Business.id))) == 2

        report = index_city(db, "toronto", [FakeAdapter("overture", first[:1])],
                            check_sites=False, settings=SETTINGS)
        assert report["sources"]["overture"]["removed"] == 1
        assert [b.name_latin for b in db.scalars(select(Business))] == ["Tehran Market"]

        # A source that suddenly returns nothing is not trusted.
        report = index_city(db, "toronto", [FakeAdapter("overture", [])], check_sites=False,
                            settings=SETTINGS)
        assert report["sources"]["overture"]["removed"] == 0
        assert db.scalar(select(func.count(Business.id))) == 1

    def test_network_errors_leave_website_unchecked(self, db):
        adapters = [FakeAdapter("overture", [listing(urls=["https://shiraz.example/"])])]
        checker = FakeChecker({"https://shiraz.example/": WebsiteResult(
            "https://shiraz.example/", ok=False, reason="error: ConnectTimeout")})
        index_city(db, "toronto", adapters, settings=SETTINGS, checker_factory=lambda: checker)
        assert db.scalar(select(Business.website_checked_at)) is None

    def test_quota_cap_stops_the_source(self, db):
        source = db.get(Source, "osm")
        source.monthly_cap = 0
        db.commit()
        try:
            report = index_city(db, "toronto", [FakeAdapter("osm", [listing()])],
                                check_sites=False, settings=SETTINGS)
            assert "cap" in report["sources"]["osm"]["error"]
            assert db.scalar(select(func.count(Business.id))) == 0
        finally:
            source.monthly_cap = 3000
            db.commit()


class TestJobs:
    def test_dedupe_key_returns_the_active_job(self, db):
        a = jobs.enqueue(db, "index_city", {"city": "toronto"}, "index_city:toronto")
        b = jobs.enqueue(db, "index_city", {"city": "toronto"}, "index_city:toronto")
        assert a.id == b.id
        a.status = "done"
        db.commit()
        c = jobs.enqueue(db, "index_city", {"city": "toronto"}, "index_city:toronto")
        assert c.id != a.id

    def test_concurrent_workers_never_share_a_job(self, db, session_maker):
        for i in range(5):
            jobs.enqueue(db, "noop", {"i": i})
        claimed, lock = [], threading.Lock()

        def worker():
            with session_maker() as session:
                while job := jobs.claim(session):
                    with lock:
                        claimed.append(job.id)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(claimed) == len(set(claimed)) == 5

    def test_failures_are_retried_then_marked_failed(self, db):
        jobs.enqueue(db, "boom", {})

        def boom(session, job):
            raise RuntimeError("kaput")

        for attempt in range(1, jobs.MAX_ATTEMPTS + 1):
            job = jobs.run_one(db, {"boom": boom})
            assert job.attempts == attempt and "kaput" in job.error
            if job.status == "queued":
                assert job.run_after > datetime.now(UTC)
                job.run_after = datetime.now(UTC) - timedelta(seconds=1)
                db.commit()
        assert job.status == "failed"

    def test_success_stores_the_result(self, db):
        jobs.enqueue(db, "ok", {"x": 1})
        job = jobs.run_one(db, {"ok": lambda s, j: {"got": j.payload["x"]}})
        assert (job.status, job.result) == ("done", {"got": 1})
        assert jobs.run_one(db, {}) is None
        assert db.scalar(select(func.count(Job.id))) == 1


def test_quota(db):
    assert consume(db, "osm", None) == 0
    assert consume(db, "osm", 2) == 1
    assert consume(db, "osm", 2) == 2
    with pytest.raises(QuotaExhausted):
        consume(db, "osm", 2)


def test_links_are_unique_per_business(db):
    city = toronto(db)
    for _ in range(2):
        store_listing(db, city, listing(urls=["https://instagram.com/a_b", "instagram.com/A_B/"]))
    db.commit()
    assert db.scalar(select(func.count(BusinessLink.id))) == 1
