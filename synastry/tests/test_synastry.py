import json
import sys
from pathlib import Path

import synastry as sy


def chart(bodies, cusps=None, angles=None, flags=()):
    return {"schema_version": 1,
            "meta": {"name": "X", "time_unknown": cusps is None, "flags": list(flags)},
            "bodies": {n: {"longitude": lon} for n, lon in bodies.items()},
            "houses": {"system": "placidus", "cusps": cusps} if cusps else None,
            "angles": angles}


CUSPS = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]


def test_inter_aspects_use_reduced_orbs():
    a = chart({"Mars": 10.0}); b = chart({"Venus": 16.5})
    result = sy.compare(a, b)
    assert result["inter_aspects"] == []          # 6.5 > conjunction 8 - 2
    b = chart({"Venus": 15.0})
    hits = sy.compare(a, b)["inter_aspects"]
    assert hits[0]["aspect"] == "Conjunction" and hits[0]["max_orb"] == 6.0 and hits[0]["applying"] is None


def test_overlays_only_where_host_has_houses():
    a = chart({"Sun": 45.0}, cusps=CUSPS, angles={"ascendant": 0.0, "mc": 270.0})
    b = chart({"Moon": 100.0})
    result = sy.compare(a, b)
    assert result["overlays"]["b_in_a_houses"] == {"Moon": 4}
    assert result["overlays"]["a_in_b_houses"] is None
    assert "b_time_unknown" in result["flags"]


def test_moon_aspects_flagged_uncertain_for_untimed_partner():
    a = chart({"Sun": 45.0}, cusps=CUSPS, angles={"ascendant": 0.0, "mc": 270.0})
    b = chart({"Moon": 45.0, "Mars": 135.0})
    hits = {(h["a"], h["b"]): h for h in sy.compare(a, b)["inter_aspects"]}
    assert hits[("Sun", "Moon")]["uncertain"] is True
    assert hits[("Sun", "Mars")]["uncertain"] is False


def test_angles_only_from_timed_chart():
    a = chart({"Sun": 45.0}, cusps=CUSPS, angles={"ascendant": 44.0, "mc": 270.0})
    b = chart({"Moon": 224.0})
    hits = sy.compare(a, b)["inter_aspects"]
    assert any(h["a"] == "Ascendant" and h["b"] == "Moon" and h["aspect"] == "Opposition" for h in hits)


def test_grid_has_a_down_and_b_across():
    a = chart({"Sun": 0.0, "Moon": 90.0}); b = chart({"Mars": 120.0})
    md = sy.render_grid(sy.compare(a, b), a, b)
    assert md.splitlines()[0] == "| A \\ B | Mars |"
    assert "| Sun | △ 0.0 |" in md


def test_natal_flags_are_merged_with_side_prefix():
    a = chart({"Sun": 0.0}, cusps=CUSPS, angles={"ascendant": 0.0, "mc": 270.0},
              flags=["polar_fallback_whole_sign"])
    b = chart({"Moon": 0.0}, flags=["time_unknown", "time_unknown"])
    flags = sy.compare(a, b)["flags"]
    assert "a_polar_fallback_whole_sign" in flags
    assert flags.count("b_time_unknown") == 1
    assert "a_time_unknown" not in flags


def test_config_block_records_sources_and_house_systems():
    a = chart({"Sun": 0.0}, cusps=CUSPS, angles={"ascendant": 0.0, "mc": 270.0})
    a["meta"]["house_system"] = "placidus"
    b = chart({"Moon": 0.0})
    b["meta"]["house_system"] = None
    cfg = sy.compare(a, b, sources={"a": "a.json", "b": "birth data"})["config"]
    assert cfg == {"orb_reduction": 2.0,
                   "a": {"source": "a.json", "house_system": "placidus"},
                   "b": {"source": "birth data", "house_system": None}}


def test_grid_marks_uncertain_cells():
    a = chart({"Sun": 0.0}, cusps=CUSPS, angles={"ascendant": 0.0, "mc": 270.0})
    b = chart({"Moon": 0.0, "Mars": 120.0})
    md = sy.render_grid(sy.compare(a, b), a, b)
    assert "| Sun | ☌ 0.0? | △ 0.0 |" in md


def test_moon_uncertain_on_a_side_and_moon_moon():
    a = chart({"Moon": 10.0})                       # untimed A
    b = chart({"Moon": 10.0, "Sun": 100.0}, cusps=CUSPS, angles={"ascendant": 0.0, "mc": 270.0})
    hits = {(h["a"], h["b"]): h for h in sy.compare(a, b)["inter_aspects"]}
    assert hits[("Moon", "Sun")]["uncertain"] is True
    assert hits[("Moon", "Moon")]["uncertain"] is True
    c = chart({"Moon": 10.0}, cusps=CUSPS, angles={"ascendant": 0.0, "mc": 270.0})
    both_timed = {(h["a"], h["b"]): h for h in sy.compare(c, b)["inter_aspects"]}
    assert both_timed[("Moon", "Moon")]["uncertain"] is False


def test_overlay_direction_follows_host_cusps():
    shifted = [(c + 45) % 360 for c in CUSPS]       # host's 1st house starts at 45
    a = chart({"Sun": 50.0}, cusps=CUSPS, angles={"ascendant": 0.0, "mc": 270.0})
    b = chart({"Venus": 50.0}, cusps=shifted, angles={"ascendant": 45.0, "mc": 315.0})
    ov = sy.compare(a, b)["overlays"]
    assert ov["a_in_b_houses"] == {"Sun": 1}         # 50 in B's shifted houses
    assert ov["b_in_a_houses"] == {"Venus": 2}       # 50 in A's zero-based houses


def _natal_module(name):
    """Load natal-chart/scripts/<name>.py by path (its siblings import each other by bare name)."""
    import importlib.util
    import pytest
    scripts = Path(__file__).resolve().parents[2] / "natal-chart" / "scripts"
    path = scripts / f"{name}.py"
    if not path.is_file():
        pytest.skip(f"{path} absent")
    pytest.importorskip("swisseph")
    spec = importlib.util.spec_from_file_location(f"natal_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scripts))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(scripts))
    return mod


def test_copied_config_matches_natal_chart():
    asp, ch = _natal_module("aspects"), _natal_module("chart")
    assert sy.ASPECTS == asp.ASPECTS and sy.ORBS == asp.ORBS and sy.LUMINARY_BONUS == asp.LUMINARY_BONUS
    for x, y in [(10.0, 350.0), (0.0, 180.0), (359.5, 0.5), (100.0, 250.0)]:
        assert sy.separation(x, y) == asp.separation(x, y)
    cusps = [350, 20, 50, 80, 110, 140, 170, 200, 230, 260, 290, 320]
    for lon in (355.0, 0.0, 19.9, 20.0, 349.9, 200.0):
        assert sy.house_of(lon, cusps) == ch.house_of(lon, cusps)
