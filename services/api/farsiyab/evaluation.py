"""Detector precision from labeled samples (docs/04-iranian-detection.md, phase 4 goal).

People label shown businesses as Iranian or not. Samples are drawn evenly from the
three confidence labels so "high" is not measured on a handful of rows, and
precision is computed with the business's *current* score, so re-running it after
a weight change shows whether the change helped.
"""

import math
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from farsiyab.config import get_settings
from farsiyab.detection.detector import confidence_label, score
from farsiyab.detection.signals import Signal
from farsiyab.models import Business, Evidence, Label

LEVELS = ("high", "medium", "low")
TARGET_PER_LEVEL = 100  # 300 in total (docs/08-roadmap.md)
GOAL = 0.90  # precision for "high" and "medium"


def next_to_label(session: Session, city_id: int | None = None) -> uuid.UUID | None:
    """A random shown, unlabeled business from the level with the fewest labels so far."""
    counts = dict(
        session.execute(
            select(Business.confidence_label, func.count())
            .join(Label, Label.business_id == Business.id)
            .group_by(Business.confidence_label)
        ).all()
    )
    for level in sorted(LEVELS, key=lambda lv: counts.get(lv, 0)):
        stmt = (
            select(Business.id)
            .where(
                Business.status == "active",
                Business.confidence_label == level,
                Business.confidence_score >= get_settings().min_display_score,
                ~select(Label.business_id).where(Label.business_id == Business.id).exists(),
            )
            .order_by(func.random())
            .limit(1)
        )
        if city_id is not None:
            stmt = stmt.where(Business.city_id == city_id)
        found = session.scalar(stmt)
        if found:
            return found
    return None


def save_label(
    session: Session, business: Business, is_iranian: bool, by: str, note: str | None = None
) -> Label:
    label = session.get(Label, business.id) or Label(business_id=business.id)
    label.is_iranian = is_iranian
    label.note = note
    label.labeled_by = by
    label.score_at_label = business.confidence_score
    label.labeled_at = datetime.now(UTC)
    session.add(label)
    return label


def wilson_interval(hits: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    p = hits / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _level_stats(rows: Iterable[tuple[str | None, bool]]) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for level in LEVELS:
        verdicts = [iranian for lv, iranian in rows if lv == level]
        hits = sum(verdicts)
        low, high = wilson_interval(hits, len(verdicts))
        stats[level] = {
            "labeled": len(verdicts),
            "iranian": hits,
            "precision": round(hits / len(verdicts), 3) if verdicts else None,
            "ci95": [round(low, 3), round(high, 3)],
        }
    return stats


def precision(session: Session) -> dict:
    """Precision per confidence label for the current scores."""
    rows = session.execute(
        select(Business.confidence_label, Label.is_iranian).join(
            Label, Label.business_id == Business.id
        )
    ).all()
    stats = _level_stats(rows)
    shown = [r for r in rows if r[0] in ("high", "medium")]
    combined = sum(iranian for _, iranian in shown) / len(shown) if shown else None
    return {
        "levels": stats,
        "high_and_medium": round(combined, 3) if combined is not None else None,
        "goal": GOAL,
        "met": combined is not None and combined >= GOAL,
        "target_per_level": TARGET_PER_LEVEL,
    }


def precision_with_weights(session: Session, weights: dict[str, float]) -> dict:
    """What precision would be if some signal weights changed (for tuning offline)."""
    evidence: dict[uuid.UUID, list[Signal]] = {}
    for business_id, signal, weight in session.execute(
        select(Evidence.business_id, Evidence.signal, Evidence.weight).join(
            Label, Label.business_id == Evidence.business_id
        )
    ):
        evidence.setdefault(business_id, []).append(
            Signal(signal, weights.get(signal, weight), "")
        )
    rows = []
    for business_id, iranian in session.execute(select(Label.business_id, Label.is_iranian)):
        rows.append((confidence_label(score(evidence.get(business_id, []))), iranian))
    return {"levels": _level_stats(rows)}
