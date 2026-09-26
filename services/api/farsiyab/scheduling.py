"""Decide which cities need re-indexing and report per-source coverage.

`farsiyab schedule` runs daily from a systemd timer (deploy/systemd) and queues
an index job for every city that was never indexed, is older than
`reindex_after_days`, or was indexed from an older Overture release.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from farsiyab import jobs
from farsiyab.config import Settings, get_settings
from farsiyab.display import is_shown
from farsiyab.models import Business, BusinessLink, City, IndexStatus, SourceRecord

SOCIAL_KINDS = ("facebook", "instagram", "telegram")


@dataclass(frozen=True)
class Due:
    city: str
    reason: str  # never_indexed | stale | new_overture_release


def due_cities(
    session: Session,
    latest_overture_release: str | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> list[Due]:
    settings = settings or get_settings()
    cutoff = (now or datetime.now(UTC)) - timedelta(days=settings.reindex_after_days)
    rows = session.execute(
        select(City.slug, IndexStatus.last_indexed_at, IndexStatus.per_source)
        .join(IndexStatus, IndexStatus.city_id == City.id, isouter=True)
        .where(City.enabled)
        .order_by(City.slug)
    ).all()
    due = []
    for slug, last, per_source in rows:
        indexed_release = ((per_source or {}).get("overture") or {}).get("release")
        if last is None:
            due.append(Due(slug, "never_indexed"))
        elif last < cutoff:
            due.append(Due(slug, "stale"))
        elif indexed_release and latest_overture_release and (
            indexed_release < latest_overture_release
        ):
            due.append(Due(slug, "new_overture_release"))
    return due


def schedule(session: Session, latest_overture_release: str | None = None) -> list[dict[str, str]]:
    queued = []
    for item in due_cities(session, latest_overture_release):
        job = jobs.enqueue(session, "index_city", {"city": item.city}, f"index_city:{item.city}")
        queued.append({"city": item.city, "reason": item.reason, "job_id": str(job.id)})
    return queued


def coverage(session: Session, min_score: float | None = None) -> list[dict[str, Any]]:
    """Per city: shown businesses, how many each source contributed, and how many
    are backed by at least two independent sources (docs/08-roadmap.md, phase 3)."""
    visible = is_shown() if min_score is None else (
        (Business.status == "active") & (Business.confidence_score >= min_score)
    )
    shown = select(Business.id, Business.city_id).where(visible).subquery()
    per_source: dict[int, dict[str, int]] = defaultdict(dict)
    independent: dict[int, set[str]] = defaultdict(set)
    for city_id, source_id, count in session.execute(
        select(shown.c.city_id, SourceRecord.source_id, func.count(distinct(shown.c.id)))
        .join(SourceRecord, SourceRecord.business_id == shown.c.id)
        .group_by(shown.c.city_id, SourceRecord.source_id)
    ):
        per_source[city_id][source_id] = count
        independent[city_id].add(source_id)
    for city_id, kind, count in session.execute(
        select(shown.c.city_id, BusinessLink.kind, func.count(distinct(shown.c.id)))
        .join(BusinessLink, BusinessLink.business_id == shown.c.id)
        .where(BusinessLink.kind.in_(SOCIAL_KINDS))
        .group_by(shown.c.city_id, BusinessLink.kind)
    ):
        per_source[city_id][kind] = count

    record_sources = (
        select(SourceRecord.business_id, func.count(distinct(SourceRecord.source_id)).label("n"))
        .group_by(SourceRecord.business_id)
        .subquery()
    )
    multi = dict(
        session.execute(
            select(shown.c.city_id, func.count())
            .join(record_sources, record_sources.c.business_id == shown.c.id)
            .where(record_sources.c.n >= 2)
            .group_by(shown.c.city_id)
        ).all()
    )
    totals = dict(
        session.execute(select(shown.c.city_id, func.count()).group_by(shown.c.city_id)).all()
    )

    report = []
    for city_id, slug in session.execute(select(City.id, City.slug).order_by(City.slug)):
        sources = per_source.get(city_id, {})
        report.append(
            {
                "city": slug,
                "shown": totals.get(city_id, 0),
                "sources": dict(sorted(sources.items())),
                # Social links are found *through* other sources, so they do not count
                # as independent sources for the phase 3 goal (3 per city).
                "source_count": len(independent.get(city_id, ())),
                "multi_source": multi.get(city_id, 0),
            }
        )
    return report


def coverage_markdown(rows: list[dict[str, Any]]) -> str:
    source_ids = sorted({s for row in rows for s in row["sources"]})
    header = ["city", "shown", *source_ids, "independent sources", "2+ sources"]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        cells = [row["city"], str(row["shown"])]
        cells += [str(row["sources"].get(s, 0)) for s in source_ids]
        cells += [str(row["source_count"]), str(row["multi_source"])]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
