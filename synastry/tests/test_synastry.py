import json
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
