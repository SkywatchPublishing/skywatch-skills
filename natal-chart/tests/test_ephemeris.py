import datetime as dt
from zoneinfo import ZoneInfo
import pytest
import ephemeris as eph


def test_julian_day_from_aware_datetime():
    d = dt.datetime(2000, 1, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
    assert eph.julian_day(d) == pytest.approx(2451545.0)


def test_sun_j2000_reference():
    pos = eph.body_positions(2451545.0)
    assert pos["Sun"]["longitude"] == pytest.approx(280.3689, abs=0.001)
    assert pos["Sun"]["speed"] > 0
    assert pos["Node"]["longitude"] >= 0


def test_sidereal_and_mean_node_options():
    pos = eph.body_positions(2451545.0, zodiac="sidereal", node="mean")
    assert pos["Sun"]["longitude"] == pytest.approx(256.516, abs=0.01)
    assert pos["Node"]["longitude"] == pytest.approx(125.041 - 23.857, abs=0.01)


def test_chiron_reference_or_flag():
    pos = eph.body_positions(eph.julian_day(dt.datetime(1990, 6, 15, 12, tzinfo=ZoneInfo("UTC"))))
    if eph.ephemeris_files_present():
        assert pos["Chiron"]["longitude"] == pytest.approx(106.0605, abs=0.01)
    else:
        assert "Chiron" not in pos


def test_placidus_new_york():
    jd = eph.julian_day(dt.datetime(1990, 6, 15, 12, tzinfo=ZoneInfo("UTC")))
    houses, flags = eph.houses(jd, 40.7, -74.0, "placidus")
    assert houses["system"] == "placidus"
    assert len(houses["cusps"]) == 12
    assert houses["angles"]["ascendant"] == pytest.approx(116.596, abs=0.01)
    assert houses["angles"]["mc"] == pytest.approx(10.349, abs=0.01)
    assert flags == []


def test_polar_falls_back_to_whole_sign():
    jd = eph.julian_day(dt.datetime(1990, 6, 15, 12, tzinfo=ZoneInfo("UTC")))
    houses, flags = eph.houses(jd, 70.0, 20.0, "placidus")
    assert houses["system"] == "whole_sign"
    assert houses["cusps"][0] % 30 == pytest.approx(0.0)
    assert flags == ["polar_fallback_whole_sign"]


def test_sidereal_houses_match_sidereal_planets():
    tropical, _ = eph.houses(2451545.0, 40.7, -74.0, "placidus")
    sidereal, flags = eph.houses(2451545.0, 40.7, -74.0, "placidus", zodiac="sidereal")
    assert flags == []
    assert tropical["angles"]["ascendant"] == pytest.approx(274.26, abs=0.01)
    assert sidereal["angles"]["ascendant"] == pytest.approx(250.40, abs=0.01)
    assert (tropical["angles"]["ascendant"] - sidereal["angles"]["ascendant"]) == pytest.approx(23.857, abs=0.01)
    assert (tropical["cusps"][9] - sidereal["cusps"][9]) % 360 == pytest.approx(23.857, abs=0.01)


def test_sidereal_whole_sign_cusps_use_sidereal_sign_boundaries():
    whole, _ = eph.houses(2451545.0, 40.7, -74.0, "whole_sign", zodiac="sidereal")
    asc = whole["angles"]["ascendant"]
    assert asc == pytest.approx(250.40, abs=0.01)
    assert whole["cusps"][0] % 30 == pytest.approx(0.0)
    assert whole["cusps"][0] == pytest.approx((asc // 30) * 30)


def test_sidereal_polar_falls_back_to_whole_sign():
    houses, flags = eph.houses(2451545.0, 70.0, 20.0, "placidus", zodiac="sidereal")
    assert houses["system"] == "whole_sign"
    assert houses["cusps"][0] % 30 == pytest.approx(0.0)
    assert flags == ["polar_fallback_whole_sign"]


def test_chiron_is_dropped_when_only_its_file_is_missing(monkeypatch):
    import swisseph as swe
    real = swe.calc_ut

    def fake(jd, ident, flags):
        if ident == swe.CHIRON:
            raise swe.Error("SwissEph file 'seas_18.se1' not found")
        return real(jd, ident, flags)

    monkeypatch.setattr(swe, "calc_ut", fake)
    pos = eph.body_positions(2451545.0)
    assert "Chiron" not in pos
    assert pos["Sun"]["longitude"] == pytest.approx(280.3689, abs=0.001)


def test_error_for_another_body_is_reraised(monkeypatch):
    import swisseph as swe
    real = swe.calc_ut

    def fake(jd, ident, flags):
        if ident == swe.MARS:
            raise swe.Error("boom")
        return real(jd, ident, flags)

    monkeypatch.setattr(swe, "calc_ut", fake)
    with pytest.raises(swe.Error):
        eph.body_positions(2451545.0)
