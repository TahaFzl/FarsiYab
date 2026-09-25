"""HTTP API (docs/05-api.md)."""

import json
import time
import uuid
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import Session, sessionmaker

from farsiyab import jobs
from farsiyab.config import get_settings
from farsiyab.db import session_factory
from farsiyab.detection.signals import label as signal_label
from farsiyab.models import (
    REPORT_REASONS,
    Business,
    BusinessCategory,
    BusinessLink,
    Category,
    City,
    Country,
    Evidence,
    IndexStatus,
    Job,
    Report,
    Source,
    SourceRecord,
)
from farsiyab.reference import load_regions, registry_links_for

Lang = Literal["fa", "en"]
MIN_SCORE = {"low": 0.25, "medium": 0.45, "high": 0.75}
SOCIAL_KINDS = ("facebook", "instagram", "telegram")
HIDE_AFTER_NOT_IRANIAN_REPORTS = 3
STREAM_POLL_SECONDS = 1.0
STREAM_TIMEOUT_SECONDS = 300
STREAM_HEARTBEAT_SECONDS = 15

app = FastAPI(title="FarsiYab API", version="0.1.0")


def get_session_factory() -> sessionmaker[Session]:
    return session_factory()


FactoryDep = Annotated[sessionmaker[Session], Depends(get_session_factory)]


def get_session(factory: FactoryDep) -> Iterator[Session]:
    with factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _name(obj: Any, lang: Lang) -> str:
    return obj.name_fa if lang == "fa" else obj.name_en


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/countries")
def countries(session: SessionDep, lang: Lang = "fa") -> list[dict[str, Any]]:
    rows = session.execute(
        select(Country, func.count(City.id))
        .join(City, City.country_code == Country.code, isouter=True)
        .where(Country.enabled)
        .group_by(Country.code)
        .order_by(Country.code)
    ).all()
    return [
        {"code": c.code, "name": _name(c, lang), "name_en": c.name_en, "city_count": n}
        for c, n in rows
    ]


@app.get("/api/v1/countries/{code}/cities")
def cities(
    session: SessionDep, code: str, q: str | None = None, lang: Lang = "fa"
) -> list[dict[str, Any]]:
    stmt = select(City).where(City.country_code == code.upper(), City.enabled)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            City.name_en.ilike(like) | City.name_fa.ilike(like) | City.slug.ilike(like)
        )
    return [
        {"slug": c.slug, "name": _name(c, lang), "name_en": c.name_en}
        for c in session.scalars(stmt.order_by(City.name_en))
    ]


@app.get("/api/v1/categories")
def categories(session: SessionDep, lang: Lang = "fa") -> list[dict[str, Any]]:
    rows = list(session.scalars(select(Category).order_by(Category.position)))
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in rows:
        if c.parent_slug:
            children[c.parent_slug].append({"slug": c.slug, "name": _name(c, lang)})
    return [
        {"slug": c.slug, "name": _name(c, lang), "mvp": c.mvp, "children": children[c.slug]}
        for c in rows
        if not c.parent_slug
    ]


def _expand_categories(session: Session, slugs: list[str]) -> list[str]:
    known = {c.slug: c.parent_slug for c in session.scalars(select(Category))}
    unknown = [s for s in slugs if s not in known]
    if unknown:
        raise HTTPException(422, f"unknown categories: {', '.join(unknown)}")
    return sorted({s for s in known if s in slugs or known[s] in slugs})


def _maybe_reindex(session: Session, city: City) -> dict[str, Any] | None:
    settings = get_settings()
    status = session.get(IndexStatus, city.id)
    fresh_after = datetime.now(UTC) - timedelta(days=settings.reindex_after_days)
    if status and status.last_indexed_at and status.last_indexed_at >= fresh_after:
        return None
    job = jobs.enqueue(session, "index_city", {"city": city.slug}, f"index_city:{city.slug}")
    return {"job_id": str(job.id), "status": job.status}


def _map_links(name: str, address: str | None, lat: float | None, lng: float | None):
    query = ", ".join(p for p in (name, address) if p)
    links = {
        "google_maps": f"https://www.google.com/maps/search/?api=1&query={quote(query)}",
        "apple_maps": f"https://maps.apple.com/?q={quote(name)}",
    }
    if lat is not None and lng is not None:
        lat, lng = round(lat, 6), round(lng, 6)
        links["apple_maps"] += f"&ll={lat},{lng}"
        links["openstreetmap"] = (
            f"https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=18/{lat}/{lng}"
        )
    return links


def _serialize(session: Session, businesses: list[Any], lang: Lang) -> list[dict[str, Any]]:
    ids = [b.id for b in businesses]
    sources = {s.id: s for s in session.scalars(select(Source))}

    cats: dict[uuid.UUID, list[str]] = defaultdict(list)
    for bid, slug in session.execute(
        select(BusinessCategory.business_id, BusinessCategory.category_slug).where(
            BusinessCategory.business_id.in_(ids)
        )
    ):
        cats[bid].append(slug)

    found_in: dict[uuid.UUID, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in session.scalars(
        select(SourceRecord)
        .where(SourceRecord.business_id.in_(ids))
        .order_by(SourceRecord.fetched_at)
    ):
        src = sources.get(r.source_id)
        entry = {"id": r.source_id, "name": _name(src, lang) if src else r.source_id, "url": r.url}
        if r.source_id == "overture" and r.raw and r.raw.get("upstream"):
            entry["via"] = [u for u in r.raw["upstream"] if u != "Overture"]
        found_in[r.business_id].setdefault(r.source_id, entry)

    contact_links: dict[uuid.UUID, list[BusinessLink]] = defaultdict(list)
    for link in session.scalars(
        select(BusinessLink).where(BusinessLink.business_id.in_(ids)).order_by(BusinessLink.id)
    ):
        contact_links[link.business_id].append(link)
        if link.kind in SOCIAL_KINDS:
            src = sources.get(link.kind)
            found_in[link.business_id].setdefault(
                link.kind,
                {"id": link.kind, "name": _name(src, lang) if src else link.kind, "url": link.url},
            )

    evidence: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
    for e, source_id in session.execute(
        select(Evidence, SourceRecord.source_id)
        .join(SourceRecord, SourceRecord.id == Evidence.source_record_id)
        .where(Evidence.business_id.in_(ids))
        .order_by(Evidence.weight.desc())
    ):
        evidence[e.business_id].append(
            {
                "signal": e.signal,
                "label": signal_label(e.signal, lang),
                "snippet": e.snippet,
                "url": e.url,
                "source": source_id,
                "weight": e.weight,
            }
        )

    results = []
    for b in businesses:
        name = b.name_latin or b.name_fa or ""
        socials = {
            link.kind: link.url for link in contact_links[b.id] if link.kind in SOCIAL_KINDS
        }
        results.append(
            {
                "id": str(b.id),
                "name": {"fa": b.name_fa, "latin": b.name_latin},
                "categories": sorted(cats[b.id]),
                "address": b.address,
                "location": (
                    {"lat": round(b.lat, 6), "lng": round(b.lng, 6)} if b.lat is not None else None
                ),
                "contact": {"phone": b.phone_e164, "website": b.website, **socials},
                "confidence": {"score": b.confidence_score, "label": b.confidence_label},
                "sources": list(found_in[b.id].values()),
                "evidence": evidence[b.id],
                "links": _map_links(name, b.address, b.lat, b.lng),
                "last_verified_at": b.last_verified_at.isoformat(),
            }
        )
    return results


def _base_query(city_id: int, min_score: float) -> Select:
    lat = func.ST_Y(func.geometry(Business.location)).label("lat")
    lng = func.ST_X(func.geometry(Business.location)).label("lng")
    return select(
        Business.id,
        Business.name_fa,
        Business.name_latin,
        Business.address,
        Business.phone_e164,
        Business.website,
        Business.confidence_score,
        Business.confidence_label,
        Business.last_verified_at,
        lat,
        lng,
    ).where(
        Business.city_id == city_id,
        Business.status == "active",
        Business.confidence_score >= min_score,
    )


@app.get("/api/v1/search")
def search(
    session: SessionDep,
    country: str,
    city: str,
    categories: Annotated[str, Query(description="comma-separated category slugs")],
    min_confidence: Literal["low", "medium", "high"] = "low",
    sources: str | None = None,
    sort: Literal["confidence", "name", "distance"] = "confidence",
    lat: float | None = None,
    lng: float | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    lang: Lang = "fa",
) -> dict[str, Any]:
    city_row = session.scalar(
        select(City).where(City.slug == city, City.country_code == country.upper())
    )
    if city_row is None:
        raise HTTPException(404, f"unknown city: {country}/{city}")
    slugs = _expand_categories(session, [s.strip() for s in categories.split(",") if s.strip()])

    min_score = max(MIN_SCORE[min_confidence], get_settings().min_display_score)
    stmt = _base_query(city_row.id, min_score).where(
        exists().where(
            BusinessCategory.business_id == Business.id,
            BusinessCategory.category_slug.in_(slugs),
        )
    )
    if sources:
        wanted = [s.strip() for s in sources.split(",") if s.strip()]
        stmt = stmt.where(
            exists().where(
                SourceRecord.business_id == Business.id, SourceRecord.source_id.in_(wanted)
            )
            | exists().where(BusinessLink.business_id == Business.id, BusinessLink.kind.in_(wanted))
        )

    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    name_order = func.coalesce(Business.name_latin, Business.name_fa)
    if sort == "distance":
        if lat is None or lng is None:
            raise HTTPException(422, "sort=distance needs lat and lng")
        here = func.Geography(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326))
        stmt = stmt.order_by(func.ST_Distance(Business.location, here).nulls_last(), name_order)
    elif sort == "name":
        stmt = stmt.order_by(name_order)
    else:
        stmt = stmt.order_by(Business.confidence_score.desc(), name_order)

    rows = session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    status = session.get(IndexStatus, city_row.id)
    return {
        "city": {
            "slug": city_row.slug,
            "country": city_row.country_code,
            "name": _name(city_row, lang),
            "last_indexed_at": (
                status.last_indexed_at.isoformat() if status and status.last_indexed_at else None
            ),
        },
        "categories": slugs,
        "registry_links": [
            {
                "id": r["id"],
                "name": r["name_fa"] if lang == "fa" else r["name_en"],
                "url": r["url"],
                "hint": r["hint_fa"] if lang == "fa" else r["hint_en"],
            }
            for r in registry_links_for(
                load_regions().get(city_row.slug, []), city_row.country_code, slugs
            )
        ],
        "results": _serialize(session, rows, lang),
        "total": total,
        "page": page,
        "page_size": page_size,
        "live_search": _maybe_reindex(session, city_row),
    }


@app.get("/api/v1/search/jobs/{job_id}")
def search_job(session: SessionDep, job_id: uuid.UUID) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "attempts": job.attempts,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def _job_state(job: Job) -> dict[str, Any]:
    result = job.result or {}
    return {
        "status": job.status,
        "sources": (result.get("progress") or result).get("sources", {}),
        "error": job.error,
    }


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/v1/search/jobs/{job_id}/stream")
def search_job_stream(job_id: uuid.UUID, factory: FactoryDep) -> StreamingResponse:
    """Server-Sent Events with an index job's progress (docs/05-api.md).

    Events: `progress` whenever the job's state changes, then exactly one of
    `done`, `failed` or `timeout`. The client refetches search results on each.
    """
    with factory() as session:
        if session.get(Job, job_id) is None:
            raise HTTPException(404, "job not found")

    def events() -> Iterator[str]:
        started = last_beat = time.monotonic()
        previous = None
        while time.monotonic() - started < STREAM_TIMEOUT_SECONDS:
            with factory() as session:
                state = _job_state(session.get(Job, job_id))
            if state != previous:
                previous = state
                yield _sse("progress", state)
                last_beat = time.monotonic()
            if state["status"] in ("done", "failed"):
                yield _sse(state["status"], state)
                return
            if time.monotonic() - last_beat > STREAM_HEARTBEAT_SECONDS:
                yield ": keep-alive\n\n"
                last_beat = time.monotonic()
            time.sleep(STREAM_POLL_SECONDS)
        yield _sse("timeout", previous)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class ReportIn(BaseModel):
    reason: Literal[REPORT_REASONS]  # type: ignore[valid-type]
    message: str | None = Field(default=None, max_length=2000)
    contact_email: EmailStr | None = None


@app.post("/api/v1/businesses/{business_id}/reports", status_code=201)
def report_business(
    session: SessionDep, business_id: uuid.UUID, body: ReportIn
) -> dict[str, str]:
    business = session.get(Business, business_id)
    if business is None:
        raise HTTPException(404, "business not found")
    report = Report(
        business_id=business_id,
        reason=body.reason,
        message=body.message,
        contact_email=body.contact_email,
    )
    session.add(report)
    session.flush()
    if body.reason == "not_iranian":
        count = session.scalar(
            select(func.count()).where(
                Report.business_id == business_id, Report.reason == "not_iranian"
            )
        )
        if count >= HIDE_AFTER_NOT_IRANIAN_REPORTS and business.status == "active":
            business.status = "hidden"
    session.commit()
    return {"id": str(report.id)}
