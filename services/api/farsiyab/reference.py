"""Reference data from data/*.yaml: countries, cities, categories, sources."""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from farsiyab.config import get_settings


def _load(name: str, data_dir: Path | None = None) -> dict[str, Any]:
    path = (data_dir or get_settings().data_dir) / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class CityInfo:
    slug: str
    country: str
    name_fa: str
    name_en: str
    center: tuple[float, float]  # lon, lat
    bbox: tuple[float, float, float, float]  # west, south, east, north


def load_countries(data_dir: Path | None = None) -> list[dict[str, Any]]:
    return _load("cities.yaml", data_dir)["countries"]


def load_cities(data_dir: Path | None = None) -> list[CityInfo]:
    return [
        CityInfo(
            slug=c["slug"],
            country=c["country"],
            name_fa=c["name_fa"],
            name_en=c["name_en"],
            center=tuple(c["center"]),
            bbox=tuple(c["bbox"]),
        )
        for c in _load("cities.yaml", data_dir)["cities"]
    ]


def load_wikivoyage_pages(data_dir: Path | None = None) -> dict[str, list[str]]:
    return {c["slug"]: c.get("wikivoyage", []) for c in _load("cities.yaml", data_dir)["cities"]}


def load_regions(data_dir: Path | None = None) -> dict[str, list[str]]:
    return {c["slug"]: c.get("regions", []) for c in _load("cities.yaml", data_dir)["cities"]}


def load_registry_links(data_dir: Path | None = None) -> list[dict[str, Any]]:
    return _load("registry_links.yaml", data_dir)["registries"]


def registry_links_for(
    city_regions: list[str], country: str, categories: list[str], data_dir: Path | None = None
) -> list[dict[str, Any]]:
    """Registries covering this city and at least one requested category (children
    included: asking for "doctor" also shows dentist registries)."""
    wanted = set(categories)
    matches = []
    for registry in load_registry_links(data_dir):
        regions = set(registry["regions"])
        covers = bool(regions & set(city_regions)) or f"country:{country}" in regions
        relevant = any(c in wanted or c.split("/")[0] in wanted for c in registry["categories"])
        if covers and relevant:
            matches.append(registry)
    return matches


def load_sources(data_dir: Path | None = None) -> list[dict[str, Any]]:
    return _load("sources.yaml", data_dir)["sources"]


@dataclass
class CategoryMapper:
    """Maps each source's own place types onto FarsiYab category slugs."""

    categories: list[dict[str, Any]]
    _taxonomy: dict[str, str] = field(default_factory=dict)
    _basic: dict[str, str] = field(default_factory=dict)
    _osm: list[tuple[str, str | None, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        for cat in self.categories:
            overture = cat.get("overture") or {}
            for value in overture.get("taxonomy") or []:
                self._taxonomy.setdefault(value, cat["slug"])
            for value in overture.get("basic_category") or []:
                self._basic.setdefault(value, cat["slug"])
            for matcher in cat.get("osm") or []:
                key, value = matcher.split("=", 1)
                self._osm.append((key, None if value == "*" else value, cat["slug"]))

    @property
    def slugs(self) -> list[str]:
        return [c["slug"] for c in self.categories]

    def overture(self, hierarchy: list[str] | None, basic_category: str | None) -> str:
        # Most specific level first: hierarchy is ordered root -> leaf.
        for value in reversed(hierarchy or []):
            if value in self._taxonomy:
                return self._taxonomy[value]
        if basic_category and basic_category in self._basic:
            return self._basic[basic_category]
        return "other"

    def osm(self, tags: dict[str, str]) -> str:
        for key, value, slug in self._osm:
            tag = tags.get(key)
            if tag is not None and (value is None or value in tag.split(";")):
                return slug
        return "other"


@lru_cache
def default_mapper() -> CategoryMapper:
    return CategoryMapper(_load("categories.yaml")["categories"])


def load_categories(data_dir: Path | None = None) -> list[dict[str, Any]]:
    return _load("categories.yaml", data_dir)["categories"]
