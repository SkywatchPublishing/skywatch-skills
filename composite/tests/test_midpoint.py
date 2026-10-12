import json
import math
import subprocess
import sys
from pathlib import Path
import pytest
import swisseph as swe
import composite as cp

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"
PARTNER = Path(__file__).resolve().parents[2] / "synastry" / "examples" / "chart_b.json"
NATAL = Path(__file__).resolve().parents[2] / "natal-chart" / "scripts" / "natal_chart.py"


def test_short_arc_midpoint():
    assert cp.midpoint(350.0, 10.0) == pytest.approx(0.0)
    assert cp.midpoint(10.0, 350.0) == pytest.approx(0.0)
    # An exactly antipodal pair has no shorter arc; the tie goes to min + 90 whichever order.
    assert cp.midpoint(0.0, 180.0) == pytest.approx(90.0)
    assert cp.midpoint(180.0, 0.0) == pytest.approx(90.0)
    assert cp.midpoint(270.0, 90.0) == pytest.approx(180.0)
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


def test_midpoint_records_requested_house_system():
    a = json.loads(EXAMPLE.read_text()); b = json.loads(PARTNER.read_text())
    c = cp.midpoint_chart(a, b, reference=a["meta"]["location"], house_system="koch")
    assert c["meta"]["house_system"] == c["meta"]["house_system_requested"] == "koch"
    b["meta"]["time_unknown"] = True; b["angles"] = None; b["houses"] = None
    c = cp.midpoint_chart(a, b, reference=a["meta"]["location"], house_system="koch")
    assert c["meta"]["house_system"] is None
    assert c["meta"]["house_system_requested"] == "koch"


def test_pair_composite_houses_and_symmetry():
    a = json.loads(EXAMPLE.read_text()); b = json.loads(PARTNER.read_text())
    c = cp.midpoint_chart(a, b, reference=a["meta"]["location"], house_system="placidus")
    cusps = c["houses"]["cusps"]
    for body in c["bodies"].values():
        assert body["house"] == cp.house_of(body["longitude"], cusps)
    asc_after_mc = (c["angles"]["ascendant"] - c["angles"]["mc"]) % 360
    assert 0 < asc_after_mc < 180
    d = cp.midpoint_chart(b, a, reference=a["meta"]["location"], house_system="placidus")
    for name in c["bodies"]:
        assert d["bodies"][name]["longitude"] == pytest.approx(c["bodies"][name]["longitude"], abs=1e-6)
    assert d["houses"]["cusps"] == pytest.approx(cusps, abs=1e-6)


def _pair():
    return json.loads(EXAMPLE.read_text()), json.loads(PARTNER.read_text())


def _zodiac_mismatch():
    a, b = _pair(); b["meta"]["zodiac"] = "sidereal"; return a, b


def _node_mismatch():
    a, b = _pair(); b["meta"]["node"] = "mean"; return a, b


def _untimed_b():
    a, b = _pair(); b["meta"]["time_unknown"] = True; b["angles"] = None; b["houses"] = None; return a, b


def _no_chiron_b():
    a, b = _pair(); del b["bodies"]["Chiron"]; return a, b


@pytest.mark.parametrize("make, expect", [
    (_zodiac_mismatch, ValueError),
    (_node_mismatch, ValueError),
    (_untimed_b, "untimed"),
    (_no_chiron_b, "chiron_unavailable"),
])
def test_mismatches_and_flags(make, expect):
    a, b = make()
    if expect is ValueError:
        with pytest.raises(ValueError):
            cp.midpoint_chart(a, b, reference=a["meta"]["location"], house_system="placidus")
        return
    c = cp.midpoint_chart(a, b, reference=a["meta"]["location"], house_system="placidus")
    if expect == "untimed":
        assert c["bodies"]["Moon"]["house"] is None and c["meta"]["moon_range"] is None
    else:
        assert "Chiron" not in c["bodies"] and "chiron_unavailable" in c["meta"]["flags"]


@pytest.fixture(scope="module")
def cast_pairs(tmp_path_factory):
    """The two example births cast through natal-chart in each zodiac: {zodiac: (a, b)}."""
    tmp = tmp_path_factory.mktemp("zodiacs")
    pairs = {}
    for zodiac in ("tropical", "sidereal"):
        charts = []
        for src in (EXAMPLE, PARTNER):
            meta = json.loads(src.read_text())["meta"]
            date, time = meta["datetime_local"].split("T")
            loc = meta["location"]
            out = tmp / f"{meta['name']}_{zodiac}.json"
            subprocess.run([sys.executable, "-I", str(NATAL), "--name", meta["name"], "--date", date,
                            "--time", time, "--lat", str(loc["latitude"]), "--lon", str(loc["longitude"]),
                            "--tz", meta["timezone"], "--zodiac", zodiac,
                            "--out", str(out), "--grid", str(out.with_suffix(".md"))],
                           check=True, capture_output=True)
            charts.append(json.loads(out.read_text()))
        pairs[zodiac] = tuple(charts)
    return pairs


@pytest.mark.parametrize("system, latitude", [
    ("placidus", None),
    ("whole_sign", None),
    ("placidus", 75.0),  # polar: falls back to whole sign
])
def test_sidereal_composite_houses_are_tropical_minus_ayanamsa(cast_pairs, system, latitude):
    (ta, tb), (sa, sb) = cast_pairs["tropical"], cast_pairs["sidereal"]
    reference = dict(ta["meta"]["location"])
    if latitude is not None:
        reference["latitude"] = latitude
    t = cp.midpoint_chart(ta, tb, reference=reference, house_system=system)
    s = cp.midpoint_chart(sa, sb, reference=reference, house_system=system)
    assert s["meta"]["zodiac"] == "sidereal_lahiri"
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    aya = swe.get_ayanamsa_ex_ut(s["meta"]["julian_day_ut"], swe.FLG_SWIEPH)[1]
    assert cp.separation(s["bodies"]["Sun"]["longitude"], t["bodies"]["Sun"]["longitude"] - aya) < 0.01
    for key in ("mc", "ascendant"):
        assert cp.separation(s["angles"][key], t["angles"][key] - aya) < 0.01, key
    assert s["houses"]["system"] == t["houses"]["system"]
    if latitude is not None:
        assert "polar_fallback_whole_sign" in s["meta"]["flags"]
    cusps = s["houses"]["cusps"]
    if s["houses"]["system"] == "whole_sign":
        assert all(c % 30 == 0 for c in cusps), cusps
        assert cusps[0] == s["angles"]["ascendant"] // 30 * 30
    else:
        for ct, cs in zip(t["houses"]["cusps"], cusps):
            assert cp.separation(cs, ct - aya) < 0.01
        # Bodies and cusps shift by the same ayanamsa, so every body keeps its tropical house.
        assert {n: x["house"] for n, x in s["bodies"].items()} == {n: x["house"] for n, x in t["bodies"].items()}
    for body in s["bodies"].values():
        assert body["house"] == cp.house_of(body["longitude"], cusps)
