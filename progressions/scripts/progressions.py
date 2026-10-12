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
