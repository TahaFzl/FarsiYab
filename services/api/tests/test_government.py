import httpx
import pytest

from farsiyab.adapters.government import (
    CraAdapter,
    IrsAdapter,
    LosAngelesAdapter,
    TorontoAdapter,
    VancouverAdapter,
    naics_category,
)
from farsiyab.detection.detector import detect
from farsiyab.reference import CityInfo
from tests.test_adapters import TORONTO

LA = CityInfo("los-angeles", "US", "لس‌آنجلس", "Los Angeles", (-118.24, 34.05),
              (-118.95, 33.60, -117.65, 34.35))
VANCOUVER = CityInfo("vancouver", "CA", "ونکوور", "Vancouver", (-123.12, 49.28),
                     (-123.30, 49.00, -122.70, 49.40))


class FakeGeocoder:
    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def locate(self, address, country):
        self.asked.append(address)
        return self.answers.get(address, (None, None))


# Rows shaped like the real APIs (checked against live data, 2026-09-25).
LA_ROWS = [
    {"location_account": "1", "business_name": "SHIRAZ HOLDINGS INC", "dba_name": "SHIRAZ KITCHEN",
     "naics": "722511", "location_1": {"latitude": "34.06", "longitude": "-118.44"}},
    {"location_account": "2", "business_name": "TEHRAN MARKET LLC",
     "naics": "445110", "location_1": {"latitude": "34.07", "longitude": "-118.40"}},
    # Sole proprietor: the "business name" is a person.
    {"location_account": "3", "business_name": "YALDA YAZDANPANAH", "naics": "541990"},
    {"location_account": "4", "business_name": "ZAGROS CONSTRUCTION INC", "naics": "236118",
     "location_1": {"latitude": "0", "longitude": "0"}},
]


def test_los_angeles_rows():
    listings = [LosAngelesAdapter.to_listing(r) for r in LA_ROWS]
    assert [x.name if x else None for x in listings] == [
        "SHIRAZ KITCHEN", "TEHRAN MARKET LLC", None, "ZAGROS CONSTRUCTION INC",
    ]
    kitchen, market, _, zagros = listings
    assert (kitchen.category, market.category) == ("restaurant", "grocery")
    assert kitchen.private_location and kitchen.lat == 34.06
    assert zagros.lat is None  # 0,0 means "no location" in this dataset


def test_los_angeles_paginates():
    pages = [[{"location_account": str(i), "dba_name": "PERSIAN CAFE"} for i in range(2)], []]

    def handler(request: httpx.Request) -> httpx.Response:
        assert "upper(dba_name) like '%PERSIAN%'" in request.url.params["$where"]
        return httpx.Response(200, json=pages.pop(0))

    adapter = LosAngelesAdapter(httpx.Client(transport=httpx.MockTransport(handler)), page_size=2)
    assert len(list(adapter.fetch(LA))) == 2
    assert list(adapter.fetch(TORONTO)) == []  # other cities: nothing, no request


@pytest.mark.parametrize(
    ("code", "slug"),
    [("722513", "restaurant"), ("621210", "doctor/dentist"), ("621111", "doctor"),
     ("541110", "lawyer"), ("813110", "community"), ("236118", "other"), (None, "other")],
)
def test_naics(code, slug):
    assert naics_category(code) == slug


def test_vancouver_keeps_latest_year_and_never_uses_a_persons_name():
    rows = [
        {"businesstradename": "Cazba Persian Grill", "businessname": "Cazba Corp",
         "businesstype": "Limited Service Food Establishment", "folderyear": "25",
         "house": "100", "street": "W GEORGIA ST", "geo_point_2d": {"lat": 49.28, "lon": -123.12}},
        {"businesstradename": "Cazba Persian Grill", "businessname": "Cazba Corp",
         "businesstype": "Restaurant", "folderyear": "26",
         "house": "100", "street": "W GEORGIA ST", "geo_point_2d": {"lat": 49.28, "lon": -123.12}},
        {"businesstradename": None, "businessname": "(Jafar Feizollahi)",
         "businesstype": "Trade Contractor", "folderyear": "26", "house": "1", "street": "X ST"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert 'status="Issued"' in request.url.params["where"]
        return httpx.Response(200, json={"total_count": len(rows), "results": rows})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    listings = list(VancouverAdapter(client).fetch(VANCOUVER))
    assert [(x.name, x.category, x.raw["year"]) for x in listings] == [
        ("Cazba Persian Grill", "restaurant", "26"),
    ]


TORONTO_CSV = "\n".join([
    "_id,Category,Licence No.,Operating Name,Issued,Client Name,Business Phone,"
    "Licence Address Line 1,Licence Address Line 2,Licence Address Line 3,Cancel Date",
    '1,EATING ESTABLISHMENT,B1,TEHRAN KABOB HOUSE,2020-01-01,SOMEONE,416-555-0100,'
    '1 YONGE ST,"TORONTO, ON",M5E 1A1,',
    '2,EATING ESTABLISHMENT,B2,PIZZA PALACE,2020-01-01,X,,2 YONGE ST,"TORONTO, ON",M5E 1A1,',
    '3,EATING ESTABLISHMENT,B3,SHIRAZ GRILL,2019-01-01,Y,,3 YONGE ST,"TORONTO, ON",M5E 1A1,'
    "2021-01-01",
]) + "\n"


def test_toronto_csv():
    def handler(request: httpx.Request) -> httpx.Response:
        if "package_show" in str(request.url):
            return httpx.Response(200, json={"result": {"resources": [
                {"format": "CSV", "datastore_active": True, "url": "https://x/old.csv",
                 "last_modified": "2022-12-01"},
                {"format": "CSV", "datastore_active": False, "url": "https://x/new.csv",
                 "last_modified": "2026-09-25"},
            ]}})
        assert str(request.url) == "https://x/new.csv"
        return httpx.Response(200, text=TORONTO_CSV)

    geocoder = FakeGeocoder({"1 YONGE ST, TORONTO, ON, M5E 1A1": (43.64, -79.37)})
    adapter = TorontoAdapter(geocoder, httpx.Client(transport=httpx.MockTransport(handler)))
    listings = list(adapter.fetch(TORONTO))
    assert [(x.name, x.category, x.phones, x.lat) for x in listings] == [
        ("TEHRAN KABOB HOUSE", "restaurant", ["416-555-0100"], 43.64),
    ]
    assert geocoder.asked == ["1 YONGE ST, TORONTO, ON, M5E 1A1"]  # not the pizza place


IRS_CSV = """EIN,NAME,ICO,STREET,CITY,STATE,ZIP,NTEE_CD
010711594,JEWISH OUTREACH IRANIAN NETWORK,% SOMEONE,1600 REXFORD DR,LOS ANGELES,CA,90035-3112,T99
061754103,IRANIAN CULTURE AND ART CLUB,% SOMEONE,8366 N RAISINA AVE,FRESNO,CA,93720-2083,A23
111111111,PERSIAN SCHOOL OF LA,,1 MAIN ST,LOS ANGELES,CA,90001,B20
222222222,FRIENDS OF THE PARK,,2 MAIN ST,LOS ANGELES,CA,90001,
"""


def test_irs_filters_geocodes_and_drops_out_of_town():
    geocoder = FakeGeocoder({
        "1600 REXFORD DR, LOS ANGELES, CA 90035": (34.05, -118.39),
        "8366 N RAISINA AVE, FRESNO, CA 93720": (36.84, -119.79),  # outside LA
        "1 MAIN ST, LOS ANGELES, CA 90001": (34.0, -118.25),
    })

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pub/irs-soi/eo_ca.csv"
        return httpx.Response(200, text=IRS_CSV)

    adapter = IrsAdapter({"los-angeles": ["CA"]}, geocoder,
                         httpx.Client(transport=httpx.MockTransport(handler)))
    listings = list(adapter.fetch(LA))
    assert [(x.name, x.category) for x in listings] == [
        ("JEWISH OUTREACH IRANIAN NETWORK", "community"),
        ("PERSIAN SCHOOL OF LA", "education"),
    ]
    assert all("SOMEONE" not in str(x.raw) for x in listings)  # ICO is never kept
    assert len(geocoder.asked) == 3  # the park was never geocoded


CRA_CSV = "﻿BN,Category,Legal Name,Account Name,Address Line 1,City,Province,Postal Code\n" \
    "870749777RR0001,0010,TORONTO FARSI SCHOOL,TORONTO FARSI SCHOOL,204 - 5635 YONGE ST," \
    "NORTH YORK,ON,M2M3S9\n" \
    "765729066RR0001,0160,International Federation of Iranian Refugees,International " \
    "Federation of Iranian Refugees,232 - 71 2ND AVE W,VANCOUVER,BC,V5Y0J7\n"


def test_cra_uses_newest_identification_file_and_province():
    def handler(request: httpx.Request) -> httpx.Response:
        if "package_search" in str(request.url):
            return httpx.Response(200, json={"result": {"results": [
                {"title": {"en": "2023 List of charities"}, "resources": [
                    {"name": {"en": "Identification"}, "url": "https://x/2023.csv"}]},
                {"title": {"en": "2024 List of charities"}, "resources": [
                    {"name": {"en": "Codes Lists"}, "url": "https://x/codes.pdf"},
                    {"name": {"en": "Identification"}, "url": "/data/2024.csv"}]},
            ]}})
        assert str(request.url) == "https://open.canada.ca/data/2024.csv"
        return httpx.Response(200, content=CRA_CSV.encode())

    geocoder = FakeGeocoder({"204 - 5635 YONGE ST, NORTH YORK, ON, M2M3S9": (43.78, -79.42)})
    adapter = CraAdapter({"toronto": ["ON"]}, geocoder,
                         httpx.Client(transport=httpx.MockTransport(handler)))
    listings = list(adapter.fetch(TORONTO))
    assert [(x.name, x.category, x.external_id) for x in listings] == [
        ("TORONTO FARSI SCHOOL", "education", "870749777RR0001"),
    ]


def test_iran_alone_is_only_a_weak_hint():
    found = detect(LosAngelesAdapter.to_listing(
        {"location_account": "9", "dba_name": "IRAN GARCIA MUSIC"}).texts)
    assert [(s.signal, s.weight) for s in found] == [("iranian_place_name", 0.15)]


@pytest.mark.parametrize(
    ("address", "cleaned", "code"),
    [
        ("879 YORK MILLS RD, #3, TORONTO, ON, M3B 1Y5", "879 YORK MILLS RD, TORONTO, ON, M3B 1Y5",
         "M3B 1Y5"),
        ("204 - 5635 YONGE ST, NORTH YORK, ON, M2M3S9", "5635 YONGE ST, NORTH YORK, ON, M2M3S9",
         "M2M3S9"),
        ("6009 YONGE ST, B, TORONTO, ON, M2M 3W2", "6009 YONGE ST, TORONTO, ON, M2M 3W2",
         "M2M 3W2"),
        ("8050 N PALM AVE STE 300, FRESNO, CA 93711", "8050 N PALM AVE, FRESNO, CA 93711",
         "93711"),
    ],
)
def test_address_cleaning(address, cleaned, code):
    from farsiyab.geocode import clean_address, postal_code

    assert clean_address(address) == cleaned
    assert postal_code(address) == code
