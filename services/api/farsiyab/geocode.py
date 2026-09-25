"""Address → coordinates with Nominatim (OpenStreetMap), used for registries that
publish addresses without coordinates (IRS, CRA, Toronto licences).

Usage policy (https://operations.osmfoundation.org/policies/nominatim/): at most one
request per second, an identifying User-Agent, and cached results. Only the few
rows that already look Iranian are geocoded, never whole registries. Photon
(photon.komoot.io, also OSM data and keyless) is the fallback when Nominatim is
rate-limiting or down; the same one-request-per-second pace applies.
"""

import logging
import re
import time

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from farsiyab.config import get_settings
from farsiyab.models import GeocodeCache

log = logging.getLogger(__name__)

Point = tuple[float | None, float | None]
NOMINATIM = "https://nominatim.openstreetmap.org/search"
PHOTON = "https://photon.komoot.io/api/"  # OSM-based too; used when Nominatim rate-limits us

UNIT = re.compile(
    r"#\s*\S+|\b(?:SUITE|STE|UNIT|APT|FLOOR|FL|RPO|GROUND)\b\.?\s*[\w-]*|^\s*\w+\s*-\s*(?=\d)",
    re.IGNORECASE,
)


def clean_address(address: str) -> str:
    """Drop unit/suite parts Nominatim cannot resolve: '204 - 5635 YONGE ST, #3, B'."""
    parts = [UNIT.sub("", part).strip(" ,") for part in address.split(",")]
    # Lone unit letters/numbers left between commas ("6009 YONGE ST, B, TORONTO").
    # Province/state codes ("ON", "CA") stay; a single letter or short number goes.
    parts = [p for p in parts if p and not re.fullmatch(r"\w|\d+\w?", p)]
    return ", ".join(parts)


def postal_code(address: str) -> str | None:
    """Canadian (M2M 3S9) or US (90035) postal code, for a coarse fallback."""
    match = re.search(r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b|\b\d{5}\b(?=[^\d]*$)", address,
                      re.IGNORECASE)
    return match.group(0) if match else None


class Geocoder:
    def __init__(self, session: Session, client: httpx.Client | None = None, interval: float = 1.1):
        self.session = session
        self.client = client or httpx.Client(
            headers={"User-Agent": get_settings().user_agent}, timeout=30, http2=True
        )
        self.interval = interval
        self._last = 0.0

    def locate(self, address: str, country_code: str) -> tuple[float | None, float | None]:
        """Street address first, then the postal code's centre. Registry locations are
        private (never shown), so postal-code precision is enough to pick the city."""
        cleaned = clean_address(address)
        lat, lng = self._lookup(cleaned, country_code)
        code = postal_code(address)
        if lat is None and code:
            lat, lng = self._lookup(code, country_code)
        return lat, lng

    def _lookup(self, address: str, country_code: str) -> tuple[float | None, float | None]:
        query = f"{address} | {country_code.lower()}"
        cached = self.session.get(GeocodeCache, query)
        if cached is not None:
            return cached.lat, cached.lng
        found = self._nominatim(address, country_code)
        if found is None:  # rate limited or down: same data, other public service
            found = self._photon(address, country_code)
        if found is None:
            return None, None  # nothing cached: asked again on the next run
        self.session.execute(
            insert(GeocodeCache).values(query=query, lat=found[0], lng=found[1])
            .on_conflict_do_nothing()
        )
        self.session.commit()
        return found

    def _get(self, url: str, params: dict[str, str | int]) -> httpx.Response | None:
        wait = self.interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            return self.client.get(url, params=params)
        except httpx.HTTPError as exc:
            log.warning("geocoder %s: %s", url, exc)
            return None
        finally:
            self._last = time.monotonic()

    def _nominatim(self, address: str, country_code: str) -> Point | None:
        """(lat, lng), (None, None) for "no such address", or None when unavailable."""
        response = self._get(NOMINATIM, {"q": address, "countrycodes": country_code.lower(),
                                         "format": "jsonv2", "limit": 1})
        if response is None or response.status_code != 200:
            if response is not None:
                log.warning("nominatim: HTTP %s for %r", response.status_code, address)
            return None
        hits = response.json()
        return (float(hits[0]["lat"]), float(hits[0]["lon"])) if hits else (None, None)

    def _photon(self, address: str, country_code: str) -> Point | None:
        response = self._get(PHOTON, {"q": address, "limit": 5})
        if response is None or response.status_code != 200:
            return None
        for feature in response.json().get("features", []):
            if (feature.get("properties", {}).get("countrycode") or "").upper() == country_code:
                lng, lat = feature["geometry"]["coordinates"]
                return float(lat), float(lng)
        return (None, None)
