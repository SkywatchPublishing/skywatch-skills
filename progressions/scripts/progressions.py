#!/usr/bin/env python3
"""
Secondary progressions and solar arc directions from a natal chart.json.

Usage:
    python progressions.py chart.json --date 2027-06-15                       # secondary progressed chart
    python progressions.py chart.json --date 2027-06-15 --angles naibod      # Naibod angles
    python progressions.py chart.json --date 2027-06-15 --method solar-arc   # solar arc directed chart
    python progressions.py chart.json --timeline --start 2027-01-01 --end 2036-12-31

One day after birth stands for one tropical year of life. Charts are ordinary schema-1 chart.json
files that chart-wheel and synastry read unchanged; the timeline is a CSV of dated events.

--out sets the output (default secondary_progressed_<date>.json, solar_arc_directed_<date>.json or
progressions_timeline.csv); --grid sets a chart's Markdown aspect grid (default <out stem>_aspects.md).
Exit codes: 0 success; 1 bad arguments or inputs.
"""
import argparse
import csv
import datetime as dt
import json
import math
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

for _ephe in (Path(__file__).resolve().parents[1] / "ephe", Path(__file__).resolve().parents[2] / "natal-chart" / "ephe"):
    if (_ephe / "seas_18.se1").exists():
        swe.set_ephe_path(str(_ephe))
        break
# Lahiri is the project-wide ayanamsa; FLG_SIDEREAL on each call selects the zodiac.
swe.set_sid_mode(swe.SIDM_LAHIRI)

SCHEMA_VERSION = 1
YEAR = 365.24219                 # tropical year in days: one progressed day per year of life
NAIBOD = 0.9856473               # Naibod rate, 0°59'08" per year
BODIES = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO, "Chiron": swe.CHIRON, "Node": swe.TRUE_NODE,
}
HOUSE_CODES = {"placidus": b"P", "koch": b"K", "equal": b"E", "porphyry": b"O", "whole_sign": b"W"}


def wrapped(x: float) -> float:
    """x reduced to (-180, 180]."""
    return ((x + 180.0) % 360.0) - 180.0


def target_jd(date: dt.date, tz: str) -> float:
    """Julian day (UT) of local noon on `date` in `tz`."""
    u = dt.datetime.combine(date, dt.time(12), tzinfo=ZoneInfo(tz)).astimezone(dt.timezone.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600)


def jd_to_local_date(jd: float, tz: str) -> dt.date:
    y, m, d, h = swe.revjul(jd)
    u = dt.datetime(y, m, d, tzinfo=dt.timezone.utc) + dt.timedelta(hours=h)
    return u.astimezone(ZoneInfo(tz)).date()


def progressed_jd(birth_jd: float, tjd: float) -> float:
    """Birth plus one day per tropical year of age."""
    return birth_jd + (tjd - birth_jd) / YEAR


def _flags(zodiac: str) -> int:
    f = swe.FLG_SWIEPH | swe.FLG_SPEED
    return f | swe.FLG_SIDEREAL if str(zodiac).startswith("sidereal") else f


def body_positions(jd: float, zodiac: str = "tropical", node: str = "true") -> dict[str, dict]:
    """Longitude, latitude, speed per body; Chiron omitted when its ephemeris file is missing."""
    out = {}
    for name, ident in BODIES.items():
        if name == "Node" and node == "mean":
            ident = swe.MEAN_NODE
        try:
            (lon, lat, _d, dlon, *_), _ = swe.calc_ut(jd, ident, _flags(zodiac))
        except swe.Error:
            if name == "Chiron":
                continue
            raise
        out[name] = {"longitude": lon % 360, "latitude": lat, "speed": dlon}
    return out


def sun_lon(jd: float, zodiac: str) -> float:
    return swe.calc_ut(jd, swe.SUN, _flags(zodiac))[0][0]


def solar_arc(birth_jd: float, tjd: float, zodiac: str = "tropical") -> float:
    """True solar arc: progressed Sun minus natal Sun, in [0, 360)."""
    return (sun_lon(progressed_jd(birth_jd, tjd), zodiac) - sun_lon(birth_jd, zodiac)) % 360


def obliquity(jd: float) -> float:
    return swe.calc_ut(jd, swe.ECL_NUT)[0][0]


def ayanamsa(jd: float, zodiac: str) -> float:
    return swe.get_ayanamsa_ut(jd) if str(zodiac).startswith("sidereal") else 0.0


def armc_from_mc(mc: float, eps: float) -> float:
    m, e = math.radians(mc), math.radians(eps)
    return math.degrees(math.atan2(math.sin(m) * math.cos(e), math.cos(m))) % 360.0


def houses_from_armc(armc: float, latitude: float, eps: float, system: str) -> dict:
    """Cusps and angles for an ARMC at a latitude; whole-sign fallback at polar latitudes."""
    flags = []
    try:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES[system])
    except swe.Error:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES["whole_sign"])
        system, flags = "whole_sign", ["polar_fallback_whole_sign"]
    asc, mc = ascmc[0] % 360, ascmc[1] % 360
    return {"system": system, "cusps": [c % 360 for c in cusps[:12]],
            "angles": {"ascendant": asc, "mc": mc, "descendant": (asc + 180) % 360, "ic": (mc + 180) % 360},
            "flags": flags}


def moved_houses(natal: dict, tjd: float, method: str) -> dict:
    """Progressed houses at the birth latitude, in the natal zodiac.

    'solar-arc': MC = natal MC + true solar arc. 'naibod': natal ARMC + 0.9856473° per year.
    houses_armc has no sidereal mode, so work in tropical and shift back by the birth ayanamsa.
    """
    meta = natal["meta"]
    zodiac, birth_jd = meta["zodiac"], meta["julian_day_ut"]
    lat = meta["location"]["latitude"]
    eps = obliquity(birth_jd)
    shift = ayanamsa(birth_jd, zodiac)
    natal_mc_trop = (natal["angles"]["mc"] + shift) % 360
    if method == "naibod":
        armc = (armc_from_mc(natal_mc_trop, eps) + NAIBOD * (tjd - birth_jd) / YEAR) % 360
    else:
        armc = armc_from_mc((natal_mc_trop + solar_arc(birth_jd, tjd, zodiac)) % 360, eps)
    h = houses_from_armc(armc, lat, eps, natal["houses"]["system"])
    h["cusps"] = [(c - shift) % 360 for c in h["cusps"]]
    h["angles"] = {k: (v - shift) % 360 for k, v in h["angles"].items()}
    return h


SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ASPECTS = {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Quincunx": 150, "Opposition": 180}
ORBS = {"Conjunction": 8.0, "Opposition": 8.0, "Square": 8.0, "Trine": 8.0, "Sextile": 6.0, "Quincunx": 3.0}
LUMINARY_BONUS = 2.0
LUMINARIES = {"Sun", "Moon"}


def sign_of(lon: float) -> tuple[str, float]:
    lon %= 360
    return SIGNS[int(lon // 30)], lon % 30


def format_degree(lon: float) -> str:
    # Round the whole longitude to the nearest arc-minute first so a value a
    # hair under a sign boundary rolls over into the next sign (never "30°00'").
    total_minutes = round(lon % 360 * 60) % (360 * 60)
    sign = SIGNS[total_minutes // (30 * 60)]
    whole, minutes = divmod(total_minutes % (30 * 60), 60)
    return f"{whole}°{minutes:02d}' {sign}"


def house_of(lon: float, cusps: list[float]) -> int:
    lon %= 360
    for i in range(12):
        start, end = cusps[i], cusps[(i + 1) % 12]
        inside = start <= lon < end if start < end else (lon >= start or lon < end)
        if inside:
            return i + 1
    return 12


def max_orb(aspect: str, b1: str, b2: str) -> float:
    return ORBS[aspect] + (LUMINARY_BONUS if (b1 in LUMINARIES or b2 in LUMINARIES) else 0.0)


def separation(lon1: float, lon2: float) -> float:
    d = abs(lon1 - lon2) % 360
    return min(d, 360 - d)


def applying(p1: dict, p2: dict, angle: float) -> bool | None:
    """Analytic applying test copied from natal-chart's aspects.py; None without relative motion."""
    if p1.get("speed") is None or p2.get("speed") is None:
        return None
    rel = p1["speed"] - p2["speed"]
    if abs(rel) < 1e-9:
        return None
    delta = ((p1["longitude"] - p2["longitude"] + 180) % 360) - 180
    target = angle if delta >= 0 else -angle
    return (delta - target) * rel < 0


def find_aspects(points: dict[str, dict]) -> list[dict]:
    names = list(points)
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]
             if not (a in ("Ascendant", "MC") and b in ("Ascendant", "MC"))]
    found = []
    for n1, n2 in pairs:
        p1, p2 = points[n1], points[n2]
        sep = separation(p1["longitude"], p2["longitude"])
        for aspect, angle in ASPECTS.items():
            limit = max_orb(aspect, n1, n2)
            if abs(sep - angle) <= limit:
                found.append({"body1": n1, "body2": n2, "aspect": aspect, "angle": angle,
                              "orb": round(abs(sep - angle), 3), "max_orb": limit,
                              "applying": applying(p1, p2, angle)})
                break
    return found


def _body(lon, speed, lat, cusps):
    sign, deg = sign_of(lon)
    return {"longitude": round(lon % 360, 4), "sign": sign, "sign_degree": round(deg, 4),
            "formatted": format_degree(lon), "speed": None if speed is None else round(speed, 4),
            "retrograde": bool(speed is not None and speed < 0),
            "house": house_of(lon, cusps) if cusps else None, "latitude": round(lat, 4)}


def _assemble(natal: dict, raw: dict, houses: dict | None, chart_type: str, tjd: float, arc: float,
              angles_method: str | None) -> dict:
    """raw: name -> (longitude, speed or None, latitude). houses: moved houses or None (untimed)."""
    import copy
    meta = copy.deepcopy(natal["meta"])
    cusps = houses["cusps"] if houses else None
    bodies = {n: _body(lon, sp, lat, cusps) for n, (lon, sp, lat) in raw.items()}
    points = {n: {"longitude": b["longitude"], "speed": b["speed"]} for n, b in bodies.items()}
    angles = None
    if houses:
        angles = {k: round(v, 4) for k, v in houses["angles"].items()}
        points["Ascendant"] = {"longitude": angles["ascendant"]}
        points["MC"] = {"longitude": angles["mc"]}
        meta["house_system"] = houses["system"]
    meta["chart_type"] = chart_type
    meta["derived_from"] = [natal["meta"]["name"]]
    meta["flags"] = sorted(set(meta.get("flags", [])) | set(houses["flags"] if houses else []))
    meta["progression"] = {"target_date": jd_to_local_date(tjd, meta["timezone"]).isoformat(),
                           "age_years": round((tjd - meta["julian_day_ut"]) / YEAR, 4),
                           "solar_arc": round(arc, 4), "angles_method": angles_method}
    return {"schema_version": SCHEMA_VERSION, "meta": meta, "angles": angles,
            "houses": {"system": houses["system"], "cusps": [round(c, 4) for c in houses["cusps"]]} if houses else None,
            "bodies": bodies, "aspects": find_aspects(points)}


def progressed_chart(natal: dict, tjd: float, angles_method: str = "solar-arc") -> dict:
    """Secondary progressed chart for target Julian day `tjd`."""
    meta = natal["meta"]
    bj = meta["julian_day_ut"]
    pos = body_positions(progressed_jd(bj, tjd), meta["zodiac"], meta.get("node", "true"))
    raw = {n: (p["longitude"], p["speed"], p["latitude"]) for n, p in pos.items() if n in natal["bodies"]}
    houses = moved_houses(natal, tjd, angles_method) if natal.get("angles") else None
    return _assemble(natal, raw, houses, "secondary_progressed", tjd, solar_arc(bj, tjd, meta["zodiac"]),
                     angles_method if houses else None)


def directed_chart(natal: dict, tjd: float) -> dict:
    """Solar arc directed chart: every body, angle and cusp moves by the true solar arc."""
    meta = natal["meta"]
    arc = solar_arc(meta["julian_day_ut"], tjd, meta["zodiac"])
    raw = {n: ((b["longitude"] + arc) % 360, None, b.get("latitude", 0.0)) for n, b in natal["bodies"].items()}
    houses = None
    if natal.get("angles"):
        houses = {"system": natal["houses"]["system"],
                  "cusps": [(c + arc) % 360 for c in natal["houses"]["cusps"]],
                  "angles": {k: (v + arc) % 360 for k, v in natal["angles"].items()}, "flags": []}
    return _assemble(natal, raw, houses, "solar_arc_directed", tjd, arc, None)


ORB = 1.0            # timeline window, degrees either side of exact
STEP = 15.0          # days of real time between samples
TOL = 0.25           # bisect crossings to a quarter day
MARGIN = 5 * YEAR    # scan this far beyond the range so windows overlapping it are found
SECONDARY_MOVERS = ["Moon", "Sun", "Mercury", "Venus", "Mars"]
STATION_BODIES = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Chiron"]


def _bisect(f, lo: float, hi: float, flo) -> float:
    """f(lo) == flo and f(hi) != flo; narrow to TOL and return the midpoint."""
    while hi - lo > TOL:
        mid = (lo + hi) / 2
        if f(mid) == flo:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _grid(t0: float, t1: float) -> list[float]:
    ts, t = [t0], t0
    while t < t1:
        t = min(t + STEP, t1)
        ts.append(t)
    return ts


def _zero_crossings(g, ts, gs) -> list[float]:
    """Where g (values in (-180, 180]) crosses zero between samples, ignoring the ±180 seam."""
    out = []
    for (a, ga), (b, gb) in zip(zip(ts, gs), zip(ts[1:], gs[1:])):
        if (ga < 0 <= gb or ga >= 0 > gb) and abs(gb - ga) < 90:
            out.append(_bisect(lambda x: g(x) >= 0, a, b, ga >= 0))
    return out


def _edge(g, te: float, direction: int, limit: float = 60 * YEAR) -> float | None:
    """First time from te (direction ±1) where |g| reaches ORB; None if it never does within limit."""
    t = te
    while abs(t - te) < limit:
        n = t + direction * STEP
        if abs(g(n)) >= ORB:
            lo, hi = (t, n) if direction > 0 else (n, t)
            return _bisect(lambda x: abs(g(x)) >= ORB, lo, hi, abs(g(lo)) >= ORB)
        t = n
    return None


def _aspect_events(technique: str, mover: str, m, targets: dict, ts: list[float]) -> list[dict]:
    ms = [m(t) for t in ts]                      # evaluate the mover once per sample
    rows = []
    for tname, tlon in targets.items():
        if technique == "solar_arc" and tname == mover:
            continue
        for aname, angle in ASPECTS.items():
            for sgn in ((1,) if angle in (0, 180) else (1, -1)):
                off = tlon + sgn * angle
                g = lambda t, o=off: wrapped(m(t) - o)
                gs = [wrapped(v - off) for v in ms]
                for te in _zero_crossings(g, ts, gs):
                    rows.append({"technique": technique, "event": "aspect", "moving": mover, "aspect": aname,
                                 "target": tname, "exact": te, "from": _edge(g, te, -1), "to": _edge(g, te, +1),
                                 "detail": ""})
    return rows


def _state_events(technique: str, event: str, mover: str, state, ts: list[float], describe) -> list[dict]:
    rows = []
    vals = [state(t) for t in ts]
    for (a, va), (b, vb) in zip(zip(ts, vals), zip(ts[1:], vals[1:])):
        if va != vb:
            rows.append({"technique": technique, "event": event, "moving": mover, "aspect": "", "target": "",
                         "exact": _bisect(state, a, b, va), "from": None, "to": None, "detail": describe(va, vb)})
    return rows


def timeline(natal: dict, start: dt.date, end: dt.date, angles_method: str = "solar-arc") -> list[dict]:
    """Dated secondary and solar arc events whose 1° window overlaps [start, end]."""
    meta = natal["meta"]
    tz, bj, zodiac, node = meta["timezone"], meta["julian_day_ut"], meta["zodiac"], meta.get("node", "true")
    timed = bool(natal.get("angles"))
    r0, r1 = target_jd(start, tz), target_jd(end, tz)
    ts = _grid(max(bj, r0 - MARGIN), r1 + MARGIN)
    targets = {n: b["longitude"] for n, b in natal["bodies"].items()}
    if timed:
        targets["Ascendant"], targets["MC"] = natal["angles"]["ascendant"], natal["angles"]["mc"]
    flags = _flags(zodiac)
    arcs: dict[float, float] = {}

    def arc(t):
        if t not in arcs:
            arcs[t] = solar_arc(bj, t, zodiac)
        return arcs[t]

    def prog_lon(name):
        ident = swe.MEAN_NODE if (name == "Node" and node == "mean") else BODIES[name]
        return lambda t: swe.calc_ut(progressed_jd(bj, t), ident, flags)[0][0]

    def prog_retro(name):
        return lambda t: swe.calc_ut(progressed_jd(bj, t), BODIES[name], flags)[0][3] < 0

    rows = []
    for name in SECONDARY_MOVERS:
        if name in natal["bodies"]:
            rows += _aspect_events("secondary", name, prog_lon(name), targets, ts)
    if timed:
        # With solar-arc angles the progressed MC is the directed MC by definition; list it once, under solar arc.
        moving = (("Ascendant", "ascendant"),) if angles_method == "solar-arc" else (("Ascendant", "ascendant"), ("MC", "mc"))
        for ang, key in moving:
            rows += _aspect_events("secondary", ang,
                                   lambda t, k=key: moved_houses(natal, t, angles_method)["angles"][k], targets, ts)
    for name, lon in targets.items():
        rows += _aspect_events("solar_arc", name, lambda t, l=lon: (l + arc(t)) % 360, targets, ts)
    for name in natal["bodies"]:
        f = prog_lon(name)
        rows += _state_events("secondary", "ingress", name, lambda t, f=f: int((f(t) % 360) // 30), ts,
                              lambda a, b: f"enters {SIGNS[b]}")
    if timed:
        cusps, f = natal["houses"]["cusps"], prog_lon("Moon")
        rows += _state_events("secondary", "house", "Moon", lambda t: house_of(f(t), cusps), ts,
                              lambda a, b: f"enters natal house {b}")
    for name in STATION_BODIES:
        if name in natal["bodies"]:
            rows += _state_events("secondary", "station", name, prog_retro(name), ts,
                                  lambda a, b: "turns retrograde" if b else "turns direct")

    def overlaps(r):
        lo = r["from"] if r["from"] is not None else r["exact"]
        hi = r["to"] if r["to"] is not None else r["exact"]
        return hi >= r0 and lo <= r1

    rows = [r for r in rows if overlaps(r)]
    for r in rows:
        # An untimed birth moves every secondary event by up to ~6 months; solar arc only through the Moon.
        r["uncertain"] = (not timed) and (r["technique"] == "secondary" or "Moon" in (r["moving"], r["target"]))
        for k in ("exact", "from", "to"):
            r[k] = jd_to_local_date(r[k], tz) if r[k] is not None else None
    rows.sort(key=lambda r: (r["exact"], r["technique"], r["moving"], r["target"]))
    return rows


# --- copied from natal-chart/scripts/grid.py ------------------------------------------------

SYMBOLS = {"Conjunction": "☌", "Sextile": "⚹", "Square": "□", "Trine": "△", "Quincunx": "⚻", "Opposition": "☍"}


def _cell(a: dict) -> str:
    suffix = {True: "a", False: "s", None: ""}[a["applying"]]
    return f"{SYMBOLS[a['aspect']]} {a['orb']:.1f}{suffix}"


def render_grid(chart: dict) -> str:
    names = list(chart["bodies"])
    if chart.get("angles"):
        names += ["Ascendant", "MC"]
    lookup = {}
    for a in chart["aspects"]:
        lookup[(a["body1"], a["body2"])] = lookup[(a["body2"], a["body1"])] = _cell(a)
    lines = ["| | " + " | ".join(names) + " |", "|" + "---|" * (len(names) + 1)]
    for row in names:
        cells = [lookup.get((row, col), "") for col in names]
        lines.append(f"| {row} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


# --- copied from composite/scripts/composite.py ---------------------------------------------

class Parser(argparse.ArgumentParser):
    """argparse exits 2 on usage errors; across these skills 2 means an ambiguous city, so exit 1."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        sys.exit(1)


def load_chart(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        try:
            chart = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(chart, dict):
        raise ValueError(f"{path}: expected a chart object")
    if chart.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{path}: expected schema_version {SCHEMA_VERSION}, got {chart.get('schema_version')!r}")
    if not isinstance(chart.get("meta"), dict) or not chart["meta"].get("name"):
        raise ValueError(f"{path}: missing meta.name")
    if not isinstance(chart.get("bodies"), dict) or not chart["bodies"]:
        raise ValueError(f"{path}: missing bodies")
    return chart


# --- command line -----------------------------------------------------------------------------

DERIVED_TYPES = ("secondary_progressed", "solar_arc_directed")
MAX_YEARS = 120
TIMELINE_HEADER = ["Technique", "Event", "Moving", "Aspect", "Target", "Exact", "Orb from", "Orb to", "Detail",
                   "Uncertain"]
TECHNIQUE_NAMES = {"secondary": "secondary", "solar_arc": "solar arc"}
UNTIMED_NOTE = ("Note: the birth time is unknown, so every secondary event, and every solar arc event involving the "
                "Moon, may fall up to about six months either side of its date (a 12-hour error in the birth moment "
                "is half a progressed day, which is half a year); those rows are marked Uncertain, and angle and "
                "house events are left out")


def build_parser() -> argparse.ArgumentParser:
    p = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("chart", type=Path, help="natal chart.json")
    p.add_argument("--date", type=dt.date.fromisoformat, help="target date for a progressed or directed chart")
    p.add_argument("--timeline", action="store_true", help="write a CSV of dated events from --start to --end")
    p.add_argument("--start", type=dt.date.fromisoformat, help="first date of the timeline")
    p.add_argument("--end", type=dt.date.fromisoformat, help="last date of the timeline")
    p.add_argument("--method", choices=["secondary", "solar-arc"], help="chart technique (default: secondary)")
    p.add_argument("--angles", choices=["solar-arc", "naibod"],
                   help="how secondary progressed angles move (default: solar-arc)")
    p.add_argument("--out", type=Path, help="output path (defaults in the description above)")
    p.add_argument("--grid", type=Path, help="Markdown aspect grid for a chart (default: <out stem>_aspects.md)")
    return p


def birth_date(natal: dict) -> dt.date:
    meta = natal["meta"]
    return jd_to_local_date(meta["julian_day_ut"], meta["timezone"])


def write_timeline(rows: list[dict], path: Path) -> None:
    """Header-clean CSV (no comment lines) so csv.DictReader and pandas.read_csv parse it as is."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(TIMELINE_HEADER)
        for r in rows:
            w.writerow([TECHNIQUE_NAMES[r["technique"]], r["event"], r["moving"], r["aspect"], r["target"],
                        r["exact"].isoformat(), r["from"].isoformat() if r["from"] else "",
                        r["to"].isoformat() if r["to"] else "", r["detail"], "yes" if r["uncertain"] else ""])


def run_chart(args, natal: dict, out: Path, grid_path: Path) -> int:
    born = birth_date(natal)
    if args.date < born:
        print(f"--date {args.date} is before the birth date {born}; progressions run forward from birth",
              file=sys.stderr)
        return 1
    tjd = target_jd(args.date, natal["meta"]["timezone"])
    if args.method == "solar-arc":
        chart = directed_chart(natal, tjd)
    else:
        chart = progressed_chart(natal, tjd, args.angles or "solar-arc")
    out.write_text(json.dumps(chart, indent=2, ensure_ascii=False), encoding="utf-8")
    grid_path.write_text(render_grid(chart), encoding="utf-8")
    print(f"Wrote {out} and {grid_path}")
    for flag in chart["meta"]["flags"]:
        print(f"Note: {flag}")
    if args.angles and not chart.get("angles"):
        print("Note: --angles ignored because the natal chart has no birth time, so no angles to progress")
    return 0


def run_timeline(args, natal: dict, out: Path) -> int:
    born, start, notes = birth_date(natal), args.start, []
    if start < born:
        notes.append(f"Note: --start {start} is before the birth date; starting at {born}")
        start = born
    if args.end < start:
        print(f"--end {args.end} is before the birth date {born}; there is nothing to list", file=sys.stderr)
        return 1
    if (args.end.year - MAX_YEARS, args.end.month, args.end.day) > (start.year, start.month, start.day):
        print(f"{start} to {args.end} is over {MAX_YEARS} years; split it into shorter ranges", file=sys.stderr)
        return 1
    rows = timeline(natal, start, args.end, args.angles or "solar-arc")
    write_timeline(rows, out)
    print(f"Wrote {len(rows)} events to {out}")
    for note in notes:
        print(note)
    if not natal.get("angles"):
        print(UNTIMED_NOTE)
    return 0


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if (args.date is None) == (not args.timeline):
        parser.error("give exactly one of --date (a chart) and --timeline (an event list)")
    if args.timeline:
        if args.start is None or args.end is None:
            parser.error("--timeline needs --start and --end")
        if args.method or args.grid:
            parser.error("--method and --grid apply to --date charts; the timeline lists both techniques")
        if args.end < args.start:
            parser.error(f"--end {args.end} is before --start {args.start}")
        out = args.out or Path("progressions_timeline.csv")
    else:
        if args.start or args.end:
            parser.error("--start and --end apply to --timeline; a chart takes --date")
        if args.method == "solar-arc" and args.angles:
            parser.error("--angles applies to secondary progressed charts; a solar arc directed chart "
                         "moves every angle by the arc")
        kind = "solar_arc_directed" if args.method == "solar-arc" else "secondary_progressed"
        out = args.out or Path(f"{kind}_{args.date.isoformat()}.json")
        grid_path = args.grid or out.with_name(out.stem + "_aspects.md")
        if grid_path.resolve() == out.resolve():
            print(f"--grid and --out are the same file ({out}); choose a different --grid", file=sys.stderr)
            return 1

    try:
        natal = load_chart(args.chart)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    meta = natal["meta"]
    if any(meta.get(k) is None for k in ("julian_day_ut", "datetime_utc", "timezone")):
        print(f"progressions: this chart has no real moment (chart_type {meta.get('chart_type', 'natal')}); "
              "progressions need a natal chart", file=sys.stderr)
        return 1
    if meta.get("chart_type") in DERIVED_TYPES:
        print("progressions: this is already a progressed or directed chart; progress the natal chart instead",
              file=sys.stderr)
        return 1

    try:
        return run_timeline(args, natal, out) if args.timeline else run_chart(args, natal, out, grid_path)
    except (OSError, ValueError, KeyError, swe.Error) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
