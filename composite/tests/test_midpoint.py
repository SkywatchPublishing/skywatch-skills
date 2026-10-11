import json
import math
from pathlib import Path
import pytest
import swisseph as swe
import composite as cp

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"
PARTNER = Path(__file__).resolve().parents[2] / "synastry" / "examples" / "chart_b.json"


def test_short_arc_midpoint():
    assert cp.midpoint(350.0, 10.0) == pytest.approx(0.0)
    assert cp.midpoint(10.0, 350.0) == pytest.approx(0.0)
    assert cp.midpoint(0.0, 180.0) in (pytest.approx(90.0), pytest.approx(270.0))
    assert cp.midpoint(100.0, 140.0) == pytest.approx(120.0)


def test_armc_from_mc_reproduces_swisseph_houses():
    jd = swe.julday(1990, 6, 15, 16.0)
    cusps, ascmc = swe.houses(jd, 40.7143, -74.006, b"P")
    eps = cp.obliquity(jd)
    houses = cp.houses_from_mc(ascmc[1], 40.7143, eps, "placidus")
    assert houses["angles"]["ascendant"] == pytest.approx(ascmc[0], abs=1e-3)
    assert houses["cusps"][1] == pytest.approx(cusps[1], abs=1e-3)


def test_self_composite_is_identity():
    a = json.loads(EXAMPLE.read_text())
    c = cp.midpoint_chart(a, a, reference=a["meta"]["location"], house_system="placidus")
    for name, body in a["bodies"].items():
        assert c["bodies"][name]["longitude"] == pytest.approx(body["longitude"], abs=1e-3)
    assert c["angles"]["mc"] == pytest.approx(a["angles"]["mc"], abs=1e-3)
    assert c["angles"]["ascendant"] == pytest.approx(a["angles"]["ascendant"], abs=0.05)
    assert c["meta"]["chart_type"] == "composite" and c["meta"]["derived_from"] == ["Example", "Example"]
    assert all(x["applying"] is None for x in c["aspects"])


def test_untimed_side_drops_houses():
    a = json.loads(EXAMPLE.read_text()); b = json.loads(PARTNER.read_text())
    b["meta"]["time_unknown"] = True; b["angles"] = None; b["houses"] = None
    c = cp.midpoint_chart(a, b, reference=a["meta"]["location"], house_system="placidus")
    assert c["angles"] is None and c["houses"] is None
    assert {"time_unknown", "moon_uncertain"} <= set(c["meta"]["flags"])
