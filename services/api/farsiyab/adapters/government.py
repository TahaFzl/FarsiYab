"""Government open data: city business licences and nonprofit registries
(docs/sources/government-open-data.md). No account or key needed.

Privacy rules applied here (docs/07-legal-and-privacy.md):
- only trade / operating / organisation names are used, never an owner's name
  (Vancouver puts sole proprietors' names in parentheses, Toronto has "Client Name",
  the IRS has "ICO" = in care of);
- registry addresses may be homes, so every listing is `private_location`: its
  coordinates help match other sources but are never stored or shown.
"""

import csv
import io
import json
import logging
import re
import time
import zipfile
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any

import httpx

from farsiyab.adapters.base import RawListing, SourceUnavailable
from farsiyab.config import get_settings
from farsiyab.detection.detector import TextField, detect, has_positive
from farsiyab.detection.lexicon import latin_hint_terms
from farsiyab.geocode import Geocoder
from farsiyab.reference import CityInfo

log = logging.getLogger(__name__)


def _client(client: httpx.Client | None) -> httpx.Client:
    return client or httpx.Client(
        headers={"User-Agent": get_settings().user_agent}, timeout=300, follow_redirects=True,
        http2=True,
    )


def _get(client: httpx.Client, url: str, what: str, **params: Any) -> httpx.Response:
    try:
        response = client.get(url, params=params or None)
    except httpx.HTTPError as exc:
        raise SourceUnavailable(f"{what} unreachable: {exc}") from exc
    if response.status_code != 200:
        raise SourceUnavailable(f"{what} returned HTTP {response.status_code}")
    return response


def hint_pattern(terms: Iterable[str] | None = None) -> re.Pattern[str]:
    """Coarse local pre-filter; the detector makes the real decision."""
    terms = list(terms or latin_hint_terms())
    return re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)


def looks_iranian(name: str) -> bool:
    """The detector's own verdict, used before any geocoding request is made."""
    return has_positive(detect([TextField("name", name)]))


def _in_box(lat: float | None, lng: float | None, city: CityInfo) -> bool:
    west, south, east, north = city.bbox
    return lat is not None and lng is not None and south <= lat <= north and west <= lng <= east


def _category(text: str, rules: tuple[tuple[str, str], ...]) -> str:
    lowered = text.lower()
    return next((slug for needle, slug in rules if needle in lowered), "other")


# ── Los Angeles: Listing of Active Businesses (Socrata) ──────────────────────

LA_DATASET = "https://data.lacity.org/resource/6rrh-rzua.json"
LA_PAGE = "https://data.lacity.org/Administration-Finance/Listing-of-Active-Businesses/6rrh-rzua"
NAICS_CATEGORY = (
    ("7225", "restaurant"), ("722", "restaurant"), ("311811", "bakery"), ("4452", "grocery"),
    ("4451", "grocery"), ("6212", "doctor/dentist"), ("6211", "doctor"), ("621", "doctor"),
    ("5411", "lawyer"), ("5312", "real_estate"), ("531", "real_estate"), ("8121", "beauty"),
    ("5412", "accounting"), ("54193", "translator"), ("611", "education"), ("813", "community"),
)


def naics_category(code: str | None) -> str:
    code = code or ""
    return next((slug for prefix, slug in NAICS_CATEGORY if code.startswith(prefix)), "other")


COMPANY_SUFFIX = re.compile(
    r"\b(INC|INCORPORATED|LLC|L\.L\.C|CORP|CORPORATION|CO|COMPANY|LTD|LP|LLP|PC|APC|GROUP)\b\.?",
    re.IGNORECASE,
)


class LosAngelesAdapter:
    id = "gov:la_business"
    cities = ("los-angeles",)

    def __init__(self, client: httpx.Client | None = None, page_size: int = 5000):
        self.client = _client(client)
        self.page_size = page_size

    def where(self) -> str:
        return " OR ".join(
            f"upper({field}) like '%{term.upper()}%'"
            for term in latin_hint_terms()
            for field in ("business_name", "dba_name")
        )

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        if city.slug not in self.cities:
            return
        offset = 0
        while True:
            rows = _get(
                self.client, LA_DATASET, "LA open data",
                **{"$where": self.where(), "$limit": self.page_size, "$offset": offset,
                   "$order": "location_account"},
            ).json()
            for row in rows:
                listing = self.to_listing(row)
                if listing:
                    yield listing
            if len(rows) < self.page_size:
                return
            offset += self.page_size

    @staticmethod
    def to_listing(row: dict[str, Any]) -> RawListing | None:
        # dba_name is the trade name. business_name is the owner's own name for sole
        # proprietors ("YALDA YAZDANPANAH"), so it is only used for companies.
        name = (row.get("dba_name") or "").strip()
        legal = (row.get("business_name") or "").strip()
        if not name and COMPANY_SUFFIX.search(legal):
            name = legal
        if not name:
            return None
        location = row.get("location_1") or {}
        lat = float(location["latitude"]) if location.get("latitude") else None
        lng = float(location["longitude"]) if location.get("longitude") else None
        if lat == 0 or lng == 0:
            lat = lng = None
        return RawListing(
            source_id="gov:la_business",
            external_id=row["location_account"],
            name=name,
            url=LA_PAGE,
            lat=lat,
            lng=lng,
            category=naics_category(row.get("naics")),
            texts=[TextField("name", name, LA_PAGE)],
            raw={"name": name, "naics": row.get("naics"),
                 "naics_description": row.get("primary_naics_description")},
            private_location=True,
        )


# ── Vancouver: Business licences (Opendatasoft) ───────────────────────────────

VANCOUVER_DATASET = (
    "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/business-licences/records"
)
VANCOUVER_PAGE = "https://opendata.vancouver.ca/explore/dataset/business-licences/"
VANCOUVER_CATEGORY = (
    ("restaurant", "restaurant"), ("food establishment", "restaurant"), ("caterer", "restaurant"),
    ("grocery", "grocery"), ("retail dealer - food", "grocery"), ("health care", "doctor"),
    ("legal", "lawyer"), ("real estate", "real_estate"), ("beauty", "beauty"),
    ("financial services", "accounting"), ("school", "education"), ("instruction", "education"),
    ("association or society", "community"),
)


class VancouverAdapter:
    id = "gov:vancouver_business"
    cities = ("vancouver",)

    def __init__(self, client: httpx.Client | None = None, page_size: int = 100):
        self.client = _client(client)
        self.page_size = page_size

    @staticmethod
    def years(now: datetime | None = None) -> list[str]:
        year = (now or datetime.now(UTC)).year % 100
        return [f"{year - 1:02d}", f"{year:02d}"]

    def where(self) -> str:
        names = " or ".join(
            f'businesstradename like "%{t}%" or businessname like "%{t}%"'
            for t in latin_hint_terms()
        )
        years = ", ".join(f'"{y}"' for y in self.years())
        return f'status="Issued" and folderyear in ({years}) and ({names})'

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        if city.slug not in self.cities:
            return
        latest: dict[tuple[str, str, str], dict[str, Any]] = {}
        offset = 0
        while True:
            data = _get(
                self.client, VANCOUVER_DATASET, "Vancouver open data",
                where=self.where(), limit=self.page_size, offset=offset,
            ).json()
            for row in data.get("results", []):
                name = self.trade_name(row)
                if not name:
                    continue
                key = (name.lower(), row.get("house") or "", (row.get("street") or "").lower())
                if key not in latest or row["folderyear"] > latest[key]["folderyear"]:
                    latest[key] = row
            offset += self.page_size
            if offset >= data.get("total_count", 0) or not data.get("results"):
                break
        for row in latest.values():
            yield self.to_listing(row)

    @staticmethod
    def trade_name(row: dict[str, Any]) -> str | None:
        """Trade name, or the legal name unless it is a person's (shown in parentheses)."""
        trade = (row.get("businesstradename") or "").strip()
        legal = (row.get("businessname") or "").strip()
        if trade:
            return trade
        if legal and not legal.startswith("("):
            return legal
        return None

    def to_listing(self, row: dict[str, Any]) -> RawListing:
        name = self.trade_name(row) or ""
        point = row.get("geo_point_2d") or {}
        street = (row.get("street") or "").lower()
        return RawListing(
            source_id=self.id,
            # Licence numbers change every year; the business and its address do not.
            external_id=f"{name.lower()}|{row.get('house') or ''}|{street}",
            name=name,
            url=VANCOUVER_PAGE,
            lat=point.get("lat"),
            lng=point.get("lon"),
            category=_category(row.get("businesstype") or "", VANCOUVER_CATEGORY),
            texts=[TextField("name", name, VANCOUVER_PAGE)],
            raw={"name": name, "type": row.get("businesstype"), "licence": row.get("licencenumber"),
                 "year": row.get("folderyear")},
            private_location=True,
        )


# ── Toronto: Business licences and permits (CKAN, full CSV) ──────────────────

TORONTO_PACKAGE = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show"
    "?id=municipal-licensing-and-standards-business-licences-and-permits"
)
TORONTO_PAGE = (
    "https://open.toronto.ca/dataset/municipal-licensing-and-standards-business-licences-and-permits/"
)
TORONTO_CATEGORY = (
    ("eating establishment", "restaurant"), ("take-out", "restaurant"), ("caterer", "restaurant"),
    ("bake", "bakery"), ("retail store (food)", "grocery"), ("grocer", "grocery"),
    ("barber", "beauty"), ("hair", "beauty"), ("body rub", "beauty"), ("holistic", "beauty"),
    ("school", "education"),
)


class TorontoAdapter:
    """The city's live query table stopped updating in 2022; the full CSV is current."""

    id = "gov:toronto_business"
    cities = ("toronto",)

    def __init__(self, geocoder: Geocoder | None = None, client: httpx.Client | None = None):
        self.client = _client(client)
        self.geocoder = geocoder

    def csv_url(self) -> str:
        package = _get(self.client, TORONTO_PACKAGE, "Toronto open data").json()["result"]
        csvs = [
            r for r in package["resources"]
            if (r.get("format") or "").upper() == "CSV" and not r.get("datastore_active")
        ]
        if not csvs:
            raise SourceUnavailable("Toronto open data: no CSV resource")
        return max(csvs, key=lambda r: r.get("last_modified") or "")["url"]

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        if city.slug not in self.cities:
            return
        text = _get(self.client, self.csv_url(), "Toronto licences CSV").text
        hints = hint_pattern()
        for row in csv.DictReader(io.StringIO(text)):
            name = (row.get("Operating Name") or "").strip()
            if not name or row.get("Cancel Date") or not hints.search(name):
                continue
            if not looks_iranian(name):
                continue  # no geocoding request for "SPARSE CLEANING" and the like
            address = ", ".join(
                p for p in (row.get("Licence Address Line 1"), row.get("Licence Address Line 2"),
                            row.get("Licence Address Line 3")) if p
            )
            lat = lng = None
            if self.geocoder and address:
                lat, lng = self.geocoder.locate(address, "CA")
            phone = (row.get("Business Phone") or "").strip()
            yield RawListing(
                source_id=self.id,
                external_id=row.get("Licence No.") or f"{name}|{address}",
                name=name,
                url=TORONTO_PAGE,
                lat=lat,
                lng=lng,
                category=_category(row.get("Category") or "", TORONTO_CATEGORY),
                phones=[phone] if phone else [],
                texts=[TextField("name", name, TORONTO_PAGE)],
                raw={"name": name, "category": row.get("Category")},
                private_location=True,
            )


# ── Nonprofits: IRS Exempt Organizations BMF (US) and CRA charities (Canada) ──

IRS_STATE_FILE = "https://www.irs.gov/pub/irs-soi/eo_{state}.csv"
IRS_PAGE = (
    "https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf"
)
CRA_PACKAGE_SEARCH = "https://open.canada.ca/data/api/3/action/package_search"
CRA_PAGE = "https://open.canada.ca/data/en/organization/cra-arc"


def _nonprofit_category(name: str, ntee: str = "") -> str:
    lowered = name.lower()
    if ntee.startswith("B") or "school" in lowered or "academy" in lowered:
        return "education"
    return "community"


class NonprofitAdapter:
    """Shared flow: download registry → keep Iranian-looking names → geocode → city box."""

    id = ""
    country = ""

    def __init__(
        self,
        regions: dict[str, list[str]] | None = None,
        geocoder: Geocoder | None = None,
        client: httpx.Client | None = None,
    ):
        # city slug -> states / provinces; by default the city's own `regions`.
        self.regions = regions or {}
        self.geocoder = geocoder
        self.client = _client(client)
        self._rows: dict[str, list[dict[str, str]]] = {}

    def rows(self, region: str) -> list[dict[str, str]]:
        raise NotImplementedError

    def to_listing(self, row: dict[str, str], lat: float, lng: float) -> RawListing:
        raise NotImplementedError

    def name_and_address(self, row: dict[str, str]) -> tuple[str, str]:
        raise NotImplementedError

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        regions = self.regions.get(city.slug) or list(city.regions)
        if not regions or city.country != self.country:
            return
        if self.geocoder is None:
            raise SourceUnavailable(f"{self.id}: a geocoder is required")
        hints = hint_pattern()
        for region in regions:
            if region not in self._rows:
                self._rows[region] = self.rows(region)
            for row in self._rows[region]:
                name, address = self.name_and_address(row)
                if not hints.search(name) or not looks_iranian(name):
                    continue
                lat, lng = self.geocoder.locate(address, self.country)
                if _in_box(lat, lng, city):
                    yield self.to_listing(row, lat, lng)


class IrsAdapter(NonprofitAdapter):
    id = "gov:irs_eo_bmf"
    country = "US"

    def rows(self, region: str) -> list[dict[str, str]]:
        text = _get(self.client, IRS_STATE_FILE.format(state=region.lower()), "IRS EO BMF").text
        return list(csv.DictReader(io.StringIO(text)))

    def name_and_address(self, row: dict[str, str]) -> tuple[str, str]:
        # ICO ("in care of") is a person's name and is never used.
        address = f"{row.get('STREET', '')}, {row.get('CITY', '')}, {row.get('STATE', '')} " \
                  f"{(row.get('ZIP') or '')[:5]}"
        return row.get("NAME", "").strip(), address

    def to_listing(self, row: dict[str, str], lat: float, lng: float) -> RawListing:
        name = row["NAME"].strip()
        return RawListing(
            source_id=self.id,
            external_id=row["EIN"],
            name=name,
            url=IRS_PAGE,
            lat=lat,
            lng=lng,
            category=_nonprofit_category(name, row.get("NTEE_CD") or ""),
            texts=[TextField("name", name, IRS_PAGE)],
            raw={"ein": row["EIN"], "name": name, "ntee": row.get("NTEE_CD")},
            private_location=True,
        )


class CraAdapter(NonprofitAdapter):
    id = "gov:cra_charities"
    country = "CA"

    def csv_url(self) -> str:
        """The newest yearly "List of charities" dataset's Identification file."""
        data = _get(self.client, CRA_PACKAGE_SEARCH, "open.canada.ca",
                    q='title:"List of charities"', rows=50).json()["result"]["results"]

        def title(p: dict[str, Any]) -> str:
            t = p.get("title")
            return t.get("en", "") if isinstance(t, dict) else (t or "")

        for package in sorted(data, key=title, reverse=True):
            for resource in package.get("resources", []):
                name = resource.get("name")
                name = name.get("en", "") if isinstance(name, dict) else (name or "")
                if name.strip().lower() == "identification":
                    url = resource["url"]
                    return url if url.startswith("http") else f"https://open.canada.ca{url}"
        raise SourceUnavailable("CRA: no Identification file found")

    def rows(self, region: str) -> list[dict[str, str]]:
        if "_all" not in self._rows:
            text = _get(self.client, self.csv_url(), "CRA charities").content.decode("utf-8-sig")
            self._rows["_all"] = list(csv.DictReader(io.StringIO(text)))
        return [r for r in self._rows["_all"] if r.get("Province") == region]

    def name_and_address(self, row: dict[str, str]) -> tuple[str, str]:
        name = (row.get("Account Name") or row.get("Legal Name") or "").strip()
        parts = (row.get("Address Line 1"), row.get("City"), row.get("Province"),
                 row.get("Postal Code"))
        return name, ", ".join(p for p in parts if p)

    def to_listing(self, row: dict[str, str], lat: float, lng: float) -> RawListing:
        name, _ = self.name_and_address(row)
        return RawListing(
            source_id=self.id,
            external_id=row["BN"],
            name=name,
            url=CRA_PAGE,
            lat=lat,
            lng=lng,
            category=_nonprofit_category(name),
            texts=[TextField("name", name, CRA_PAGE)],
            raw={"bn": row["BN"], "name": name, "category": row.get("Category")},
            private_location=True,
        )


# ── Phase 5: United Kingdom and Australia ─────────────────────────────────────

UK_CHARITIES_ZIP = (
    "https://ccewuksprdoneregsadata1.blob.core.windows.net/data/json/publicextract.charity.zip"
)
UK_CHARITY_PAGE = (
    "https://register-of-charities.charitycommission.gov.uk/charity-search/-/charity-details/{number}"
)
ACNC_PACKAGE = "https://data.gov.au/data/api/3/action/package_show"
ACNC_PAGE = "https://www.acnc.gov.au/charity/charities?search={abn}"


def iter_json_lines(lines: Iterable[bytes]) -> Iterator[dict[str, Any]]:
    """The Charity Commission extract is one JSON array with one record per line
    ("[{…}", ",{…}", "]"), 500 MB unpacked: read it a line at a time."""
    for raw in lines:
        line = raw.decode("utf-8-sig").strip().lstrip("[,").rstrip("]").strip()
        if line.startswith("{"):
            yield json.loads(line)


class UkCharityAdapter(NonprofitAdapter):
    """Charity Commission for England and Wales, full register extract (Open Government
    Licence, no account). Only registered main charities; the contact address may be a
    trustee's home, so it is private like every registry address."""

    id = "gov:uk_charities"
    country = "GB"

    def rows(self, region: str) -> list[dict[str, str]]:
        if "_all" not in self._rows:
            content = _get(self.client, UK_CHARITIES_ZIP, "Charity Commission").content
            hints = hint_pattern()
            with zipfile.ZipFile(io.BytesIO(content)) as archive, \
                    archive.open(archive.namelist()[0]) as extract:
                self._rows["_all"] = [
                    r for r in iter_json_lines(extract)
                    if r.get("charity_registration_status") == "Registered"
                    and r.get("linked_charity_number") == 0
                    and hints.search(r.get("charity_name") or "")
                ]
        return self._rows["_all"]

    def name_and_address(self, row: dict[str, Any]) -> tuple[str, str]:
        parts = [row.get(f"charity_contact_address{i}") for i in range(1, 6)]
        parts.append(row.get("charity_contact_postcode"))
        return (row.get("charity_name") or "").strip(), ", ".join(p.strip() for p in parts if p)

    def to_listing(self, row: dict[str, Any], lat: float, lng: float) -> RawListing:
        name = row["charity_name"].strip()
        number = row["registered_charity_number"]
        url = UK_CHARITY_PAGE.format(number=number)
        web = (row.get("charity_contact_web") or "").strip()
        return RawListing(
            source_id=self.id,
            external_id=str(number),
            name=name,
            url=url,
            lat=lat,
            lng=lng,
            category=_nonprofit_category(name),
            urls=[web if web.startswith("http") else f"https://{web}"] if web else [],
            texts=[TextField("name", name, url)],
            raw={"number": number, "name": name},
            private_location=True,
        )


class AcncAdapter(NonprofitAdapter):
    """Australian Charities and Not-for-profits Commission register (CC BY 3.0 AU)."""

    id = "gov:acnc_charities"
    country = "AU"

    def csv_url(self) -> str:
        package = _get(self.client, ACNC_PACKAGE, "data.gov.au", id="acnc-register").json()
        for resource in package["result"]["resources"]:
            if (resource.get("format") or "").upper() == "CSV":
                return resource["url"]
        raise SourceUnavailable("ACNC: no CSV resource")

    def rows(self, region: str) -> list[dict[str, str]]:
        if "_all" not in self._rows:
            text = _get(self.client, self.csv_url(), "ACNC register").content.decode("utf-8-sig")
            self._rows["_all"] = list(csv.DictReader(io.StringIO(text)))
        return [r for r in self._rows["_all"] if r.get("State") == region]

    def name_and_address(self, row: dict[str, str]) -> tuple[str, str]:
        # Other names ("Persian Language School WA") often say more than the legal name.
        name = " | ".join(n for n in (row.get("Charity_Legal_Name"),
                                      row.get("Other_Organisation_Names")) if n)
        parts = (row.get("Address_Line_1"), row.get("Town_City"), row.get("State"),
                 row.get("Postcode"))
        return name.strip(), ", ".join(p for p in parts if p)

    def to_listing(self, row: dict[str, str], lat: float, lng: float) -> RawListing:
        name = row["Charity_Legal_Name"].strip()
        url = ACNC_PAGE.format(abn=row["ABN"])
        texts = [TextField("name", name, url)]
        if row.get("Other_Organisation_Names"):
            texts.append(TextField("name", row["Other_Organisation_Names"], url))
        web = (row.get("Charity_Website") or "").strip()
        return RawListing(
            source_id=self.id,
            external_id=row["ABN"],
            name=name,
            url=url,
            lat=lat,
            lng=lng,
            category=_nonprofit_category(name),
            urls=[web if web.startswith("http") else f"https://{web}"] if web else [],
            texts=texts,
            raw={"abn": row["ABN"], "name": name},
            private_location=True,
        )


SIRENE_SEARCH = "https://recherche-entreprises.api.gouv.fr/search"
SIRENE_PAGE = "https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}"
SIRENE_EXTRA_TERMS = ("persan", "iranien", "iranienne", "perse")
# NAF rev. 2 codes (INSEE) -> our categories; the longest matching prefix wins.
NAF_CATEGORY = {
    "56.10": "restaurant", "56.30": "restaurant", "10.71": "bakery", "47.24": "bakery",
    "47.11": "grocery", "47.2": "grocery", "86.21": "doctor", "86.22": "doctor",
    "86.23": "doctor/dentist", "69.10": "lawyer", "68.31": "real_estate", "96.02": "beauty",
    "69.20": "accounting", "85": "education", "94": "community", "74.30": "translator",
}


def naf_category(code: str) -> str:
    matches = [prefix for prefix in NAF_CATEGORY if code.startswith(prefix)]
    return NAF_CATEGORY[max(matches, key=len)] if matches else "other"


class SireneAdapter:
    """France: the government company search API over the SIRENE register
    (recherche-entreprises.api.gouv.fr, Licence Ouverte, no key, 7 requests/s).

    Searched by name terms per département; every open establishment in the city box
    becomes a listing. Sole traders (legal forms 1xxx) are skipped: their "company
    name" is the person's name. Records not fully public (statut_diffusion != "O")
    are skipped too."""

    id = "gov:fr_sirene"

    def __init__(self, departments: dict[str, list[str]] | None = None,
                 client: httpx.Client | None = None, delay: float = 0.25, max_pages: int = 20):
        # city slug -> départements ("75", "92", ...); by default the city's `regions`.
        self.departments = departments or {}
        self.client = _client(client)
        self.delay = delay
        self.max_pages = max_pages

    def search(self, term: str, department: str) -> Iterator[dict[str, Any]]:
        for page in range(1, self.max_pages + 1):
            time.sleep(self.delay)
            data = _get(self.client, SIRENE_SEARCH, "recherche-entreprises", q=term,
                        departement=department, etat_administratif="A", per_page=25,
                        page=page).json()
            yield from data.get("results", [])
            if page >= (data.get("total_pages") or 1):
                break

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        departments = self.departments.get(city.slug) or list(city.regions)
        if not departments or city.country != "FR":
            return
        terms = tuple(dict.fromkeys((*latin_hint_terms(), *SIRENE_EXTRA_TERMS)))
        seen: set[str] = set()
        for department in departments:
            for term in terms:
                for company in self.search(term, department):
                    yield from self._listings(company, city, seen)

    def _listings(self, company: dict[str, Any], city: CityInfo,
                  seen: set[str]) -> Iterator[RawListing]:
        if str(company.get("nature_juridique") or "").startswith("1"):
            return  # entrepreneur individuel: the name is a person's
        if company.get("statut_diffusion") not in (None, "O"):
            return
        name = (company.get("nom_complet") or "").strip()
        if not name or not looks_iranian(name):
            return
        url = SIRENE_PAGE.format(siren=company["siren"])
        for place in company.get("matching_etablissements") or [company.get("siege") or {}]:
            siret = place.get("siret")
            if not siret or siret in seen or place.get("etat_administratif") != "A":
                continue
            lat, lng = _float(place.get("latitude")), _float(place.get("longitude"))
            if not _in_box(lat, lng, city):
                continue
            seen.add(siret)
            yield RawListing(
                source_id=self.id,
                external_id=siret,
                name=name,
                url=url,
                lat=lat,
                lng=lng,
                category=naf_category(place.get("activite_principale")
                                      or company.get("activite_principale") or ""),
                texts=[TextField("name", name, url)],
                raw={"siren": company["siren"], "siret": siret, "name": name,
                     "naf": place.get("activite_principale")},
                private_location=True,
            )


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
