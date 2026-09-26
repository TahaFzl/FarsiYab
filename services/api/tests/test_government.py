import io
import json
import zipfile

import httpx
import pytest

from farsiyab.adapters.government import (
    AcncAdapter,
    CraAdapter,
    IrsAdapter,
    LosAngelesAdapter,
    SireneAdapter,
    TorontoAdapter,
    UkCharityAdapter,
    VancouverAdapter,
    naf_category,
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


LONDON = CityInfo(slug="london", country="GB", name_fa="لندن", name_en="London",
                  center=(-0.13, 51.51), bbox=(-0.51, 51.29, 0.33, 51.69))
SYDNEY = CityInfo(slug="sydney", country="AU", name_fa="سیدنی", name_en="Sydney",
                  center=(151.21, -33.87), bbox=(150.60, -34.15, 151.35, -33.55))


def uk_extract(records):
    """A zip shaped like publicextract.charity.zip: a JSON array, one record per line."""
    lines = "[" + "\n,".join(json.dumps(r) for r in records) + "]"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("publicextract.charity.json", "﻿" + lines)
    return buffer.getvalue()


def uk_record(number, name, status="Registered", linked=0, postcode="W9 1SF", web=None):
    return {"registered_charity_number": number, "linked_charity_number": linked,
            "charity_name": name, "charity_registration_status": status,
            "charity_contact_address1": "1 Some Road", "charity_contact_address2": "London",
            "charity_contact_postcode": postcode, "charity_contact_web": web}


def test_uk_charities_keep_registered_main_charities_in_the_city():
    content = uk_extract([
        uk_record(1, "PARS CULTURAL CENTRE", web="www.pars.example"),
        uk_record(2, "IRANIAN COMMUNITY SERVICE", status="Removed"),  # no longer registered
        uk_record(1, "PARS CULTURAL CENTRE LONDON BRANCH", linked=1),  # a linked subsidiary
        uk_record(3, "ANGLO IRANIAN SOCIETY", postcode="BS2 0BW"),  # Bristol
        uk_record(4, "HITCHAM FREE CHURCH"),  # not Iranian
    ])
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=content)))
    geocoder = FakeGeocoder({"1 Some Road, London, W9 1SF": (51.52, -0.19),
                             "1 Some Road, London, BS2 0BW": (51.46, -2.58)})
    listings = list(UkCharityAdapter({"london": ["ENG"]}, geocoder, client).fetch(LONDON))
    assert [(x.name, x.external_id, x.urls) for x in listings] == [
        ("PARS CULTURAL CENTRE", "1", ["https://www.pars.example"]),
    ]
    assert listings[0].private_location
    assert listings[0].url.endswith("/charity-details/1")
    # The non-Iranian name was never sent to the geocoder.
    assert not any("HITCHAM" in a for a in geocoder.asked)


def test_acnc_reads_other_names_and_filters_by_state():
    csv_text = (
        "ABN,Charity_Legal_Name,Other_Organisation_Names,Address_Line_1,Town_City,State,"
        "Postcode,Charity_Website\n"
        "1,Persian Library Incorporated,,1 Station St,Harris Park,NSW,2150,persianlib.example\n"
        "2,Iranian Association Inc,Persian Language School WA,,Mount Pleasant,WA,6153,\n"
        "3,Community Care Ltd,Persian Happy Family,2 High St,Parramatta,NSW,2150,\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "package_show" in str(request.url):
            return httpx.Response(200, json={"result": {"resources": [
                {"format": "PDF", "url": "https://x/notes.pdf"},
                {"format": "CSV", "url": "https://x/datadotgov_main.csv"}]}})
        return httpx.Response(200, content=csv_text.encode())

    geocoder = FakeGeocoder({"1 Station St, Harris Park, NSW, 2150": (-33.82, 151.01),
                             "2 High St, Parramatta, NSW, 2150": (-33.81, 151.00)})
    adapter = AcncAdapter({"sydney": ["NSW"]}, geocoder,
                          httpx.Client(transport=httpx.MockTransport(handler)))
    listings = list(adapter.fetch(SYDNEY))
    assert [(x.name, x.urls) for x in listings] == [
        ("Persian Library Incorporated", ["https://persianlib.example"]),
        ("Community Care Ltd", []),  # found through its other name
    ]
    assert "Persian Happy Family" in [t.text for t in listings[1].texts]


PARIS = CityInfo(slug="paris", country="FR", name_fa="پاریس", name_en="Paris",
                 center=(2.35, 48.86), bbox=(2.00, 48.65, 2.70, 49.05))


def sirene_company(siren, name, nature="5710", diffusion="O", places=None):
    # Shape of recherche-entreprises.api.gouv.fr/search results (checked 2026-09-26).
    return {"siren": siren, "nom_complet": name, "nature_juridique": nature,
            "statut_diffusion": diffusion, "activite_principale": "56.10A",
            "matching_etablissements": places or [
                {"siret": f"{siren}00016", "activite_principale": "56.10A", "latitude": "48.845",
                 "longitude": "2.291", "etat_administratif": "A", "adresse": "Paris 15"}]}


def test_sirene_skips_sole_traders_and_keeps_open_places_in_the_box():
    companies = [
        sirene_company("111", "CHEZ MINA RESTAURANT PERSAN"),
        sirene_company("222", "SHIRAZ BAHRAMI", nature="1000"),  # entrepreneur individuel
        sirene_company("333", "ESKAN EPICERIE IRANIENNE", diffusion="P"),  # not public
        sirene_company("444", "LE PERSAN IMMOBILIER", places=[
            {"siret": "44400001", "latitude": "43.3", "longitude": "5.4",  # Marseille
             "etat_administratif": "A", "activite_principale": "68.31Z"},
            {"siret": "44400002", "latitude": "48.87", "longitude": "2.33",
             "etat_administratif": "F", "activite_principale": "68.31Z"},  # closed
        ]),
    ]
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(dict(request.url.params))
        first = request.url.params["q"] == "persian"
        return httpx.Response(200, json={"results": companies if first else [], "total_pages": 1})

    adapter = SireneAdapter({"paris": ["75"]}, httpx.Client(transport=httpx.MockTransport(handler)),
                            delay=0)
    listings = list(adapter.fetch(PARIS))
    assert [(x.name, x.external_id, x.category) for x in listings] == [
        ("CHEZ MINA RESTAURANT PERSAN", "11100016", "restaurant"),
    ]
    assert listings[0].private_location
    assert listings[0].url == "https://annuaire-entreprises.data.gouv.fr/entreprise/111"
    assert {a["departement"] for a in asked} == {"75"}
    assert {"persan", "iranien"} <= {a["q"] for a in asked}
    assert all(a["etat_administratif"] == "A" for a in asked)


def test_naf_category():
    assert naf_category("56.10A") == "restaurant"
    assert naf_category("86.23Z") == "doctor/dentist"
    assert naf_category("86.21Z") == "doctor"
    assert naf_category("01.11Z") == "other"
