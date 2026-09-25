"""Index one city: fetch every source, detect, merge, store, check websites, score."""

import asyncio
import logging
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from farsiyab.adapters.base import RawListing, SourceAdapter, SourceUnavailable
from farsiyab.adapters.website import WebsiteChecker, WebsiteResult
from farsiyab.config import Settings, get_settings
from farsiyab.detection import script
from farsiyab.detection.detector import confidence_label, detect, has_positive, score
from farsiyab.detection.signals import Signal
from farsiyab.links import Link, classify_url, phone_link, website_link
from farsiyab.models import (
    Business,
    BusinessCategory,
    BusinessLink,
    City,
    DoNotIndex,
    Evidence,
    IndexStatus,
    Source,
    SourceRecord,
)
from farsiyab.quota import QuotaExhausted, consume
from farsiyab.reference import CityInfo
from farsiyab.resolution import resolve

log = logging.getLogger(__name__)

COMMIT_EVERY = 200


def city_info(city: City) -> CityInfo:
    return CityInfo(
        slug=city.slug,
        country=city.country_code,
        name_fa=city.name_fa,
        name_en=city.name_en,
        center=(0.0, 0.0),
        bbox=(city.west, city.south, city.east, city.north),
    )


def _point(lat: float | None, lng: float | None) -> str | None:
    if lat is None or lng is None:
        return None
    return f"SRID=4326;POINT({lng} {lat})"


def listing_links(listing: RawListing, region: str) -> list[Link]:
    found = [classify_url(u) for u in listing.urls]
    found += [phone_link(p, region) for p in listing.phones]
    unique: dict[tuple[str, str], Link] = {}
    for link in found:
        if link:
            unique.setdefault((link.kind, link.value), link)
    return list(unique.values())


def is_blocked(session: Session, links: list[Link]) -> bool:
    if not links:
        return False
    pairs = [(link.kind, link.value) for link in links]
    return bool(
        session.scalar(
            select(DoNotIndex.id).where(func.row(DoNotIndex.kind, DoNotIndex.value).in_(pairs))
        )
    )


def _split_name(name: str) -> tuple[str | None, str | None]:
    """(persian, latin) parts of a name such as 'Diplomat Exchange | صرافی دیپلمات'."""
    persian = None
    if script.classify(name) in (script.Script.PERSIAN_DEFINITIVE, script.Script.PERSIAN_LIKELY):
        persian = script.arabic_script_part(name) or None
    latin = script.latin_part(name) if script.ARABIC_SCRIPT.search(name) else name.strip()
    return persian, latin or None


def _upsert_record(
    session: Session,
    business_id: uuid.UUID,
    source_id: str,
    external_id: str,
    url: str | None,
    raw: dict[str, Any] | None,
) -> SourceRecord:
    record = session.scalar(
        select(SourceRecord).where(
            SourceRecord.source_id == source_id, SourceRecord.external_id == external_id
        )
    )
    if record is None:
        record = SourceRecord(source_id=source_id, external_id=external_id)
        session.add(record)
    record.business_id = business_id
    record.url = url
    record.raw = raw
    record.fetched_at = datetime.now(UTC)
    session.flush()
    return record


def _replace_evidence(
    session: Session, record: SourceRecord, signals: Iterable[Signal]
) -> None:
    session.execute(delete(Evidence).where(Evidence.source_record_id == record.id))
    for s in signals:
        session.add(
            Evidence(
                business_id=record.business_id,
                source_record_id=record.id,
                signal=s.signal,
                weight=s.weight,
                snippet=s.snippet,
                url=s.url or record.url,
            )
        )


def _add_links(session: Session, business_id: uuid.UUID, links: Iterable[Link]) -> None:
    for link in links:
        session.execute(
            insert(BusinessLink)
            .values(business_id=business_id, kind=link.kind, value=link.value, url=link.url)
            .on_conflict_do_nothing()
        )


def _add_category(session: Session, business_id: uuid.UUID, slug: str) -> None:
    existing = set(
        session.scalars(
            select(BusinessCategory.category_slug).where(
                BusinessCategory.business_id == business_id
            )
        )
    )
    if slug in existing or (slug == "other" and existing):
        return
    if slug != "other" and "other" in existing:
        session.execute(
            delete(BusinessCategory).where(
                BusinessCategory.business_id == business_id,
                BusinessCategory.category_slug == "other",
            )
        )
    session.add(BusinessCategory(business_id=business_id, category_slug=slug))


def known_external_ids(session: Session, city_id: int, source_id: str) -> set[str]:
    return set(
        session.scalars(
            select(SourceRecord.external_id)
            .join(Business, Business.id == SourceRecord.business_id)
            .where(Business.city_id == city_id, SourceRecord.source_id == source_id)
        )
    )


def store_listing(
    session: Session, city: City, listing: RawListing, known: set[str] | None = None
) -> bool:
    """Detect, merge and store one listing. Returns True if it was kept.

    `known` holds the external ids this source already has in the city; passing
    it avoids a database round trip for each of the (many) non-Iranian places.
    """
    signals = detect(listing.texts, listing.signals)
    if not has_positive(signals):
        if known is not None and listing.external_id not in known:
            return False
        # A place we stored before no longer shows any Iranian signal.
        stale = session.scalar(
            select(SourceRecord).where(
                SourceRecord.source_id == listing.source_id,
                SourceRecord.external_id == listing.external_id,
            )
        )
        if stale:
            _replace_evidence(session, stale, [])
        return False

    links = listing_links(listing, city.country_code)
    if is_blocked(session, links):
        return False

    business_id = resolve(
        session, city.id, listing.source_id, listing.external_id,
        listing.name, listing.lat, listing.lng, links,
    )
    business = session.get(Business, business_id) if business_id else None
    if business is None:
        business = Business(city_id=city.id, status="active")
        session.add(business)
        session.flush()

    persian, latin = _split_name(listing.name)
    business.name_fa = business.name_fa or persian
    business.name_latin = business.name_latin or latin
    business.address = business.address or listing.address
    if business.location is None:
        business.location = _point(listing.lat, listing.lng)
    phone = next((link for link in links if link.kind == "phone"), None)
    site = next((link for link in links if link.kind == "website"), None)
    business.phone_e164 = business.phone_e164 or (phone.value if phone else None)
    business.website = business.website or (site.url if site else None)
    business.last_verified_at = datetime.now(UTC)

    record = _upsert_record(
        session, business.id, listing.source_id, listing.external_id, listing.url, listing.raw
    )
    _replace_evidence(session, record, signals)
    _add_links(session, business.id, links)
    _add_category(session, business.id, listing.category)
    return True


def recompute_scores(session: Session, city_id: int) -> None:
    rows = session.execute(
        select(Business.id, Evidence.signal, Evidence.weight)
        .join(Evidence, Evidence.business_id == Business.id, isouter=True)
        .where(Business.city_id == city_id)
    ).all()
    by_business: dict[uuid.UUID, list[Signal]] = defaultdict(list)
    for business_id, signal, weight in rows:
        signals = by_business[business_id]  # creates the entry even without evidence
        if signal:
            signals.append(Signal(signal, weight, ""))
    for business_id, signals in by_business.items():
        business = session.get(Business, business_id)
        business.confidence_score = score(signals)
        business.confidence_label = confidence_label(business.confidence_score)


def _category_counts(session: Session, city_id: int, min_score: float) -> dict[str, int]:
    rows = session.execute(
        select(BusinessCategory.category_slug, func.count())
        .join(Business, Business.id == BusinessCategory.business_id)
        .where(
            Business.city_id == city_id,
            Business.status == "active",
            Business.confidence_score >= min_score,
        )
        .group_by(BusinessCategory.category_slug)
    ).all()
    return dict(rows)


def website_candidates(
    session: Session, city_id: int, settings: Settings
) -> list[tuple[uuid.UUID, str]]:
    cutoff = datetime.now(UTC) - timedelta(days=settings.website_recheck_days)
    rows = session.execute(
        select(Business.id, BusinessLink.url)
        .join(BusinessLink, BusinessLink.business_id == Business.id)
        .where(
            Business.city_id == city_id,
            Business.status == "active",
            Business.confidence_score >= settings.min_score_for_website_check,
            BusinessLink.kind == "website",
            (Business.website_checked_at.is_(None)) | (Business.website_checked_at < cutoff),
        )
        .order_by(Business.id, BusinessLink.id)
    ).all()
    first: dict[uuid.UUID, str] = {}
    for business_id, url in rows:
        first.setdefault(business_id, url)
    return list(first.items())


def store_website_result(session: Session, business_id: uuid.UUID, result: WebsiteResult) -> None:
    business = session.get(Business, business_id)
    if result.retryable:
        return  # try again on the next index run
    business.website_checked_at = datetime.now(UTC)
    if not result.ok:
        return
    link = website_link(result.final_url or result.url)
    external_id = link.url if link else (result.final_url or result.url)
    if result.signals:
        record = _upsert_record(
            session, business_id, "website", external_id, result.final_url,
            {"lang": result.lang, "title": result.title},
        )
        _replace_evidence(session, record, result.signals)
    _add_links(session, business_id, result.links)


async def _check_all(
    urls: list[str], checker_factory: Callable[[], WebsiteChecker]
) -> list[WebsiteResult]:
    checker = checker_factory()
    try:
        return await checker.check_many(urls)
    finally:
        await checker.aclose()


def check_websites(
    session: Session,
    city: City,
    settings: Settings,
    checker_factory: Callable[[], WebsiteChecker] = WebsiteChecker,
) -> dict[str, Any]:
    candidates = website_candidates(session, city.id, settings)
    if not candidates:
        return {"checked": 0}
    log.info("website: checking %d sites in %s", len(candidates), city.slug)
    results = asyncio.run(_check_all([url for _, url in candidates], checker_factory))
    outcome: Counter[str] = Counter()
    for (business_id, _), result in zip(candidates, results, strict=True):
        store_website_result(session, business_id, result)
        if result.ok:
            outcome["with_evidence" if result.signals else "no_evidence"] += 1
        else:
            outcome[(result.reason or "error").split(":")[0]] += 1
    session.commit()
    return {"checked": len(candidates), **outcome}


def index_city(
    session: Session,
    city_slug: str,
    adapters: list[SourceAdapter],
    check_sites: bool = True,
    settings: Settings | None = None,
    checker_factory: Callable[[], WebsiteChecker] = WebsiteChecker,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Index one city. `on_progress` receives the report so far after each stage."""
    settings = settings or get_settings()
    notify = on_progress or (lambda report: None)
    city = session.scalar(select(City).where(City.slug == city_slug))
    if city is None:
        raise ValueError(f"unknown city: {city_slug}")
    info = city_info(city)
    report: dict[str, Any] = {"city": city_slug, "sources": {}}

    for adapter in adapters:
        source = session.get(Source, adapter.id)
        stats: dict[str, Any] = {"seen": 0, "stored": 0}
        report["sources"][adapter.id] = stats
        if source is None or not source.enabled:
            stats["error"] = "source disabled"
            continue
        try:
            consume(session, adapter.id, source.monthly_cap)
            known = known_external_ids(session, city.id, adapter.id)
            for listing in adapter.fetch(info):
                stats["seen"] += 1
                if store_listing(session, city, listing, known):
                    stats["stored"] += 1
                    if stats["stored"] % COMMIT_EVERY == 0:
                        session.commit()
            session.commit()
        except (SourceUnavailable, QuotaExhausted) as exc:
            session.rollback()
            log.warning("%s: %s", adapter.id, exc)
            stats["error"] = str(exc)
        release = getattr(adapter, "release", None)
        if release:
            stats["release"] = release
        stats["at"] = datetime.now(UTC).isoformat()
        notify(report)

    recompute_scores(session, city.id)
    session.commit()
    if check_sites:
        report["sources"]["website"] = {"status": "running"}
        notify(report)
        report["sources"]["website"] = check_websites(session, city, settings, checker_factory)
        recompute_scores(session, city.id)

    status = session.get(IndexStatus, city.id) or IndexStatus(city_id=city.id)
    status.last_indexed_at = datetime.now(UTC)
    status.per_source = report["sources"]
    status.category_counts = _category_counts(session, city.id, settings.min_display_score)
    session.add(status)
    session.commit()
    report["category_counts"] = status.category_counts
    return report
