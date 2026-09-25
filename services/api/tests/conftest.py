import os
from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_URL = os.environ.get(
    "FARSIYAB_TEST_DATABASE_URL",
    "postgresql+psycopg://farsiyab:farsiyab@localhost:5432/farsiyab_test",
)

# Everything except reference data, which is loaded once per session.
MUTABLE_TABLES = (
    "evidence", "source_record", "business_link", "business_category", "report",
    "business", "index_status", "job", "quota_usage", "do_not_index",
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
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


@pytest.fixture
def session_maker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
