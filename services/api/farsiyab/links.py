"""Normalize websites, social profiles and phone numbers.

Normalized values are what Entity Resolution compares, so two sources that
link to "https://www.Instagram.com/ShirazKitchen/?hl=en" and
"instagram.com/shirazkitchen" end up on the same business.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import parse_qs, urlsplit

import phonenumbers

from farsiyab.config import get_settings

INSTAGRAM_RESERVED = {
    "p", "reel", "reels", "explore", "stories", "accounts", "tv", "about", "developer",
    "direct", "legal", "privacy", "web", "share",
}
FACEBOOK_RESERVED = {
    "sharer", "sharer.php", "share", "share.php", "groups", "events", "watch", "login",
    "login.php", "dialog", "plugins", "hashtag", "help", "policies", "privacy", "tr",
    "photo", "photo.php", "story.php", "permalink.php", "marketplace", "gaming",
}
TELEGRAM_RESERVED = {"s", "joinchat", "share", "addstickers", "proxy", "iv", "c"}

INSTAGRAM_USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")
FACEBOOK_NAME = re.compile(r"^[A-Za-z0-9.\-]{2,100}$")
TELEGRAM_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")


@dataclass(frozen=True)
class Link:
    kind: str  # website | facebook | instagram | telegram | phone
    value: str  # normalized, used for matching
    url: str  # canonical, shown to users


def _split(url: str):
    url = url.strip()
    if not re.match(r"^[a-z][a-z0-9+.\-]*://", url, re.IGNORECASE):
        url = "https://" + url
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m.") or host.startswith("mobile."):
        host = host.split(".", 1)[1]
    segments = [s for s in parts.path.split("/") if s]
    return parts, host, segments


@lru_cache
def non_business_domains() -> frozenset[str]:
    path = get_settings().data_dir / "non_business_domains.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().lower() for line in lines if line.strip() and line[0] != "#")


def _domain_listed(host: str, domains: frozenset[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def social_link(url: str) -> Link | None:
    try:
        parts, host, segments = _split(url)
    except ValueError:
        return None

    if host in ("instagram.com", "instagr.am"):
        if segments and segments[0].lower() not in INSTAGRAM_RESERVED:
            username = segments[0].lstrip("@")
            if INSTAGRAM_USERNAME.match(username):
                username = username.lower()
                return Link("instagram", username, f"https://www.instagram.com/{username}/")
        return None

    if host in ("facebook.com", "fb.com", "fb.me", "business.facebook.com"):
        if not segments:
            return None
        first = segments[0].lower()
        if first == "profile.php":
            page_id = parse_qs(parts.query).get("id", [""])[0]
            if page_id.isdigit():
                return Link("facebook", page_id, f"https://www.facebook.com/{page_id}")
            return None
        if first == "pages" and segments[-1].isdigit():
            return Link("facebook", segments[-1], f"https://www.facebook.com/{segments[-1]}")
        if first in FACEBOOK_RESERVED or not FACEBOOK_NAME.match(segments[0]):
            return None
        return Link("facebook", first, f"https://www.facebook.com/{segments[0]}")

    if host in ("t.me", "telegram.me", "telegram.dog"):
        if segments and segments[0].lower() not in TELEGRAM_RESERVED:
            name = segments[0]
            if TELEGRAM_NAME.match(name):
                return Link("telegram", name.lower(), f"https://t.me/{name}")
        return None

    return None


def website_link(url: str) -> Link | None:
    """The business's own website; None for social networks, directories, etc.

    The match value is the host ("ghazale.ca"), except for deep paths such as
    "/gsbiz/1a98d1c3-...": those are pages on a shared site, so the path is kept
    to stop unrelated businesses on the same site from being merged.
    """
    try:
        parts, host, segments = _split(url)
    except ValueError:
        return None
    if not host or "." not in host or parts.scheme not in ("http", "https"):
        return None
    if _domain_listed(host, non_business_domains()):
        return None
    canonical = f"{parts.scheme}://{parts.hostname}{parts.path or '/'}"
    shared_site_page = len(segments) >= 2 or (bool(segments) and len(segments[0]) > 24)
    value = f"{host}/{'/'.join(segments).lower()}" if shared_site_page else host
    return Link("website", value, canonical)


def phone_link(number: str, region: str) -> Link | None:
    try:
        parsed = phonenumbers.parse(number, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(parsed):
        return None
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return Link("phone", e164, f"tel:{e164}")


def classify_url(url: str) -> Link | None:
    """Social profile if it is one, otherwise the business website (or None)."""
    return social_link(url) or website_link(url)
