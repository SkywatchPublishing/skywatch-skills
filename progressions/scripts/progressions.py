#!/usr/bin/env python3
"""
Secondary progressions and solar arc directions from a natal chart.json.

Usage:
    python progressions.py chart.json --date 2027-06-15                      # secondary progressed chart
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
import copy
import csv
import datetime as dt
import json
import math
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

EPHE_DIRS = (Path(__file__).resolve().parents[1] / "ephe",
             Path(__file__).resolve().parents[2] / "natal-chart" / "ephe")
# The first folder holding the files, else this skill's own ephe/: without them pyswisseph falls back to its
# built-in Moshier ephemeris, which has no Chiron.
EPHE_DIR = next((d for d in EPHE_DIRS if (d / "seas_18.se1").exists()), EPHE_DIRS[0])
swe.set_ephe_path(str(EPHE_DIR))
# Lahiri is the project-wide ayanamsa, set once here (nothing in this script changes it); FLG_SIDEREAL on each
# call selects the zodiac.
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


def ephemeris_files_present() -> bool:
    return (EPHE_DIR / "seas_18.se1").exists()


def wrapped(x: float) -> float:
    """x reduced to [-180, 180): the signed difference of two longitudes."""
    return ((x + 180.0) % 360.0) - 180.0


def local_jd(date: dt.date, time: dt.time, tz: str) -> float:
    """Julian day (UT) of a local wall-clock time on `date` in `tz`."""
    u = dt.datetime.combine(date, time, tzinfo=ZoneInfo(tz)).astimezone(dt.timezone.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600)


def target_jd(date: dt.date, tz: str) -> float:
    """Julian day (UT) of local noon on `date` in `tz`."""
    return local_jd(date, dt.time(12), tz)


def jd_to_local_date(jd: float, tz: str) -> dt.date:
    """Local date of a Julian day (UT). The time is rounded to the second first, so float error in revjul's
    hour cannot push an exact local midnight back into the previous day."""
    y, m, d, h = swe.revjul(jd)
    u = dt.datetime(y, m, d, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=round(h * 3600))
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


def solar_arc(birth_jd: float, tjd: float, zodiac: str = "tropical", natal_sun: float | None = None) -> float:
    """True solar arc: progressed Sun minus natal Sun, in [0, 360). Callers that need many arcs pass
    `natal_sun`, sun_lon(birth_jd, zodiac), so it is not recomputed each time."""
    if natal_sun is None:
        natal_sun = sun_lon(birth_jd, zodiac)
    return (sun_lon(progressed_jd(birth_jd, tjd), zodiac) - natal_sun) % 360


def obliquity(jd: float) -> float:
    return swe.calc_ut(jd, swe.ECL_NUT)[0][0]


def ayanamsa(jd: float, zodiac: str) -> float:
    """Lahiri ayanamsa with nutation, the value calc_ut and houses_ex subtract under FLG_SIDEREAL, so it
    matches natal-chart's sidereal output (get_ayanamsa_ut is the mean value, up to ~0.005° off); 0 for tropical."""
    if not str(zodiac).startswith("sidereal"):
        return 0.0
    return swe.get_ayanamsa_ex_ut(jd, swe.FLG_SWIEPH)[1]


def armc_from_mc(mc: float, eps: float) -> float:
    m, e = math.radians(mc), math.radians(eps)
    return math.degrees(math.atan2(math.sin(m) * math.cos(e), math.cos(m))) % 360.0


def whole_sign_cusps(ascendant: float) -> list[float]:
    """The 12 sign boundaries, starting with the sign the Ascendant is in."""
    start = ascendant // 30 * 30
    return [(start + 30 * i) % 360 for i in range(12)]


def houses_from_armc(armc: float, latitude: float, eps: float, system: str, shift: float = 0.0) -> dict:
    """Cusps and angles for an ARMC at a latitude; whole-sign fallback at polar latitudes.

    houses_armc is tropical: a sidereal chart passes its ayanamsa as `shift`, subtracted from the angles and
    cusps. Whole-sign cusps are then rebuilt from the shifted Ascendant's sign, since shifted tropical sign
    boundaries are not sidereal ones.
    """
    flags = []
    try:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES[system])
    except swe.Error:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES["whole_sign"])
        system, flags = "whole_sign", ["polar_fallback_whole_sign"]
    asc, mc = (ascmc[0] - shift) % 360, (ascmc[1] - shift) % 360
    cusps = whole_sign_cusps(asc) if system == "whole_sign" else [(c - shift) % 360 for c in cusps[:12]]
    return {"system": system, "cusps": cusps,
            "angles": {"ascendant": asc, "mc": mc, "descendant": (asc + 180) % 360, "ic": (mc + 180) % 360},
            "flags": flags}


def house_mover(natal: dict, method: str):
    """A function tjd -> progressed houses (see moved_houses), with the natal constants worked out once."""
    meta = natal["meta"]
    zodiac, birth_jd = meta["zodiac"], meta["julian_day_ut"]
    lat, system = meta["location"]["latitude"], natal["houses"]["system"]
    eps = obliquity(birth_jd)
    natal_mc_trop = (natal["angles"]["mc"] + ayanamsa(birth_jd, zodiac)) % 360
    natal_armc = armc_from_mc(natal_mc_trop, eps)
    natal_sun = sun_lon(birth_jd, "tropical")

    def at(tjd: float) -> dict:
        if method == "naibod":
            armc = (natal_armc + NAIBOD * (tjd - birth_jd) / YEAR) % 360
        else:
            armc = armc_from_mc((natal_mc_trop + solar_arc(birth_jd, tjd, "tropical", natal_sun)) % 360, eps)
        return houses_from_armc(armc, lat, eps, system, ayanamsa(progressed_jd(birth_jd, tjd), zodiac))
    return at


def moved_houses(natal: dict, tjd: float, method: str) -> dict:
    """Progressed houses at the birth latitude, in the natal zodiac.

    'solar-arc': MC = natal MC + true solar arc. 'naibod': natal ARMC + 0.9856473° per year.
    houses_armc has no sidereal mode, so the natal MC goes to tropical with the birth ayanamsa, the houses
    are worked out in tropical (with the tropical arc), and they come back to sidereal with the ayanamsa at
    the progressed instant, the moment the progressed bodies are computed for. A sidereal solar-arc MC is
    therefore natal MC + sidereal arc, as for the bodies.
    """
    return house_mover(natal, method)(tjd)


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


def birth_date(natal: dict) -> dt.date:
    meta = natal["meta"]
    return jd_to_local_date(meta["julian_day_ut"], meta["timezone"])


def day_edges(natal: dict) -> tuple[float, float]:
    """Julian days of 00:00 and 23:59 local on the birth date: the span natal-chart's moon_range covers."""
    day, tz = birth_date(natal), natal["meta"]["timezone"]
    return local_jd(day, dt.time(0, 0), tz), local_jd(day, dt.time(23, 59), tz)


def _moon_range(start: float, end: float) -> dict:
    return {"start": round(start % 360, 4), "end": round(end % 360, 4)}


def _assemble(natal: dict, raw: dict, houses: dict | None, chart_type: str, tjd: float, arc: float,
              angles_method: str | None, moon_range: dict | None) -> dict:
    """raw: name -> (longitude, speed or None, latitude). houses: moved houses or None (untimed).
    The natal meta is copied whole (keeping keys such as house_system_requested); the moving parts are replaced.
    A natal body missing from raw is Chiron without its ephemeris file, flagged as natal-chart flags it."""
    meta = copy.deepcopy(natal["meta"])
    meta["moon_range"] = moon_range
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
    lost = {"chiron_unavailable"} if set(natal["bodies"]) - set(raw) else set()
    meta["flags"] = sorted(set(meta.get("flags", [])) | set(houses["flags"] if houses else []) | lost)
    # The positions come from this run's pyswisseph, so its version and ephemeris replace the natal cast's.
    meta["source"] = {**(meta.get("source") or {}), "library": "pyswisseph", "version": swe.version,
                      "ephemeris_files": ephemeris_files_present()}
    meta["progression"] = {"target_date": jd_to_local_date(tjd, meta["timezone"]).isoformat(),
                           "age_years": round((tjd - meta["julian_day_ut"]) / YEAR, 4),
                           "solar_arc": round(arc, 4), "angles_method": angles_method}
    return {"schema_version": SCHEMA_VERSION, "meta": meta, "angles": angles,
            "houses": {"system": houses["system"], "cusps": [round(c, 4) for c in houses["cusps"]]} if houses else None,
            "bodies": bodies, "aspects": find_aspects(points)}


def progressed_chart(natal: dict, tjd: float, angles_method: str = "solar-arc") -> dict:
    """Secondary progressed chart for target Julian day `tjd` (a target before the birth moment is the birth)."""
    meta = natal["meta"]
    bj = meta["julian_day_ut"]
    tjd = max(tjd, bj)
    pos = body_positions(progressed_jd(bj, tjd), meta["zodiac"], meta.get("node", "true"))
    raw = {n: (p["longitude"], p["speed"], p["latitude"]) for n, p in pos.items() if n in natal["bodies"]}
    houses = moved_houses(natal, tjd, angles_method) if natal.get("angles") else None
    moon = None
    if meta.get("moon_range") is not None:
        # Untimed: the progressed Moon for a birth at each edge of the birth day, each progressed by its own age,
        # never below 0 (on the birth date, a birth at 23:59 has not happened by noon).
        moon = _moon_range(*(swe.calc_ut(progressed_jd(e, max(tjd, e)), swe.MOON, _flags(meta["zodiac"]))[0][0]
                             for e in day_edges(natal)))
    return _assemble(natal, raw, houses, "secondary_progressed", tjd, solar_arc(bj, tjd, meta["zodiac"]),
                     angles_method if houses else None, moon)


def directed_chart(natal: dict, tjd: float) -> dict:
    """Solar arc directed chart: every body, angle and cusp moves by the true solar arc (a target before the
    birth moment is the birth). Whole-sign cusps stay on sign boundaries, from the directed Ascendant's sign."""
    meta = natal["meta"]
    bj = meta["julian_day_ut"]
    tjd = max(tjd, bj)
    arc = solar_arc(bj, tjd, meta["zodiac"])
    raw = {n: ((b["longitude"] + arc) % 360, None, b.get("latitude", 0.0)) for n, b in natal["bodies"].items()}
    houses = None
    if natal.get("angles"):
        angles = {k: (v + arc) % 360 for k, v in natal["angles"].items()}
        system = natal["houses"]["system"]
        cusps = (whole_sign_cusps(angles["ascendant"]) if system == "whole_sign"
                 else [(c + arc) % 360 for c in natal["houses"]["cusps"]])
        houses = {"system": system, "cusps": cusps, "angles": angles, "flags": []}
    moon = None
    if meta.get("moon_range") is not None:
        moon = _moon_range(meta["moon_range"]["start"] + arc, meta["moon_range"]["end"] + arc)
    return _assemble(natal, raw, houses, "solar_arc_directed", tjd, arc, None, moon)


ORB = 1.0                  # timeline window, degrees either side of exact
STEP = 15.0                # days of real time between samples
TOL = 1 / 1440             # bisect to a minute; _settle then puts each moment on its side of local midnight
MARGIN = 5 * YEAR          # scan this far beyond the range so windows overlapping it are found
SLOW_MARGIN = 40 * YEAR    # the same for movers that can stall at a station: windows up to ~37 years (Mars)
EDGE_LIMIT = 60 * YEAR     # look this far past exact for a window's closing edge; beyond it the window is open
SECONDARY_MOVERS = ["Moon", "Sun", "Mercury", "Venus", "Mars"]
SLOW_MOVERS = {"Mercury", "Venus", "Mars"}
STATION_BODIES = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Chiron"]
# Natal positions a ±12 h birth-time error moves by about 0.4° (Mars) to 7° (the Moon): months of solar arc.
TIME_SENSITIVE = {"Moon", "Sun", "Mercury", "Venus", "Mars"}


def _bisect(f, lo: float, hi: float, flo, tz: str) -> float:
    """f(lo) == flo and f(hi) != flo; narrow to TOL and return the moment of the change, on its own local date."""
    while hi - lo > TOL:
        mid = (lo + hi) / 2
        if f(mid) == flo:
            lo = mid
        else:
            hi = mid
    return _settle(f, lo, hi, flo, tz)


def _next_midnight(jd: float, tz: str) -> float:
    """Julian day (UT) at which the local date after jd's begins in `tz`: its 00:00, or on a day whose clocks skip
    midnight the moment they jump past it (zoneinfo reads a skipped time at the offset before the jump, and a
    repeated one at its first occurrence)."""
    y, m, d, h = swe.revjul(jd)
    u = dt.datetime(y, m, d, tzinfo=dt.timezone.utc) + dt.timedelta(hours=h)
    return local_jd(u.astimezone(ZoneInfo(tz)).date() + dt.timedelta(days=1), dt.time(0), tz)


def _settle(f, lo: float, hi: float, flo, tz: str) -> float:
    """The moment to report for a change of f inside the final bracket (lo, hi]: its midpoint, unless a local
    midnight falls inside, where f is evaluated to keep the half that holds the change. The moment is then on the
    change's side of midnight, so its local date is exact whatever the bracket, and printed dates do not depend
    on the sample grid. Before midnight it stays a second clear of it, as jd_to_local_date rounds to the second."""
    m = _next_midnight(lo, tz)
    if m <= hi:
        if f(m) == flo:
            return (m + hi) / 2          # the change comes after midnight: the later date
        hi = m                           # at or before it: the earlier date
    return min((lo + hi) / 2, m - 1 / 86400)


def _grid(t0: float, t1: float) -> list[float]:
    ts, t = [t0], t0
    while t < t1:
        t = min(t + STEP, t1)
        ts.append(t)
    return ts


def _zero_crossings(g, ts, gs, tz: str) -> list[float]:
    """Where g (values in [-180, 180)) crosses zero between samples, ignoring the ±180 seam."""
    out = []
    for (a, ga), (b, gb) in zip(zip(ts, gs), zip(ts[1:], gs[1:])):
        # A real crossing moves g far less than 90° between samples. The exception is within ~0.01° of the
        # polar circle, where the Ascendant can jump ~180° (natal-chart falls back to whole sign there): like
        # the ±180 seam, that jump is not a crossing.
        if (ga < 0 <= gb or ga >= 0 > gb) and abs(gb - ga) < 90:
            out.append(_bisect(lambda x: g(x) >= 0, a, b, ga >= 0, tz))
    return out


def _edge(g, te: float, direction: int, bound: float, tz: str) -> float | None:
    """First time from te toward `bound` (direction ±1) where |g| reaches ORB; None if it stays inside to bound."""
    t = te
    while (bound - t) * direction > 0:
        n = min(t + STEP, bound) if direction > 0 else max(t - STEP, bound)
        if abs(g(n)) >= ORB:
            lo, hi = (t, n) if direction > 0 else (n, t)
            return _bisect(lambda x: abs(g(x)) >= ORB, lo, hi, abs(g(lo)) >= ORB, tz)
        t = n
    return None


def _aspect_events(technique: str, mover: str, m, targets: dict, ts: list[float], tz: str,
                   birth_jd: float) -> list[dict]:
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
                for te in _zero_crossings(g, ts, gs, tz):
                    if tname == mover and te - birth_jd < STEP:
                        continue         # a point leaving its own natal place; rounding makes it look like a pass
                    start = _edge(g, te, -1, birth_jd, tz)
                    rows.append({"technique": technique, "event": "aspect", "moving": mover, "aspect": aname,
                                 "target": tname, "exact": te, "from": birth_jd if start is None else start,
                                 "to": _edge(g, te, +1, te + EDGE_LIMIT, tz), "detail": ""})
    return rows


def _state_events(technique: str, event: str, mover: str, state, ts: list[float], tz: str, describe) -> list[dict]:
    """Rows where state(t) changes between samples; describe(old, new, exact) gives the Detail."""
    rows = []
    vals = [state(t) for t in ts]
    for (a, va), (b, vb) in zip(zip(ts, vals), zip(ts[1:], vals[1:])):
        if va != vb:
            te = _bisect(state, a, b, va, tz)
            rows.append({"technique": technique, "event": event, "moving": mover, "aspect": "", "target": "",
                         "exact": te, "from": None, "to": None, "detail": describe(va, vb, te)})
    return rows


def progressable(natal: dict) -> list[str]:
    """The natal bodies pyswisseph can progress here: Chiron drops out when its ephemeris file is missing."""
    meta = natal["meta"]
    pos = body_positions(meta["julian_day_ut"], meta["zodiac"], meta.get("node", "true"))
    return [n for n in natal["bodies"] if n in pos]


def overlaps(row: dict, start: dt.date, end: dt.date) -> bool:
    """Whether a timeline row, its dates already local, touches start..end, compared as whole days.

    An aspect's window runs from `from` to `to`, open on a side whose edge is None. Ingresses, house ingresses
    and stations have no window: they are point events on `exact`.
    """
    if row["event"] == "aspect":
        lo = row["from"] if row["from"] is not None else dt.date.min
        hi = row["to"] if row["to"] is not None else dt.date.max
    else:
        lo = hi = row["exact"]
    return lo <= end and hi >= start


def timeline(natal: dict, start: dt.date, end: dt.date, angles_method: str = "solar-arc") -> list[dict]:
    """Dated secondary and solar arc events whose 1° window overlaps [start, end], as whole local days."""
    meta = natal["meta"]
    tz, bj, zodiac, node = meta["timezone"], meta["julian_day_ut"], meta["zodiac"], meta.get("node", "true")
    timed = bool(natal.get("angles"))
    r0, r1 = max(target_jd(start, tz), bj), max(target_jd(end, tz), bj)   # never before the birth moment
    ts = _grid(max(bj, r0 - MARGIN), r1 + MARGIN)
    slow_ts = _grid(max(bj, r0 - SLOW_MARGIN), r1 + SLOW_MARGIN)
    targets = {n: b["longitude"] for n, b in natal["bodies"].items()}
    if timed:
        targets["Ascendant"], targets["MC"] = natal["angles"]["ascendant"], natal["angles"]["mc"]
    flags = _flags(zodiac)
    natal_sun = sun_lon(bj, zodiac)
    arcs: dict[float, float] = {}

    def arc(t):
        if t not in arcs:
            arcs[t] = solar_arc(bj, t, zodiac, natal_sun)
        return arcs[t]

    def prog_lon(name):
        ident = swe.MEAN_NODE if (name == "Node" and node == "mean") else BODIES[name]
        return lambda t: swe.calc_ut(progressed_jd(bj, t), ident, flags)[0][0]

    def prog_retro(name):
        return lambda t: swe.calc_ut(progressed_jd(bj, t), BODIES[name], flags)[0][3] < 0

    progressed = progressable(natal)
    rows = []
    for name in SECONDARY_MOVERS:
        if name in natal["bodies"]:
            rows += _aspect_events("secondary", name, prog_lon(name), targets,
                                   slow_ts if name in SLOW_MOVERS else ts, tz, bj)
    if timed:
        # With solar-arc angles the progressed MC is the directed MC by definition; list it once, under solar arc.
        moving = (("Ascendant", "ascendant"),)
        if angles_method != "solar-arc":
            moving += (("MC", "mc"),)
        houses_at = house_mover(natal, angles_method)
        for ang, key in moving:
            rows += _aspect_events("secondary", ang, lambda t, k=key: houses_at(t)["angles"][k], targets, ts, tz, bj)
    for name, lon in targets.items():
        # The directed Sun is the progressed Sun (the arc is the progressed Sun's travel); list it once, under
        # secondary.
        if name != "Sun":
            rows += _aspect_events("solar_arc", name, lambda t, l=lon: (l + arc(t)) % 360, targets, ts, tz, bj)
    for name in progressed:
        f = prog_lon(name)
        rows += _state_events("secondary", "ingress", name, lambda t, f=f: int((f(t) % 360) // 30), ts, tz,
                              lambda a, b, t: f"enters {SIGNS[b]}")
    if timed:
        cusps, f = natal["houses"]["cusps"], prog_lon("Moon")
        rows += _state_events("secondary", "house", "Moon", lambda t: house_of(f(t), cusps), ts, tz,
                              lambda a, b, t: f"enters natal house {b}")
    for name in STATION_BODIES:
        if name in progressed:
            rows += _state_events("secondary", "station", name, prog_retro(name), ts, tz,
                                  lambda a, b, t, f=prog_lon(name):
                                  f"turns {'retrograde' if b else 'direct'} at {format_degree(f(t))}")

    for r in rows:
        for k in ("exact", "from", "to"):
            r[k] = jd_to_local_date(r[k], tz) if r[k] is not None else None
    rows = [r for r in rows if overlaps(r, start, end)]
    for r in rows:
        # Untimed: a 12-hour error in the birth moment moves every secondary event by up to ~6 months (half a
        # progressed day). Solar arc rows move with the natal positions instead, so they are uncertain when
        # the Moon, Sun, Mercury, Venus or Mars is the mover or the target.
        r["uncertain"] = (not timed) and (r["technique"] == "secondary"
                                          or bool(TIME_SENSITIVE & {r["moving"], r["target"]}))
    rows.sort(key=lambda r: (r["exact"], r["technique"], r["moving"], r["target"]))
    return rows


# --- copied from natal-chart/scripts/grid.py ------------------------------------------------

SYMBOLS = {"Conjunction": "☌", "Sextile": "⚹", "Square": "□", "Trine": "△", "Quincunx": "⚻",
           "Opposition": "☍"}


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

MAX_YEARS = 120
TIMELINE_HEADER = ["Technique", "Event", "Moving", "Aspect", "Target", "Exact", "Orb from", "Orb to", "Detail",
                   "Uncertain"]
TECHNIQUE_NAMES = {"secondary": "secondary", "solar_arc": "solar arc"}
UNTIMED_NOTE = ("Note: the birth time is unknown, so every secondary event may fall up to about six months either "
                "side of its date (a 12-hour error in the birth moment is half a progressed day, which is half a "
                "year), and solar arc events involving the Moon, Sun, Mercury, Venus or Mars shift with those natal "
                "positions, by months (years for the Moon); those rows are marked Uncertain, and angle and house "
                "events are left out")
ANGLES_IGNORED_NOTE = "Note: --angles ignored because the natal chart has no birth time, so no angles to progress"


def derived_type(meta: dict) -> str | None:
    """What a chart that is not natal is (its chart_type), or None for a natal chart. A missing chart_type
    means natal (older files); any other value is refused, an empty or null one shown as JSON, and a chart
    carrying meta.progression is progressed whatever it says."""
    chart_type = meta.get("chart_type", "natal")
    if chart_type == "natal":
        return "progressed" if "progression" in meta else None
    return chart_type if chart_type and isinstance(chart_type, str) else json.dumps(chart_type)


def same_file(a: Path, b: Path) -> bool:
    """Whether two paths name one file: the same path after symlinks and `..`, or a hard link."""
    if a.resolve() == b.resolve():
        return True
    try:
        return a.samefile(b)
    except OSError:              # either one does not exist yet
        return False


def build_parser() -> argparse.ArgumentParser:
    p = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("chart", type=Path, help="natal chart.json")
    p.add_argument("--date", type=dt.date.fromisoformat, metavar="YYYY-MM-DD",
                   help="target date for a progressed or directed chart")
    p.add_argument("--timeline", action="store_true", help="write a CSV of dated events from --start to --end")
    p.add_argument("--start", type=dt.date.fromisoformat, metavar="YYYY-MM-DD", help="first date of the timeline")
    p.add_argument("--end", type=dt.date.fromisoformat, metavar="YYYY-MM-DD", help="last date of the timeline")
    p.add_argument("--method", choices=["secondary", "solar-arc"], help="chart technique (default: secondary)")
    p.add_argument("--angles", choices=["solar-arc", "naibod"],
                   help="how secondary progressed angles move (default: solar-arc)")
    p.add_argument("--out", type=Path, help="output path (defaults in the description above)")
    p.add_argument("--grid", type=Path, help="Markdown aspect grid for a chart (default: <out stem>_aspects.md)")
    return p


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
        print(ANGLES_IGNORED_NOTE)
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
    if "Chiron" in natal["bodies"] and "Chiron" not in progressable(natal):
        print("Note: chiron_unavailable")
    if not natal.get("angles"):
        print(UNTIMED_NOTE)
        if args.angles:
            print(ANGLES_IGNORED_NOTE)
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
        out, grid_path = args.out or Path("progressions_timeline.csv"), None
    else:
        if args.start or args.end:
            parser.error("--start and --end apply to --timeline; a chart takes --date")
        if args.method == "solar-arc" and args.angles:
            parser.error("--angles applies to secondary progressed charts; a solar arc directed chart "
                         "moves every angle by the arc")
        kind = "solar_arc_directed" if args.method == "solar-arc" else "secondary_progressed"
        out = args.out or Path(f"{kind}_{args.date.isoformat()}.json")
        grid_path = args.grid or out.with_name(out.stem + "_aspects.md")
        if same_file(grid_path, out):
            print(f"--grid and --out are the same file ({out}); choose a different --grid", file=sys.stderr)
            return 1
    # Every output is checked before anything is computed or written, so a bad --grid never leaves a chart
    # without its grid.
    for flag, path in (("--out", out), ("--grid", grid_path)):
        if path is None:
            continue
        if same_file(path, args.chart):
            print(f"{flag} {path} is the input chart; choose a different {flag}", file=sys.stderr)
            return 1
        if path.is_dir():
            print(f"{flag} {path} is a folder; give a file name", file=sys.stderr)
            return 1
        if not path.parent.is_dir():
            print(f"{flag} {path}: the folder {path.parent} does not exist; create it first", file=sys.stderr)
            return 1

    try:
        natal = load_chart(args.chart)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    meta = natal["meta"]
    kind = derived_type(meta)
    if kind:
        # Returns, composites, Davison and progressed charts all fail here, whether or not they carry a moment.
        print(f"progressions: this is a {kind} chart, not a natal one; progress the natal chart instead",
              file=sys.stderr)
        return 1
    if any(meta.get(k) is None for k in ("julian_day_ut", "datetime_utc", "timezone")):
        print("progressions: this natal chart has no real moment (julian_day_ut, datetime_utc or timezone is "
              "null); recast it with natal-chart", file=sys.stderr)
        return 1

    try:
        return run_timeline(args, natal, out) if args.timeline else run_chart(args, natal, out, grid_path)
    except (KeyError, TypeError, AttributeError) as exc:
        # A key the computation needs is missing or holds the wrong type (a hand-edited or foreign file): name
        # the file and the error, rather than print a bare key name or a traceback.
        print(f"progressions: {args.chart}: malformed chart ({exc!r})", file=sys.stderr)
        return 1
    except (OSError, ValueError, swe.Error) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
