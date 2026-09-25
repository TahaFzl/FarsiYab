"""Job queue on a PostgreSQL table (no Redis). See docs/02-architecture.md."""

import logging
import time
import traceback
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from farsiyab.models import Job

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
Handler = Callable[[Session, Job], dict[str, Any] | None]


def enqueue(
    session: Session, kind: str, payload: dict[str, Any], dedupe_key: str | None = None
) -> Job:
    """Add a job, or return the queued/running job that has the same dedupe key."""
    if dedupe_key:
        inserted = session.execute(
            insert(Job)
            .values(id=uuid.uuid4(), kind=kind, payload=payload, dedupe_key=dedupe_key)
            .on_conflict_do_nothing(
                index_elements=["dedupe_key"],
                index_where=text("status IN ('queued', 'running')"),
            )
            .returning(Job.id)
        ).scalar()
        session.commit()
        job_id = inserted or session.scalar(
            select(Job.id).where(
                Job.dedupe_key == dedupe_key, Job.status.in_(("queued", "running"))
            )
        )
        return session.get(Job, job_id)
    job = Job(kind=kind, payload=payload)
    session.add(job)
    session.commit()
    return job


def claim(session: Session) -> Job | None:
    """Take the oldest runnable job; concurrent workers never get the same one."""
    job = session.scalar(
        select(Job)
        .where(Job.status == "queued", Job.run_after <= datetime.now(UTC))
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        session.rollback()
        return None
    job.status = "running"
    job.attempts += 1
    job.started_at = datetime.now(UTC)
    session.commit()
    return job


def run_one(session: Session, handlers: dict[str, Handler]) -> Job | None:
    job = claim(session)
    if job is None:
        return None
    try:
        result = handlers[job.kind](session, job)
    except Exception as exc:
        session.rollback()
        log.exception("job %s (%s) failed", job.id, job.kind)
        job = session.get(Job, job.id)
        job.error = "".join(traceback.format_exception_only(exc)).strip()
        if job.attempts >= MAX_ATTEMPTS:
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
        else:
            job.status = "queued"
            job.run_after = datetime.now(UTC) + timedelta(minutes=2**job.attempts)
    else:
        job.status = "done"
        job.result = result
        job.error = None
        job.finished_at = datetime.now(UTC)
    session.commit()
    return job


def save_progress(session_factory: Callable[[], Session], job_id: uuid.UUID, progress: Any) -> None:
    """Store partial results on a running job from a separate, short transaction,
    so the indexer's own transactions (and rollbacks) cannot lose it."""
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is not None and job.status == "running":
            job.result = {"progress": progress}
            session.commit()


def work(
    session_factory: Callable[[], Session],
    handlers: dict[str, Handler],
    poll_seconds: float = 5.0,
    once: bool = False,
) -> None:
    while True:
        with session_factory() as session:
            job = run_one(session, handlers)
        if once:
            return
        if job is None:
            time.sleep(poll_seconds)
