import datetime as dt
from zoneinfo import ZoneInfo

import pytest
import chart as ch

NY = {"name": "New York City, NY, US", "latitude": 40.7143, "longitude": -74.006, "geonameid": 5128581}


def test_sign_formatting():
    assert ch.sign_of(84.1296) == ("Gemini", pytest.approx(24.1296))
    assert ch.format_degree(84.1296) == "24°08' Gemini"
    assert ch.format_degree(359.99) == "29°59' Pisces"


def test_format_degree_rounds_across_sign_boundary():
    # Rounding to the nearest arc-minute happens on the whole longitude, so
    # 29°59.9994' Aries becomes 0°00' Taurus rather than the impossible "30°00' Aries".
    assert ch.format_degree(29.99999) == "0°00' Taurus"
    assert ch.format_degree(359.99999) == "0°00' Aries"
    # 29.9916° = 1799.496', which Python's round() takes down to 1799' (29°59').
    assert ch.format_degree(29.9916) == "29°59' Aries"


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


AMSTERDAM = {"name": "Amsterdam, NL", "latitude": 52.374, "longitude": 4.8897, "geonameid": 2759794}
CHICAGO = {"name": "Chicago, IL, US", "latitude": 41.85, "longitude": -87.65, "geonameid": 4887398}
# A tz database built without backzone data links Europe/Amsterdam to Europe/Brussels (+00:00 in 1900).
needs_amsterdam_lmt = pytest.mark.skipif(
    dt.datetime(1900, 1, 1, 12, tzinfo=ZoneInfo("Europe/Amsterdam")).utcoffset() != dt.timedelta(minutes=19, seconds=32),
    reason="tz database has no Amsterdam local mean time")


@pytest.mark.parametrize("date, time, tz, location, offset, utc", [
    # Local mean time before standard time carries seconds; they round to the nearest minute.
    (dt.date(1880, 3, 1), dt.time(10, 0), "America/New_York", NY, "-04:56", "1880-03-01T14:56:02Z"),  # -04:56:02
    pytest.param(dt.date(1900, 1, 1), dt.time(12, 0), "Europe/Amsterdam", AMSTERDAM, "+00:20", "1900-01-01T11:40:28Z",
                 marks=needs_amsterdam_lmt),  # +00:19:32
    (dt.date(1880, 3, 1), dt.time(10, 0), "America/Chicago", CHICAGO, "-05:51", "1880-03-01T15:50:36Z"),  # -05:50:36
    (dt.date(2024, 7, 4), dt.time(12, 0), "America/New_York", NY, "-04:00", "2024-07-04T16:00:00Z"),
])
def test_utc_offset_is_hh_mm_rounded_to_the_minute(date, time, tz, location, offset, utc):
    meta = ch.build_chart("Test", date, time, tz, location, "placidus")["meta"]
    assert meta["utc_offset"] == offset
    assert meta["datetime_utc"] == utc  # the exact instant keeps its seconds


@pytest.mark.parametrize("seconds, label", [
    (-(4 * 3600 + 59 * 60 + 30), "-05:00"),  # negative, rounds up across the hour
    (-(17 * 60 + 30), "-00:18"),  # a half minute rounds away from zero on either side
    (17 * 60 + 30, "+00:18"),
    (-20, "+00:00"),  # rounds to zero: no "-00:00"
    (5 * 3600 + 30 * 60, "+05:30"),
])
def test_format_utc_offset(seconds, label):
    assert ch.format_utc_offset(dt.timedelta(seconds=seconds)) == label


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


def test_meta_carries_chart_type_and_derivation():
    c = ch.build_chart("Test", dt.date(1990, 6, 15), dt.time(12, 0), "America/New_York", NY, "placidus")
    assert c["meta"]["chart_type"] == "natal"
    assert c["meta"]["derived_from"] == []
