#!/usr/bin/env python3
"""Render a chart.json (natal-chart contract, schema_version 1) as an 800x800 SVG wheel.

Convention: Ascendant at 9 o'clock, zodiac running counter-clockwise. Standard library only.

    python chart_wheel.py chart.json [--out wheel.svg]
"""
import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wheel_geometry as g  # noqa: E402

SIZE = 800
CX = CY = 400.0

R_OUTER = 380.0        # sign ring outer edge
R_SIGN_IN = 340.0      # sign ring inner edge / house ring outer edge
R_HOUSE_IN = 300.0     # house ring inner edge; planet ticks sit here
R_HOUSE_NUM = 320.0
R_GLYPH = 270.0
R_LABEL = 240.0
R_ASPECT = 210.0
R_ANGLE_EXT = 390.0
WHEEL_SCALE = 0.85     # shrink the rings about the centre so the captions at y=40 and y=770 clear the outer ring
LABEL_STAGGER = 16.0   # labels of nudged neighbours alternate between R_LABEL and R_LABEL - LABEL_STAGGER

SIGN_GLYPHS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
PLANET_GLYPHS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂", "Jupiter": "♃",
    "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇", "Chiron": "⚷", "Node": "☊",
}
ASPECT_COLOURS = {
    "Opposition": "#c0392b", "Square": "#c0392b",
    "Trine": "#2e86c1", "Sextile": "#2e86c1",
    "Quincunx": "#7f8c8d",
}
FONT = "'DejaVu Sans', 'Segoe UI Symbol', 'Noto Sans Symbols2', 'Apple Symbols', sans-serif"
MIN_GAP = 6.0


def _pt(asc: float, lon: float, r: float) -> tuple[float, float]:
    return g.point(asc, lon, CX, CY, r)


def _fmt(v: float) -> str:
    return f"{v:.2f}"


def _line(asc: float, lon: float, r1: float, r2: float, **attrs: str) -> str:
    x1, y1 = _pt(asc, lon, r1)
    x2, y2 = _pt(asc, lon, r2)
    a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y2)}" {a}/>'


def _sector(asc: float, lon_a: float, lon_b: float, r_in: float, r_out: float, fill: str) -> str:
    """Annular sector from lon_a forward (counter-clockwise on screen) to lon_b."""
    ax, ay = _pt(asc, lon_a, r_out)
    bx, by = _pt(asc, lon_b, r_out)
    cx_, cy_ = _pt(asc, lon_b, r_in)
    dx, dy = _pt(asc, lon_a, r_in)
    large = 1 if (lon_b - lon_a) % 360 > 180 else 0
    d = (f"M {_fmt(ax)} {_fmt(ay)} A {_fmt(r_out)} {_fmt(r_out)} 0 {large} 0 {_fmt(bx)} {_fmt(by)} "
         f"L {_fmt(cx_)} {_fmt(cy_)} A {_fmt(r_in)} {_fmt(r_in)} 0 {large} 1 {_fmt(dx)} {_fmt(dy)} Z")
    return f'<path d="{d}" fill="{fill}" stroke="#555" stroke-width="0.5"/>'


def _text(x: float, y: float, s: str, size: float, cls: str | None = None, **attrs: str) -> str:
    extra = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    c = f' class="{cls}"' if cls else ""
    return (f'<text x="{_fmt(x)}" y="{_fmt(y)}"{c} font-size="{size}" text-anchor="middle" '
            f'dominant-baseline="central" {extra}>{s}</text>')


def degree_label(body: dict) -> str:
    sd = body["longitude"] % 30.0
    deg = int(sd)
    minutes = int(round((sd - deg) * 60))
    if minutes == 60:
        deg, minutes = deg + 1, 0
    label = f"{deg}°{minutes:02d}'"
    if body.get("retrograde"):
        label += " ℞"
    return label


def svg_header() -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
            f'width="{SIZE}" height="{SIZE}" font-family="{FONT}">\n'
            f'<rect width="{SIZE}" height="{SIZE}" fill="#ffffff"/>\n'
            f'<g id="wheel" transform="translate({CX} {CY}) scale({WHEEL_SCALE}) translate({-CX} {-CY})">\n'
            f'<circle cx="{CX}" cy="{CY}" r="{R_OUTER}" fill="none" stroke="#333" stroke-width="1.5"/>\n'
            f'<circle cx="{CX}" cy="{CY}" r="{R_SIGN_IN}" fill="none" stroke="#333" stroke-width="1"/>\n'
            f'<circle cx="{CX}" cy="{CY}" r="{R_HOUSE_IN}" fill="none" stroke="#333" stroke-width="1"/>\n'
            f'<circle cx="{CX}" cy="{CY}" r="{R_ASPECT}" fill="none" stroke="#999" stroke-width="0.75"/>\n')


def sign_ring(asc: float) -> str:
    out = ['<g id="signs">']
    for i, glyph in enumerate(SIGN_GLYPHS):
        a = 30.0 * i
        fill = "#f4f1ea" if i % 2 == 0 else "#e4e0d6"
        out.append(_sector(asc, a, a + 30.0, R_SIGN_IN, R_OUTER, fill))
        x, y = _pt(asc, a + 15.0, (R_SIGN_IN + R_OUTER) / 2)
        out.append(_text(x, y, glyph, 24, "sign", fill="#222"))
    out.append("</g>")
    return "\n".join(out) + "\n"


def house_ring(chart: dict, asc: float) -> str:
    houses = chart.get("houses")
    angles = chart.get("angles")
    if not houses:
        return ""
    cusps = houses["cusps"]
    out = ['<g id="houses">']
    for i, c in enumerate(cusps):
        out.append(_line(asc, c, R_HOUSE_IN, R_OUTER, stroke="#555", stroke_width="1"))
        nxt = cusps[(i + 1) % 12]
        span = (nxt - c) % 360.0
        mid = c + span / 2.0
        x, y = _pt(asc, mid, R_HOUSE_NUM)
        out.append(_text(x, y, str(i + 1), 14, "house-number", fill="#444"))
    if angles:
        for key, label in (("ascendant", "ASC"), ("mc", "MC"), ("descendant", "DSC"), ("ic", "IC")):
            lon = angles[key]
            width = "3" if key in ("ascendant", "mc") else "1.5"
            out.append(_line(asc, lon, R_HOUSE_IN, R_ANGLE_EXT, stroke="#111", stroke_width=width))
            x, y = _pt(asc, lon, R_ANGLE_EXT + 6)
            anchor = "end" if x < CX - 1 else ("start" if x > CX + 1 else "middle")
            out.append(f'<text x="{_fmt(x)}" y="{_fmt(y)}" class="angle" font-size="11" '
                       f'font-weight="bold" text-anchor="{anchor}" dominant-baseline="central" fill="#111">{label}</text>')
    out.append("</g>")
    return "\n".join(out) + "\n"


def planet_ring(chart: dict, asc: float) -> str:
    names = [n for n in chart["bodies"] if n in PLANET_GLYPHS]
    true_lons = [chart["bodies"][n]["longitude"] for n in names]
    shown = g.spread(true_lons, MIN_GAP)
    # stagger the degree labels of bodies that were nudged into a cluster, so the labels do not touch
    label_r = {}
    prev, flip = None, False
    for i in sorted(range(len(names)), key=lambda k: shown[k]):
        flip = (not flip) if prev is not None and shown[i] - shown[prev] < MIN_GAP + 3.0 else False
        label_r[i] = R_LABEL - LABEL_STAGGER if flip else R_LABEL
        prev = i
    out = ['<g id="planets">']
    for i, (name, lon, disp) in enumerate(zip(names, true_lons, shown)):
        body = chart["bodies"][name]
        out.append(_line(asc, lon, R_HOUSE_IN - 6, R_HOUSE_IN + 6, stroke="#111", stroke_width="1.5"))
        if abs(disp - lon) > 0.05:
            # lead from the true position in to the nudged glyph
            x1, y1 = _pt(asc, lon, R_HOUSE_IN - 6)
            x2, y2 = _pt(asc, disp, R_GLYPH + 14)
            out.append(f'<line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y2)}" '
                       f'stroke="#999" stroke-width="0.75"/>')
        gx, gy = _pt(asc, disp, R_GLYPH)
        out.append(_text(gx, gy, PLANET_GLYPHS[name], 22, "planet", fill="#111"))
        lx, ly = _pt(asc, disp, label_r[i])
        out.append(_text(lx, ly, escape(degree_label(body)), 10, "degree", fill="#333"))
    out.append("</g>")
    return "\n".join(out) + "\n"


def aspect_lines(chart: dict, asc: float) -> str:
    positions = {n: b["longitude"] for n, b in chart["bodies"].items()}
    if chart.get("angles"):
        positions["Ascendant"] = chart["angles"]["ascendant"]
        positions["MC"] = chart["angles"]["mc"]
    out = ['<g id="aspects">']
    for a in chart.get("aspects", []):
        colour = ASPECT_COLOURS.get(a["aspect"])
        if colour is None or a["body1"] not in positions or a["body2"] not in positions:
            continue
        x1, y1 = _pt(asc, positions[a["body1"]], R_ASPECT)
        x2, y2 = _pt(asc, positions[a["body2"]], R_ASPECT)
        dash = ' stroke-dasharray="6 4"' if a.get("applying") is False else ""
        out.append(f'<line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y2)}" '
                   f'stroke="{colour}" stroke-width="1.5" stroke-opacity="0.8"{dash}/>')
    out.append("</g>")
    return "\n".join(out) + "\n"


def captions(chart: dict) -> str:
    meta = chart["meta"]
    top = f'{meta.get("name", "")}  ·  {meta.get("datetime_local", "").replace("T", " ")} ({meta.get("timezone", "")})'
    parts = [meta.get("location", {}).get("name", "")]
    if meta.get("time_unknown"):
        parts.append("Birth time unknown: houses not shown, Moon approximate")
    elif meta.get("house_system"):
        parts.append(f'{meta["house_system"].replace("_", " ").title()} houses')
    if meta.get("zodiac") and meta["zodiac"] != "tropical":
        parts.append(meta["zodiac"].replace("_", " "))
    for flag in meta.get("flags", []):
        if flag in ("time_unknown", "moon_uncertain"):
            continue
        parts.append(flag.replace("_", " "))
    bottom = "  ·  ".join(p for p in parts if p)
    return (_text(CX, 40, escape(top), 18, "caption", fill="#111") + "\n"
            + _text(CX, 770, escape(bottom), 13, "caption", fill="#333") + "\n")


def render(chart: dict) -> str:
    if chart.get("schema_version") != 1:
        raise ValueError(f"unsupported chart schema_version {chart.get('schema_version')!r}")
    asc = chart["angles"]["ascendant"] if chart.get("angles") and not chart["meta"].get("time_unknown") else 0.0
    return "".join([
        svg_header(),
        sign_ring(asc),
        house_ring(chart, asc),
        aspect_lines(chart, asc),
        planet_ring(chart, asc),
        "</g>\n",
        captions(chart),
        "</svg>\n",
    ])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render chart.json as an SVG wheel.")
    p.add_argument("chart", help="path to chart.json from natal-chart")
    p.add_argument("--out", default="wheel.svg", help="output SVG path (default wheel.svg)")
    args = p.parse_args(argv)
    try:
        chart = json.loads(Path(args.chart).read_text(encoding="utf-8"))
        svg = render(chart)
    except (OSError, ValueError, KeyError) as e:
        print(f"chart_wheel: {e}", file=sys.stderr)
        return 1
    Path(args.out).write_text(svg, encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
