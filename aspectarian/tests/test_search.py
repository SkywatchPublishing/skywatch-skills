"""Root finding, ingresses, and the void-of-course rule.

Independent source for the lunar phase times
--------------------------------------------
U.S. Naval Observatory, Astronomical Applications API, phases of the Moon for 2026:
    https://aa.usno.navy.mil/api/moon/phases/year?year=2026
Accessed 2026-10-12. USNO gives each phase to the minute in UT. A New Moon is the Sun-Moon
conjunction in ecliptic longitude, a Full Moon the opposition, and each quarter a square,
so all 50 phases of the year are aspects the search must find, at the published minute.
"""
import datetime as dt

import numpy as np
import pytest

import aspectarian as A

USNO_2026 = [
    '01-03 10:03 O', '01-10 15:48 L', '01-18 19:52 N', '01-26 04:47 F', '02-01 22:09 O', '02-09 12:43 L',
    '02-17 12:01 N', '02-24 12:27 F', '03-03 11:38 O', '03-11 09:38 L', '03-19 01:23 N', '03-25 19:18 F',
    '04-02 02:12 O', '04-10 04:51 L', '04-17 11:52 N', '04-24 02:32 F', '05-01 17:23 O', '05-09 21:10 L',
    '05-16 20:01 N', '05-23 11:11 F', '05-31 08:45 O', '06-08 10:00 L', '06-15 02:54 N', '06-21 21:55 F',
    '06-29 23:56 O', '07-07 19:29 L', '07-14 09:43 N', '07-21 11:05 F', '07-29 14:36 O', '08-06 02:21 L',
    '08-12 17:37 N', '08-20 02:46 F', '08-28 04:18 O', '09-04 07:51 L', '09-11 03:27 N', '09-18 20:44 F',
    '09-26 16:49 O', '10-03 13:25 L', '10-10 15:50 N', '10-18 16:12 F', '10-26 04:12 O', '11-01 20:28 L',
    '11-09 07:02 N', '11-17 11:48 F', '11-24 14:53 O', '12-01 06:08 L', '12-09 00:52 N', '12-17 05:42 F',
    '12-24 01:28 O', '12-30 18:59 L',
]
PHASE_ASPECT = {"N": "Conjunction", "F": "Square", "O": "Opposition", "L": "Square"}


# ── Pure helpers ───────────────────────────────────────────────────────────────

def test_wrap180():
    assert A.wrap180(190.0) == -170.0
    assert A.wrap180(-190.0) == 170.0
    assert A.wrap180(360.0) == 0.0


def test_targets_cover_both_sides_once():
    assert A.targets(0) == [0]
    assert A.targets(180) == [180]
    assert A.targets(60) == [60, 300]
    assert A.targets(120) == [120, 240]


def test_crossings_ignore_the_wraparound():
    assert list(A.crossings(np.array([-10.0, 10.0]))) == [0]
    assert list(A.crossings(np.array([170.0, -170.0]))) == []
    assert list(A.crossings(np.array([5.0, -5.0, 5.0]))) == [0, 1]
    assert list(A.crossings(np.array([1.0, 2.0, 3.0]))) == []


def test_bisect_many_finds_each_root_to_the_tolerance():
    roots = np.array([0.25, 0.7])
    lo, hi = np.array([0.0, 0.5]), np.array([0.5, 1.0])
    found = A.bisect_many(lambda t: t - roots, lo, hi)
    assert np.all(np.abs(found - roots) <= A.TOLERANCE_DAYS)


def _aspect(jd, b1, asp, b2):
    return A.Aspect(jd, b1, asp, b2)


def test_void_begins_at_the_last_moon_aspect_before_each_ingress():
    aspects = [
        _aspect(1.0, "Moon", "Trine", "Venus"),
        _aspect(2.0, "Moon", "Square", "Saturn"),
        _aspect(2.5, "Sun", "Sextile", "Mars"),       # not the Moon: ignored
        _aspect(4.0, "Moon", "Conjunction", "Jupiter"),
    ]
    ingresses = [A.Ingress(3.0, "Leo"), A.Ingress(5.0, "Virgo")]
    voids = A.void_of_course(aspects, ingresses)
    assert [(v.last.body2, v.ingress.sign) for v in voids] == [("Saturn", "Leo"), ("Jupiter", "Virgo")]


def test_a_sign_without_moon_aspects_is_void_from_the_sign_before():
    aspects = [_aspect(1.0, "Moon", "Trine", "Venus")]
    ingresses = [A.Ingress(2.0, "Leo"), A.Ingress(4.5, "Virgo")]
    voids = A.void_of_course(aspects, ingresses)
    assert [(v.last.jd, v.ingress.sign) for v in voids] == [(1.0, "Leo"), (1.0, "Virgo")]


def test_an_ingress_with_no_earlier_aspect_in_the_window_is_dropped():
    assert A.void_of_course([_aspect(3.0, "Moon", "Trine", "Venus")], [A.Ingress(2.0, "Leo")]) == []


def test_duration_label():
    assert A.duration_label(dt.timedelta(hours=35, minutes=43)) == "35h 43m"
    assert A.duration_label(dt.timedelta(minutes=7)) == "0h 07m"


# ── Against the sky ────────────────────────────────────────────────────────────

def test_every_2026_lunar_phase_matches_usno_to_the_minute(sky):
    start = sky.ts.utc(2025, 12, 31).tt
    end = sky.ts.utc(2027, 1, 2).tt
    aspects, _ = A.search(sky, start, end, ["Moon", "Sun"])
    found = [(sky.utc(a.jd), a.aspect) for a in aspects if a.aspect in ("Conjunction", "Square", "Opposition")]
    in_2026 = [f for f in found if f[0].year == 2026]
    assert len(in_2026) == len(USNO_2026) == 50
    for entry in USNO_2026:
        date, clock, code = entry.split()
        published = dt.datetime.fromisoformat(f"2026-{date}T{clock}+00:00")
        matches = [t for t, asp in in_2026 if asp == PHASE_ASPECT[code] and abs(t - published) <= dt.timedelta(seconds=60)]
        assert len(matches) == 1, entry


def test_moon_ingresses_land_on_sign_boundaries(sky):
    start, end = sky.ts.utc(2026, 4, 1).tt, sky.ts.utc(2026, 5, 1).tt
    _, ingresses = A.search(sky, start, end, ["Moon"])
    assert len(ingresses) in (13, 14)
    for ing in ingresses:
        lon = sky.longitudes(ing.jd, ["Moon"])["Moon"]
        assert abs(A.wrap180(lon - 30 * A.SIGNS.index(ing.sign))) < 1e-4
    signs = [i.sign for i in ingresses]
    assert all(A.SIGNS[(A.SIGNS.index(a) + 1) % 12] == b for a, b in zip(signs, signs[1:]))


def test_april_2026_counts(sky):
    aspect_rows, void_rows = A.compute_month(sky, 2026, 4, A.ZoneInfo("America/Los_Angeles"), traditional=False)
    assert len(aspect_rows) == 95
    assert len([r for r in aspect_rows if r["Body 1"] == "Moon"]) == 77
    assert len(void_rows) == 13


def test_a_long_void_through_gemini(sky):
    _, void_rows = A.compute_month(sky, 2026, 4, A.ZoneInfo("America/Los_Angeles"), traditional=False)
    row = next(r for r in void_rows if r["Moon Enters"] == "Cancer")
    assert (row["Begins Date"], row["Begins Time"], row["Last Aspect"]) == ("2026-04-19", "10:17 PM PDT", "Moon Sextile Mars")
    assert (row["Ingress Date"], row["Ingress Time"], row["Duration"]) == ("2026-04-21", "10:00 AM PDT", "35h 43m")


def test_traditional_uses_the_visible_planets_only(sky):
    aspect_rows, void_rows = A.compute_month(sky, 2026, 4, A.ZoneInfo("America/Los_Angeles"), traditional=True)
    outer = {"Uranus", "Neptune", "Pluto"}
    assert not any({r["Body 1"], r["Body 2"]} & outer for r in aspect_rows)
    assert not any(set(r["Last Aspect"].split()) & outer for r in void_rows)
    # Without Uranus the Moon's last aspect before Sagittarius on 2026-04-05 is the trine to Mars.
    row = next(r for r in void_rows if r["Moon Enters"] == "Sagittarius")
    assert row["Last Aspect"] == "Moon Trine Mars"


@pytest.mark.parametrize("month", [3, 11], ids=["spring-forward", "fall-back"])
def test_durations_are_real_elapsed_time_across_daylight_saving(sky, month):
    _, void_rows = A.compute_month(sky, 2026, month, A.ZoneInfo("America/Los_Angeles"), traditional=False)
    for row in void_rows:
        begins = dt.datetime.fromisoformat(row["Begins UTC"].replace("Z", "+00:00"))
        ends = dt.datetime.fromisoformat(row["Ingress UTC"].replace("Z", "+00:00"))
        minutes = round((A.round_minute(ends) - A.round_minute(begins)).total_seconds() / 60)
        assert row["Duration"] == f"{minutes // 60}h {minutes % 60:02d}m"


def test_rows_fall_inside_the_month_by_their_rounded_local_time(sky):
    zone = A.ZoneInfo("America/New_York")
    aspect_rows, void_rows = A.compute_month(sky, 2026, 4, zone, traditional=False)
    assert all(r["Date"].startswith("2026-04") for r in aspect_rows)
    assert all(r["Time"].endswith(" EDT") for r in aspect_rows)
    assert all(r["Begins Date"] <= "2026-04-30" and r["Ingress Date"] >= "2026-04-01" for r in void_rows)
