from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from farsiyab import jobs
from farsiyab.api import app, get_session_factory
from farsiyab.detection.signals import make
from farsiyab.indexer import recompute_scores, store_listing
from farsiyab.models import Business, City, IndexStatus
from tests.test_pipeline import listing


@pytest.fixture
def client(db, session_maker):
    app.dependency_overrides[get_session_factory] = lambda: session_maker
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def toronto_data(db):
    city = db.scalar(select(City).where(City.slug == "toronto"))
    store_listing(db, city, listing(
        external_id="a", name="Shiraz Kitchen | آشپزخانه شیراز",
        urls=["https://www.facebook.com/470792293411166", "https://shiraz.example/"],
        phones=["(416) 555-0100"],
        signals=[make("overture_persian_category", "taxonomy: persian_restaurant")],
    ))
    store_listing(db, city, listing(external_id="b", name="Tehran Market", lat=43.60,
                                    category="grocery"))
    store_listing(db, city, listing(source="osm", external_id="c", name="Dr. Karimzadeh Dental",
                                    lat=43.9, category="doctor/dentist"))  # weak signal only
    recompute_scores(db, city.id)
    db.add(IndexStatus(city_id=city.id, last_indexed_at=datetime.now(UTC)))
    db.commit()
    return city


def search(client, **params):
    params = {"country": "CA", "city": "toronto", **params}
    response = client.get("/api/v1/search", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_reference_endpoints(client):
    countries = client.get("/api/v1/countries").json()
    assert {c["code"]: c["city_count"] for c in countries} == {"CA": 3, "DE": 3, "US": 4}
    cities = client.get("/api/v1/countries/ca/cities", params={"q": "tor", "lang": "en"}).json()
    assert cities == [{"slug": "toronto", "name": "Toronto", "name_en": "Toronto"}]
    doctor = next(c for c in client.get("/api/v1/categories").json() if c["slug"] == "doctor")
    assert doctor["name"] == "پزشک" and doctor["children"][0]["slug"] == "doctor/dentist"


def test_search_result_shape(client, toronto_data):
    body = search(client, categories="restaurant,grocery")
    assert body["total"] == 2 and body["live_search"] is None
    top = body["results"][0]
    assert top["name"] == {"fa": "آشپزخانه شیراز", "latin": "Shiraz Kitchen"}
    assert top["confidence"]["label"] == "high"
    assert top["contact"]["phone"] == "+14165550100"
    assert {s["id"] for s in top["sources"]} == {"overture", "facebook"}
    facebook = next(s for s in top["sources"] if s["id"] == "facebook")
    assert facebook["url"] == "https://www.facebook.com/470792293411166"
    assert top["evidence"][0]["signal"] == "overture_persian_category"
    assert top["evidence"][0]["label"] == "دسته‌ی رستوران ایرانی در Overture Maps"
    assert top["links"]["google_maps"].startswith("https://www.google.com/maps/search/?api=1")
    assert top["location"] == {"lat": 43.7, "lng": -79.4}


def test_weak_results_are_hidden_and_parent_category_includes_children(client, toronto_data, db):
    # Only a surname signal (0.2) — below the 0.25 display threshold.
    assert search(client, categories="doctor")["total"] == 0

    store_listing(db, toronto_data, listing(source="osm", external_id="d", lat=43.5,
                                            name="Farsi Speaking Dentist Toronto",
                                            category="doctor/dentist"))
    recompute_scores(db, toronto_data.id)
    db.commit()
    assert search(client, categories="doctor")["total"] == 1
    assert search(client, categories="doctor/dentist")["total"] == 1


def test_filters_and_sorting(client, toronto_data):
    assert search(client, categories="restaurant,grocery", min_confidence="high")["total"] == 1
    assert search(client, categories="restaurant,grocery", sources="facebook")["total"] == 1
    names = [r["name"]["latin"]
             for r in search(client, categories="restaurant,grocery", sort="name")["results"]]
    assert names == ["Shiraz Kitchen", "Tehran Market"]
    nearest = search(client, categories="restaurant,grocery", sort="distance", lat=43.6, lng=-79.4)
    assert nearest["results"][0]["name"]["latin"] == "Tehran Market"
    english = search(client, categories="restaurant", lang="en")["results"][0]
    assert english["evidence"][0]["label"] == "Persian restaurant category in Overture Maps"


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"country": "CA", "city": "atlantis", "categories": "restaurant"}, 404),
        ({"country": "US", "city": "toronto", "categories": "restaurant"}, 404),
        ({"country": "CA", "city": "toronto", "categories": "spaceships"}, 422),
        ({"country": "CA", "city": "toronto", "categories": "restaurant", "sort": "distance"}, 422),
    ],
)
def test_search_errors(client, toronto_data, params, status):
    assert client.get("/api/v1/search", params=params).status_code == status


def test_unindexed_city_queues_one_job(client):
    first = client.get("/api/v1/search",
                       params={"country": "DE", "city": "hamburg", "categories": "restaurant"})
    second = client.get("/api/v1/search",
                        params={"country": "DE", "city": "hamburg", "categories": "grocery"})
    job = first.json()["live_search"]
    assert job["status"] == "queued"
    assert second.json()["live_search"]["job_id"] == job["job_id"]
    status = client.get(f"/api/v1/search/jobs/{job['job_id']}").json()
    assert (status["kind"], status["status"]) == ("index_city", "queued")
    assert client.get("/api/v1/search/jobs/00000000-0000-0000-0000-000000000000").status_code == 404


def test_registry_links_follow_city_and_category(client, toronto_data):
    doctors = search(client, categories="doctor")["registry_links"]
    assert [r["id"] for r in doctors] == ["cpso", "rcdso"]  # dentists are doctors' children
    assert doctors[0]["hint"].startswith("در «Languages spoken»")
    assert search(client, categories="restaurant")["registry_links"] == []
    hamburg = client.get("/api/v1/search", params={
        "country": "DE", "city": "hamburg", "categories": "translator", "lang": "en"}).json()
    assert [r["id"] for r in hamburg["registry_links"]] == ["bdue", "justiz_dolmetscher"]


def test_search_includes_city_and_index_time(client, toronto_data):
    body = search(client, categories="doctor", lang="en")
    assert body["city"]["name"] == "Toronto" and body["city"]["last_indexed_at"]
    assert body["categories"] == ["doctor", "doctor/dentist"]


def test_job_stream_reports_progress_then_done(client, db, monkeypatch):
    import farsiyab.api as api_module

    monkeypatch.setattr(api_module, "STREAM_POLL_SECONDS", 0.01)
    job = jobs.enqueue(db, "index_city", {"city": "toronto"}, "index_city:toronto")
    job.status = "done"
    job.result = {"city": "toronto", "sources": {"overture": {"seen": 3, "stored": 1}}}
    db.commit()

    with client.stream("GET", f"/api/v1/search/jobs/{job.id}/stream") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    events = [block.split("\n")[0] for block in body.strip().split("\n\n")]
    assert events == ["event: progress", "event: done"]
    assert '"stored": 1' in body


def test_job_stream_unknown_job(client):
    url = "/api/v1/search/jobs/00000000-0000-0000-0000-000000000000/stream"
    assert client.get(url).status_code == 404


def test_three_not_iranian_reports_hide_a_business(client, toronto_data, db):
    business_id = search(client, categories="grocery")["results"][0]["id"]
    url = f"/api/v1/businesses/{business_id}/reports"
    for _ in range(3):
        assert client.post(url, json={"reason": "not_iranian"}).status_code == 201
    assert search(client, categories="grocery")["total"] == 0
    db.expire_all()
    assert db.get(Business, business_id).status == "hidden"


def test_report_validation(client, toronto_data):
    business_id = search(client, categories="grocery")["results"][0]["id"]
    url = f"/api/v1/businesses/{business_id}/reports"
    assert client.post(url, json={"reason": "boring"}).status_code == 422
    assert client.post(url, json={"reason": "remove_request",
                                  "contact_email": "not-an-email"}).status_code == 422
    assert client.post(url, json={"reason": "remove_request",
                                  "contact_email": "owner@example.com"}).status_code == 201
