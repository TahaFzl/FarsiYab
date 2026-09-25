import json

import httpx

from farsiyab.adapters.directories import (
    Bazaarche,
    DirectoryAdapter,
    DirectoryEntry,
    IranianBusinessCenter,
    category_for,
)
from farsiyab.detection.detector import detect, score
from tests.test_adapters import TORONTO

# Shaped like the live pages (2026-09-25).
IBC_PAGE = """<html><head><script type="application/ld+json">{"@context":"https://schema.org","@graph":[
{"@type":"LocalBusiness","name":"Shiraz Kitchen &#8211; Toronto",
 "description":"رستوران ایرانی در تورنتو با غذای اصیل ایرانی","telephone":"416-555-0100",
 "sameAs":["https://shirazkitchen.example"],
 "address":{"@type":"PostalAddress","streetAddress":"1 Yonge St, Toronto"},
 "geo":{"@type":"GeoCoordinates","latitude":43.70,"longitude":-79.40},
 "additionalType":"Restaurant"}]}</script></head>
<body><a href="https://www.instagram.com/shirazkitchen/">IG</a>
<a href="https://www.instagram.com/irbusinesscenter/">Directory IG</a>
<a href="https://www.google.com/maps/dir/?api=1&destination=1%20Yonge">map</a></body></html>"""

BAZAARCHE_PAGE = """<html><head>
<meta property="og:description" content="Immigration lawyer, Farsi speaking"></head>
<body><h1>Zandi Immigration Lawyer</h1><span itemprop="address">Vancouver</span>
<a href="https://www.google.com/maps/dir/?api=1&destination=43.763726,-79.403759">Directions</a>
<a href="https://zandimmigration.example/">Website</a><a href="tel:+14165550199">Call</a>
<a href="https://bazaarche.ca/listing/other/">Other</a></body></html>"""


def test_iranian_business_center_page():
    entry = IranianBusinessCenter().parse("https://iranianbusinesscenter.com/job/x/", IBC_PAGE)
    assert entry.name == "Shiraz Kitchen – Toronto"
    assert (entry.lat, entry.lng, entry.phone) == (43.70, -79.40, "416-555-0100")
    # The directory's own Instagram in the page chrome is not the business's.
    assert entry.links == ["https://shirazkitchen.example",
                           "https://www.instagram.com/shirazkitchen/"]
    assert category_for(entry) == "restaurant"


def test_bazaarche_page_takes_coordinates_from_the_map_link():
    entry = Bazaarche().parse("https://bazaarche.ca/listing/zandi/", BAZAARCHE_PAGE)
    assert entry.name == "Zandi Immigration Lawyer"
    assert (entry.lat, entry.lng) == (43.763726, -79.403759)
    assert entry.links == ["https://zandimmigration.example/"]
    assert entry.phone == "+14165550199"
    assert category_for(entry) == "lawyer"


def test_adapter_crawls_sitemap_respects_robots_and_caches(tmp_path):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requests.append(url)
        if url.endswith("robots.txt"):
            return httpx.Response(200, text="User-agent: *\nDisallow: /job/private/")
        if url.endswith(".xml"):
            return httpx.Response(200, text=(
                "<urlset><url><loc>https://iranianbusinesscenter.com/job/shiraz/</loc></url>"
                "<url><loc>https://iranianbusinesscenter.com/job/private/</loc></url>"
                "<url><loc>https://iranianbusinesscenter.com/about/</loc></url></urlset>"))
        return httpx.Response(200, text=IBC_PAGE)

    adapter = DirectoryAdapter(IranianBusinessCenter(),
                               httpx.Client(transport=httpx.MockTransport(handler)),
                               cache_dir=tmp_path, delay=0)
    listings = list(adapter.fetch(TORONTO))
    assert len(listings) == 1
    listing = listings[0]
    assert listing.source_id == "directory:iranianbusinesscenter"
    assert listing.url == "https://iranianbusinesscenter.com/job/shiraz/"
    found = detect(listing.texts, listing.signals)
    assert "listed_in_iranian_directory" in {s.signal for s in found}
    assert score(found) >= 0.75
    assert not any("/job/private/" in u or "/about/" in u for u in requests)

    # Second run within a week: served from the cache, no requests.
    before = len(requests)
    assert len(list(adapter.fetch(TORONTO))) == 1
    assert len(requests) == before
    cached = json.loads(adapter.cache_file.read_text())
    assert cached["entries"][0]["name"] == "Shiraz Kitchen – Toronto"


def test_entries_outside_the_city_are_skipped(tmp_path):
    adapter = DirectoryAdapter(IranianBusinessCenter(), cache_dir=tmp_path, delay=0)
    adapter.entries = lambda: [DirectoryEntry(url="u", name="New Jersey Realtor",
                                              lat=39.95, lng=-74.97)]
    assert list(adapter.fetch(TORONTO)) == []
