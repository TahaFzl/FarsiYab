"""Runtime settings, read from environment variables prefixed with FARSIYAB_."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FARSIYAB_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://farsiyab:farsiyab@localhost:5432/farsiyab"
    data_dir: Path = REPO_ROOT / "data"

    # Identifies the crawler to the sites it visits (docs/07-legal-and-privacy.md).
    bot_url: str = "https://github.com/TahaFzl/FarsiYab"

    # Overture release such as "2026-09-23.1"; empty means "latest in the bucket".
    overture_release: str = ""
    overture_bucket: str = "overturemaps-us-west-2"
    overture_region: str = "us-west-2"

    # Public Overpass instances, tried in order (https://wiki.openstreetmap.org/wiki/Overpass_API).
    overpass_urls: list[str] = [
        "https://overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]

    # A city is re-indexed when a search hits it and its index is older than this.
    reindex_after_days: int = 7

    # Detector thresholds (docs/04-iranian-detection.md).
    min_display_score: float = 0.25
    # Lower than the display threshold on purpose: the website is how borderline
    # candidates (an ambiguous place name, a surname) get confirmed or not.
    min_score_for_website_check: float = 0.15
    website_recheck_days: int = 30

    website_concurrency: int = 8
    website_timeout_seconds: float = 15.0
    website_min_interval_seconds: float = 1.0
    website_max_bytes: int = 2_000_000

    @property
    def user_agent(self) -> str:
        return f"FarsiYabBot/0.1 (+{self.bot_url})"


@lru_cache
def get_settings() -> Settings:
    return Settings()
