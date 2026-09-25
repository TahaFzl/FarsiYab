"""Entity resolution: decide whether a listing is a business we already know.

Rules (docs/02-architecture.md, "Entity Resolution"), in order:
1. the same source record was seen before
2. a shared normalized link (website domain, social profile, phone), within 1 km
3. within 150 m and name similarity >= 0.8
"""

import re
import unicodedata
import uuid

from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from farsiyab.links import Link
from farsiyab.models import Business, BusinessLink, SourceRecord

MATCH_DISTANCE_METERS = 150
SAME_LINK_MAX_DISTANCE_METERS = 1000
MATCH_NAME_SIMILARITY = 80

GENERIC_WORDS = {
    "the", "restaurant", "restaurants", "cafe", "café", "kitchen", "grill", "bar", "market",
    "supermarket", "bakery", "inc", "ltd", "llc", "co", "corp", "corporation", "company",
    "gmbh", "ug", "e.k", "and", "&", "of", "dds", "md", "pc", "رستوران", "کافه", "فروشگاه",
}


def normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKC", name).lower()
    name = name.replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    name = re.sub(r"[^\w\s&]", " ", name)
    words = [w for w in name.split() if w not in GENERIC_WORDS]
    return " ".join(words)


def name_similarity(a: str, b: str) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    return fuzz.token_set_ratio(na, nb)


def find_by_record(session: Session, source_id: str, external_id: str) -> uuid.UUID | None:
    return session.scalar(
        select(SourceRecord.business_id).where(
            SourceRecord.source_id == source_id, SourceRecord.external_id == external_id
        )
    )


def find_by_links(
    session: Session,
    city_id: int,
    links: list[Link],
    lat: float | None = None,
    lng: float | None = None,
) -> uuid.UUID | None:
    """A business sharing a link, unless both have locations more than 1 km apart:
    branches of a chain share one website and one Facebook page."""
    if not links:
        return None
    pairs = [(link.kind, link.value) for link in links]
    stmt = (
        select(BusinessLink.business_id)
        .join(Business, Business.id == BusinessLink.business_id)
        .where(
            Business.city_id == city_id,
            func.row(BusinessLink.kind, BusinessLink.value).in_(pairs),
        )
    )
    if lat is not None and lng is not None:
        here = func.Geography(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326))
        stmt = stmt.where(
            Business.location.is_(None)
            | func.ST_DWithin(Business.location, here, SAME_LINK_MAX_DISTANCE_METERS)
        )
    return session.scalar(stmt.limit(1))


def find_nearby(
    session: Session, city_id: int, name: str, lat: float | None, lng: float | None
) -> uuid.UUID | None:
    if lat is None or lng is None:
        return None
    point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
    rows = session.execute(
        select(Business.id, Business.name_latin, Business.name_fa).where(
            Business.city_id == city_id,
            func.ST_DWithin(Business.location, func.Geography(point), MATCH_DISTANCE_METERS),
        )
    ).all()
    best_id, best_score = None, 0.0
    for business_id, name_latin, name_fa in rows:
        similarity = max(name_similarity(name, n) for n in (name_latin or "", name_fa or ""))
        if similarity >= MATCH_NAME_SIMILARITY and similarity > best_score:
            best_id, best_score = business_id, similarity
    return best_id


def resolve(
    session: Session,
    city_id: int,
    source_id: str,
    external_id: str,
    name: str,
    lat: float | None,
    lng: float | None,
    links: list[Link],
) -> uuid.UUID | None:
    return (
        find_by_record(session, source_id, external_id)
        or find_by_links(session, city_id, links, lat, lng)
        or find_nearby(session, city_id, name, lat, lng)
    )
