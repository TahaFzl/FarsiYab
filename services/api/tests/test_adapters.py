import asyncio
import json

import httpx
import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq
import pytest

from farsiyab.adapters.base import SourceUnavailable
from farsiyab.adapters.osm import OsmAdapter, build_query, element_to_listing
from farsiyab.adapters.overture import OvertureAdapter, latest_release, row_to_listing
from farsiyab.adapters.website import WebsiteChecker, analyse_html
from farsiyab.config import Settings
from farsiyab.detection.detector import detect, has_positive
from farsiyab.reference import CityInfo, default_mapper

TORONTO = CityInfo(
    "toronto", "CA", "تورنتو", "Toronto", (-79.38, 43.65), (-79.7, 43.55, -79.1, 43.95)
)


def overture_row(**overrides):
    row = {
        "id": "08f2b",
        "name": "Sina Persian Grill",
        "common_names": [("fa", "کباب سینا")],
        "taxonomy_hierarchy": ["food_and_drink", "restaurant", "persian_restaurant"],
        "basic_category": "restaurant",
        "websites": ["http://www.sinapersiangrill.com/"],
        "socials": ["https://www.facebook.com/470792293411166"],
        "phones": ["+14165550100"],
        "addresses": [{"freeform": "1 Yonge St", "locality": "Toronto", "region": "ON"}],
        "sources": [{"dataset": "meta"}, {"dataset": "Overture"}],
        "operating_status": "open",
        "xmin": -79.4, "xmax": -79.4, "ymin": 43.7, "ymax": 43.7,
    }
    row.update(overrides)
    return row


class TestOverture:
    def test_row_to_listing(self):
        listing = row_to_listing(overture_row(), default_mapper())
        assert listing.category == "restaurant"
        assert listing.url == "https://www.facebook.com/470792293411166"
        assert listing.address == "1 Yonge St, Toronto, ON"
        assert (listing.lat, listing.lng) == (43.7, -79.4)
        assert [s.signal for s in listing.signals] == ["overture_persian_category"]
        assert {t.text for t in listing.texts} == {"Sina Persian Grill", "کباب سینا"}
        assert listing.raw["upstream"] == ["Overture", "meta"]

    def test_website_is_the_link_when_there_is_no_facebook(self):
        listing = row_to_listing(overture_row(socials=None), default_mapper())
        assert listing.url == "http://www.sinapersiangrill.com/"

    @pytest.mark.parametrize("change", [{"operating_status": "permanently_closed"}, {"name": None}])
    def test_skipped_rows(self, change):
        assert row_to_listing(overture_row(**change), default_mapper()) is None

    def test_latest_release(self, tmp_path):
        for release in ("2026-08-19.0", "2026-09-23.0", "2026-09-23.1"):
            (tmp_path / "release" / release).mkdir(parents=True)
        assert latest_release(pafs.LocalFileSystem(), str(tmp_path)) == "2026-09-23.1"

    def test_fetch_reads_only_the_city_bbox_from_parquet(self, tmp_path):
        release_dir = tmp_path / "release" / "2026-09-23.1" / "theme=places" / "type=place"
        release_dir.mkdir(parents=True)
        schema = pa.schema([
            ("id", pa.string()),
            ("names", pa.struct([("primary", pa.string()),
                                 ("common", pa.map_(pa.string(), pa.string()))])),
            ("taxonomy", pa.struct([("primary", pa.string()),
                                    ("hierarchy", pa.list_(pa.string()))])),
            ("basic_category", pa.string()),
            ("websites", pa.list_(pa.string())),
            ("socials", pa.list_(pa.string())),
            ("phones", pa.list_(pa.string())),
            ("addresses", pa.list_(pa.struct([("freeform", pa.string()),
                                              ("locality", pa.string()),
                                              ("region", pa.string())]))),
            ("sources", pa.list_(pa.struct([("dataset", pa.string())]))),
            ("operating_status", pa.string()),
            ("bbox", pa.struct([("xmin", pa.float32()), ("xmax", pa.float32()),
                                ("ymin", pa.float32()), ("ymax", pa.float32())])),
        ])

        def place(pid, name, lng, lat):
            return {
                "id": pid, "names": {"primary": name, "common": None},
                "taxonomy": {"primary": "restaurant", "hierarchy": ["restaurant"]},
                "basic_category": "restaurant", "websites": None, "socials": None,
                "phones": None, "addresses": None, "sources": [{"dataset": "meta"}],
                "operating_status": "open",
                "bbox": {"xmin": lng, "xmax": lng, "ymin": lat, "ymax": lat},
            }

        table = pa.Table.from_pylist(
            [place("in", "Tehran Kebab", -79.4, 43.7), place("out", "Tehran Kebab", 13.4, 52.5)],
            schema=schema,
        )
        pq.write_table(table, release_dir / "part-0.parquet")

        adapter = OvertureAdapter(filesystem=pafs.LocalFileSystem(), mapper=default_mapper())
        adapter.bucket = str(tmp_path)
        listings = list(adapter.fetch(TORONTO))
        assert [x.external_id for x in listings] == ["in"]
        assert adapter.release == "2026-09-23.1"


OVERPASS_RESPONSE = {
    "elements": [
        {"type": "node", "id": 1, "lat": 43.7, "lon": -79.4,
         "tags": {"amenity": "restaurant", "name": "Shiraz Kitchen", "name:fa": "آشپزخانه شیراز",
                  "cuisine": "persian;kebab", "contact:instagram": "shirazkitchen",
                  "phone": "+1 416 555 0100", "addr:housenumber": "12", "addr:street": "Yonge St"}},
        {"type": "way", "id": 2, "center": {"lat": 43.71, "lon": -79.41},
         "tags": {"healthcare": "doctor", "name": "Dr. Ahmadi", "language:fa": "yes"}},
        {"type": "node", "id": 3, "lat": 43.72, "lon": -79.42,
         "tags": {"name": "Persian Gulf Street"}},  # not a place of business
    ]
}


class TestOsm:
    def test_query_uses_south_west_north_east(self):
        query = build_query(TORONTO.bbox)
        assert "(43.55,-79.7,43.95,-79.1)" in query
        assert '["cuisine"~"persian|iranian",i]' in query
        assert 'nwr["amenity"](43.55,-79.7,43.95,-79.1);' in query

    def test_element_to_listing(self):
        restaurant = element_to_listing(OVERPASS_RESPONSE["elements"][0], default_mapper())
        assert restaurant.category == "restaurant"
        assert restaurant.url == "https://www.openstreetmap.org/node/1"
        assert restaurant.urls == ["https://www.instagram.com/shirazkitchen"]
        assert restaurant.address == "12 Yonge St"
        assert [s.signal for s in restaurant.signals] == ["osm_cuisine_tag"]

        doctor = element_to_listing(OVERPASS_RESPONSE["elements"][1], default_mapper())
        assert (doctor.lat, doctor.category) == (43.71, "doctor")
        assert [s.signal for s in doctor.signals] == ["osm_language_fa"]

        assert element_to_listing(OVERPASS_RESPONSE["elements"][2], default_mapper()) is None

    def test_name_fa_is_a_display_name_not_evidence(self):
        # Labeled false positives: "Finley Park" / پارک فینلی, "PENNY" / پنی.
        park = element_to_listing(
            {"type": "node", "id": 9, "lat": 43.7, "lon": -79.4,
             "tags": {"leisure": "park", "amenity": "park", "name": "Finley Park",
                      "name:fa": "پارک فینلی"}},
            default_mapper(),
        )
        assert park.name == "Finley Park | پارک فینلی"
        assert "پارک فینلی" not in [t.text for t in park.texts]
        assert not has_positive(detect(park.texts, park.signals))

    def test_fetch_through_http(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["user-agent"].startswith("FarsiYabBot/")
            return httpx.Response(200, json=OVERPASS_RESPONSE)

        client = httpx.Client(transport=httpx.MockTransport(handler),
                              headers={"User-Agent": "FarsiYabBot/test"})
        listings = list(OsmAdapter(client=client).fetch(TORONTO))
        assert [x.external_id for x in listings] == ["node/1", "way/2"]

    def test_falls_back_to_the_next_instance(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "overpass-api.de":
                return httpx.Response(504)
            return httpx.Response(200, json=OVERPASS_RESPONSE)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        listings = list(OsmAdapter(client=client, retries=0).fetch(TORONTO))
        assert len(listings) == 2

    def test_errors_become_source_unavailable(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403)))
        with pytest.raises(SourceUnavailable):
            list(OsmAdapter(client=client, retries=0).fetch(TORONTO))


PERSIAN_PAGE = """<html lang="fa"><head><title>رستوران شیراز</title>
<meta name="description" content="Authentic Persian food in Toronto"></head>
<body><h1>رستوران شیراز</h1><p>کباب کوبیده، جوجه کباب و قرمه‌سبزی. ما فارسی صحبت می‌کنیم.</p>
<a href="https://www.instagram.com/shirazkitchen/">Instagram</a>
<a href="https://t.me/shiraz_kitchen">Telegram</a>
<a href="/menu">Menu</a><script>var persian = "ignored";</script></body></html>"""


def test_analyse_html():
    lang, title, signals, links = analyse_html(PERSIAN_PAGE, "https://shiraz.example/")
    assert (lang, title) == ("fa", "رستوران شیراز")
    names = {s.signal for s in signals}
    assert {"website_persian_content", "explicit_keyword", "iranian_food_terms"} <= names
    assert {(link.kind, link.value) for link in links} == {
        ("instagram", "shirazkitchen"), ("telegram", "shiraz_kitchen"),
    }


def test_english_page_without_evidence():
    _, _, signals, links = analyse_html("<html><body>Pizza and pasta</body></html>", "https://x.ca")
    assert signals == [] and links == []


class TestWebsiteChecker:
    settings = Settings(website_min_interval_seconds=0)

    def check(self, routes: dict[str, httpx.Response], url: str):
        def handler(request: httpx.Request) -> httpx.Response:
            return routes.get(str(request.url), httpx.Response(404))

        async def run():
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            checker = WebsiteChecker(client=client, settings=self.settings)
            try:
                return await checker.check(url)
            finally:
                await checker.aclose()

        return asyncio.run(run())

    def test_reads_page_when_robots_is_missing(self):
        result = self.check(
            {"https://shiraz.example/": httpx.Response(
                200, text=PERSIAN_PAGE, headers={"content-type": "text/html; charset=utf-8"})},
            "https://shiraz.example/",
        )
        assert result.ok and result.lang == "fa"
        assert any(s.signal == "website_persian_content" for s in result.signals)

    def test_respects_robots_disallow(self):
        result = self.check(
            {"https://shiraz.example/robots.txt":
                httpx.Response(200, text="User-agent: *\nDisallow: /")},
            "https://shiraz.example/",
        )
        assert (result.ok, result.reason, result.retryable) == (False, "robots", False)

    def test_server_errors_are_retryable(self):
        result = self.check(
            {"https://shiraz.example/robots.txt": httpx.Response(503)}, "https://shiraz.example/"
        )
        assert (result.reason, result.retryable) == ("robots_unreachable", True)

    def test_http_links_try_https_first(self):
        routes = {"https://shiraz.example/": httpx.Response(
            200, text=PERSIAN_PAGE, headers={"content-type": "text/html"})}
        result = self.check(routes, "http://shiraz.example/")
        assert result.ok and result.final_url == "https://shiraz.example/"
        assert result.url == "http://shiraz.example/"

    def test_falls_back_to_http_when_https_fails(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.scheme == "https":
                raise httpx.ConnectError("no TLS here")
            if request.url.path == "/robots.txt":
                return httpx.Response(404)
            return httpx.Response(200, text=PERSIAN_PAGE, headers={"content-type": "text/html"})

        async def run():
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            checker = WebsiteChecker(client=client, settings=self.settings)
            try:
                return await checker.check("http://shiraz.example/")
            finally:
                await checker.aclose()

        result = asyncio.run(run())
        assert result.ok and result.final_url == "http://shiraz.example/"

    def test_non_html_is_skipped(self):
        result = self.check(
            {"https://shiraz.example/menu.pdf": httpx.Response(
                200, content=b"%PDF", headers={"content-type": "application/pdf"})},
            "https://shiraz.example/menu.pdf",
        )
        assert result.reason == "not_html"


def test_fixture_json_is_serializable():
    json.dumps(OVERPASS_RESPONSE)
