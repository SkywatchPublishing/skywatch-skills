#!/usr/bin/env python3
"""
Composite charts: the midpoint composite and the Davison relationship chart.

Midpoint: every body shared by the two charts is placed at the midpoint of its two positions on
the shorter arc; the composite MC is the midpoint of the two MCs and the houses are derived from
it at a reference latitude (default: chart A's place) with pyswisseph's ARMC house routine. There
is no real sky behind it, so speeds are averaged, ``retrograde`` is false and every aspect has
``applying: null``. If either side has an unknown time the composite has no angles or houses.

Davison: the mean of the two UTC instants cast at the great-circle midpoint of the two
birthplaces; a real moment, delegated to the sibling natal-chart script.

The small helpers (sign formatting, house placement, the aspect table and ``find_aspects``) are
copied from natal-chart/scripts, as synastry does; nothing is imported across skill folders.

Usage:
    python composite.py --a chartA.json --b chartB.json [--method midpoint|davison] [--out composite.json]
"""

import itertools
import math
from pathlib import Path

import swisseph as swe

for _ephe in (Path(__file__).resolve().parents[1] / "ephe",
              Path(__file__).resolve().parents[2] / "natal-chart" / "ephe"):
    if (_ephe / "seas_18.se1").exists():
        swe.set_ephe_path(str(_ephe))
        break

SCHEMA_VERSION = 1

# --- copied from natal-chart/scripts/chart.py -------------------------------------------

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
BODY_ORDER = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus",
              "Neptune", "Pluto", "Chiron", "Node"]
ANGLE_NAMES = ("Ascendant", "MC")


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


# --- copied from natal-chart/scripts/aspects.py (``applying`` dropped: a composite does not move)

ASPECTS = {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Quincunx": 150, "Opposition": 180}
ORBS = {"Conjunction": 8.0, "Opposition": 8.0, "Square": 8.0, "Trine": 8.0, "Sextile": 6.0, "Quincunx": 3.0}
LUMINARY_BONUS = 2.0
LUMINARIES = {"Sun", "Moon"}


def max_orb(aspect: str, b1: str, b2: str, reduction: float = 0.0) -> float:
    bonus = LUMINARY_BONUS if (b1 in LUMINARIES or b2 in LUMINARIES) else 0.0
    return ORBS[aspect] + bonus - reduction


def separation(lon1: float, lon2: float) -> float:
    d = abs(lon1 - lon2) % 360
    return min(d, 360 - d)


def find_aspects(bodies: dict[str, dict], reduction: float = 0.0, pairs=None) -> list[dict]:
    """bodies: name -> {longitude}. pairs: optional iterable of (name1, name2); default all combinations.
    Every hit carries ``applying: None`` because composite positions have no motion."""
    pairs = pairs if pairs is not None else itertools.combinations(bodies, 2)
    found = []
    for n1, n2 in pairs:
        p1, p2 = bodies[n1], bodies[n2]
        sep = separation(p1["longitude"], p2["longitude"])
        for aspect, angle in ASPECTS.items():
            limit = max_orb(aspect, n1, n2, reduction)
            orb = abs(sep - angle)
            if orb <= limit:
                found.append({"body1": n1, "body2": n2, "aspect": aspect, "angle": angle,
                              "orb": round(orb, 3), "max_orb": limit, "applying": None})
                break
    return found


# --- midpoint geometry ---------------------------------------------------------------------

def midpoint(a: float, b: float) -> float:
    """Midpoint on the shorter arc, in [0, 360)."""
    d = ((b - a + 180.0) % 360.0) - 180.0
    return (a + d / 2.0) % 360.0


def obliquity(jd: float) -> float:
    return swe.calc_ut(jd, swe.ECL_NUT)[0][0]


def armc_from_mc(mc: float, eps: float) -> float:
    m, e = math.radians(mc), math.radians(eps)
    return math.degrees(math.atan2(math.sin(m) * math.cos(e), math.cos(m))) % 360.0


HOUSE_CODES = {"placidus": b"P", "koch": b"K", "equal": b"E", "porphyry": b"O", "whole_sign": b"W"}


def houses_from_mc(mc: float, latitude: float, eps: float, system: str) -> dict:
    """Cusps and angles for a given MC at a latitude; whole-sign fallback at polar latitudes."""
    flags = []
    armc = armc_from_mc(mc, eps)
    try:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES[system])
    except swe.Error:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES["whole_sign"])
        system, flags = "whole_sign", ["polar_fallback_whole_sign"]
    asc, mc_out = ascmc[0] % 360, ascmc[1] % 360
    return {"system": system, "cusps": [c % 360 for c in cusps[:12]],
            "angles": {"ascendant": asc, "mc": mc_out, "descendant": (asc + 180) % 360, "ic": (mc_out + 180) % 360},
            "flags": flags}


# --- midpoint composite --------------------------------------------------------------------

def _time_unknown(chart: dict) -> bool:
    meta = chart.get("meta") or {}
    return (bool(meta.get("time_unknown")) or "time_unknown" in (meta.get("flags") or [])
            or not chart.get("angles"))


def midpoint_chart(a: dict, b: dict, reference: dict, house_system: str) -> dict:
    """A midpoint composite of two chart.json dicts as a chart.json dict.

    ``reference`` is a contract ``location`` object whose latitude places the houses.
    Raises ValueError when the two charts disagree on zodiac or lunar node.
    """
    ma, mb = a["meta"], b["meta"]
    for key in ("zodiac", "node"):
        if ma.get(key) != mb.get(key):
            raise ValueError(f"charts disagree on {key}: {ma.get(key)!r} vs {mb.get(key)!r}; "
                             f"recast one of them so both match")

    flags: list[str] = []
    untimed = _time_unknown(a) or _time_unknown(b)
    jd = (ma["julian_day_ut"] + mb["julian_day_ut"]) / 2.0

    angles = houses = None
    if untimed:
        flags += ["time_unknown", "moon_uncertain"]
    else:
        mc = midpoint(a["angles"]["mc"], b["angles"]["mc"])
        derived = houses_from_mc(mc, reference["latitude"], obliquity(jd), house_system)
        flags += derived["flags"]
        angles = {k: round(v, 4) for k, v in derived["angles"].items()}
        houses = {"system": derived["system"], "cusps": [round(c, 4) for c in derived["cusps"]]}

    bodies = {}
    for name in BODY_ORDER:
        if name not in a["bodies"] or name not in b["bodies"]:
            continue
        pa, pb = a["bodies"][name], b["bodies"][name]
        lon = midpoint(pa["longitude"], pb["longitude"])
        sign, deg = sign_of(lon)
        bodies[name] = {
            "longitude": round(lon, 4), "sign": sign, "sign_degree": round(deg, 4),
            "formatted": format_degree(lon),
            "speed": round((pa["speed"] + pb["speed"]) / 2.0, 4), "retrograde": False,
            "house": house_of(lon, houses["cusps"]) if houses else None,
            "latitude": round((pa["latitude"] + pb["latitude"]) / 2.0, 4),
        }
    if "Chiron" not in bodies:
        flags.append("chiron_unavailable")

    aspect_input = {n: {"longitude": body["longitude"]} for n, body in bodies.items()}
    if angles:
        aspect_input["Ascendant"] = {"longitude": angles["ascendant"]}
        aspect_input["MC"] = {"longitude": angles["mc"]}
    pairs = [(x, y) for i, x in enumerate(aspect_input) for y in list(aspect_input)[i + 1:]
             if not (x in ANGLE_NAMES and y in ANGLE_NAMES)]

    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "name": f"{ma['name']} & {mb['name']}",
            "chart_type": "composite",
            "derived_from": [ma["name"], mb["name"]],
            "datetime_local": None,
            "timezone": None,
            "datetime_utc": None,
            "utc_offset": None,
            "julian_day_ut": round(jd, 7),
            "time_unknown": untimed,
            "moon_range": None,
            "location": reference,
            "zodiac": ma.get("zodiac", "tropical"),
            "house_system": houses["system"] if houses else None,
            "node": ma.get("node", "true"),
            "flags": flags,
            "source": {**(ma.get("source") or {}), "method": "midpoint"},
        },
        "angles": angles,
        "houses": houses,
        "bodies": bodies,
        "aspects": find_aspects(aspect_input, pairs=pairs),
    }
