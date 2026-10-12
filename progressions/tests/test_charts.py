import datetime as dt
import json
from pathlib import Path

import pytest
import progressions as pg

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"


@pytest.fixture
def natal():
    return json.loads(EXAMPLE.read_text())


def at(natal, y, m, d):
    return pg.target_jd(dt.date(y, m, d), natal["meta"]["timezone"])


def test_progressed_chart_example(natal):
    p = pg.progressed_chart(natal, at(natal, 2027, 6, 15))
    assert p["schema_version"] == 1
    assert p["meta"]["chart_type"] == "secondary_progressed"
    assert p["meta"]["derived_from"] == ["Example"]
    prog = p["meta"]["progression"]
    assert prog["target_date"] == "2027-06-15" and prog["angles_method"] == "solar-arc"
    assert prog["age_years"] == pytest.approx(37.0001, abs=1e-4)
    assert prog["solar_arc"] == pytest.approx(35.2991, abs=1e-3)
    assert p["bodies"]["Sun"]["formatted"] == "29°35' Cancer"
    assert p["bodies"]["Moon"]["formatted"] == "6°48' Leo"
    assert p["meta"]["datetime_local"] == natal["meta"]["datetime_local"]
    for b in p["bodies"].values():
        assert b["house"] == pg.house_of(b["longitude"], p["houses"]["cusps"])


def test_directed_chart_moves_everything_by_the_arc(natal):
    d = pg.directed_chart(natal, at(natal, 2027, 6, 15))
    arc = d["meta"]["progression"]["solar_arc"]
    assert d["meta"]["chart_type"] == "solar_arc_directed"
    assert d["meta"]["progression"]["angles_method"] is None
    for n, b in natal["bodies"].items():
        assert abs(pg.wrapped(d["bodies"][n]["longitude"] - (b["longitude"] + arc))) < 1e-3
        assert d["bodies"][n]["house"] == b["house"]
    for k in ("ascendant", "mc"):
        assert abs(pg.wrapped(d["angles"][k] - (natal["angles"][k] + arc))) < 1e-3
    assert all(a["applying"] is None for a in d["aspects"])


def test_solar_arc_angles_make_progressed_mc_equal_directed_mc(natal):
    t = at(natal, 2027, 6, 15)
    assert pg.progressed_chart(natal, t)["angles"]["mc"] == pytest.approx(pg.directed_chart(natal, t)["angles"]["mc"], abs=1e-3)


def test_identity_at_birth(natal):
    bj = natal["meta"]["julian_day_ut"]
    p, d = pg.progressed_chart(natal, bj), pg.directed_chart(natal, bj)
    for n, b in natal["bodies"].items():
        assert abs(pg.wrapped(p["bodies"][n]["longitude"] - b["longitude"])) < 1e-3
        assert abs(pg.wrapped(d["bodies"][n]["longitude"] - b["longitude"])) < 1e-3
    assert d["meta"]["progression"]["solar_arc"] == pytest.approx(0.0, abs=1e-6)


def test_untimed_natal(natal):
    natal["angles"] = None; natal["houses"] = None; natal["meta"]["time_unknown"] = True
    for chart in (pg.progressed_chart(natal, at(natal, 2027, 6, 15)), pg.directed_chart(natal, at(natal, 2027, 6, 15))):
        assert chart["angles"] is None and chart["houses"] is None
        assert chart["meta"]["progression"]["angles_method"] is None
        assert all(b["house"] is None for b in chart["bodies"].values())


def test_missing_chiron_stays_missing(natal):
    del natal["bodies"]["Chiron"]
    assert "Chiron" not in pg.progressed_chart(natal, at(natal, 2027, 6, 15))["bodies"]
