import pytest
import aspects as asp


def body(lon, speed=1.0):
    return {"longitude": lon, "speed": speed}


def test_orb_table_and_luminary_bonus():
    assert asp.max_orb("Trine", "Mercury", "Venus") == 8.0
    assert asp.max_orb("Trine", "Sun", "Venus") == 10.0
    assert asp.max_orb("Sextile", "Moon", "Moon") == 8.0
    assert asp.max_orb("Quincunx", "Mars", "Venus") == 3.0


def test_finds_trine_within_orb():
    found = asp.find_aspects({"Sun": body(10), "Mars": body(132, 0.5)})
    assert len(found) == 1
    a = found[0]
    assert (a["body1"], a["body2"], a["aspect"]) == ("Sun", "Mars", "Trine")
    assert a["orb"] == pytest.approx(2.0)
    assert a["max_orb"] == 10.0


def test_outside_orb_is_not_listed():
    assert asp.find_aspects({"Mercury": body(0), "Venus": body(68)}) == []


def test_quincunx_has_its_own_tight_orb():
    assert asp.find_aspects({"Mercury": body(0), "Venus": body(152)})[0]["aspect"] == "Quincunx"
    assert asp.find_aspects({"Mercury": body(0), "Venus": body(154)}) == []


def test_applying_when_separation_closes_on_exact():
    # Sun at 10 moving 1/day, Mars at 132 moving 0.5/day: separation 122 shrinking toward 120.
    a = asp.find_aspects({"Sun": body(10, 1.0), "Mars": body(132, 0.5)})[0]
    assert a["applying"] is True
    # Reverse the speeds: separation grows away from 120.
    b = asp.find_aspects({"Sun": body(10, 0.5), "Mars": body(132, 1.0)})[0]
    assert b["applying"] is False


def test_applying_is_null_without_speed():
    a = asp.find_aspects({"Sun": body(10), "Ascendant": {"longitude": 70}})[0]
    assert a["applying"] is None


def test_synastry_orbs_are_natal_minus_two():
    assert asp.max_orb("Conjunction", "Mars", "Venus", reduction=2.0) == 6.0


def test_applying_fast_pair_that_overshoots_within_an_hour():
    # Moon-speed body 0.1 short of an exact trine: approaching, even though it passes exact within the hour.
    assert asp.applying(body(0, 13.2), body(120.1, 0.0), 120) is True


def test_separating_fast_pair_just_past_exact():
    assert asp.applying(body(120.1, 13.2), body(0, 0.0), 120) is False


def test_applying_conjunction_across_the_zero_wrap():
    assert asp.applying(body(359, 1.0), body(1, 0.0), 0) is True


def test_applying_retrograde_conjunction_across_the_zero_wrap():
    assert asp.applying(body(1, -1.0), body(359, 0.0), 0) is True


def test_applying_opposition_from_either_side():
    assert asp.applying(body(179, 1.0), body(0, 0.0), 180) is True
    # delta = -179 with the first body moving slower: rel < 0, still closing on 180.
    assert asp.applying(body(0, 0.0), body(179, 1.0), 180) is True
    # Moving away from the opposition.
    assert asp.applying(body(179, 0.0), body(0, 1.0), 180) is False


def test_applying_is_null_for_equal_speeds():
    assert asp.applying(body(10, 1.0), body(130, 1.0), 120) is None


def test_applying_is_null_when_speed_is_none():
    assert asp.applying(body(10, None), body(130, 1.0), 120) is None
    assert asp.applying(body(10, 1.0), body(130, None), 120) is None
