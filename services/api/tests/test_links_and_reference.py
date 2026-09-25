import pytest

from farsiyab.links import classify_url, phone_link, social_link, website_link
from farsiyab.reference import default_mapper, load_cities, load_regions, load_sources


@pytest.mark.parametrize(
    ("url", "kind", "value"),
    [
        ("https://www.Instagram.com/ShirazKitchen/?hl=en", "instagram", "shirazkitchen"),
        ("instagram.com/lmlawcpa.persian", "instagram", "lmlawcpa.persian"),
        ("https://www.instagram.com/p/Cx123/", None, None),
        ("https://www.facebook.com/470792293411166", "facebook", "470792293411166"),
        ("https://m.facebook.com/ShirazKitchenTO/", "facebook", "shirazkitchento"),
        ("https://www.facebook.com/profile.php?id=100064", "facebook", "100064"),
        ("https://www.facebook.com/pages/Shiraz/12345", "facebook", "12345"),
        ("https://www.facebook.com/sharer/sharer.php?u=x", None, None),
        ("https://t.me/tehran_market", "telegram", "tehran_market"),
        ("https://t.me/joinchat/AAAA", None, None),
        ("https://www.sinapersiangrill.com/menu", None, None),
    ],
)
def test_social_links(url, kind, value):
    link = social_link(url)
    assert (link.kind, link.value) == (kind, value) if kind else link is None


def test_website_links_skip_directories_but_keep_agent_subdomains():
    assert website_link("http://yp.ca/bus/101343761") is None
    assert website_link("https://www.homestars.com/companies/1") is None
    link = website_link("http://www.monasadatshirazi.royallepage.ca/")
    assert link.value == "monasadatshirazi.royallepage.ca"
    assert website_link("https://WWW.Ghazale.ca") .value == "ghazale.ca"


def test_pages_on_shared_sites_keep_their_path():
    # Hamburg: two unrelated businesses listed pages on the same directory site.
    assert website_link("https://www.gelbeseiten.de/gsbiz/1a98d1c3") is None
    a = website_link("https://www.example-directory.com/biz/1a98d1c3-97e6")
    b = website_link("https://www.example-directory.com/biz/3931d73c-0d3f")
    assert a.value != b.value
    assert website_link("https://ghazale.ca/menu").value == "ghazale.ca"
    assert website_link("https://ghazale.ca/fa/").value == "ghazale.ca"


def test_classify_url_prefers_social_profiles():
    assert classify_url("https://www.facebook.com/tehranchisepehr").kind == "facebook"
    assert classify_url("https://persiandesignerrugs.ca/").kind == "website"


def test_phone_numbers_become_e164():
    assert phone_link("(647) 350-5581", "CA").value == "+16473505581"
    assert phone_link("040 1234567", "DE").value == "+49401234567"
    assert phone_link("not a phone", "CA") is None


# Real Overture hierarchies from Toronto (release 2026-09-23.1).
@pytest.mark.parametrize(
    ("hierarchy", "basic", "expected"),
    [
        (["food_and_drink", "restaurant", "middle_eastern_restaurant", "persian_restaurant"],
         "restaurant", "restaurant"),
        (["health_care", "dental_clinic", "general_dentistry"], "dental_clinic", "doctor/dentist"),
        (["services_and_business", "legal_service", "immigration_law"], "attorney_or_law_firm",
         "lawyer"),
        (["shopping", "food_and_beverage_store", "bakery"], "food_and_beverage_store", "bakery"),
        (["shopping", "food_and_beverage_store", "grocery_store"], "food_and_beverage_store",
         "grocery"),
        (["shopping", "vehicle_dealer", "auto_dealer"], "auto_dealer", "other"),
        ([], "real_estate_service", "real_estate"),
        (None, None, "other"),
    ],
)
def test_overture_category_mapping(hierarchy, basic, expected):
    assert default_mapper().overture(hierarchy, basic) == expected


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"amenity": "restaurant", "cuisine": "persian"}, "restaurant"),
        ({"amenity": "dentist"}, "doctor/dentist"),
        ({"healthcare": "doctor"}, "doctor"),
        ({"shop": "bakery"}, "bakery"),
        ({"shop": "hairdresser;beauty"}, "beauty"),
        ({"tourism": "hotel"}, "other"),
    ],
)
def test_osm_category_mapping(tags, expected):
    assert default_mapper().osm(tags) == expected


def test_city_bounding_boxes_are_sane():
    cities = load_cities()
    assert len(cities) == 10
    for c in cities:
        west, south, east, north = c.bbox
        assert west < c.center[0] < east and south < c.center[1] < north, c.slug


def test_source_registry_is_consistent():
    sources = load_sources()
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids))
    for s in sources:
        assert s["status"] in {"mvp", "planned", "candidate", "optional", "deferred", "rejected"}
        # ADR-005: nothing before phase 6 may need an account.
        assert not s["account_required"] or s["phase"] == 6, s["id"]


def test_regions_are_strings():
    # Unquoted, YAML reads ON (Ontario) as the boolean true.
    regions = load_regions()
    assert regions["toronto"] == ["ON"] and regions["washington-dc"] == ["DC", "MD", "VA"]
    assert all(isinstance(r, str) for rs in regions.values() for r in rs)
