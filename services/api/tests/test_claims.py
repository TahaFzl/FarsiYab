import httpx
import pytest
from sqlalchemy import select

from farsiyab import claims
from farsiyab.config import get_settings
from farsiyab.models import Business, Claim
from tests.test_api import search

TOKEN = "test-admin-token"
REAL_PAGE_HAS_TOKEN = claims.page_has_token


def shiraz(db):
    return db.scalar(select(Business).where(Business.name_latin == "Shiraz Kitchen"))


def fake_site(monkeypatch, pages):
    """Serve `pages` (url -> html) to the claim checker instead of the internet."""
    def handler(request: httpx.Request) -> httpx.Response:
        html = pages.get(str(request.url))
        return httpx.Response(200, text=html) if html is not None else httpx.Response(404)

    def checker(url, token, client=None):
        return REAL_PAGE_HAS_TOKEN(url, token, httpx.Client(transport=httpx.MockTransport(handler)))

    monkeypatch.setattr(claims, "page_has_token", checker)


def test_website_claim_gives_an_owner_key_that_edits_the_listing(client, db, toronto_data,
                                                                  monkeypatch):
    business = shiraz(db)
    started = client.post(f"/api/v1/businesses/{business.id}/claims",
                          json={"method": "website", "contact_email": "owner@shiraz.example"})
    assert started.status_code == 201
    body = started.json()
    assert body["where"] == "https://shiraz.example/"
    assert body["token"].startswith("farsiyab-")

    # Token not on the page yet.
    fake_site(monkeypatch, {"https://shiraz.example/": "<html>welcome</html>"})
    assert client.post(f"/api/v1/claims/{body['id']}/verify").status_code == 409

    fake_site(monkeypatch, {"https://shiraz.example/":
                            f'<meta name="farsiyab-verification" content="{body["token"]}">'})
    verified = client.post(f"/api/v1/claims/{body['id']}/verify")
    assert verified.status_code == 200
    key = verified.json()["owner_key"]
    stored = db.scalar(select(Claim))
    assert stored.owner_key_hash != key  # only the hash is kept

    headers = {"X-Owner-Key": key}
    view = client.get(f"/api/v1/owner/{body['id']}", headers=headers).json()
    assert view["business"]["name"]["latin"] == "Shiraz Kitchen"
    edit = client.patch(f"/api/v1/owner/{body['id']}", headers=headers,
                        json={"address": "12 Yonge St, Toronto", "phone": "416 555 0199"})
    assert edit.status_code == 200
    card = search(client, categories="restaurant")["results"][0]
    assert card["address"] == "12 Yonge St, Toronto"
    assert card["contact"]["phone"] == "+14165550199"
    assert card["owner_verified"] is True

    # The owner can close it; a wrong key cannot.
    assert client.patch(f"/api/v1/owner/{body['id']}", headers={"X-Owner-Key": "nope"},
                        json={"status": "closed"}).status_code == 403
    client.patch(f"/api/v1/owner/{body['id']}", headers=headers, json={"status": "closed"})
    assert search(client, categories="restaurant")["total"] == 0


def test_claim_needs_a_known_link_for_its_method(client, db, toronto_data):
    tehran = db.scalar(select(Business).where(Business.name_latin == "Tehran Market"))
    response = client.post(f"/api/v1/businesses/{tehran.id}/claims", json={"method": "website"})
    assert response.status_code == 422 and "no known website" in response.text
    manual = client.post(f"/api/v1/businesses/{tehran.id}/claims", json={"method": "manual"})
    assert manual.status_code == 422  # needs an email to send the key to


def test_manual_claim_is_verified_by_an_admin(client, db, toronto_data, monkeypatch):
    tehran = db.scalar(select(Business).where(Business.name_latin == "Tehran Market"))
    started = client.post(f"/api/v1/businesses/{tehran.id}/claims",
                          json={"method": "manual", "contact_email": "me@example.com",
                                "note": "call us at the shop"}).json()
    assert client.post(f"/api/v1/claims/{started['id']}/verify").status_code == 409

    monkeypatch.setattr(get_settings(), "admin_token", TOKEN)
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    pending = client.get("/api/v1/admin/claims").json()
    assert [c["contact_email"] for c in pending] == ["me@example.com"]
    granted = client.post(f"/api/v1/admin/claims/{started['id']}/verify").json()
    assert granted["contact_email"] == "me@example.com" and granted["owner_key"]
    view = client.get(f"/api/v1/owner/{started['id']}",
                      headers={"X-Owner-Key": granted["owner_key"]})
    assert view.status_code == 200
    assert client.post(f"/api/v1/admin/claims/{started['id']}/verify").status_code == 409


@pytest.mark.parametrize("changes", [{"website": "https://facebook.com/x"}, {"phone": "abc"}])
def test_owner_edit_validation(client, db, toronto_data, changes):
    business = shiraz(db)
    claim = Claim(business_id=business.id, method="manual", token="farsiyab-x")
    db.add(claim)
    key = claims.grant(claim)
    db.commit()
    response = client.patch(f"/api/v1/owner/{claim.id}", headers={"X-Owner-Key": key},
                            json=changes)
    assert response.status_code == 422


def test_public_business_card(client, db, toronto_data):
    business = shiraz(db)
    card = client.get(f"/api/v1/businesses/{business.id}").json()
    assert card["name"]["latin"] == "Shiraz Kitchen" and card["city"]["slug"] == "toronto"
    weak = db.scalar(select(Business).where(Business.name_latin == "Dr. Karimzadeh Dental"))
    assert client.get(f"/api/v1/businesses/{weak.id}").status_code == 404  # not shown
