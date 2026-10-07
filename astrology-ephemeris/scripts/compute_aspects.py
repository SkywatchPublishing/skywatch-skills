#!/usr/bin/env python3
"""
Compute planetary aspects for a given month/year using Swiss Ephemeris.
Outputs a CSV with all major aspects (conjunction, sextile, square, trine, opposition)
within a 1° orb. Moon aspects include exact time in PST/PDT.

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
except ImportError:
    print("Installing pyswisseph...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyswisseph", "--quiet"])
    import swisseph as swe

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

ORB = 1.0          # degrees
MOON_STEP_MIN = 10 # minutes — resolution for finding Moon exact times
PST = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")

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

def find_moon_exact_time(
    jd_start: float,
    jd_end: float,
    other_planet_id: int,
    target_angle: float,
) -> datetime.datetime | None:
    """
    Scan in MOON_STEP_MIN increments for the moment Moon's aspect to other_planet is closest to
    exact within [jd_start, jd_end]. Returns PST/PDT datetime or None.
    """
    step = MOON_STEP_MIN / (60 * 24)  # in JD units
    best_jd = None
    best_diff = float("inf")

    jd = jd_start
    while jd <= jd_end:
        moon_lon = get_longitude(jd, swe.MOON)
        other_lon = get_longitude(jd, other_planet_id)
        dist = angular_distance(moon_lon, other_lon)
        diff = abs(dist - target_angle)
        if diff < best_diff:
            best_diff = diff
            best_jd = jd
        jd += step

    if best_jd is None or best_diff > ORB:
        return None

    # Convert JD → UTC → PST/PDT
    y, m, d, h = swe.revjul(best_jd)
    hour = int(h)
    minute = int((h - hour) * 60)
    utc_dt = datetime.datetime(y, m, d, hour, minute, tzinfo=UTC)
    return utc_dt.astimezone(PST)

# ── Main computation ───────────────────────────────────────────────────────────

def compute_aspects(month: int, year: int) -> list[dict]:
    """
    Return a list of aspect dicts for every day of the given month/year.
    Moon aspects include exact PST/PDT time; others just the date.
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

        # Day boundaries in JD (for Moon search)
        day_start_pst = datetime.datetime(year, month, day, 0, 0, tzinfo=PST)
        day_end_pst   = datetime.datetime(year, month, day, 23, 59, tzinfo=PST)
        jd_day_start  = dt_to_jd(day_start_pst)
        jd_day_end    = dt_to_jd(day_end_pst)

        # Pre-fetch all longitudes at noon
        lons = {name: get_longitude(jd_noon, pid) for name, pid in PLANETS.items()}

        # Check every planet pair
        for i, p1 in enumerate(planet_names):
            for p2 in planet_names[i + 1:]:
                dist = angular_distance(lons[p1], lons[p2])
                asp = aspect_name(dist)
                if asp is None:
                    continue

                orb_val = round(abs(dist - ASPECTS[asp]), 3)
                exact_time_str = ""

                # For Moon aspects, find the exact time within the day
                if p1 == "Moon" or p2 == "Moon":
                    other = p2 if p1 == "Moon" else p1
                    other_id = PLANETS[other]
                    exact_dt = find_moon_exact_time(
                        jd_day_start, jd_day_end,
                        other_id, ASPECTS[asp]
                    )
                    if exact_dt:
                        tz_label = "PDT" if exact_dt.dst() else "PST"
                        exact_time_str = exact_dt.strftime(f"%I:%M %p {tz_label}")

                rows.append({
                    "Date":        date.strftime("%Y-%m-%d"),
                    "Planet 1":    p1,
                    "Aspect":      asp,
                    "Planet 2":    p2,
                    "Orb (°)":     orb_val,
                    "Exact Time":  exact_time_str,
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
