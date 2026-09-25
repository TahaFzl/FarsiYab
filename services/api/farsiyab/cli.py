"""Command line: `farsiyab --help`."""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from farsiyab import jobs
from farsiyab.adapters.base import SourceAdapter, SourceUnavailable
from farsiyab.adapters.government import (
    CraAdapter,
    IrsAdapter,
    LosAngelesAdapter,
    TorontoAdapter,
    VancouverAdapter,
)
from farsiyab.adapters.osm import OsmAdapter
from farsiyab.adapters.overture import OvertureAdapter
from farsiyab.adapters.wikimedia import WikidataAdapter, WikivoyageAdapter
from farsiyab.config import get_settings
from farsiyab.db import session_factory, session_scope
from farsiyab.geocode import Geocoder
from farsiyab.indexer import index_city
from farsiyab.loader import load_reference
from farsiyab.models import City, IndexStatus, Job
from farsiyab.reference import load_regions, load_wikivoyage_pages
from farsiyab.scheduling import coverage as coverage_rows
from farsiyab.scheduling import coverage_markdown
from farsiyab.scheduling import schedule as schedule_jobs

app = typer.Typer(help="FarsiYab backend tools.", no_args_is_help=True)
db_app = typer.Typer(help="Database setup.", no_args_is_help=True)
app.add_typer(db_app, name="db")

API_DIR = Path(__file__).resolve().parents[1]
AdapterFactory = Callable[[str | None], SourceAdapter]


def _geocoder() -> Geocoder:
    # Its own session: the geocoder commits its cache independently of the indexer.
    return Geocoder(session_factory()())


ADAPTERS: dict[str, AdapterFactory] = {
    "overture": lambda release: OvertureAdapter(release=release),
    "osm": lambda release: OsmAdapter(),
    "wikidata": lambda release: WikidataAdapter(),
    "wikivoyage": lambda release: WikivoyageAdapter(load_wikivoyage_pages()),
    "gov:la_business": lambda release: LosAngelesAdapter(),
    "gov:vancouver_business": lambda release: VancouverAdapter(),
    "gov:toronto_business": lambda release: TorontoAdapter(_geocoder()),
    "gov:irs_eo_bmf": lambda release: IrsAdapter(load_regions(), _geocoder()),
    "gov:cra_charities": lambda release: CraAdapter(load_regions(), _geocoder()),
}


def _alembic_config() -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


@app.callback()
def main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # One line per HTTP request drowns the useful output.
    logging.getLogger("httpx").setLevel(logging.DEBUG if verbose else logging.WARNING)


@db_app.command("migrate")
def db_migrate() -> None:
    """Apply database migrations."""
    command.upgrade(_alembic_config(), "head")


@db_app.command("load")
def db_load() -> None:
    """Load countries, cities, categories and sources from data/*.yaml."""
    with session_scope() as session:
        counts = load_reference(session)
    typer.echo(json.dumps(counts))


@db_app.command("init")
def db_init() -> None:
    """Migrate and load reference data."""
    db_migrate()
    db_load()


def build_adapters(sources: list[str], release: str | None) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    for source in sources:
        if source not in ADAPTERS:
            raise typer.BadParameter(f"unknown source {source!r}; choose from {list(ADAPTERS)}")
        adapters.append(ADAPTERS[source](release))
    return adapters


def run_index_job(session: Session, job: Job) -> dict:
    return index_city(
        session,
        job.payload["city"],
        build_adapters(list(ADAPTERS), None),
        on_progress=lambda report: jobs.save_progress(session_factory(), job.id, report),
    )


@app.command()
def index(
    city: Annotated[str, typer.Argument(help="City slug, e.g. toronto")],
    source: Annotated[list[str] | None, typer.Option(help="Repeat to pick sources")] = None,
    websites: Annotated[bool, typer.Option(help="Check business websites")] = True,
    release: Annotated[str | None, typer.Option(help="Overture release")] = None,
) -> None:
    """Index one city now (without the job queue)."""
    adapters = build_adapters(source or list(ADAPTERS), release)
    with session_factory()() as session:
        report = index_city(session, city, adapters, check_sites=websites)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


@app.command()
def cities() -> None:
    """List cities and when they were last indexed."""
    with session_factory()() as session:
        rows = session.execute(
            select(City.slug, City.country_code, IndexStatus.last_indexed_at)
            .join(IndexStatus, IndexStatus.city_id == City.id, isouter=True)
            .order_by(City.country_code, City.slug)
        ).all()
    for slug, country, last in rows:
        typer.echo(f"{country}  {slug:<16} {last.isoformat() if last else 'never indexed'}")


@app.command()
def schedule() -> None:
    """Queue index jobs for cities that are due (run daily by a systemd timer)."""
    try:
        latest = OvertureAdapter().resolve_release()
    except SourceUnavailable as exc:
        logging.getLogger(__name__).warning("cannot check Overture releases: %s", exc)
        latest = None
    with session_factory()() as session:
        queued = schedule_jobs(session, latest)
    typer.echo(json.dumps({"overture_release": latest, "queued": queued}, indent=2))


@app.command()
def coverage(
    markdown: Annotated[bool, typer.Option(help="Print a Markdown table")] = False,
) -> None:
    """How many shown businesses each source contributed, per city."""
    with session_factory()() as session:
        rows = coverage_rows(session)
    typer.echo(coverage_markdown(rows) if markdown else json.dumps(rows, indent=2))


@app.command()
def worker(
    once: Annotated[bool, typer.Option(help="Run at most one job and exit")] = False,
    poll: Annotated[float, typer.Option(help="Seconds between polls")] = 5.0,
) -> None:
    """Process queued jobs (index_city)."""
    jobs.work(session_factory(), {"index_city": run_index_job}, poll_seconds=poll, once=once)


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    access_log: Annotated[
        bool, typer.Option(help="Log every request (includes client IPs; off for privacy)")
    ] = False,
) -> None:
    """Run the HTTP API."""
    import uvicorn

    uvicorn.run("farsiyab.api:app", host=host, port=port, reload=reload, access_log=access_log)
