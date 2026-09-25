"""Iranian community directories whose terms and robots.txt allow reading
(docs/sources/community-directories.md, review of 2026-09-25).

Only facts are taken: the business name, its own links (website, Instagram…),
phone, location and the directory page URL, which is shown to users as the
source. Descriptions are not stored (copyright); they are only read by the
detector. A directory is crawled from its sitemap at most once a week, one
request per second, with our identifying User-Agent.
"""

import json
import logging
import re
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from farsiyab.adapters.base import RawListing, SourceUnavailable
from farsiyab.config import get_settings
from farsiyab.detection.detector import TextField
from farsiyab.detection.signals import make
from farsiyab.links import classify_url
from farsiyab.reference import CityInfo

log = logging.getLogger(__name__)

CACHE_DAYS = 7
LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
COORDS_IN_MAPS_LINK = re.compile(r"(?:destination|query|q)=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)")


@dataclass
class DirectoryEntry:
    url: str
    name: str
    description: str = ""
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None
    links: list[str] = field(default_factory=list)
    kind: str = ""  # the directory's own category label


class Directory:
    """One directory: where its listing pages are and how to read one."""

    id = ""
    home = ""
    sitemaps: tuple[str, ...] = ()
    listing_path = ""  # only sitemap URLs containing this are business pages
    own_domains: tuple[str, ...] = ()

    def parse(self, url: str, html: str) -> DirectoryEntry | None:
        raise NotImplementedError

    def external_links(self, soup: BeautifulSoup) -> list[str]:
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            host = (urlsplit(href).hostname or "").lower()
            if not href.startswith("http") or any(host.endswith(d) for d in self.own_domains):
                continue
            if "google." in host or "maps.apple" in host:
                continue
            link = classify_url(href)
            # The directory's own social accounts sit in every page's header/footer.
            if link and link.url not in links and link.value not in self.own_socials:
                links.append(link.url)
        return links

    own_socials: tuple[str, ...] = ()


class IranianBusinessCenter(Directory):
    id = "directory:iranianbusinesscenter"
    home = "https://iranianbusinesscenter.com/"
    sitemaps = (
        "https://iranianbusinesscenter.com/job_listing-sitemap1.xml",
        "https://iranianbusinesscenter.com/job_listing-sitemap2.xml",
    )
    listing_path = "/job/"
    own_domains = ("iranianbusinesscenter.com",)
    own_socials = ("irbusinesscenter", "iranbusinesscenter", "iranianbusinesscenter_com")

    def parse(self, url: str, html: str) -> DirectoryEntry | None:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            for node in data.get("@graph", [data]) if isinstance(data, dict) else []:
                if node.get("@type") != "LocalBusiness":
                    continue
                geo = node.get("geo") or {}
                links = [u for u in node.get("sameAs", []) if isinstance(u, str)]
                links += [u for u in self.external_links(soup) if u not in links]
                return DirectoryEntry(
                    url=url,
                    name=_text(node.get("name", "")).strip(),
                    description=_text(node.get("description", "")),
                    lat=_float(geo.get("latitude")),
                    lng=_float(geo.get("longitude")),
                    phone=node.get("telephone"),
                    links=links,
                    kind=node.get("additionalType") or "",
                )
        return None


class Bazaarche(Directory):
    id = "directory:bazaarche"
    home = "https://bazaarche.ca/"
    sitemaps = ("https://bazaarche.ca/listing-sitemap.xml",)
    listing_path = "/listing/"
    own_domains = ("bazaarche.ca",)
    own_socials = ("bazaarche.ca", "bazaarche")

    def parse(self, url: str, html: str) -> DirectoryEntry | None:
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.find("h1")
        name = heading.get_text(" ", strip=True) if heading else ""
        if not name:
            return None
        lat = lng = None
        for a in soup.find_all("a", href=True):
            match = COORDS_IN_MAPS_LINK.search(unquote(a["href"]))
            if match and "google." in a["href"]:
                lat, lng = float(match.group(1)), float(match.group(2))
                break
        meta = soup.find("meta", attrs={"property": "og:description"})
        phone = next(
            (a["href"][4:] for a in soup.find_all("a", href=True) if a["href"].startswith("tel:")),
            None,
        )
        return DirectoryEntry(
            url=url,
            name=name,
            description=meta.get("content", "") if meta else "",
            lat=lat,
            lng=lng,
            phone=phone,
            links=self.external_links(soup),
        )


def _text(html: str) -> str:
    """JSON-LD strings carry HTML entities (&#8211;, &hellip;)."""
    return BeautifulSoup(html, "html.parser").get_text()


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


DIRECTORY_CATEGORY = (
    ("real estate", "real_estate"), ("realtor", "real_estate"), ("restaurant", "restaurant"),
    ("food", "restaurant"), ("cafe", "restaurant"), ("bakery", "bakery"), ("grocery", "grocery"),
    ("market", "grocery"), ("dentist", "doctor/dentist"), ("dental", "doctor/dentist"),
    ("doctor", "doctor"), ("medical", "doctor"), ("clinic", "doctor"), ("lawyer", "lawyer"),
    ("immigration", "lawyer"), ("legal", "lawyer"), ("beauty", "beauty"), ("salon", "beauty"),
    ("hair", "beauty"), ("account", "accounting"), ("tax", "accounting"),
    ("translat", "translator"), ("school", "education"), ("tutor", "education"),
    ("class", "education"),
)


def category_for(entry: DirectoryEntry) -> str:
    text = f"{entry.kind} {entry.name} {entry.url}".lower()
    return next((slug for needle, slug in DIRECTORY_CATEGORY if needle in text), "other")


def shared_links(entries: list[DirectoryEntry], limit: int = 2) -> set[str]:
    """Links on more than `limit` entries: a site template link or a big company's host
    (mortgage.rbc.com) that would otherwise merge unrelated businesses."""
    counts: dict[str, int] = {}
    for entry in entries:
        for value in {link.value for u in entry.links if (link := classify_url(u))}:
            counts[value] = counts.get(value, 0) + 1
    return {
        u for entry in entries for u in entry.links
        if (link := classify_url(u)) and counts[link.value] > limit
    }


class DirectoryAdapter:
    """Crawls one directory (cached for a week) and yields its entries in the city box."""

    def __init__(
        self,
        directory: Directory,
        client: httpx.Client | None = None,
        cache_dir: Path | None = None,
        delay: float = 1.0,
    ):
        settings = get_settings()
        self.directory = directory
        self.id = directory.id
        self.client = client or httpx.Client(
            headers={"User-Agent": settings.user_agent}, timeout=30, follow_redirects=True,
            http2=True,
        )
        self.cache_dir = cache_dir or settings.cache_dir
        self.delay = delay

    @property
    def cache_file(self) -> Path:
        return self.cache_dir / f"{self.id.replace(':', '_')}.json"

    def _get(self, url: str) -> httpx.Response | None:
        time.sleep(self.delay)
        try:
            response = self.client.get(url)
        except httpx.HTTPError as exc:
            log.warning("%s: %s for %s", self.id, type(exc).__name__, url)
            return None
        return response if response.status_code == 200 else None

    def crawl(self) -> list[DirectoryEntry]:
        robots = RobotFileParser()
        robots_response = self._get(self.directory.home + "robots.txt")
        robots.parse(robots_response.text.splitlines() if robots_response else [])
        agent = self.client.headers.get("user-agent", "*")
        urls: list[str] = []
        for sitemap in self.directory.sitemaps:
            response = self._get(sitemap)
            if response is None:
                raise SourceUnavailable(f"{self.id}: sitemap {sitemap} unavailable")
            urls += [u for u in LOC.findall(response.text) if self.directory.listing_path in u]
        entries = []
        for url in dict.fromkeys(urls):
            if not robots.can_fetch(agent, url):
                continue
            response = self._get(url)
            entry = self.directory.parse(url, response.text) if response else None
            if entry and entry.name:
                entries.append(entry)
        log.info("%s: %d entries from %d pages", self.id, len(entries), len(urls))
        return entries

    def entries(self) -> list[DirectoryEntry]:
        if self.cache_file.exists():
            cached = json.loads(self.cache_file.read_text())
            fetched = datetime.fromisoformat(cached["fetched_at"])
            if datetime.now(UTC) - fetched < timedelta(days=CACHE_DAYS):
                return [DirectoryEntry(**e) for e in cached["entries"]]
        entries = self.crawl()
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(
            {"fetched_at": datetime.now(UTC).isoformat(), "entries": [asdict(e) for e in entries]},
            ensure_ascii=False,
        ))
        return entries

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        west, south, east, north = city.bbox
        entries = self.entries()
        shared = shared_links(entries)
        for entry in entries:
            if entry.lat is None or entry.lng is None:
                continue
            if not (south <= entry.lat <= north and west <= entry.lng <= east):
                continue
            yield RawListing(
                source_id=self.id,
                external_id=entry.url,
                name=entry.name,
                url=entry.url,
                lat=entry.lat,
                lng=entry.lng,
                category=category_for(entry),
                phones=[entry.phone] if entry.phone else [],
                urls=[u for u in entry.links if u not in shared],
                texts=[TextField("name", entry.name, entry.url),
                       TextField("text", entry.description, entry.url)],
                # The business chose to list itself in an Iranian directory.
                signals=[make("listed_in_iranian_directory", self.directory.home, entry.url)],
                raw={"name": entry.name, "kind": entry.kind},
            )


DIRECTORIES: dict[str, type[Directory]] = {
    IranianBusinessCenter.id: IranianBusinessCenter,
    Bazaarche.id: Bazaarche,
}
