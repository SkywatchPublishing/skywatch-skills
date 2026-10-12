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
"""
import datetime as dt
import math
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
