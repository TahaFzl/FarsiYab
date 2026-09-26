import pytest
from sqlalchemy import select

from farsiyab import evaluation
from farsiyab.config import get_settings
from farsiyab.indexer import recompute_scores, store_listing
from farsiyab.loader import load_reference
from farsiyab.models import Business, DoNotIndex, Label, Source, Submission
from tests.test_api import search
from tests.test_pipeline import listing

TOKEN = "test-admin-token"


@pytest.fixture
def admin(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_token", TOKEN)
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    return client


def submit(client, **fields):
    body = {
        "country": "CA", "city": "toronto", "name": "Kabab Sara", "category": "restaurant",
        "links": ["https://www.instagram.com/kababsara/"], **fields,
    }
    return client.post("/api/v1/submissions", json=body)


# ── Public submission form ────────────────────────────────────────────────────


def test_submission_is_pending_and_not_shown(client, db):
    response = submit(client, name="رستوران کباب سرا", is_owner=True)
    assert response.status_code == 201 and response.json()["status"] == "pending"
    stored = db.scalar(select(Submission))
    assert stored.is_owner and stored.detected_score > 0 and stored.client_hash
    assert db.scalar(select(Business)) is None


@pytest.mark.parametrize("fields, status", [
    ({"city": "atlantis"}, 422),
    ({"category": "spaceship"}, 422),
    ({"links": []}, 422),
    ({"links": ["javascript:alert(1)"]}, 422),
    ({"name": "x"}, 422),
])
def test_submission_validation(client, fields, status):
    assert submit(client, **fields).status_code == status


def test_honeypot_stores_nothing(client, db):
    assert submit(client, company_website="http://spam.example").status_code == 201
    assert db.scalar(select(Submission)) is None


def test_submissions_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "submissions_per_day", 2)
    assert [submit(client).status_code for _ in range(3)] == [201, 201, 429]


# ── Admin auth ────────────────────────────────────────────────────────────────


def test_admin_is_off_without_a_token_and_needs_it_otherwise(client, monkeypatch):
    assert client.get("/api/v1/admin/overview").status_code == 503
    monkeypatch.setattr(get_settings(), "admin_token", TOKEN)
    assert client.get("/api/v1/admin/overview").status_code == 401
    client.headers["Authorization"] = "Bearer wrong"
    assert client.get("/api/v1/admin/overview").status_code == 401
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    assert client.get("/api/v1/admin/overview").status_code == 200


# ── Review ────────────────────────────────────────────────────────────────────


def test_approved_submission_is_shown_with_its_evidence(admin, db):
    submit(admin, name="Kabab Sara", links=["https://kababsara.example/"])
    pending = admin.get("/api/v1/admin/submissions").json()
    assert len(pending) == 1 and pending[0]["possible_duplicate"] is None
    response = admin.post(f"/api/v1/admin/submissions/{pending[0]['id']}/approve", json={})
    assert response.status_code == 200

    body = search(admin, categories="restaurant")
    card = body["results"][0]
    assert card["name"]["latin"] == "Kabab Sara"
    assert card["evidence"][0]["signal"] == "user_submission_verified"
    assert {s["id"] for s in card["sources"]} == {"user_submission"}
    # A decision is final.
    again = admin.post(f"/api/v1/admin/submissions/{pending[0]['id']}/approve", json={})
    assert again.status_code == 409


def test_submission_merges_with_a_known_business(admin, db, toronto_data):
    submit(admin, name="Shiraz Kitchen", links=["https://shiraz.example/about"])
    pending = admin.get("/api/v1/admin/submissions").json()[0]
    assert pending["possible_duplicate"]["name"]["latin"] == "Shiraz Kitchen"
    admin.post(f"/api/v1/admin/submissions/{pending['id']}/approve", json={})
    assert db.scalar(select(Business.id).where(Business.name_latin == "Kabab Sara")) is None
    card = search(admin, categories="restaurant")["results"][0]
    assert {"overture", "user_submission"} <= {s["id"] for s in card["sources"]}


def test_rejected_submission_stays_hidden(admin, db):
    submit(admin)
    submission_id = admin.get("/api/v1/admin/submissions").json()[0]["id"]
    admin.post(f"/api/v1/admin/submissions/{submission_id}/reject", json={"note": "spam"})
    assert admin.get("/api/v1/admin/submissions").json() == []
    assert admin.get("/api/v1/admin/submissions", params={"status": "rejected"}).json()
    assert db.scalar(select(Business)) is None


def test_removal_request_blocks_the_business_for_good(admin, db, toronto_data):
    shiraz = db.scalar(select(Business).where(Business.name_latin == "Shiraz Kitchen"))
    admin.post(f"/api/v1/businesses/{shiraz.id}/reports",
               json={"reason": "remove_request", "message": "I own it, please remove"})
    queue = admin.get("/api/v1/admin/reports").json()
    assert queue[0]["business"]["id"] == str(shiraz.id)
    report_id = queue[0]["reports"][0]["id"]
    assert admin.post(f"/api/v1/admin/reports/{report_id}/resolve",
                      json={"action": "remove"}).json() == {"status": "resolved"}

    db.expire_all()
    assert db.get(Business, shiraz.id).status == "removed_by_request"
    assert ("website", "shiraz.example") in set(
        db.execute(select(DoNotIndex.kind, DoNotIndex.value)).all()
    )
    assert search(admin, categories="restaurant")["total"] == 0
    # Another source listing the same website does not bring it back.
    assert not store_listing(db, toronto_data, listing(
        source="osm", external_id="x", name="Shiraz Kitchen", lat=43.2,
        urls=["https://shiraz.example/"],
    ))
    # Nor does a submission.
    submit(admin, name="Shiraz Kitchen", links=["https://shiraz.example/"])
    submission_id = admin.get("/api/v1/admin/submissions").json()[0]["id"]
    blocked = admin.post(f"/api/v1/admin/submissions/{submission_id}/approve", json={})
    assert blocked.status_code == 409


def test_hidden_business_can_be_restored(admin, db, toronto_data):
    tehran = db.scalar(select(Business).where(Business.name_latin == "Tehran Market"))
    for _ in range(3):
        admin.post(f"/api/v1/businesses/{tehran.id}/reports", json={"reason": "not_iranian"})
    assert [b["id"] for b in admin.get("/api/v1/admin/hidden").json()] == [str(tehran.id)]
    report_id = admin.get("/api/v1/admin/reports").json()[0]["reports"][0]["id"]
    admin.post(f"/api/v1/admin/reports/{report_id}/resolve", json={"action": "restore"})
    assert admin.get("/api/v1/admin/reports").json() == []
    assert admin.get("/api/v1/admin/hidden").json() == []


# ── Sources and indexing ──────────────────────────────────────────────────────


def test_disabled_source_survives_a_reference_reload(admin, db):
    assert admin.patch("/api/v1/admin/sources/osm", json={"enabled": False}).status_code == 200
    load_reference(db)
    db.expire_all()
    assert db.get(Source, "osm").enabled is False
    # Sources that need an account cannot be switched on here.
    assert admin.patch("/api/v1/admin/sources/google_places",
                       json={"enabled": True}).status_code == 409
    admin.patch("/api/v1/admin/sources/osm", json={"enabled": True})


def test_manual_index_queues_one_job(admin):
    first = admin.post("/api/v1/admin/index", json={"city": "berlin"}).json()
    second = admin.post("/api/v1/admin/index", json={"city": "berlin"}).json()
    assert first["job_id"] == second["job_id"]
    assert admin.get("/api/v1/admin/jobs").json()[0]["city"] == "berlin"
    assert admin.post("/api/v1/admin/index", json={"city": "atlantis"}).status_code == 404


def test_overview(admin, toronto_data):
    submit(admin)
    body = admin.get("/api/v1/admin/overview").json()
    assert body["pending_submissions"] == 1 and body["open_reports"] == 0
    toronto = next(c for c in body["cities"] if c["slug"] == "toronto")
    assert toronto["last_indexed_at"] is not None


# ── Labels and precision ──────────────────────────────────────────────────────


def test_labeling_measures_precision_per_level(admin, db, toronto_data):
    seen = set()
    while (card := admin.get("/api/v1/admin/labels/next").json()["business"]) is not None:
        assert card["id"] not in seen
        seen.add(card["id"])
        is_iranian = card["name"]["latin"] != "Tehran Market"
        admin.post(f"/api/v1/admin/businesses/{card['id']}/label",
                   json={"is_iranian": is_iranian, "by": "tester"})
    assert len(seen) == 2  # the weak dentist is not shown, so it is not sampled
    result = admin.get("/api/v1/admin/precision").json()
    levels = result["levels"]
    assert sum(level["labeled"] for level in levels.values()) == 2
    # Shiraz Kitchen (Iranian) is "high"; Tehran Market (labeled not Iranian) is "low",
    # so the published levels are 100% precise and the low one is 0%.
    assert levels["high"] == {"labeled": 1, "iranian": 1, "precision": 1.0,
                              "ci95": [0.207, 1.0]}
    assert levels["low"]["precision"] == 0.0
    assert result["high_and_medium"] == 1.0 and result["met"] is True
    assert db.scalar(select(Label.labeled_by)) == "tester"


def test_what_if_weights(db, toronto_data):
    for business in db.scalars(select(Business)):
        evaluation.save_label(db, business, business.name_latin == "Shiraz Kitchen", "t")
    db.flush()
    recompute_scores(db, toronto_data.id)
    base = evaluation.precision_with_weights(db, {})
    assert base["levels"]["high"]["labeled"] >= 1
    muted = evaluation.precision_with_weights(db, {"overture_persian_category": 0.0})
    assert muted["levels"]["high"]["labeled"] < base["levels"]["high"]["labeled"]


def test_wilson_interval():
    assert evaluation.wilson_interval(0, 0) == (0.0, 0.0)
    low, high = evaluation.wilson_interval(90, 100)
    assert 0.82 < low < 0.9 < high < 0.95
