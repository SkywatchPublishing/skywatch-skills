#!/usr/bin/env python3
"""
Cast return charts (solar, lunar, Mars, Jupiter, Saturn, Uranus, Chiron) for a date range.

Usage:
    python returns.py chart.json --body sun --start 2027-01-01 --end 2027-12-31 --city "Austin, TX"
    python returns.py chart.json --body moon --start 2027-01-01 --end 2027-03-31 --geonameid 5128581
    python returns.py chart.json --start 2027-01-01 --end 2027-12-31            # natal place, flagged

Each return is cast by the sibling natal-chart script, so the output files are ordinary chart.json
files that chart-wheel, transits-to-natal and synastry read unchanged. Exit 2 means an ambiguous
city (candidates printed); re-run with --geonameid.
"""
import argparse
import datetime as dt
import json
import math
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

for _ephe in (Path(__file__).resolve().parents[1] / "ephe", Path(__file__).resolve().parents[2] / "natal-chart" / "ephe"):
    if (_ephe / "seas_18.se1").exists():
        swe.set_ephe_path(str(_ephe))
        break

BODIES = {
    "sun": ("Sun", swe.SUN), "moon": ("Moon", swe.MOON), "mars": ("Mars", swe.MARS),
    "jupiter": ("Jupiter", swe.JUPITER), "saturn": ("Saturn", swe.SATURN),
    "uranus": ("Uranus", swe.URANUS), "chiron": ("Chiron", swe.CHIRON),
}
FLAGS = swe.FLG_SWIEPH


def wrapped(lon: float, target: float) -> float:
    """Signed difference lon - target in (-180, 180]."""
    return ((lon - target + 180.0) % 360.0) - 180.0


def longitude(jd: float, body: int, sidereal: bool = False) -> float:
    flags = FLAGS | (swe.FLG_SIDEREAL if sidereal else 0)
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
    return swe.calc_ut(jd, body, flags)[0][0]


def precession_shift(natal_jd: float, jd: float) -> float:
    """Ayanamsa drift between two moments (Lahiri), in degrees; add to the tropical target."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    return swe.get_ayanamsa_ut(jd) - swe.get_ayanamsa_ut(natal_jd)


def find_returns(body: int, target: float, start: dt.date, end: dt.date, sidereal: bool = False,
                 shift_fn=None) -> list[float]:
    """Julian days (UT) at which `body` crosses `target` longitude between start 00:00 and end 24:00 UT.

    Samples daily, detects sign changes of the wrapped difference (ignoring the 180° wrap), and
    bisects each to about 1e-10 day. Retrograde loops give one hit per crossing. `shift_fn(jd)`,
    when given, is added to the target at each evaluation (precession correction).
    """
    def diff(jd: float) -> float:
        t = target + (shift_fn(jd) if shift_fn else 0.0)
        return wrapped(longitude(jd, body, sidereal), t)

    jd = swe.julday(start.year, start.month, start.day, 0.0)
    last = swe.julday(end.year, end.month, end.day, 24.0)
    hits = []
    prev = diff(jd)
    while jd < last:
        nxt = min(jd + 1.0, last)
        cur = diff(nxt)
        if prev == 0.0:
            hits.append(jd)
        elif (prev < 0 < cur or prev > 0 > cur) and abs(cur - prev) < 180.0:
            lo, hi, flo = jd, nxt, prev
            for _ in range(60):
                mid = (lo + hi) / 2
                fm = diff(mid)
                if (fm < 0) == (flo < 0):
                    lo, flo = mid, fm
                else:
                    hi = mid
            hits.append((lo + hi) / 2)
        jd, prev = nxt, cur
    return hits
