"""Which businesses are shown: the display threshold, global or per country."""

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from farsiyab.config import get_settings
from farsiyab.models import Business, City, Country


def threshold_for(session: Session, city: City) -> float:
    country = session.get(Country, city.country_code)
    override = country.min_display_score if country else None
    return override if override is not None else get_settings().min_display_score


def shown_threshold() -> ColumnElement[float]:
    """SQL for the threshold of each business's country, for queries across cities."""
    per_country = (
        select(Country.min_display_score)
        .join(City, City.country_code == Country.code)
        .where(City.id == Business.city_id)
        .scalar_subquery()
    )
    return func.coalesce(per_country, get_settings().min_display_score)


def is_shown() -> ColumnElement[bool]:
    return (Business.status == "active") & (Business.confidence_score >= shown_threshold())
