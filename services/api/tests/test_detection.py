import pytest

from farsiyab.detection import script
from farsiyab.detection.detector import TextField, confidence_label, detect, score
from farsiyab.detection.signals import Signal


def signals_for(name: str, kind: str = "name") -> dict[str, float]:
    return {s.signal: s.weight for s in detect([TextField(kind, name)])}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("صرافی دیپلمات", script.Script.PERSIAN_DEFINITIVE),  # پ
        ("قومی آواز", script.Script.PERSIAN_LIKELY),  # Persian yeh, no definitive letter
        ("مكتب سلامة للمحاماة", script.Script.OTHER),  # Arabic kaf and teh marbuta
        ("افغان د چرګانو فارم", script.Script.OTHER),  # Pashto ګ despite the چ
        ("پاکستان ٹیکسی", script.Script.OTHER),  # Urdu ٹ
        ("Sina Persian Grill", script.Script.NONE),
    ],
)
def test_script_classification(text, expected):
    assert script.classify(text) is expected


def test_name_is_split_into_persian_and_latin_parts():
    name = "Diplomat Exchange | صرافی دیپلمات"
    assert script.arabic_script_part(name) == "صرافی دیپلمات"
    assert script.latin_part(name) == "Diplomat Exchange"


# Real names from the Overture test on Toronto (docs/04-iranian-detection.md).
@pytest.mark.parametrize(
    ("name", "expected_signals", "expected_label"),
    [
        ("Sina Persian Grill", {"explicit_keyword"}, "medium"),
        ("Tehran Supermarket", {"iranian_place_name"}, "low"),
        ("Diplomat Exchange | صرافی دیپلمات", {"persian_script_name"}, "medium"),
        # "Persian" describes the product, not the owner.
        ("Persian Bokhara Rug Co", {"persian_product_term"}, None),
        ("Arian Rugs Inc (Retailer of Persian antique and Tribal Rugs)",
         {"persian_product_term"}, None),
        # Shirazi is a surname here, not the city.
        ("Cars With Shirazi", {"persian_personal_name"}, None),
        # Pashto and Arabic script must not count as Persian.
        ("افغان د چرګانو فارم", set(), None),
        ("Salama Law Office مكتب سلامة للمحاماة", set(), None),
        ("California Pizza", set(), None),
        ("Kabul Afghan Kabob", {"negative_keyword"}, None),
        ("Babak Mohammadzadeh DDS", {"persian_personal_name"}, None),
        # Found in Los Angeles: words that are also names or ordinary English.
        ("Irvine Foot & Ankle: Michael Bastani, DPM", set(), None),
        ("Sohan L Dua, Facp, A Medical Corp", set(), None),
        ("Chelo's Beauty & Barber Salon", set(), None),
        ("Caspian Coast Coffee", {"iranian_place_name"}, None),
        ("Kish Mish", {"iranian_place_name"}, None),
        ("Pars Travel Agency", {"iranian_place_name"}, "low"),
        ("Alex Parsi Dds Inc", {"iranian_place_name"}, None),
        ("Chelo Kabab House", {"iranian_food_terms"}, "low"),
    ],
)
def test_real_world_names(name, expected_signals, expected_label):
    found = detect([TextField("name", name)])
    assert {s.signal for s in found} == expected_signals
    assert confidence_label(score(found)) == expected_label


def test_iranian_keyword_is_not_downgraded_by_product_nouns():
    assert "explicit_keyword" in signals_for("Iranian Carpet House")


def test_short_name_without_definitive_letters_gets_half_weight():
    assert signals_for("قومی آواز")["persian_script_name"] == pytest.approx(0.25)
    assert signals_for("صرافی دیپلمات")["persian_script_name"] == pytest.approx(0.5)


def test_text_fields_emit_text_signal_and_pages_emit_none():
    assert "persian_script_text" in signals_for("غذای اصیل ایرانی در تورنتو", kind="text")
    page = signals_for("غذای اصیل ایرانی در تورنتو", kind="page")
    assert "persian_script_text" not in page and "persian_script_name" not in page
    assert "explicit_keyword" in page


def test_negative_keywords_on_pages_only_count_in_the_head():
    body = "Persian kabab. We accept CAD, AFGHANI and USD. Turkish coffee."
    assert "negative_keyword" not in signals_for(body, kind="page")
    assert "negative_keyword" in signals_for("Kabob, Mantu & Afghan Food in Toronto",
                                             kind="page_head")


def test_foods_and_occasions():
    found = signals_for("Best koobideh and tahdig in town, Nowruz specials")
    assert {"iranian_food_terms", "nowruz_yalda_mentions"} <= set(found)


def test_persian_keyword_with_zwnj_variants():
    assert "explicit_keyword" in signals_for("دکتر فارسی‌زبان", kind="text")
    assert "explicit_keyword" in signals_for("دکتر فارسي زبان", kind="text")  # Arabic yeh


def test_one_signal_per_type_keeps_the_strongest():
    found = detect(
        [TextField("name", "قومی آواز"), TextField("name", "صرافی دیپلمات")],
    )
    assert [(s.signal, s.weight) for s in found] == [("persian_script_name", 0.5)]


def test_score_is_noisy_or_and_negatives_damp_once():
    a = Signal("explicit_keyword", 0.6, "")
    b = Signal("iranian_food_terms", 0.4, "")
    assert score([a, b]) == pytest.approx(1 - 0.4 * 0.6)
    neg = Signal("negative_keyword", 0.3, "")
    assert score([a, b, neg, neg]) == pytest.approx((1 - 0.4 * 0.6) * 0.7)
    assert score([a, Signal("explicit_keyword", 0.2, "")]) == pytest.approx(0.6)


@pytest.mark.parametrize(
    ("value", "label"),
    [(0.9, "high"), (0.75, "high"), (0.5, "medium"), (0.3, "low"), (0.2, None)],
)
def test_confidence_labels(value, label):
    assert confidence_label(value) == label


def test_urdu_heh_goal_is_not_persian():
    # Phase 4 labeling: "آئینہِ لفظ" (Urdu) was counted as a Persian-script name.
    from farsiyab.detection import script

    assert script.classify("آئینہِ لفظ") == script.Script.OTHER
    assert script.classify("آئینه") != script.Script.OTHER
