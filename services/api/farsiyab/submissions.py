"""User submissions and admin review (docs/sources/user-submissions.md).

A submission is stored as `pending` and never shown until an admin approves it.
Approval turns it into an ordinary listing of the `user_submission` source, so it
goes through the same detection and entity resolution as every other source and
merges with a business we already know when a link or the location matches.
"""

import hashlib
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from farsiyab.adapters.base import RawListing
from farsiyab.config import get_settings
from farsiyab.detection.detector import TextField, detect, score
from farsiyab.detection.signals import make
from farsiyab.indexer import listing_links, recompute_scores, store_listing
from farsiyab.links import _split
from farsiyab.models import (
    Business,
    BusinessLink,
    City,
    DoNotIndex,
    Report,
    SourceRecord,
    Submission,
)
from farsiyab.resolution import find_by_links

SOURCE_ID = "user_submission"
# A link to one of these is public proof enough even though it is not the business's
# own site (a Google Maps place, a Yelp page, a directory listing).
PROOF_HOSTS = ("google.com", "goo.gl", "maps.app.goo.gl", "apple.com", "yelp.com", "yelp.ca")


class BlockedSubmission(Exception):
    """The business asked to be removed; approving the submission would bring it back."""


def client_hash(client: str | None, day: date | None = None) -> str | None:
    if not client:
        return None
    day = day or datetime.now(UTC).date()
    data = f"{get_settings().secret_key}|{day.isoformat()}|{client}"
    return hashlib.sha256(data.encode()).hexdigest()


def submissions_today(session: Session, hashed: str | None) -> int:
    if hashed is None:
        return 0
    return session.scalar(
        select(func.count()).where(Submission.client_hash == hashed)
    ) or 0


def is_public_link(url: str) -> bool:
    try:
        parts, host, _ = _split(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and "." in host


def _listing(submission: Submission) -> RawListing:
    url = submission.links[0] if submission.links else None
    who = "owner" if submission.is_owner else "community"
    return RawListing(
        source_id=SOURCE_ID,
        external_id=str(submission.id),
        name=submission.name,
        url=url,
        address=submission.address,
        category=submission.category_slug,
        phones=[submission.phone] if submission.phone else [],
        urls=list(submission.links),
        texts=[TextField("name", submission.name, url)],
        raw={"name": submission.name, "submitted_by": who},
    )


def detected_score(submission: Submission) -> float:
    """What the detector alone says about the name, shown to the reviewer."""
    return score(detect(_listing(submission).texts))


def possible_duplicate(session: Session, submission: Submission) -> uuid.UUID | None:
    city = session.get(City, submission.city_id)
    links = listing_links(_listing(submission), city.country_code)
    return find_by_links(session, submission.city_id, links)


def approve(session: Session, submission: Submission, note: str | None = None) -> Business:
    """Store the submission as a verified listing and show it."""
    city = session.get(City, submission.city_id)
    listing = _listing(submission)
    who = "صاحب کسب‌وکار" if submission.is_owner else "کاربر"
    listing.signals = [
        make("user_submission_verified", f"ثبت توسط {who}، تأیید ادمین", listing.url)
    ]
    if not store_listing(session, city, listing):
        # Only a do-not-index entry (an earlier removal request) stops a verified listing.
        raise BlockedSubmission("a link of this business is on the do-not-index list")
    session.flush()
    business = session.get(Business, _business_for(session, submission.id))
    if business.status == "hidden":
        business.status = "active"
    recompute_scores(session, city.id)
    submission.status = "approved"
    submission.business_id = business.id
    submission.review_note = note
    submission.reviewed_at = datetime.now(UTC)
    return business


def _business_for(session: Session, submission_id: uuid.UUID) -> uuid.UUID:
    return session.scalar(
        select(SourceRecord.business_id).where(
            SourceRecord.source_id == SOURCE_ID, SourceRecord.external_id == str(submission_id)
        )
    )


def reject(submission: Submission, note: str | None = None) -> None:
    submission.status = "rejected"
    submission.review_note = note
    submission.reviewed_at = datetime.now(UTC)


# ── Reports ───────────────────────────────────────────────────────────────────

REPORT_ACTIONS = ("dismiss", "hide", "restore", "close", "remove")


def resolve_report(
    session: Session, report: Report, action: str, note: str | None = None
) -> None:
    """Apply an admin decision to the reported business and close every open report on it.

    - hide: not shown until restored (e.g. not Iranian)
    - close: the business closed
    - remove: removal at the owner's request; its links go on the do-not-index
      list so no source brings it back (docs/07-legal-and-privacy.md)
    - restore: shown again
    - dismiss: the report was wrong; nothing changes
    """
    if action not in REPORT_ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    business = session.get(Business, report.business_id)
    if action == "hide":
        business.status = "hidden"
    elif action == "close":
        business.status = "closed"
    elif action == "restore":
        business.status = "active"
    elif action == "remove":
        business.status = "removed_by_request"
        links = session.execute(
            select(BusinessLink.kind, BusinessLink.value).where(
                BusinessLink.business_id == business.id
            )
        ).all()
        known = set(session.execute(select(DoNotIndex.kind, DoNotIndex.value)).all())
        for kind, value in links:
            if (kind, value) not in known:
                session.add(DoNotIndex(kind=kind, value=value, note=f"report {report.id}"))
    status = "dismissed" if action == "dismiss" else "resolved"
    now = datetime.now(UTC)
    # One decision answers every open report on the business (they are shown together).
    targets = session.scalars(
        select(Report).where(Report.business_id == business.id, Report.status == "open")
    ).all()
    for r in targets:
        r.status = status
        r.reviewed_at = now
        r.review_note = note
