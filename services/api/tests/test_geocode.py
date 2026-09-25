import httpx

from farsiyab.geocode import Geocoder
from farsiyab.models import GeocodeCache


def geocoder(db, handler):
    return Geocoder(db, httpx.Client(transport=httpx.MockTransport(handler)), interval=0)


def test_nominatim_answer_is_cached(db):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        return httpx.Response(200, json=[{"lat": "43.78", "lon": "-79.41"}])

    g = geocoder(db, handler)
    assert g.locate("5635 YONGE ST, NORTH YORK, ON, M2M3S9", "CA") == (43.78, -79.41)
    assert g.locate("5635 YONGE ST, NORTH YORK, ON, M2M3S9", "CA") == (43.78, -79.41)
    assert calls == ["nominatim.openstreetmap.org"]


def test_photon_is_used_when_nominatim_rate_limits(db):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "nominatim.openstreetmap.org":
            return httpx.Response(429)
        return httpx.Response(200, json={"features": [
            {"geometry": {"coordinates": [2.35, 48.85]}, "properties": {"countrycode": "FR"}},
            {"geometry": {"coordinates": [-79.41, 43.78]}, "properties": {"countrycode": "CA"}},
        ]})

    assert geocoder(db, handler).locate("5635 YONGE ST, TORONTO", "CA") == (43.78, -79.41)


def test_unavailable_services_are_not_cached(db):
    g = geocoder(db, lambda request: httpx.Response(503))
    assert g.locate("1 NOWHERE RD, M2M3S9", "CA") == (None, None)
    assert db.query(GeocodeCache).count() == 0


def test_postal_code_fallback(db):
    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params.get("q")
        if q == "M2M3S9":
            return httpx.Response(200, json=[{"lat": "43.80", "lon": "-79.39"}])
        return httpx.Response(200, json=[])  # street address unknown

    found = geocoder(db, handler).locate("9 UNKNOWN LANE, TORONTO, ON, M2M3S9", "CA")
    assert found == (43.8, -79.39)
