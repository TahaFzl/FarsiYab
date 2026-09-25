"""Load data/*.yaml into the reference tables (idempotent upserts)."""

from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from farsiyab.models import Category, City, Country, Source
from farsiyab.reference import load_categories, load_cities, load_countries, load_sources


def _upsert(session: Session, model: Any, rows: list[dict[str, Any]], key: str) -> None:
    for row in rows:
        stmt = insert(model).values(**row)
        updates = {k: stmt.excluded[k] for k in row if k != key}
        session.execute(stmt.on_conflict_do_update(index_elements=[key], set_=updates))


def load_reference(session: Session, data_dir: Path | None = None) -> dict[str, int]:
    countries = load_countries(data_dir)
    _upsert(
        session, Country,
        [{"code": c["code"], "name_fa": c["name_fa"], "name_en": c["name_en"]} for c in countries],
        "code",
    )

    cities = load_cities(data_dir)
    _upsert(
        session, City,
        [
            {
                "slug": c.slug,
                "country_code": c.country,
                "name_fa": c.name_fa,
                "name_en": c.name_en,
                "center": f"SRID=4326;POINT({c.center[0]} {c.center[1]})",
                "west": c.bbox[0],
                "south": c.bbox[1],
                "east": c.bbox[2],
                "north": c.bbox[3],
            }
            for c in cities
        ],
        "slug",
    )

    categories = load_categories(data_dir)
    # Parents first so the self-referencing foreign key is satisfied.
    ordered = sorted(enumerate(categories), key=lambda ic: ic[1].get("parent") is not None)
    _upsert(
        session, Category,
        [
            {
                "slug": c["slug"],
                "name_fa": c["name_fa"],
                "name_en": c["name_en"],
                "parent_slug": c.get("parent"),
                "mvp": bool(c.get("mvp")),
                "position": position,
                "source_mappings": {"overture": c.get("overture") or {}, "osm": c.get("osm") or []},
            }
            for position, c in ordered
        ],
        "slug",
    )

    sources = load_sources(data_dir)
    _upsert(
        session, Source,
        [
            {
                "id": s["id"],
                "name_fa": s.get("name_fa") or s["name_en"],
                "name_en": s["name_en"],
                "kind": s["kind"],
                "status": s["status"],
                "phase": s["phase"],
                "account_required": bool(s.get("account_required")),
                "monthly_cap": s.get("monthly_cap"),
                "enabled": not s.get("account_required") and s["status"] != "rejected",
                "definition": s,
            }
            for s in sources
        ],
        "id",
    )
    session.commit()
    return {
        "countries": len(countries),
        "cities": len(cities),
        "categories": len(categories),
        "sources": len(sources),
    }
