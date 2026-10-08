import json
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "chart_wheel.py"
EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"
SVG_NS = "{http://www.w3.org/2000/svg}"

sys.path.insert(0, str(SCRIPT.parent))
import chart_wheel as cw  # noqa: E402


def load_example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def unknown_time_chart() -> dict:
    chart = load_example()
    chart["angles"] = chart["houses"] = None
    chart["meta"]["time_unknown"] = True
    chart["meta"]["flags"] = ["time_unknown", "moon_uncertain"]
    for b in chart["bodies"].values():
        b["house"] = None
    return chart


def render_root(chart: dict) -> ET.Element:
    return ET.fromstring(cw.render(chart))


def group(root: ET.Element, gid: str) -> ET.Element:
    el = root.find(f".//{SVG_NS}g[@id='{gid}']")
    assert el is not None, gid
    return el


def lines(root: ET.Element, gid: str) -> list[ET.Element]:
    return group(root, gid).findall(f"{SVG_NS}line")


def texts(root: ET.Element, cls: str) -> list[ET.Element]:
    return [t for t in root.iter(f"{SVG_NS}text") if t.get("class") == cls]


# --- command line -----------------------------------------------------------

def test_renders_well_formed_svg(tmp_path):
    out = tmp_path / "wheel.svg"
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), str(EXAMPLE), "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    root = ET.parse(out).getroot()
    assert root.tag.endswith("svg")
    text = out.read_text(encoding="utf-8")
    assert "☉" in text and "♈" in text
    assert text.count("<line") >= 12            # at least the cusps


def test_unknown_time_has_no_house_numbers(tmp_path):
    src = tmp_path / "c.json"
    src.write_text(json.dumps(unknown_time_chart()))
    out = tmp_path / "wheel.svg"
    subprocess.run([sys.executable, "-I", str(SCRIPT), str(src), "--out", str(out)], check=True)
    text = out.read_text(encoding="utf-8")
    assert "Birth time unknown" in text
    assert 'class="house-number"' not in text


def test_main_exits_1_on_malformed_chart(tmp_path, capsys):
    src = tmp_path / "c.json"
    src.write_text(json.dumps({"schema_version": 1, "meta": "not a dict", "bodies": {}}))
    assert cw.main([str(src), "--out", str(tmp_path / "w.svg")]) == 1
    assert "chart_wheel:" in capsys.readouterr().err


# --- degree labels -----------------------------------------------------------

@pytest.mark.parametrize("sign_degree, expected", [
    (29.9999, "0°00'"),
    (24.1296, "24°08'"),
    (24.2887, "24°17'"),
    (0.0, "0°00'"),
    (12.5, "12°30'"),
])
def test_degree_label_rounds_to_arc_minute_with_rollover(sign_degree, expected):
    body = {"longitude": 60.0 + sign_degree, "sign_degree": sign_degree, "retrograde": False}
    assert cw.degree_label(body) == expected


def test_degree_label_marks_retrograde():
    body = {"longitude": 1.0, "sign_degree": 1.0, "retrograde": True}
    assert cw.degree_label(body) == "1°00' ℞"


# --- glyph presentation ------------------------------------------------------

def test_sign_and_planet_glyphs_carry_text_presentation_selector():
    for glyph in cw.SIGN_GLYPHS:
        assert glyph.endswith("︎"), glyph
    for name in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"):
        assert cw.PLANET_GLYPHS[name].endswith("︎"), name
    for name in ("Chiron", "Node"):
        assert "︎" not in cw.PLANET_GLYPHS[name], name
    assert "︎" not in cw.degree_label({"longitude": 0.0, "sign_degree": 0.0, "retrograde": True})


def test_text_uses_dy_not_dominant_baseline():
    svg = cw.render(load_example())
    assert "dominant-baseline" not in svg
    for t in ET.fromstring(svg).iter(f"{SVG_NS}text"):
        assert t.get("dy") == "0.35em"


# --- label stagger -----------------------------------------------------------

def _label_radii(chart: dict, names: list[str]) -> list[float]:
    root = render_root(chart)
    radii = []
    for t in texts(root, "degree"):
        if t.get("data-body") in names:
            radii.append(math.hypot(float(t.get("x")) - cw.CX, float(t.get("y")) - cw.CY))
    assert len(radii) == len(names)
    return radii


def test_three_neighbours_within_nine_degrees_get_three_label_radii():
    chart = unknown_time_chart()
    chart["aspects"] = []
    chart["bodies"]["Uranus"]["longitude"] = 150.0
    chart["bodies"]["Neptune"]["longitude"] = 154.0
    chart["bodies"]["Pluto"]["longitude"] = 158.0
    radii = _label_radii(chart, ["Uranus", "Neptune", "Pluto"])
    assert len({round(r, 1) for r in radii}) == 3
    for a in radii:
        for b in radii:
            assert a == b or abs(a - b) >= cw.LABEL_STAGGER - 0.01


def test_isolated_bodies_share_the_outer_label_radius():
    chart = unknown_time_chart()
    chart["aspects"] = []
    chart["bodies"]["Uranus"]["longitude"] = 150.0
    chart["bodies"]["Neptune"]["longitude"] = 170.0
    radii = _label_radii(chart, ["Uranus", "Neptune"])
    assert all(abs(r - cw.R_LABEL) < 0.05 for r in radii)


def test_degree_label_font_is_about_ten_px_after_group_scale():
    root = render_root(load_example())
    sizes = {float(t.get("font-size")) for t in texts(root, "degree")}
    assert len(sizes) == 1
    assert abs(sizes.pop() * cw.WHEEL_SCALE - 10.0) <= 0.5


# --- defensive ---------------------------------------------------------------

def test_missing_location_renders():
    chart = load_example()
    chart["meta"]["location"] = None
    root = render_root(chart)
    assert root.tag == f"{SVG_NS}svg"
    chart["meta"].pop("location")
    render_root(chart)


def test_name_with_xml_specials_is_well_formed():
    chart = load_example()
    chart["meta"]["name"] = "<&\"'"
    root = render_root(chart)
    caps = texts(root, "caption")
    assert any("<&\"'" in (t.text or "") for t in caps)


def test_chart_without_chiron_renders():
    chart = load_example()
    del chart["bodies"]["Chiron"]
    chart["aspects"] = [a for a in chart["aspects"] if "Chiron" not in (a["body1"], a["body2"])]
    root = render_root(chart)
    assert all(t.get("data-body") != "Chiron" for t in texts(root, "planet"))


# --- geometry (coordinates in the file are untransformed) --------------------

def test_angle_and_cusp_lines():
    root = render_root(load_example())
    hl = lines(root, "houses")
    cusps = [l for l in hl if l.get("stroke-width") == "1"]
    angles = [l for l in hl if l.get("stroke-width") in ("3", "1.5")]
    assert len(cusps) == 12
    assert len(angles) == 4
    thick = [l for l in hl if l.get("stroke-width") == "3"]
    assert len(thick) == 2
    asc = min(thick, key=lambda l: abs(float(l.get("y2")) - 400))
    mc = max(thick, key=lambda l: abs(float(l.get("y2")) - 400))
    assert float(asc.get("x2")) < 400
    assert abs(float(asc.get("y2")) - 400) < 1
    assert float(mc.get("y2")) < 400


def test_sun_is_above_horizon_in_example():
    root = render_root(load_example())
    sun = [t for t in texts(root, "planet") if t.get("data-body") == "Sun"]
    assert len(sun) == 1
    assert float(sun[0].get("y")) < 400


def test_separating_aspect_dashed_and_unknown_applying_solid():
    chart = load_example()
    root = render_root(chart)
    al = lines(root, "aspects")
    pos = {n: b["longitude"] for n, b in chart["bodies"].items()}
    pos["Ascendant"] = chart["angles"]["ascendant"]
    pos["MC"] = chart["angles"]["mc"]
    asc = chart["angles"]["ascendant"]

    def find(a: dict) -> ET.Element:
        x1, y1 = cw._pt(asc, pos[a["body1"]], cw.R_ASPECT)
        x2, y2 = cw._pt(asc, pos[a["body2"]], cw.R_ASPECT)
        for l in al:
            if (abs(float(l.get("x1")) - x1) < 0.02 and abs(float(l.get("y1")) - y1) < 0.02
                    and abs(float(l.get("x2")) - x2) < 0.02 and abs(float(l.get("y2")) - y2) < 0.02):
                return l
        raise AssertionError(f"aspect line not found: {a}")

    sun_saturn = next(a for a in chart["aspects"] if {a["body1"], a["body2"]} == {"Sun", "Saturn"})
    assert sun_saturn["aspect"] == "Quincunx" and sun_saturn["applying"] is False
    assert find(sun_saturn).get("stroke-dasharray")
    null_applying = next(a for a in chart["aspects"] if a["applying"] is None and a["aspect"] in cw.ASPECT_COLOURS)
    assert find(null_applying).get("stroke-dasharray") is None
