"""Overture Maps places (docs/sources/overture-maps.md).

Reads the public GeoParquet release anonymously from S3; only the row groups
inside the city's bounding box are downloaded (HTTP range requests).
"""

import logging
from collections.abc import Iterator
from typing import Any

import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.fs as pafs

from farsiyab.adapters.base import RawListing, SourceUnavailable
from farsiyab.config import get_settings
from farsiyab.detection.detector import TextField
from farsiyab.detection.signals import make
from farsiyab.links import social_link
from farsiyab.reference import CategoryMapper, CityInfo, default_mapper

log = logging.getLogger(__name__)

PERSIAN_TAXONOMY = "persian_restaurant"
CLOSED_STATUSES = {"permanently_closed"}

COLUMNS = {
    "id": pc.field("id"),
    "name": pc.field("names", "primary"),
    "common_names": pc.field("names", "common"),
    "taxonomy_hierarchy": pc.field("taxonomy", "hierarchy"),
    "basic_category": pc.field("basic_category"),
    "websites": pc.field("websites"),
    "socials": pc.field("socials"),
    "phones": pc.field("phones"),
    "addresses": pc.field("addresses"),
    "sources": pc.field("sources"),
    "operating_status": pc.field("operating_status"),
    "xmin": pc.field("bbox", "xmin"),
    "ymin": pc.field("bbox", "ymin"),
    "xmax": pc.field("bbox", "xmax"),
    "ymax": pc.field("bbox", "ymax"),
}


def latest_release(filesystem: pafs.FileSystem, bucket: str) -> str:
    infos = filesystem.get_file_info(pafs.FileSelector(f"{bucket}/release/"))
    releases = sorted(
        info.base_name for info in infos if info.type == pafs.FileType.Directory
    )
    if not releases:
        raise SourceUnavailable("no Overture releases found")
    return releases[-1]


def _common_names(value: Any) -> list[str]:
    # A parquet map comes back as a list of (key, value) tuples, or as a dict.
    if not value:
        return []
    items = value.items() if isinstance(value, dict) else value
    return [v for _, v in items if v]


def _address(addresses: list[dict[str, Any]] | None) -> str | None:
    if not addresses:
        return None
    first = addresses[0]
    parts = [first.get("freeform"), first.get("locality"), first.get("region")]
    return ", ".join(p for p in parts if p) or None


def row_to_listing(row: dict[str, Any], mapper: CategoryMapper) -> RawListing | None:
    name = row.get("name")
    if not name or row.get("operating_status") in CLOSED_STATUSES:
        return None

    urls = [u for u in (row.get("socials") or []) + (row.get("websites") or []) if u]
    social_links = [link for link in map(social_link, urls) if link]
    facebook = next((link.url for link in social_links if link.kind == "facebook"), None)
    website = next((u for u in row.get("websites") or [] if u and not social_link(u)), None)
    display_url = facebook or website

    hierarchy = row.get("taxonomy_hierarchy") or []
    texts = [TextField("name", name, display_url)]
    texts += [TextField("name", n, display_url) for n in _common_names(row.get("common_names"))]
    texts += [
        TextField("username", link.value, link.url)
        for link in social_links
        if link.kind == "instagram"
    ]
    signals = []
    if PERSIAN_TAXONOMY in hierarchy:
        snippet = f"taxonomy: {PERSIAN_TAXONOMY}"
        signals.append(make("overture_persian_category", snippet, display_url))

    lng = (row["xmin"] + row["xmax"]) / 2 if row.get("xmin") is not None else None
    lat = (row["ymin"] + row["ymax"]) / 2 if row.get("ymin") is not None else None
    upstream = sorted({s.get("dataset") for s in row.get("sources") or [] if s.get("dataset")})

    return RawListing(
        source_id="overture",
        external_id=row["id"],
        name=name,
        url=display_url,
        lat=lat,
        lng=lng,
        address=_address(row.get("addresses")),
        category=mapper.overture(hierarchy, row.get("basic_category")),
        phones=[p for p in row.get("phones") or [] if p],
        urls=urls,
        texts=texts,
        signals=signals,
        raw={
            "id": row["id"],
            "name": name,
            "taxonomy": hierarchy,
            "basic_category": row.get("basic_category"),
            "websites": row.get("websites"),
            "socials": row.get("socials"),
            "phones": row.get("phones"),
            "upstream": upstream,
        },
    )


class OvertureAdapter:
    id = "overture"

    def __init__(
        self,
        release: str | None = None,
        filesystem: pafs.FileSystem | None = None,
        mapper: CategoryMapper | None = None,
    ) -> None:
        settings = get_settings()
        self.bucket = settings.overture_bucket
        self.filesystem = filesystem or pafs.S3FileSystem(
            anonymous=True, region=settings.overture_region
        )
        self.release = release or settings.overture_release or None
        self.mapper = mapper or default_mapper()

    def resolve_release(self) -> str:
        if not self.release:
            try:
                self.release = latest_release(self.filesystem, self.bucket)
            except OSError as exc:
                raise SourceUnavailable(f"cannot list Overture releases: {exc}") from exc
        return self.release

    def fetch(self, city: CityInfo) -> Iterator[RawListing]:
        release = self.resolve_release()
        west, south, east, north = city.bbox
        path = f"{self.bucket}/release/{release}/theme=places/type=place/"
        log.info("overture: reading %s for %s", release, city.slug)
        try:
            dataset = ds.dataset(path, filesystem=self.filesystem, format="parquet")
            in_bbox = (
                (pc.field("bbox", "xmin") >= west)
                & (pc.field("bbox", "xmax") <= east)
                & (pc.field("bbox", "ymin") >= south)
                & (pc.field("bbox", "ymax") <= north)
            )
            for batch in dataset.to_batches(columns=COLUMNS, filter=in_bbox):
                for row in batch.to_pylist():
                    listing = row_to_listing(row, self.mapper)
                    if listing:
                        yield listing
        except OSError as exc:
            raise SourceUnavailable(f"cannot read Overture release {release}: {exc}") from exc
