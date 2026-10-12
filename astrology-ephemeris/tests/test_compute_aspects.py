"""Moon coverage for compute_aspects.

Independent source for the lunar phase times
--------------------------------------------
U.S. Naval Observatory, Astronomical Applications API, phases of the Moon for 2026:
    https://aa.usno.navy.mil/api/moon/phases/year?year=2026
Accessed 2026-10-12. USNO gives each phase to the minute in UT. A New Moon is the Sun-Moon
conjunction in ecliptic longitude, a Full Moon the opposition, and each quarter a square,
so every phase is also a row this script must write, at the published minute.
"""
import csv
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import compute_aspects as ca

PT = ZoneInfo("America/Los_Angeles")
EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "aspects_april_2026.csv"

USNO_APRIL_2026 = [
    ("Full Moon", dt.datetime(2026, 4, 2, 2, 12, tzinfo=dt.timezone.utc), "Opposition"),
    ("Last Quarter", dt.datetime(2026, 4, 10, 4, 51, tzinfo=dt.timezone.utc), "Square"),
    ("New Moon", dt.datetime(2026, 4, 17, 11, 52, tzinfo=dt.timezone.utc), "Conjunction"),
    ("First Quarter", dt.datetime(2026, 4, 24, 2, 32, tzinfo=dt.timezone.utc), "Square"),
]


@pytest.fixture(scope="module")
def april():
    return ca.compute_aspects(4, 2026)


def is_moon(row):
    return "Moon" in (row["Planet 1"], row["Planet 2"])


def listed_time(row):
    """The row's Exact Time as an aware datetime in Pacific time."""
    clock = row["Exact Time"].rsplit(" ", 1)[0]  # drop the PST/PDT label
    return dt.datetime.strptime(f"{row['Date']} {clock}", "%Y-%m-%d %I:%M %p").replace(tzinfo=PT)


@pytest.mark.parametrize("phase, utc, aspect", USNO_APRIL_2026, ids=[p[0] for p in USNO_APRIL_2026])
def test_lunar_phases_are_listed_at_the_published_minute(april, phase, utc, aspect):
    local = utc.astimezone(PT)
    rows = [r for r in april if (r["Planet 1"], r["Aspect"], r["Planet 2"]) == ("Sun", aspect, "Moon")
            and r["Date"] == local.strftime("%Y-%m-%d")]
    assert len(rows) == 1, f"{phase} on {local:%Y-%m-%d} missing"
    assert abs(listed_time(rows[0]) - local) <= dt.timedelta(minutes=1)


def test_every_moon_aspect_of_the_month_is_listed(april):
    # 77 is the count an independent search finds for the same local dates (the aspectarian skill,
    # Skyfield and JPL DE440). The noon-snapshot version listed 13.
    assert len([r for r in april if is_moon(r)]) == 77


def test_night_time_moon_aspect_is_listed():
    # Exact at 01:55 Pacific, when the noon sample has the Moon five degrees past it.
    hits = ca.moon_aspects_on(dt.date(2026, 4, 2))
    assert [(o, a, w.strftime("%I:%M %p %Z")) for o, a, w in hits if o == "Jupiter"] == [
        ("Jupiter", "Square", "01:55 AM PDT")]


def test_moon_rows_have_an_exact_time_and_zero_orb(april):
    for row in april:
        if is_moon(row):
            assert row["Exact Time"].endswith((" PST", " PDT"))
            assert row["Orb (°)"] == 0.0


def test_each_moon_aspect_is_listed_once(april):
    keys = [(r["Date"], r["Planet 1"], r["Aspect"], r["Planet 2"]) for r in april if is_moon(r)]
    assert len(keys) == len(set(keys))


def test_hits_are_sorted_and_inside_the_local_day():
    day = dt.date(2026, 4, 19)
    hits = ca.moon_aspects_on(day)
    times = [w for _, _, w in hits]
    assert times == sorted(times)
    assert all(w.date() == day for w in times)


@pytest.mark.parametrize("day", [dt.date(2026, 3, 8), dt.date(2026, 11, 1)], ids=["spring-forward", "fall-back"])
def test_daylight_saving_days_label_each_hit_by_its_own_offset(day):
    hits = ca.moon_aspects_on(day)
    assert hits
    for _, _, when in hits:
        assert when.date() == day
        assert when.tzname() == ("PDT" if when.dst() else "PST")


def test_slow_planet_rows_match_the_committed_example(april):
    with EXAMPLE.open(encoding="utf-8") as f:
        expected = [r for r in csv.DictReader(f) if not is_moon(r)]
    got = [{k: str(v) for k, v in r.items()} for r in april if not is_moon(r)]
    assert got == expected
    assert {"Date": "2026-04-16", "Planet 1": "Mars", "Aspect": "Sextile", "Planet 2": "Pluto",
            "Orb (°)": "0.002", "Exact Time": ""} in got
