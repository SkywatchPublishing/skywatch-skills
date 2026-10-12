#!/usr/bin/env python3
"""
Monthly aspectarian and void-of-course Moon table, computed from NASA JPL's DE440 ephemeris
with Skyfield. No Swiss Ephemeris: Skyfield and jplephem are MIT-licensed and DE440 is NASA data.

Usage:
    python aspectarian.py <month> <year> [--tz ZONE] [--traditional] [--out-dir DIR] [--ephemeris PATH]
    python aspectarian.py 4 2026
    python aspectarian.py 4 2026 --tz America/New_York --out-dir datebook/

Writes aspectarian_<year>_<month>.csv (every exact major aspect between the bodies, in time order)
and voc_<year>_<month>.csv (every void-of-course Moon period touching the month, ending at the
Moon's sign ingress). --traditional adds a _traditional suffix. Fetch the ephemeris once with
scripts/fetch_ephemeris.py.
"""
import argparse
import bisect
import csv
import datetime as dt
import sys
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
from skyfield.api import load, load_file
from skyfield.errors import EphemerisRangeError
from skyfield.framelib import ecliptic_frame

# ── Configuration ─────────────────────────────────────────────────────────────

# Moon first, then by mean speed, so each aspect names the faster body first.
BODIES = {
    "Moon": "moon", "Sun": "sun", "Mercury": "mercury", "Venus": "venus", "Mars": "mars barycenter",
    "Jupiter": "jupiter barycenter", "Saturn": "saturn barycenter", "Uranus": "uranus barycenter",
    "Neptune": "neptune barycenter", "Pluto": "pluto barycenter",
}
TRADITIONAL = ["Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
ASPECTS = {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Opposition": 180}
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

STEP_DAYS = 1 / 24              # sampling grid; the Moon moves about half a degree an hour
TOLERANCE_DAYS = 0.1 / 86400    # each crossing is bisected to a tenth of a second
PAD_DAYS = 4                    # a void can begin days before the month and end days after it
EPHEMERIS = Path(__file__).resolve().parents[1] / "ephe" / "de440s.bsp"  # 1849-12-26 to 2150-01-22

ASPECT_FIELDS = ["Date", "Time", "Body 1", "Aspect", "Body 2", "UTC"]
VOID_FIELDS = ["Begins Date", "Begins Time", "Last Aspect", "Moon Enters", "Ingress Date", "Ingress Time",
               "Duration", "Begins UTC", "Ingress UTC"]


class Aspect(NamedTuple):
    jd: float  # Julian Day, Terrestrial Time
    body1: str
    aspect: str
    body2: str


class Ingress(NamedTuple):
    jd: float
    sign: str


class Void(NamedTuple):
    last: Aspect
    ingress: Ingress


# ── Ephemeris ─────────────────────────────────────────────────────────────────

class Sky:
    def __init__(self, ephemeris_path):
        self.ts = load.timescale()  # built-in leap seconds and delta T, no download
        self.eph = load_file(str(ephemeris_path))
        self.earth = self.eph["earth"]

    def longitudes(self, jd_tt, names):
        """Apparent geocentric ecliptic longitude of date (tropical zodiac), in degrees.

        Light time, aberration, precession and nutation are applied, which is what an ephemeris
        means by "the Moon at 14° Leo". Accepts one Julian Day or an array of them.
        """
        observer = self.earth.at(self.ts.tt_jd(jd_tt))
        out = {}
        for name in names:
            _, lon, _ = observer.observe(self.eph[BODIES[name]]).apparent().frame_latlon(ecliptic_frame)
            out[name] = lon.degrees
        return out

    def utc(self, jd_tt) -> dt.datetime:
        return self.ts.tt_jd(jd_tt).utc_datetime()


# ── Search ────────────────────────────────────────────────────────────────────

def wrap180(x):
    return (x + 180.0) % 360.0 - 180.0


def targets(angle):
    """Separations at which an aspect is exact: both sides of the circle, once for 0° and 180°."""
    return sorted({angle, (360 - angle) % 360})


def crossings(values):
    """Indices i where values cross zero between samples i and i+1, ignoring the ±180° wraparound."""
    sign = values >= 0
    small_step = np.abs(np.diff(values)) < 90
    return np.nonzero((sign[:-1] != sign[1:]) & small_step)[0]


def bisect_many(fn, lo, hi):
    """Bisect many bracketed sign changes at once; fn maps an array of times to an array of values."""
    lo, hi = np.array(lo, dtype=float), np.array(hi, dtype=float)
    f_lo = fn(lo)
    while np.max(hi - lo) > TOLERANCE_DAYS:
        mid = (lo + hi) / 2
        f_mid = fn(mid)
        same = (f_mid >= 0) == (f_lo >= 0)
        lo, f_lo, hi = np.where(same, mid, lo), np.where(same, f_mid, f_lo), np.where(same, hi, mid)
    return (lo + hi) / 2


def exact_aspects(sky, grid, lons, names):
    found = []  # (sample index, body 1, body 2, target separation, aspect name)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for aspect, angle in ASPECTS.items():
                for target in targets(angle):
                    for k in crossings(wrap180(lons[a] - lons[b] - target)):
                        found.append((k, a, b, target, aspect))
    if not found:
        return []
    k = np.array([f[0] for f in found])
    ia = np.array([names.index(f[1]) for f in found])
    ib = np.array([names.index(f[2]) for f in found])
    target = np.array([f[3] for f in found], dtype=float)
    column = np.arange(len(found))

    def gap(times):
        pos = sky.longitudes(times, names)
        table = np.vstack([pos[n] for n in names])
        return wrap180(table[ia, column] - table[ib, column] - target)

    jds = bisect_many(gap, grid[k], grid[k + 1])
    return sorted(Aspect(float(jd), f[1], f[4], f[2]) for jd, f in zip(jds, found))


def moon_ingresses(sky, grid, moon):
    sign = (moon // 30).astype(int) % 12
    k = np.nonzero(sign[:-1] != sign[1:])[0]
    if len(k) == 0:
        return []
    boundary = 30.0 * sign[k + 1]
    jds = bisect_many(lambda t: wrap180(sky.longitudes(t, ["Moon"])["Moon"] - boundary), grid[k], grid[k + 1])
    return [Ingress(float(jd), SIGNS[s]) for jd, s in zip(jds, sign[k + 1])]


def search(sky, start_tt, end_tt, names):
    """Every exact aspect between `names`, and every Moon sign ingress, between two Julian Days (TT)."""
    grid = np.arange(start_tt, end_tt + STEP_DAYS, STEP_DAYS)
    lons = sky.longitudes(grid, names)
    ingresses = moon_ingresses(sky, grid, lons["Moon"]) if "Moon" in names else []
    return exact_aspects(sky, grid, lons, names), ingresses


def void_of_course(aspects, ingresses):
    """The Moon is void from its last exact aspect until it enters the next sign.

    If the Moon makes no aspect in a whole sign, the void runs on from its last aspect in the
    sign before. An ingress with no Moon aspect before it in the searched window is dropped.
    """
    moon = [a for a in aspects if "Moon" in (a.body1, a.body2)]
    times = [a.jd for a in moon]
    voids = []
    for ingress in ingresses:
        i = bisect.bisect_left(times, ingress.jd)
        if i:
            voids.append(Void(moon[i - 1], ingress))
    return voids


# ── Formatting ────────────────────────────────────────────────────────────────

def round_minute(when: dt.datetime) -> dt.datetime:
    return (when + dt.timedelta(seconds=30)).replace(second=0, microsecond=0)


def clock(when: dt.datetime) -> str:
    return f"{when:%I:%M %p} {when.tzname()}"


def iso_utc(when: dt.datetime) -> str:
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def duration_label(span: dt.timedelta) -> str:
    minutes = round(span.total_seconds() / 60)
    return f"{minutes // 60}h {minutes % 60:02d}m"


def compute_month(sky, year, month, zone, traditional=False):
    """Rows for the aspectarian and void-of-course CSVs of one calendar month in `zone`.

    An event belongs to the month of its local time rounded to the minute, the time printed.
    """
    names = TRADITIONAL if traditional else list(BODIES)
    first = dt.datetime(year, month, 1, tzinfo=zone)
    nxt = dt.datetime(year + month // 12, month % 12 + 1, 1, tzinfo=zone)
    lo, hi = first.astimezone(dt.timezone.utc), nxt.astimezone(dt.timezone.utc)
    start = sky.ts.from_datetime(lo - dt.timedelta(days=PAD_DAYS)).tt
    end = sky.ts.from_datetime(hi + dt.timedelta(days=PAD_DAYS)).tt
    aspects, ingresses = search(sky, start, end, names)

    aspect_rows = []
    for a in aspects:
        exact = sky.utc(a.jd)
        shown = round_minute(exact)
        if lo <= shown < hi:
            local = shown.astimezone(zone)
            aspect_rows.append({"Date": f"{local:%Y-%m-%d}", "Time": clock(local), "Body 1": a.body1,
                                "Aspect": a.aspect, "Body 2": a.body2, "UTC": iso_utc(exact)})

    void_rows = []
    for v in void_of_course(aspects, ingresses):
        begins, ends = sky.utc(v.last.jd), sky.utc(v.ingress.jd)
        b, e = round_minute(begins), round_minute(ends)
        if b < hi and e >= lo:
            bl, el = b.astimezone(zone), e.astimezone(zone)
            void_rows.append({
                "Begins Date": f"{bl:%Y-%m-%d}", "Begins Time": clock(bl),
                "Last Aspect": f"{v.last.body1} {v.last.aspect} {v.last.body2}",
                "Moon Enters": v.ingress.sign, "Ingress Date": f"{el:%Y-%m-%d}", "Ingress Time": clock(el),
                "Duration": duration_label(e - b),  # both UTC, so a daylight-saving change is counted
                "Begins UTC": iso_utc(begins), "Ingress UTC": iso_utc(ends),
            })
    return aspect_rows, void_rows


# ── Output ────────────────────────────────────────────────────────────────────

def write_csv(rows, fields, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("month", type=int)
    parser.add_argument("year", type=int)
    parser.add_argument("--tz", default="America/Los_Angeles", help="IANA time zone for dates and times")
    parser.add_argument("--traditional", action="store_true",
                        help="aspects and voids among the visible planets only, Sun through Saturn")
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    parser.add_argument("--ephemeris", type=Path, default=EPHEMERIS)
    args = parser.parse_args(argv)

    def fail(message):
        print(f"aspectarian: {message}", file=sys.stderr)
        return 1

    if not 1 <= args.month <= 12:
        return fail("month must be 1 to 12")
    if not 2 <= args.year <= 9998:  # the padded window must stay inside Python's datetime
        return fail("year must be 2 to 9998")
    try:
        zone = ZoneInfo(args.tz)
    except (ZoneInfoNotFoundError, ValueError):
        return fail(f"unknown time zone {args.tz!r}; use an IANA name such as America/New_York")
    if not args.ephemeris.exists():
        return fail(f"ephemeris not found at {args.ephemeris}; run python scripts/fetch_ephemeris.py once "
                    "(a 32 MB download from NASA JPL)")

    try:
        aspect_rows, void_rows = compute_month(Sky(args.ephemeris), args.year, args.month, zone, args.traditional)
    except EphemerisRangeError as exc:
        return fail(f"{args.year}-{args.month:02d} is outside {args.ephemeris.name}: {exc}; "
                    "fetch de440.bsp (1550 to 2650) from the same NAIF folder and pass --ephemeris")

    suffix = "_traditional" if args.traditional else ""
    args.out_dir.mkdir(parents=True, exist_ok=True)
    aspect_path = args.out_dir / f"aspectarian_{args.year}_{args.month:02d}{suffix}.csv"
    void_path = args.out_dir / f"voc_{args.year}_{args.month:02d}{suffix}.csv"
    write_csv(aspect_rows, ASPECT_FIELDS, aspect_path)
    write_csv(void_rows, VOID_FIELDS, void_path)
    print(f"Wrote {len(aspect_rows)} aspects to {aspect_path}")
    print(f"Wrote {len(void_rows)} void-of-course periods to {void_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
