"""Check a business's own website for evidence (docs/sources/business-websites.md).

Rules: honour robots.txt, identify ourselves, at most one request per second
per host, only the first page (HTML only, size-capped), never follow links to
social networks, never run JavaScript.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from farsiyab.config import Settings, get_settings
from farsiyab.detection import detector, script
from farsiyab.detection.detector import TextField
from farsiyab.detection.signals import Signal, make
from farsiyab.links import Link, social_link

log = logging.getLogger(__name__)

MAX_PAGE_TEXT = 20_000
MIN_PERSIAN_LETTERS = 100
MIN_PERSIAN_RATIO = 0.3


@dataclass(frozen=True)
class Page:
    status_code: int
    url: str
    content_type: str
    text: str


@dataclass
class WebsiteResult:
    url: str
    ok: bool
    final_url: str | None = None
    # Why nothing was read: robots, robots_unreachable, http_404, not_html, error: ...
    reason: str | None = None

    @property
    def retryable(self) -> bool:
        """Network trouble rather than a definitive answer from the site."""
        return not self.ok and bool(
            self.reason
            and (self.reason.startswith("error") or self.reason == "robots_unreachable"
                 or self.reason.startswith("http_5"))
        )
    lang: str | None = None
    title: str | None = None
    signals: list[Signal] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)


def analyse_html(html: str, url: str) -> tuple[str | None, str | None, list[Signal], list[Link]]:
    """(lang, title, signals, social links) for one HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    lang = (soup.html.get("lang") if soup.html else None) or None
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    description = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        description = meta["content"]

    links: dict[tuple[str, str], Link] = {}
    for a in soup.find_all("a", href=True):
        link = social_link(urljoin(url, a["href"]))
        if link:
            links.setdefault((link.kind, link.value), link)

    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    body_text = soup.get_text(" ", strip=True)[:MAX_PAGE_TEXT]
    page_text = " ".join(p for p in (title, description, body_text) if p)

    signals: list[Signal] = []
    persian_letters, ratio = script.persian_letter_ratio(page_text)
    is_fa_lang = bool(lang and lang.lower().startswith("fa"))
    persian_script = script.classify(page_text) in (
        script.Script.PERSIAN_DEFINITIVE,
        script.Script.PERSIAN_LIKELY,
    )
    if persian_script and (
        is_fa_lang or (persian_letters >= MIN_PERSIAN_LETTERS and ratio >= MIN_PERSIAN_RATIO)
    ):
        sample = script.arabic_script_part(page_text)
        snippet = f'lang="{lang}"' if is_fa_lang and not sample else sample
        signals.append(make("website_persian_content", snippet, url))

    # Keyword signals from the page; "page" fields skip the script signal covered above.
    signals.extend(detector.detect([TextField("page", page_text, url)]))
    return lang, title, signals, list(links.values())


class WebsiteChecker:
    def __init__(self, client: httpx.AsyncClient | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = client or httpx.AsyncClient(
            headers={"User-Agent": self.settings.user_agent, "Accept": "text/html"},
            timeout=self.settings.website_timeout_seconds,
            follow_redirects=True,
        )
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last_request: dict[str, float] = {}
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._semaphore = asyncio.Semaphore(self.settings.website_concurrency)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def _polite_get(self, url: str) -> "Page":
        host = urlsplit(url).netloc
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = self.settings.website_min_interval_seconds - (
                time.monotonic() - self._last_request.get(host, 0.0)
            )
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                async with self.client.stream("GET", url) as response:
                    body = b""
                    async for chunk in response.aiter_bytes():
                        body += chunk
                        if len(body) > self.settings.website_max_bytes:
                            break
                    return Page(
                        status_code=response.status_code,
                        url=str(response.url),
                        content_type=response.headers.get("content-type", ""),
                        text=body.decode(response.encoding or "utf-8", errors="replace"),
                    )
            finally:
                self._last_request[host] = time.monotonic()

    async def _robots_for(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = RobotFileParser()
            try:
                response = await self._polite_get(f"{origin}/robots.txt")
                if response.status_code >= 500:
                    self._robots[origin] = None  # server trouble: assume disallowed
                    return None
                parser.parse(response.text.splitlines() if response.status_code == 200 else [])
            except httpx.HTTPError:
                self._robots[origin] = None
                return None
            self._robots[origin] = parser
        return self._robots[origin]

    async def check(self, url: str) -> WebsiteResult:
        async with self._semaphore:
            robots = await self._robots_for(url)
            if robots is None:
                return WebsiteResult(url, ok=False, reason="robots_unreachable")
            if not robots.can_fetch(self.settings.user_agent, url):
                return WebsiteResult(url, ok=False, reason="robots")
            try:
                response = await self._polite_get(url)
            except httpx.HTTPError as exc:
                return WebsiteResult(url, ok=False, reason=f"error: {type(exc).__name__}")
            final_url = response.url
            if response.status_code != 200:
                return WebsiteResult(url, ok=False, final_url=final_url,
                                     reason=f"http_{response.status_code}")
            if response.content_type and "html" not in response.content_type:
                return WebsiteResult(url, ok=False, final_url=final_url, reason="not_html")
            lang, title, signals, links = analyse_html(response.text, final_url)
            return WebsiteResult(url, ok=True, final_url=final_url, lang=lang, title=title,
                                 signals=signals, links=links)

    async def check_many(self, urls: list[str]) -> list[WebsiteResult]:
        return await asyncio.gather(*(self.check(u) for u in urls))
