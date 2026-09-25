"""Monthly per-source request caps, kept in PostgreSQL (docs/02-architecture.md)."""

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


class QuotaExhausted(Exception):
    pass


def current_period(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m")


def consume(session: Session, source_id: str, cap: int | None, amount: int = 1) -> int:
    """Atomically add `amount` to this month's usage; raise if it would pass `cap`."""
    if cap is None:
        return 0
    used = session.execute(
        text(
            """
            INSERT INTO quota_usage (source_id, period, used)
            VALUES (:source_id, :period, :amount)
            ON CONFLICT (source_id, period) DO UPDATE
                SET used = quota_usage.used + :amount
                WHERE quota_usage.used + :amount <= :cap
            RETURNING used
            """
        ),
        {"source_id": source_id, "period": current_period(), "amount": amount, "cap": cap},
    ).scalar()
    if used is None or used > cap:
        session.rollback()
        raise QuotaExhausted(f"{source_id}: monthly cap of {cap} reached")
    session.commit()
    return used
