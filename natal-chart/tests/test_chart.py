import datetime as dt
import pytest
import chart as ch

NY = {"name": "New York City, NY, US", "latitude": 40.7143, "longitude": -74.006, "geonameid": 5128581}


def test_sign_formatting():
    assert ch.sign_of(84.1296) == ("Gemini", pytest.approx(24.1296))
    assert ch.format_degree(84.1296) == "24°08' Gemini"
    assert ch.format_degree(359.99) == "29°59' Pisces"


def test_house_of():
    cusps = [116.6, 140.1, 165.2, 190.3, 219.4, 254.3, 296.6, 320.1, 345.2, 10.3, 39.4, 74.3]
    assert ch.house_of(84.1, cusps) == 12
    assert ch.house_of(117.0, cusps) == 1
    assert ch.house_of(5.0, cusps) == 9


def test_build_chart_known_time():
    c = ch.build_chart("Test", dt.date(1990, 6, 15), dt.time(12, 0), "America/New_York", NY, "placidus")
    assert c["schema_version"] == 1
    assert c["meta"]["time_unknown"] is False
    assert c["meta"]["datetime_utc"] == "1990-06-15T16:00:00Z"
    assert c["meta"]["utc_offset"] == "-04:00"
    assert c["meta"]["zodiac"] == "tropical" and c["meta"]["node"] == "true"
    assert list(c["bodies"])[:3] == ["Sun", "Moon", "Mercury"]
    assert c["bodies"]["Sun"]["sign"] == "Gemini"
    assert c["houses"]["system"] == "placidus"
    assert 1 <= c["bodies"]["Sun"]["house"] <= 12
    assert any(a["aspect"] for a in c["aspects"])


def test_build_chart_unknown_time():
    c = ch.build_chart("Test", dt.date(1990, 6, 15), None, "America/New_York", NY, "placidus")
    assert c["meta"]["time_unknown"] is True
    assert c["meta"]["datetime_local"] == "1990-06-15T12:00:00"
    assert c["angles"] is None and c["houses"] is None
    assert c["bodies"]["Sun"]["house"] is None
    assert set(c["meta"]["flags"]) >= {"time_unknown", "moon_uncertain"}
    rng = c["meta"]["moon_range"]
    assert rng["start"] == pytest.approx(340.92, abs=0.05) and rng["end"] == pytest.approx(354.34, abs=0.05)


def test_build_chart_sidereal():
    c = ch.build_chart("Test", dt.date(2000, 1, 1), dt.time(12, 0), "UTC", NY, "placidus", zodiac="sidereal")
    assert c["meta"]["zodiac"] == "sidereal_lahiri"
    assert c["bodies"]["Sun"]["longitude"] == pytest.approx(256.516, abs=0.01)


def test_build_chart_sidereal_houses_are_sidereal():
    """The ascendant must be shifted by the ayanamsa too, not only the bodies."""
    args = ("Test", dt.date(1990, 6, 15), dt.time(12, 0), "America/New_York", NY, "placidus")
    tropical = ch.build_chart(*args)
    sidereal = ch.build_chart(*args, zodiac="sidereal")
    shift = (tropical["angles"]["ascendant"] - sidereal["angles"]["ascendant"]) % 360
    assert shift == pytest.approx(23.8, abs=0.2)
    cusp_shift = (tropical["houses"]["cusps"][0] - sidereal["houses"]["cusps"][0]) % 360
    assert cusp_shift == pytest.approx(shift, abs=0.01)
