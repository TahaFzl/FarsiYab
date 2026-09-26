"""Telegram channels and groups a business links to (docs/sources/telegram.md).

Only links that other sources already found are checked; nothing is discovered
here. For each one, the public preview page t.me/<name> is read once a month, one
request a second: its title and description, never messages or member lists.
t.me has no robots.txt restrictions, and the preview is the page Telegram makes for
sharing a channel on the web.
"""

import logging
import time
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

from farsiyab.config import get_settings
from farsiyab.detection import detector, script
from farsiyab.detection.detector import TextField
from farsiyab.detection.signals import Signal, make

log = logging.getLogger(__name__)

PREVIEW = "https://t.me/{name}"
MIN_PERSIAN_LETTERS = 12  # a couple of Persian words, not a stray letter


@dataclass
class TelegramResult:
    name: str
    url: str
    ok: bool  # the page was read (the channel may still not exist)
    exists: bool = False
    title: str | None = None
    description: str | None = None
    signals: list[Signal] = field(default_factory=list)
    retryable: bool = False


def analyse_preview(html: str, url: str) -> tuple[bool, str | None, str | None, list[Signal]]:
    """(exists, title, description, signals) from a t.me preview page."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find(class_="tgme_page_title")
    if title_tag is None:
        # Unknown names get a generic "Telegram: Contact @name" page without a title block.
        return False, None, None, []
    title = title_tag.get_text(" ", strip=True)
    description_tag = soup.find(class_="tgme_page_description")
    description = description_tag.get_text(" ", strip=True) if description_tag else ""
    text = " ".join(p for p in (title, description) if p)

    signals: list[Signal] = []
    letters, _ = script.persian_letter_ratio(text)
    if letters >= MIN_PERSIAN_LETTERS and script.classify(text) in (
        script.Script.PERSIAN_DEFINITIVE, script.Script.PERSIAN_LIKELY,
    ):
        signals.append(make("telegram_persian_content", script.arabic_script_part(text), url))
    # Keywords ("Persian bakery", "ایرانی") in the title and description.
    signals.extend(detector.detect([TextField("page_head", text, url)]))
    return True, title, description or None, signals


class TelegramChecker:
    def __init__(self, client: httpx.Client | None = None, interval: float = 1.0):
        self.client = client or httpx.Client(
            headers={"User-Agent": get_settings().user_agent}, timeout=20,
            follow_redirects=True,
        )
        self.interval = interval
        self._last = 0.0

    def check(self, name: str) -> TelegramResult:
        url = PREVIEW.format(name=name)
        wait = self._last + self.interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        try:
            response = self.client.get(url)
        except httpx.HTTPError as exc:
            log.info("telegram %s: %s", name, type(exc).__name__)
            return TelegramResult(name, url, ok=False, retryable=True)
        if response.status_code == 429 or response.status_code >= 500:
            return TelegramResult(name, url, ok=False, retryable=True)
        if response.status_code != 200:
            return TelegramResult(name, url, ok=False)
        exists, title, description, signals = analyse_preview(response.text, url)
        return TelegramResult(name, url, ok=True, exists=exists, title=title,
                              description=description, signals=signals)
