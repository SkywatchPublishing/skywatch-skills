#!/usr/bin/env python3
"""
Compute planetary aspects for a given month/year using Swiss Ephemeris.
Outputs a CSV with all major aspects (conjunction, sextile, square, trine, opposition)
within a 1° orb at noon Pacific, plus every aspect the Moon perfects each day with its
exact time in PST/PDT.

Usage:
    python compute_aspects.py <month> <year> [output.csv]
    python compute_aspects.py 5 2026
    python compute_aspects.py 5 2026 may_2026_aspects.csv
"""

import sys
import csv
import datetime
from zoneinfo import ZoneInfo

try:
    import swisseph as swe
except ImportError as exc:
    print(f"compute_aspects: pyswisseph is required but could not be imported ({exc}); "
          "see Troubleshooting in SKILL.md. Run: pip install pyswisseph", file=sys.stderr)
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────

PLANETS = {
    "Sun":     swe.SUN,
    "Moon":    swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus":   swe.VENUS,
    "Mars":    swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn":  swe.SATURN,
    "Uranus":  swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto":   swe.PLUTO,
}

ASPECTS = {
    "Conjunction": 0,
    "Sextile":     60,
    "Square":      90,
    "Trine":       120,
    "Opposition":  180,
}

ORB = 1.0               # degrees
MOON_SCAN_STEP_MIN = 60 # minutes between Moon samples; each crossing is then refined to the second
PST = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")
J2000 = datetime.datetime(2000, 1, 1, 12, 0, tzinfo=UTC)  # Julian Day 2451545.0

# ── Ephemeris helpers ──────────────────────────────────────────────────────────

def dt_to_jd(dt: datetime.datetime) -> float:
    """Convert a timezone-aware datetime to Julian Day (UT)."""
    utc_dt = dt.astimezone(UTC)
    return swe.julday(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    )

def get_longitude(jd: float, planet_id: int) -> float:
    """Return ecliptic longitude (0–360) for a planet at a given JD."""
    result, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH)
    return result[0]

def angular_distance(lon1: float, lon2: float) -> float:
    """Shortest arc between two ecliptic longitudes."""
    diff = abs(lon1 - lon2) % 360
    return min(diff, 360 - diff)

def aspect_name(dist: float) -> str | None:
    """Return aspect name if dist is within ORB of a major aspect angle."""
    for name, angle in ASPECTS.items():
        if abs(dist - angle) <= ORB:
            return name
    return None

# ── Moon exact-time finder ─────────────────────────────────────────────────────

def wrap180(x: float) -> float:
    return (x + 180.0) % 360.0 - 180.0

def jd_to_local_minute(jd: float) -> datetime.datetime:
    """Julian Day (UT) to PST/PDT, rounded to the nearest minute."""
    exact = J2000 + datetime.timedelta(days=jd - 2451545.0)
    rounded = (exact + datetime.timedelta(seconds=30)).replace(second=0, microsecond=0)
    return rounded.astimezone(PST)

def refine_moon_root(other_planet_id: int, target: float, lo: float, hi: float) -> float:
    """Bisect the moment the Moon is exactly `target` degrees ahead of the other body."""
    def gap(jd):
        return wrap180(get_longitude(jd, swe.MOON) - get_longitude(jd, other_planet_id) - target)

    gap_lo = gap(lo)
    while (hi - lo) * 86400 > 0.5:
        mid = (lo + hi) / 2
        gap_mid = gap(mid)
        if (gap_mid >= 0) == (gap_lo >= 0):
            lo, gap_lo = mid, gap_mid
        else:
            hi = mid
    return (lo + hi) / 2

def moon_aspects_on(date: datetime.date) -> list[tuple[str, str, datetime.datetime]]:
    """
    Every aspect the Moon perfects during one Pacific calendar day, as (other body, aspect,
    local time rounded to the minute), sorted by time. The Moon is sampled every
    MOON_SCAN_STEP_MIN minutes and each sign change of its distance from exact is bisected
    to the second, so no aspect is missed however far it falls from noon.
    """
    # The window is shifted back 30 seconds so an aspect lands on the day its rounded time shows.
    start = datetime.datetime(date.year, date.month, date.day, tzinfo=PST)
    end = datetime.datetime.combine(date + datetime.timedelta(days=1), datetime.time(), tzinfo=PST)
    half_minute = datetime.timedelta(seconds=30)
    jd0, jd1 = dt_to_jd(start - half_minute), dt_to_jd(end - half_minute)
    steps = max(1, round((jd1 - jd0) * 1440 / MOON_SCAN_STEP_MIN))
    grid = [jd0 + (jd1 - jd0) * k / steps for k in range(steps + 1)]
    moon = [get_longitude(jd, swe.MOON) for jd in grid]

    hits = []
    for other, other_id in PLANETS.items():
        if other == "Moon":
            continue
        lons = [get_longitude(jd, other_id) for jd in grid]
        for aspect, angle in ASPECTS.items():
            for target in {angle, (360 - angle) % 360}:  # waxing and waning sides
                gaps = [wrap180(m - o - target) for m, o in zip(moon, lons)]
                for k in range(steps):
                    a, b = gaps[k], gaps[k + 1]
                    # a sign change, not the ±180° wraparound on the far side of the circle
                    if (a >= 0) != (b >= 0) and abs(b - a) < 90:
                        jd = refine_moon_root(other_id, target, grid[k], grid[k + 1])
                        if jd0 <= jd < jd1:
                            hits.append((other, aspect, jd_to_local_minute(jd)))
    return sorted(hits, key=lambda h: h[2])

# ── Main computation ───────────────────────────────────────────────────────────

def compute_aspects(month: int, year: int) -> list[dict]:
    """
    Return a list of aspect dicts for every day of the given month/year.
    Slow bodies: listed when within ORB at noon Pacific, with the noon orb.
    Moon: every aspect that perfects during the day, with its PST/PDT time and an orb of 0.
    """
    rows = []
    planet_names = list(PLANETS.keys())

    # Iterate over each day
    num_days = (
        datetime.date(year + (month // 12), (month % 12) + 1, 1)
        - datetime.date(year, month, 1)
    ).days

    for day in range(1, num_days + 1):
        date = datetime.date(year, month, day)

        # Noon PST as the canonical daily snapshot for slow planets
        noon_pst = datetime.datetime(year, month, day, 12, 0, tzinfo=PST)
        jd_noon = dt_to_jd(noon_pst)

        # Pre-fetch all longitudes at noon
        lons = {name: get_longitude(jd_noon, pid) for name, pid in PLANETS.items()}

        # Every Moon aspect that perfects today, keyed by the other body
        moon_hits = {}
        for other, asp, when in moon_aspects_on(date):
            moon_hits.setdefault(other, []).append((asp, when))

        # Check every planet pair
        for i, p1 in enumerate(planet_names):
            for p2 in planet_names[i + 1:]:
                if p1 == "Moon" or p2 == "Moon":
                    other = p2 if p1 == "Moon" else p1
                    for asp, when in moon_hits.get(other, []):
                        tz_label = "PDT" if when.dst() else "PST"
                        rows.append({
                            "Date":        date.strftime("%Y-%m-%d"),
                            "Planet 1":    p1,
                            "Aspect":      asp,
                            "Planet 2":    p2,
                            "Orb (°)":     0.0,  # listed at the moment it perfects
                            "Exact Time":  when.strftime(f"%I:%M %p {tz_label}"),
                        })
                    continue

                dist = angular_distance(lons[p1], lons[p2])
                asp = aspect_name(dist)
                if asp is None:
                    continue

                rows.append({
                    "Date":        date.strftime("%Y-%m-%d"),
                    "Planet 1":    p1,
                    "Aspect":      asp,
                    "Planet 2":    p2,
                    "Orb (°)":     round(abs(dist - ASPECTS[asp]), 3),
                    "Exact Time":  "",
                })

    return rows

# ── Output ─────────────────────────────────────────────────────────────────────

def write_csv(rows: list[dict], path: str):
    fieldnames = ["Date", "Planet 1", "Aspect", "Planet 2", "Orb (°)", "Exact Time"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} aspects to {path}")

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python compute_aspects.py <month> <year> [output.csv]")
        sys.exit(1)

    month = int(sys.argv[1])
    year  = int(sys.argv[2])
    month_name = datetime.date(year, month, 1).strftime("%B_%Y").lower()
    out_path = sys.argv[3] if len(sys.argv) > 3 else f"aspects_{month_name}.csv"

    print(f"Computing aspects for {datetime.date(year, month, 1).strftime('%B %Y')}...")
    rows = compute_aspects(month, year)
    write_csv(rows, out_path)
    print(f"Done. {len(rows)} aspect rows written.")
