"""Thin wrapper over pyswisseph: positions, houses, and the two fallbacks the design requires."""
import datetime as dt
from pathlib import Path

import swisseph as swe

EPHE_DIR = Path(__file__).resolve().parents[1] / "ephe"
swe.set_ephe_path(str(EPHE_DIR))

BODIES = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO, "Chiron": swe.CHIRON, "Node": swe.TRUE_NODE,
}
HOUSE_CODES = {"placidus": b"P", "koch": b"K", "equal": b"E", "porphyry": b"O", "whole_sign": b"W"}
FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED


def ephemeris_files_present() -> bool:
    return (EPHE_DIR / "seas_18.se1").exists()


def julian_day(when: dt.datetime) -> float:
    u = when.astimezone(dt.timezone.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600)


def body_positions(jd: float, zodiac: str = "tropical", node: str = "true") -> dict[str, dict]:
    """Longitude, latitude, speed for every body. Chiron is omitted when its file is missing.
    zodiac: 'tropical' or 'sidereal' (Lahiri). node: 'true' or 'mean'."""
    flags = FLAGS
    if zodiac == "sidereal":
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL
    out = {}
    for name, ident in BODIES.items():
        if name == "Node" and node == "mean":
            ident = swe.MEAN_NODE
        try:
            (lon, lat, _dist, dlon, *_), _ = swe.calc_ut(jd, ident, flags)
        except swe.Error:
            if name == "Chiron":
                continue
            raise
        out[name] = {"longitude": lon % 360, "latitude": lat, "speed": dlon}
    return out


def houses(jd: float, latitude: float, longitude: float, system: str) -> tuple[dict, list[str]]:
    """Cusps and angles. Falls back to Whole Sign where the requested system fails (polar latitudes)."""
    flags = []
    try:
        cusps, ascmc = swe.houses(jd, latitude, longitude, HOUSE_CODES[system])
    except swe.Error:
        if system == "whole_sign":
            raise
        cusps, ascmc = swe.houses(jd, latitude, longitude, HOUSE_CODES["whole_sign"])
        system = "whole_sign"
        flags.append("polar_fallback_whole_sign")
    asc, mc = ascmc[0] % 360, ascmc[1] % 360
    return {
        "system": system,
        "cusps": [c % 360 for c in cusps[:12]],
        "angles": {"ascendant": asc, "mc": mc, "descendant": (asc + 180) % 360, "ic": (mc + 180) % 360},
    }, flags
