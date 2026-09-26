import httpx
import pytest
from sqlalchemy import select

from farsiyab import places
from farsiyab.models import City, Country, Job

# Shapes of the live responses (checked 2026-09-26).
PHOTON = {"features": [
    {"properties": {"osm_type": "N", "osm_id": 25930131, "osm_key": "place", "osm_value": "city",
                    "name": "Gothenburg", "country": "Sweden", "countrycode": "SE"}},
    {"properties": {"osm_type": "R", "osm_id": 169270, "osm_key": "place", "osm_value": "city",
                    "name": "Gothenburg", "state": "Nebraska", "country": "United States",
                    "countrycode": "US"}},
    {"properties": {"osm_type": "W", "osm_id": 1, "osm_key": "highway", "osm_value": "residential",
                    "name": "Gothenburg Road", "countrycode": "GB"}},
]}


def lookup(lang, **overrides):
    place = {
        "lat": "59.91", "lon": "10.75", "addresstype": "city", "name": "Oslo",
        "boundingbox": ["59.81", "60.13", "10.49", "10.95"],
        "namedetails": {"name": "Oslo", "name:en": "Oslo", "name:fa": "اسلو"},
        "address": {"country": "نروژ" if lang == "fa" else "Norway", "country_code": "no",
                    "ISO3166-2-lvl4": "NO-03"},
    }
    place.update(overrides)
    return [place]


def nominatim(**overrides):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/lookup"
        return httpx.Response(200, json=lookup(request.url.params["accept-language"], **overrides))
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_photon_keeps_only_cities():
    found = places.parse_photon(PHOTON)
    assert [(s.osm_id, s.country_code) for s in found] == [("N25930131", "SE"), ("R169270", "US")]


def test_create_city_with_country_region_and_persian_name(db):
    city = places.create_city(db, "R406091", client=nominatim(), interval=0)
    assert (city.slug, city.country_code) == ("oslo", "NO")
    assert (city.name_fa, city.name_en) == ("اسلو", "Oslo")
    assert city.regions == ["03"] and city.wikivoyage == ["Oslo"]
    assert city.added_by == "visitor"
    west, south, east, north = city.west, city.south, city.east, city.north
    assert west < 10.49 and east > 10.95 and south < 59.81 and north > 60.13  # widened
    assert north - south <= places.MAX_SPAN + 1e-9
    country = db.get(Country, "NO")
    assert (country.name_en, country.name_fa) == ("Norway", "نروژ")
    # Asking again returns the same city without a lookup.
    assert places.create_city(db, "R406091", client=None) is city


def test_point_city_gets_a_default_box():
    west, south, east, north = places.metro_bbox(57.7, 11.97, None)
    assert north - south == pytest.approx(2 * places.MIN_HALF_SPAN, abs=0.01)
    assert east - west > north - south  # longitude degrees are shorter up north


def test_not_a_city_is_refused(db):
    with pytest.raises(places.PlaceError, match="not a city"):
        places.create_city(db, "R1", client=nominatim(addresstype="country"), interval=0)
    with pytest.raises(places.PlaceError, match="not an OSM id"):
        places.create_city(db, "X1")


def test_french_regions_are_departements():
    address = {"ISO3166-2-lvl4": "FR-IDF", "ISO3166-2-lvl6": "FR-75"}
    assert places.region_codes(address, "FR") == ["75"]
    assert places.region_codes({"ISO3166-2-lvl4": "US-CA"}, "US") == ["CA"]


def test_new_city_through_the_api_is_indexed_on_first_search(client, db, monkeypatch):
    real = places.create_city
    monkeypatch.setattr(places, "create_city",
                        lambda session, osm_id: real(session, osm_id, nominatim(), 0))
    body = client.post("/api/v1/cities", json={"osm_id": "R406091"}).json()
    assert body == {"slug": "oslo", "country": "NO", "name": "اسلو"}
    search = client.get("/api/v1/search", params={"country": "NO", "city": "oslo",
                                                  "categories": "restaurant"}).json()
    assert search["total"] == 0 and search["live_search"]["status"] == "queued"
    assert db.scalar(select(Job.payload)) == {"city": "oslo"}
    assert client.post("/api/v1/cities", json={"osm_id": "oslo"}).status_code == 422


def test_suggestions_endpoint(client, monkeypatch):
    monkeypatch.setattr(places, "suggest", lambda q, lang: places.parse_photon(PHOTON))
    body = client.get("/api/v1/places", params={"q": "gothen"}).json()
    assert body[0] == {"osm_id": "N25930131", "name": "Gothenburg", "state": None,
                       "country": "Sweden", "country_code": "SE"}


def test_curated_cities_keep_regions_from_yaml(db):
    toronto = db.scalar(select(City).where(City.slug == "toronto"))
    assert toronto.regions == ["ON"] and toronto.added_by == "curated"


def test_a_place_inside_a_known_city_gets_that_city(db):
    # Irvine is inside the curated Los Angeles box.
    irvine = nominatim(lat="33.68", lon="-117.79", name="Irvine",
                       namedetails={"name": "Irvine"},
                       address={"country": "United States", "country_code": "us",
                                "ISO3166-2-lvl4": "US-CA"})
    assert places.create_city(db, "R114485", client=irvine, interval=0).slug == "los-angeles"


def test_persian_speaking_countries_are_excluded(db):
    tehran = nominatim(address={"country": "Iran", "country_code": "ir"})
    with pytest.raises(places.PlaceError, match="Persian-speaking"):
        places.create_city(db, "R6663864", client=tehran, interval=0)
    photon = {"features": [{"properties": {"osm_type": "R", "osm_id": 1, "osm_key": "place",
                                           "osm_value": "city", "name": "Tehran",
                                           "countrycode": "IR"}}]}
    assert places.parse_photon(photon) == []


def test_cities_are_suggested_before_villages():
    data = {"features": [
        {"properties": {"osm_type": "R", "osm_id": 1, "osm_key": "place", "osm_value": "village",
                        "name": "Mun", "countrycode": "FR"}},
        {"properties": {"osm_type": "R", "osm_id": 2, "osm_key": "place", "osm_value": "city",
                        "name": "Munich", "countrycode": "DE"}},
    ]}
    assert [s.name for s in places.parse_photon(data)] == ["Munich", "Mun"]
