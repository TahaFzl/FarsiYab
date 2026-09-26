from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from farsiyab.indexer import recompute_scores, store_listing
from farsiyab.models import City, IndexStatus, Job
from farsiyab.scheduling import Due, coverage, coverage_markdown, due_cities, schedule
from tests.test_pipeline import listing


def city_id(db, slug):
    return db.scalar(select(City.id).where(City.slug == slug))


def indexed(db, slug, days_ago, release="2026-09-23.1"):
    db.add(IndexStatus(
        city_id=city_id(db, slug),
        last_indexed_at=datetime.now(UTC) - timedelta(days=days_ago),
        per_source={"overture": {"release": release}},
    ))


def test_due_cities(db):
    indexed(db, "toronto", days_ago=1)
    indexed(db, "hamburg", days_ago=30)
    indexed(db, "berlin", days_ago=1, release="2026-08-19.0")
    db.commit()
    due = {d.city: d.reason for d in due_cities(db, latest_overture_release="2026-09-23.1")}
    assert "toronto" not in due
    assert due["hamburg"] == "stale"
    assert due["berlin"] == "new_overture_release"
    assert due["los-angeles"] == "never_indexed"
    # Without knowing the latest release, only age matters.
    assert Due("berlin", "new_overture_release") not in due_cities(db, None)


def test_schedule_queues_one_job_per_city(db):
    every_city = db.scalars(select(City.slug)).all()
    for slug in every_city:
        if slug != "frankfurt":
            indexed(db, slug, days_ago=1)
    db.commit()
    first = schedule(db)
    again = schedule(db)
    assert [q["city"] for q in first] == ["frankfurt"]
    assert again[0]["job_id"] == first[0]["job_id"]
    assert len(db.scalars(select(Job)).all()) == 1


def test_coverage_counts_sources_per_city(db):
    city = db.scalar(select(City).where(City.slug == "toronto"))
    insta = ["https://instagram.com/shirazkitchen"]
    store_listing(db, city, listing(name="Shiraz Kitchen Persian", urls=insta))
    store_listing(db, city, listing(source="osm", external_id="n1", name="Shiraz Kitchen Persian",
                                    urls=insta))
    store_listing(db, city, listing(external_id="o2", name="Tehran Market", lat=43.8))
    store_listing(db, city, listing(external_id="o3", name="Mr Mohammadzadeh", lat=43.6))  # hidden
    recompute_scores(db, city.id)
    db.commit()

    toronto = next(r for r in coverage(db) if r["city"] == "toronto")
    assert toronto == {
        "city": "toronto",
        "shown": 2,
        "sources": {"instagram": 1, "osm": 1, "overture": 2},
        "source_count": 2,  # overture + osm; the Instagram link is not independent
        "multi_source": 1,
    }
    table = coverage_markdown([toronto])
    header = "| city | shown | instagram | osm | overture | independent sources | 2+ sources |"
    assert table.splitlines()[0] == header
    assert table.splitlines()[2] == "| toronto | 2 | 1 | 1 | 2 | 2 | 1 |"
