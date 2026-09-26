"""Any city in the world: suggestions while typing, and creating a city on first use.

- Suggestions come from Photon (photon.komoot.io, OpenStreetMap data), which is made
  for search-as-you-type. Nominatim's usage policy forbids autocomplete, so it is
  asked only once per new city, when a visitor picks it.
- A new city stores what the indexer needs: a bounding box widened to the metro area
  (and capped, so one city cannot mean indexing a whole region), English and Persian
  names, the country, and its state/province code for the registries that are read
  per region (IRS, CRA, ACNC, Charity Commission, SIRENE).
"""

import logging
import math
import re
import time
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from farsiyab.config import get_settings
from farsiyab.models import City, Country

log = logging.getLogger(__name__)

PHOTON = "https://photon.komoot.io/api/"
NOMINATIM_LOOKUP = "https://nominatim.openstreetmap.org/lookup"
# Settlement types kept, most important first (a village named "Mun" after Munich).
PLACE_RANK = {"city": 0, "town": 1, "municipality": 1, "borough": 2, "suburb": 2, "village": 3}
PLACE_VALUES = set(PLACE_RANK)
MAX_SUGGESTIONS = 8
# Countries where Persian is the everyday language: nearly every business would match,
# and FarsiYab is for finding Persian speakers abroad.
EXCLUDED_COUNTRIES = {"IR", "AF", "TJ"}

# Bounding box, in degrees of latitude: at least this big around the centre (a city
# given as a single point, or a small inner-city boundary)...
MIN_HALF_SPAN = 0.18
# ...widened by this share on every side (suburbs), and never bigger than this.
WIDEN = 0.25
MAX_SPAN = 1.2
# Where a registry's region is not the ISO first level (French départements).
REGION_LEVEL = {"FR": "ISO3166-2-lvl6"}


class PlaceError(Exception):
    """The place cannot become a city (not found, not a city, service down)."""


@dataclass(frozen=True)
class Suggestion:
    osm_id: str  # "R935611"
    name: str
    state: str | None
    country: str | None
    country_code: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"osm_id": self.osm_id, "name": self.name, "state": self.state,
                "country": self.country, "country_code": self.country_code}


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": get_settings().user_agent}, timeout=15)


def parse_photon(data: dict[str, Any]) -> list[Suggestion]:
    out: list[tuple[int, Suggestion]] = []
    for feature in data.get("features", []):
        p = feature.get("properties") or {}
        if p.get("osm_key") != "place" or p.get("osm_value") not in PLACE_VALUES:
            continue
        if not p.get("osm_type") or not p.get("osm_id") or not p.get("name"):
            continue
        if (p.get("countrycode") or "").upper() in EXCLUDED_COUNTRIES:
            continue
        rank = PLACE_RANK[p["osm_value"]]
        suggestion = Suggestion(
            osm_id=f"{p['osm_type']}{p['osm_id']}",
            name=p["name"],
            state=p.get("state"),
            country=p.get("country"),
            country_code=(p.get("countrycode") or "").upper() or None,
        )
        if suggestion not in [x for _, x in out]:
            out.append((rank, suggestion))
    return [x for _, x in sorted(out, key=lambda pair: pair[0])]  # stable: Photon order


@lru_cache(maxsize=2048)
def _suggest_cached(query: str, lang: str) -> tuple[Suggestion, ...]:
    with _client() as client:
        try:
            # No layer=city: it drops Istanbul and Dubai, which OSM maps as provinces with a
            # place=city point inside. The filter in parse_photon keeps only settlements.
            response = client.get(PHOTON, params={"q": query, "limit": 20, "lang": lang})
        except httpx.HTTPError as exc:
            raise PlaceError(f"place search unavailable: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise PlaceError(f"place search returned HTTP {response.status_code}")
    return tuple(parse_photon(response.json())[:MAX_SUGGESTIONS])


def suggest(query: str, lang: str = "en") -> list[Suggestion]:
    query = " ".join(query.split())[:80]
    if len(query) < 2:
        return []
    # Photon has English, German, French and Italian names; Persian is added on creation.
    return list(_suggest_cached(query.lower(), "en" if lang == "fa" else lang))


def metro_bbox(lat: float, lng: float, box: list[float] | None) -> tuple[float, ...]:
    """(west, south, east, north) around the city, widened and capped."""
    if box:
        south, north, west, east = box
    else:
        south = north = lat
        west = east = lng
    stretch = 1 / max(math.cos(math.radians(lat)), 0.2)  # degrees of longitude per km
    half_lat = min(max((north - south) / 2 * (1 + 2 * WIDEN), MIN_HALF_SPAN), MAX_SPAN / 2)
    half_lng = min(max((east - west) / 2 * (1 + 2 * WIDEN), MIN_HALF_SPAN * stretch),
                   MAX_SPAN / 2 * stretch)
    mid_lat, mid_lng = (south + north) / 2, (west + east) / 2
    return (round(mid_lng - half_lng, 3), round(mid_lat - half_lat, 3),
            round(mid_lng + half_lng, 3), round(mid_lat + half_lat, 3))


def region_codes(address: dict[str, str], country: str) -> list[str]:
    code = address.get(REGION_LEVEL.get(country, "ISO3166-2-lvl4"), "")
    return [code.split("-", 1)[1]] if "-" in code else []


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "city"


def _lookup(client: httpx.Client, osm_id: str, lang: str) -> dict[str, Any]:
    try:
        response = client.get(NOMINATIM_LOOKUP, params={
            "osm_ids": osm_id, "format": "jsonv2", "addressdetails": 1, "namedetails": 1,
            "accept-language": lang,
        })
    except httpx.HTTPError as exc:
        raise PlaceError(f"place lookup unavailable: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise PlaceError(f"place lookup returned HTTP {response.status_code}")
    found = response.json()
    if not found:
        raise PlaceError(f"no such place: {osm_id}")
    return found[0]


def create_city(session: Session, osm_id: str, client: httpx.Client | None = None,
                interval: float = 1.0) -> City:
    """The city for an OSM place, created on first use (two Nominatim requests)."""
    if not re.fullmatch(r"[NWR]\d{1,12}", osm_id):
        raise PlaceError("not an OSM id")
    existing = session.scalar(select(City).where(City.osm_id == osm_id))
    if existing:
        return existing
    own = client is None
    client = client or _client()
    try:
        place = _lookup(client, osm_id, "en")
        time.sleep(interval)  # Nominatim: at most one request a second
        persian = _lookup(client, osm_id, "fa")
    finally:
        if own:
            client.close()
    kind = place.get("addresstype") or place.get("type")
    if kind not in PLACE_VALUES | {"city_district", "county"}:
        raise PlaceError(f"not a city: {kind}")
    address = place.get("address") or {}
    country_code = (address.get("country_code") or "").upper()
    if len(country_code) != 2:
        raise PlaceError("place without a country")
    if country_code in EXCLUDED_COUNTRIES:
        raise PlaceError("Persian-speaking country")

    lat, lng = float(place["lat"]), float(place["lon"])
    # Irvine is inside the Los Angeles box, and a visitor picking "Istanbul" should get
    # the curated Istanbul: an existing city whose box holds the place wins.
    covering = session.scalar(
        select(City).where(City.country_code == country_code, City.west <= lng,
                           City.east >= lng, City.south <= lat, City.north >= lat)
        .order_by((City.east - City.west) * (City.north - City.south))
    )
    if covering:
        return covering

    names = place.get("namedetails") or {}
    name_en = names.get("name:en") or place.get("name") or names.get("name")
    name_fa = names.get("name:fa") or persian.get("name") or name_en
    if session.get(Country, country_code) is None:
        persian_address = persian.get("address") or {}
        session.add(Country(code=country_code, name_en=address.get("country") or country_code,
                            name_fa=persian_address.get("country") or address.get("country")
                            or country_code))
        session.flush()

    west, south, east, north = metro_bbox(
        lat, lng, [float(x) for x in place["boundingbox"]] if place.get("boundingbox") else None
    )
    slug = slugify(name_en)
    if session.scalar(select(City.id).where(City.slug == slug)):
        slug = f"{slug}-{country_code.lower()}"
    if session.scalar(select(City.id).where(City.slug == slug)):
        slug = f"{slug}-{osm_id.lower()}"
    city = City(
        slug=slug, country_code=country_code, name_en=name_en, name_fa=name_fa,
        center=f"SRID=4326;POINT({lng} {lat})", west=west, south=south, east=east, north=north,
        regions=region_codes(address, country_code), wikivoyage=[name_en], osm_id=osm_id,
        added_by="visitor",
    )
    session.add(city)
    session.flush()
    log.info("new city %s (%s) %s", slug, osm_id, (west, south, east, north))
    return city
