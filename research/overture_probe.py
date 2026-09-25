"""Probe Overture Maps places for Iranian-looking businesses in a bounding box.

No account or API key needed: reads the public S3 bucket anonymously.
Used to validate ADR-005 (docs/decisions/005-no-account-sources-first.md).

    pip install pyarrow
    python research/overture_probe.py --release 2026-09-23.1 --bbox=-79.64,43.58,-79.11,43.86
"""
import argparse
import collections
import re

import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.fs as fs

NAME_PATTERN = re.compile(r"(?i)persian|iranian|shiraz|tehran|isfahan|tabriz|persepolis|[پچژگ]")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    parser.add_argument("--bbox", required=True, help="west,south,east,north")
    args = parser.parse_args()
    west, south, east, north = map(float, args.bbox.split(","))

    s3 = fs.S3FileSystem(anonymous=True, region="us-west-2")
    places = ds.dataset(
        f"overturemaps-us-west-2/release/{args.release}/theme=places/type=place/",
        filesystem=s3,
        format="parquet",
    )
    in_bbox = (
        (pc.field("bbox", "xmin") > west) & (pc.field("bbox", "xmin") < east)
        & (pc.field("bbox", "ymin") > south) & (pc.field("bbox", "ymin") < north)
    )
    rows = places.to_table(
        filter=in_bbox,
        columns=["names", "taxonomy", "basic_category", "websites", "socials", "sources"],
    ).to_pylist()

    datasets = collections.Counter(s["dataset"] for r in rows for s in r["sources"] or [])
    print(f"{len(rows)} places; sources: {datasets.most_common()}")

    for r in rows:
        name = (r["names"] or {}).get("primary") or ""
        category = (r["taxonomy"] or {}).get("primary") or ""
        if NAME_PATTERN.search(name) or category == "persian_restaurant":
            print(f"{name} | {category} | {r['websites']} | {r['socials']}")


if __name__ == "__main__":
    main()
