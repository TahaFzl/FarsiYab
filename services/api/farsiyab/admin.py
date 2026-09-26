"""Admin API (docs/05-api.md, "ادمین"): review queue, reports, sources, labels.

Every route needs `Authorization: Bearer <FARSIYAB_ADMIN_TOKEN>`. With no token
configured the admin API answers 503, so a fresh install is never open.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from farsiyab import claims, evaluation, jobs, submissions
from farsiyab.api import SessionDep, _base_query, _name, _serialize
from farsiyab.config import get_settings
from farsiyab.models import (
    Business,
    Category,
    City,
    Claim,
    IndexStatus,
    Job,
    Label,
    Report,
    Source,
    Submission,
)


def require_admin(authorization: Annotated[str | None, Header()] = None) -> str:
    token = get_settings().admin_token
    if not token:
        raise HTTPException(503, "admin API disabled (FARSIYAB_ADMIN_TOKEN is not set)")
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not secrets.compare_digest(given.encode(), token.encode()):
        raise HTTPException(401, "admin token required")
    return "admin"


router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])
Lang = Literal["fa", "en"]


def _business(session: Session, business_id: uuid.UUID, lang: Lang) -> dict[str, Any] | None:
    """A business card as search shows it, whatever its status or score."""
    stmt = _base_query(None, None).where(Business.id == business_id)
    rows = session.execute(stmt).all()
    if not rows:
        return None
    card = _serialize(session, rows, lang)[0]
    business = session.get(Business, business_id)
    city = session.get(City, business.city_id)
    card["status"] = business.status
    card["city"] = {"slug": city.slug, "country": city.country_code, "name": _name(city, lang)}
    label = session.get(Label, business_id)
    card["label"] = (
        {"is_iranian": label.is_iranian, "note": label.note, "by": label.labeled_by}
        if label else None
    )
    return card


# ── Overview ──────────────────────────────────────────────────────────────────


@router.get("/overview")
def overview(session: SessionDep, lang: Lang = "fa") -> dict[str, Any]:
    count = lambda stmt: session.scalar(select(func.count()).select_from(stmt.subquery()))  # noqa: E731
    cities = []
    for city, status in session.execute(
        select(City, IndexStatus)
        .join(IndexStatus, IndexStatus.city_id == City.id, isouter=True)
        .order_by(City.country_code, City.slug)
    ):
        failed = {
            source: stats.get("error")
            for source, stats in (status.per_source if status else {}).items()
            if isinstance(stats, dict) and stats.get("error")
        }
        cities.append({
            "slug": city.slug,
            "country": city.country_code,
            "name": _name(city, lang),
            "last_indexed_at": status.last_indexed_at.isoformat()
            if status and status.last_indexed_at else None,
            "shown": sum((status.category_counts or {}).values()) if status else 0,
            "failed_sources": failed,
        })
    return {
        "pending_submissions": count(select(Submission).where(Submission.status == "pending")),
        "pending_claims": count(select(Claim).where(Claim.status == "pending")),
        "open_reports": count(select(Report).where(Report.status == "open")),
        "hidden_businesses": count(select(Business).where(Business.status == "hidden")),
        "labels": count(select(Label)),
        "cities": cities,
        "precision": evaluation.precision(session),
    }


# ── Submissions ───────────────────────────────────────────────────────────────


class ReviewIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


@router.get("/submissions")
def list_submissions(
    session: SessionDep,
    status: Literal["pending", "approved", "rejected"] = "pending",
    lang: Lang = "fa",
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Submission).where(Submission.status == status).order_by(Submission.created_at)
    ).all()
    out = []
    for s in rows:
        city = session.get(City, s.city_id)
        category = session.get(Category, s.category_slug)
        duplicate = submissions.possible_duplicate(session, s)
        out.append({
            "id": str(s.id),
            "name": s.name,
            "city": _name(city, lang),
            "category": _name(category, lang),
            "address": s.address,
            "phone": s.phone,
            "links": s.links,
            "is_owner": s.is_owner,
            "contact_email": s.contact_email,
            "note": s.note,
            "detected_score": round(s.detected_score, 2),
            "status": s.status,
            "created_at": s.created_at.isoformat(),
            "possible_duplicate": _business(session, duplicate, lang) if duplicate else None,
            "business_id": str(s.business_id) if s.business_id else None,
        })
    return out


def _submission(session: Session, submission_id: uuid.UUID) -> Submission:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(404, "submission not found")
    if submission.status != "pending":
        raise HTTPException(409, f"submission already {submission.status}")
    return submission


@router.post("/submissions/{submission_id}/approve")
def approve_submission(
    session: SessionDep, submission_id: uuid.UUID, body: ReviewIn
) -> dict[str, str]:
    submission = _submission(session, submission_id)
    try:
        business = submissions.approve(session, submission, body.note)
    except submissions.BlockedSubmission as exc:
        session.rollback()
        raise HTTPException(409, str(exc)) from exc
    session.commit()
    return {"status": "approved", "business_id": str(business.id)}


@router.post("/submissions/{submission_id}/reject")
def reject_submission(
    session: SessionDep, submission_id: uuid.UUID, body: ReviewIn
) -> dict[str, str]:
    submissions.reject(_submission(session, submission_id), body.note)
    session.commit()
    return {"status": "rejected"}


# ── Reports ───────────────────────────────────────────────────────────────────


class ResolveIn(BaseModel):
    action: Literal["dismiss", "hide", "restore", "close", "remove"]
    note: str | None = Field(default=None, max_length=2000)


@router.get("/reports")
def list_reports(
    session: SessionDep, status: Literal["open", "resolved", "dismissed"] = "open",
    lang: Lang = "fa",
) -> list[dict[str, Any]]:
    """Reports grouped by business, the most reported first."""
    reports = session.scalars(
        select(Report).where(Report.status == status).order_by(Report.created_at)
    ).all()
    grouped: dict[uuid.UUID, list[Report]] = {}
    for r in reports:
        grouped.setdefault(r.business_id, []).append(r)
    out = []
    for business_id, items in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        out.append({
            "business": _business(session, business_id, lang),
            "reports": [
                {
                    "id": str(r.id),
                    "reason": r.reason,
                    "message": r.message,
                    "contact_email": r.contact_email,
                    "created_at": r.created_at.isoformat(),
                    "review_note": r.review_note,
                }
                for r in items
            ],
        })
    return out


@router.post("/reports/{report_id}/resolve")
def resolve_report(session: SessionDep, report_id: uuid.UUID, body: ResolveIn) -> dict[str, str]:
    report = session.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "report not found")
    submissions.resolve_report(session, report, body.action, body.note)
    session.commit()
    return {"status": report.status}


# ── Businesses ────────────────────────────────────────────────────────────────


class StatusIn(BaseModel):
    status: Literal["active", "hidden", "closed", "removed_by_request"]


@router.get("/businesses/{business_id}")
def get_business(session: SessionDep, business_id: uuid.UUID, lang: Lang = "fa") -> dict:
    card = _business(session, business_id, lang)
    if card is None:
        raise HTTPException(404, "business not found")
    return card


@router.patch("/businesses/{business_id}")
def set_business_status(session: SessionDep, business_id: uuid.UUID, body: StatusIn) -> dict:
    business = session.get(Business, business_id)
    if business is None:
        raise HTTPException(404, "business not found")
    business.status = body.status
    session.commit()
    return {"status": business.status}


@router.get("/hidden")
def hidden_businesses(session: SessionDep, lang: Lang = "fa") -> list[dict[str, Any]]:
    ids = session.scalars(
        select(Business.id).where(Business.status == "hidden").order_by(Business.name_latin)
    ).all()
    return [_business(session, i, lang) for i in ids]


# ── Labels (detector precision) ───────────────────────────────────────────────


class LabelIn(BaseModel):
    is_iranian: bool
    note: str | None = Field(default=None, max_length=500)
    by: str = Field(default="admin", max_length=100)


@router.get("/labels/next")
def next_label(session: SessionDep, city: str | None = None, lang: Lang = "fa") -> dict:
    city_id = None
    if city:
        city_id = session.scalar(select(City.id).where(City.slug == city))
        if city_id is None:
            raise HTTPException(404, f"unknown city: {city}")
    business_id = evaluation.next_to_label(session, city_id)
    return {
        "business": _business(session, business_id, lang) if business_id else None,
        "precision": evaluation.precision(session),
    }


@router.post("/businesses/{business_id}/label")
def label_business(session: SessionDep, business_id: uuid.UUID, body: LabelIn) -> dict:
    business = session.get(Business, business_id)
    if business is None:
        raise HTTPException(404, "business not found")
    evaluation.save_label(session, business, body.is_iranian, body.by, body.note)
    session.commit()
    return evaluation.precision(session)


@router.get("/precision")
def get_precision(session: SessionDep) -> dict:
    return evaluation.precision(session)


# ── Sources and indexing ──────────────────────────────────────────────────────


class SourceIn(BaseModel):
    enabled: bool


@router.get("/sources")
def list_sources(session: SessionDep, lang: Lang = "fa") -> list[dict[str, Any]]:
    per_city: dict[str, dict[str, Any]] = {}
    for city, status in session.execute(
        select(City.slug, IndexStatus).join(IndexStatus, IndexStatus.city_id == City.id)
    ):
        for source_id, stats in (status.per_source or {}).items():
            per_city.setdefault(source_id, {})[city] = stats
    return [
        {
            "id": s.id,
            "name": _name(s, lang),
            "kind": s.kind,
            "status": s.status,
            "phase": s.phase,
            "enabled": s.enabled,
            "account_required": s.account_required,
            "last_runs": per_city.get(s.id, {}),
        }
        for s in session.scalars(select(Source).order_by(Source.phase, Source.id))
    ]


@router.patch("/sources/{source_id}")
def set_source(session: SessionDep, source_id: str, body: SourceIn) -> dict:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "source not found")
    if body.enabled and (source.account_required or source.status == "rejected"):
        raise HTTPException(409, "this source needs an account or was rejected")
    source.enabled = body.enabled
    session.commit()
    return {"id": source.id, "enabled": source.enabled}


class IndexIn(BaseModel):
    city: str


@router.post("/index", status_code=202)
def index_now(session: SessionDep, body: IndexIn) -> dict[str, str]:
    if session.scalar(select(City.id).where(City.slug == body.city)) is None:
        raise HTTPException(404, f"unknown city: {body.city}")
    job = jobs.enqueue(session, "index_city", {"city": body.city}, f"index_city:{body.city}")
    return {"job_id": str(job.id), "status": job.status}


@router.get("/jobs")
def recent_jobs(session: SessionDep, days: int = 7) -> list[dict[str, Any]]:
    since = datetime.now(UTC) - timedelta(days=days)
    return [
        {
            "id": str(j.id),
            "kind": j.kind,
            "city": j.payload.get("city"),
            "status": j.status,
            "attempts": j.attempts,
            "error": j.error,
            "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        }
        for j in session.scalars(
            select(Job).where(Job.created_at >= since).order_by(Job.created_at.desc()).limit(50)
        )
    ]


# ── Owner claims ──────────────────────────────────────────────────────────────


@router.get("/claims")
def list_claims(
    session: SessionDep, status: Literal["pending", "verified", "rejected"] = "pending",
    lang: Lang = "fa",
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Claim).where(Claim.status == status).order_by(Claim.created_at)
    ).all()
    return [
        {
            "id": str(c.id),
            "method": c.method,
            "token": c.token,
            "contact_email": c.contact_email,
            "note": c.note,
            "status": c.status,
            "created_at": c.created_at.isoformat(),
            "business": _business(session, c.business_id, lang),
        }
        for c in rows
    ]


def _pending_claim(session: Session, claim_id: uuid.UUID) -> Claim:
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "claim not found")
    if claim.status != "pending":
        raise HTTPException(409, f"claim already {claim.status}")
    return claim


@router.post("/claims/{claim_id}/verify")
def verify_claim(session: SessionDep, claim_id: uuid.UUID) -> dict[str, str]:
    """For claims checked by hand (e.g. a call to the business's public number). The
    key is returned once, for the admin to send to the owner's contact email."""
    claim = _pending_claim(session, claim_id)
    key = claims.grant(claim)
    session.get(Business, claim.business_id).owner_verified_at = claim.verified_at
    session.commit()
    return {"owner_key": key, "contact_email": claim.contact_email or ""}


@router.post("/claims/{claim_id}/reject")
def reject_claim(session: SessionDep, claim_id: uuid.UUID) -> dict[str, str]:
    _pending_claim(session, claim_id).status = "rejected"
    session.commit()
    return {"status": "rejected"}
