"""Shared adapter interface (docs/02-architecture.md, "آداپتر سورس")."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from farsiyab.detection.detector import TextField
from farsiyab.detection.signals import Signal
from farsiyab.reference import CityInfo


class SourceUnavailable(Exception):
    """The source could not be reached; the indexer records it and moves on."""


@dataclass
class RawListing:
    """One place as a source describes it, before detection and merging."""

    source_id: str
    external_id: str
    name: str
    url: str | None = None  # link shown to users for this source
    lat: float | None = None
    lng: float | None = None
    address: str | None = None
    category: str = "other"
    phones: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)  # websites and social profiles
    texts: list[TextField] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)  # structured, source-specific
    raw: dict[str, Any] | None = None
    # Government registries often list a home address; such coordinates are used to
    # match other sources but never stored or shown (docs/07-legal-and-privacy.md).
    private_location: bool = False


class SourceAdapter(Protocol):
    id: str

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        """Every candidate place in the city's bounding box."""
        ...
