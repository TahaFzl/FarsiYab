import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from farsiyab.api import app, get_session_factory
from farsiyab.detection.signals import make
from farsiyab.indexer import recompute_scores, store_listing
from farsiyab.models import City, IndexStatus
from tests.test_pipeline import listing

TEST_DATABASE_URL = os.environ.get(
    "FARSIYAB_TEST_DATABASE_URL",
    "postgresql+psycopg://farsiyab:farsiyab@localhost:5432/farsiyab_test",
)

# Everything except reference data, which is loaded once per session.
MUTABLE_TABLES = (
    "evidence", "source_record", "business_link", "business_category", "report",
    "business", "index_status", "job", "quota_usage", "do_not_index", "geocode_cache",
    "submission", "label", "claim",
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    engine = create_engine(TEST_DATABASE_URL)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"test database unavailable ({exc.orig}); see services/api/README.md")

    from farsiyab.cli import _alembic_config
    from farsiyab.loader import load_reference

    config = _alembic_config()
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")
    with Session(engine) as session:
        load_reference(session)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(MUTABLE_TABLES)} CASCADE"))
        # Cities visitors added (tests/test_places.py) and countries they brought.
        conn.execute(text("DELETE FROM city WHERE added_by = 'visitor'"))
        conn.execute(text("DELETE FROM country WHERE code NOT IN (SELECT country_code FROM city)"))
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


@pytest.fixture
def session_maker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


# ── Shared by the API and admin tests ──────────────────────────────────────────


@pytest.fixture
def client(db, session_maker):
    app.dependency_overrides[get_session_factory] = lambda: session_maker
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def toronto_data(db):
    city = db.scalar(select(City).where(City.slug == "toronto"))
    store_listing(db, city, listing(
        external_id="a", name="Shiraz Kitchen | آشپزخانه شیراز",
        urls=["https://www.facebook.com/470792293411166", "https://shiraz.example/"],
        phones=["(416) 555-0100"],
        signals=[make("overture_persian_category", "taxonomy: persian_restaurant")],
    ))
    store_listing(db, city, listing(external_id="b", name="Tehran Market", lat=43.60,
                                    category="grocery"))
    store_listing(db, city, listing(source="osm", external_id="c", name="Dr. Karimzadeh Dental",
                                    lat=43.9, category="doctor/dentist"))  # weak signal only
    recompute_scores(db, city.id)
    db.add(IndexStatus(city_id=city.id, last_indexed_at=datetime.now(UTC)))
    db.commit()
    return city
