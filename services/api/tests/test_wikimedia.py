import httpx
import pytest

from farsiyab.adapters.base import SourceUnavailable
from farsiyab.adapters.wikimedia import (
    WikidataAdapter,
    WikivoyageAdapter,
    binding_to_listing,
    build_sparql,
    category_from_types,
    find_listings,
    plain_text,
)
from farsiyab.detection.detector import detect, score
from tests.test_adapters import TORONTO

WIKITEXT = """==Eat==
* {{eat
| name=Takht-e Tavoos | alt=تخت طاووس | url=https://takhtetavoos.example/
| address=1582 Dundas St W | lat=43.6493 | long=-79.4402 | phone=+1 416-555-0101
| content=Persian café with [[Iran|Iranian]] teas, ''sholeh zard'' and live music. {{price|$$}}
}}
* {{listing|type=drink|name=Some Bar|lat=43.65|long=-79.38|content=Craft beer.}}
* {{see|name=Niagara Falls|lat=43.08|long=-79.07|content=Day trip.}}
{{Routebox|a=b}}
"""


def test_template_parsing_handles_nested_links_and_templates():
    listings = list(find_listings(WIKITEXT))
    assert [kind for kind, _ in listings] == ["eat", "drink", "see"]
    kind, params = listings[0]
    assert params["name"] == "Takht-e Tavoos"
    assert params["lat"] == "43.6493"
    assert plain_text(params["content"]) == (
        "Persian café with Iranian teas, sholeh zard and live music."
    )


def wikivoyage_client():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"].startswith("FarsiYabBot/")
        params = dict(request.url.params)
        if params.get("list") == "allpages":
            pages = [{"title": "Toronto/West End"}]
            return httpx.Response(200, json={"query": {"allpages": pages}})
        wikitext = WIKITEXT if params["page"] == "Toronto/West End" else "No listings."
        return httpx.Response(200, json={"parse": {"wikitext": wikitext}})

    return httpx.Client(transport=httpx.MockTransport(handler),
                        headers={"User-Agent": "FarsiYabBot/test"})


def test_wikivoyage_adapter_reads_district_pages_and_skips_out_of_town():
    adapter = WikivoyageAdapter({"toronto": ["Toronto"]}, client=wikivoyage_client())
    listings = list(adapter.fetch(TORONTO))
    assert [x.name for x in listings] == ["Takht-e Tavoos", "Some Bar"]  # not Niagara Falls
    cafe = listings[0]
    assert cafe.category == "restaurant"
    assert cafe.url == "https://en.wikivoyage.org/wiki/Toronto/West_End"
    assert cafe.urls == ["https://takhtetavoos.example/"]
    # "تخت طاووس" has no letter that exists only in Persian, so it is (rightly) not
    # counted as Persian script; the description carries the evidence.
    signals = {s.signal for s in detect(cafe.texts, cafe.signals)}
    assert {"explicit_keyword", "iranian_food_terms"} <= signals


BINDINGS = [
    {
        "item": {"value": "http://www.wikidata.org/entity/Q123"},
        "enLabel": {"value": "Iranian Cultural Centre of Toronto"},
        "enDesc": {"value": "community organization in Toronto, Canada"},
        "faLabel": {"value": "مرکز فرهنگی ایرانیان تورنتو"},
        "coord": {"value": "Point(-79.41 43.77)"},
        "website": {"value": "https://iccto.example/"},
        "instagram": {"value": "iccto"},
        "types": {"value": "cultural center|nonprofit organization"},
    },
    {
        # A famous place with a Persian translation: the label alone is no evidence.
        "item": {"value": "http://www.wikidata.org/entity/Q456"},
        "enLabel": {"value": "CN Tower"},
        "faLabel": {"value": "برج سی‌ان"},
        "coord": {"value": "Point(-79.3871 43.6426)"},
    },
]


def test_wikidata_binding_to_listing():
    centre = binding_to_listing(BINDINGS[0])
    assert (centre.external_id, centre.category) == ("Q123", "community")
    assert (centre.lat, centre.lng) == (43.77, -79.41)
    assert centre.urls == ["https://iccto.example/", "https://www.instagram.com/iccto/"]
    assert centre.name == "Iranian Cultural Centre of Toronto | مرکز فرهنگی ایرانیان تورنتو"
    assert score(detect(centre.texts)) >= 0.45

    tower = binding_to_listing(BINDINGS[1])
    assert detect(tower.texts) == []


def test_sparql_uses_the_city_box():
    query = build_sparql(TORONTO.bbox)
    assert '"Point(-79.7 43.55)"^^geo:wktLiteral' in query
    assert '"Point(-79.1 43.95)"^^geo:wktLiteral' in query


def test_wikidata_adapter_over_http():
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"wikibase%3Abox" in request.content or b"wikibase:box" in request.content
        return httpx.Response(200, json={"results": {"bindings": BINDINGS}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    listings = WikidataAdapter(client=client).fetch(TORONTO)
    assert [x.external_id for x in listings] == ["Q123", "Q456"]

    failing = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    with pytest.raises(SourceUnavailable):
        list(WikidataAdapter(client=failing).fetch(TORONTO))


@pytest.mark.parametrize(
    ("types", "expected"),
    [("restaurant|business", "restaurant"), ("mosque", "community"), ("skyscraper", "other")],
)
def test_category_from_types(types, expected):
    assert category_from_types(types) == expected
