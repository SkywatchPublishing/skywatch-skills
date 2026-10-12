"""Moon aspects are found across the whole local day and listed once, on the day they perfect.

Each test checks the script against an independent reference: the signed Moon-minus-planet
elongation is sampled hourly with pyswisseph and every zero crossing is bisected to under a second.
"""
import datetime
from zoneinfo import ZoneInfo

import pytest
import swisseph as swe

import compute_aspects

LA = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")
OTHERS = {
    "Sun": swe.SUN, "Mercury": swe.MERCURY, "Venus": swe.VENUS, "Mars": swe.MARS,
    "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
}
ANGLES = {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Opposition": 180}


def _lon(dt, pid):
    u = dt.astimezone(UTC)
    hour = u.hour + u.minute / 60 + u.second / 3600 + u.microsecond / 3.6e9
    return swe.calc_ut(swe.julday(u.year, u.month, u.day, hour), pid, swe.FLG_SWIEPH)[0][0]


def _wrap(deg):
    return (deg + 180) % 360 - 180


def reference_perfections(month, year):
    """[(exact local datetime, other planet, aspect)] for every Moon aspect perfecting in the local month."""
    start = datetime.datetime(year, month, 1, tzinfo=LA).astimezone(UTC)
    nxt = datetime.date(year + month // 12, month % 12 + 1, 1)
    end = datetime.datetime(nxt.year, nxt.month, 1, tzinfo=LA).astimezone(UTC)
    hours = int((end - start).total_seconds() // 3600)
    grid = [start + datetime.timedelta(hours=h) for h in range(hours + 1)]
    moon = [_lon(t, swe.MOON) for t in grid]
    found = []
    for name, pid in OTHERS.items():
        other = [_lon(t, pid) for t in grid]
        for aspect, angle in ANGLES.items():
            for target in {angle, (360 - angle) % 360}:
                err = [_wrap(m - o - target) for m, o in zip(moon, other)]
                for k in range(hours):
                    if err[k] < 0 <= err[k + 1]:
                        lo, hi = grid[k], grid[k + 1]
                        while hi - lo > datetime.timedelta(seconds=0.5):
                            mid = lo + (hi - lo) / 2
                            if _wrap(_lon(mid, swe.MOON) - _lon(mid, pid) - target) < 0:
                                lo = mid
                            else:
                                hi = mid
                        found.append(((lo + (hi - lo) / 2).astimezone(LA), name, aspect))
    return found


def to_minute(dt):
    """Nearest whole minute."""
    return (dt + datetime.timedelta(seconds=30)).replace(second=0, microsecond=0)


def moon_rows(rows):
    return [r for r in rows if "Moon" in (r["Planet 1"], r["Planet 2"])]


def key(row):
    other = row["Planet 2"] if row["Planet 1"] == "Moon" else row["Planet 1"]
    return other, row["Aspect"]


def listed_time(row):
    clock = row["Exact Time"].rsplit(" ", 1)[0]
    return datetime.datetime.strptime(f'{row["Date"]} {clock}', "%Y-%m-%d %I:%M %p").replace(tzinfo=LA)


def find_rows(rows, other, aspect, date):
    return [r for r in moon_rows(rows) if key(r) == (other, aspect) and r["Date"] == date]


@pytest.fixture(scope="module")
def april_rows():
    return compute_aspects.compute_aspects(4, 2026)


@pytest.fixture(scope="module")
def april_reference():
    return reference_perfections(4, 2026)


@pytest.mark.parametrize("other, aspect, date", [
    ("Pluto", "Sextile", "2026-04-06"),    # perfects about 03:10 PDT
    ("Neptune", "Trine", "2026-04-05"),    # perfects about 21:20 PDT
])
def test_moon_aspect_far_from_noon_is_listed_at_its_exact_time(april_rows, april_reference, other, aspect, date):
    [exact] = [t for t, o, a in april_reference if (o, a) == (other, aspect) and t.date().isoformat() == date]
    assert abs(exact - exact.replace(hour=12, minute=0, second=0, microsecond=0)) > datetime.timedelta(hours=8)

    rows = find_rows(april_rows, other, aspect, date)
    assert len(rows) == 1, f"Moon {aspect} {other} missing from {date}"
    assert abs(listed_time(rows[0]) - exact) <= datetime.timedelta(minutes=2)
    assert rows[0]["Orb (°)"] < 0.01  # the orb at the exact moment, not at noon


def test_every_moon_perfection_is_listed_once_on_its_local_day(april_rows, april_reference):
    assert len(april_reference) > 60  # sanity: about 2.5 Moon aspects a day
    for exact, other, aspect in april_reference:
        rows = find_rows(april_rows, other, aspect, to_minute(exact).date().isoformat())
        assert len(rows) == 1, f"Moon {aspect} {other} at {exact} listed {len(rows)} times"
        assert abs(listed_time(rows[0]) - exact) <= datetime.timedelta(minutes=2)
    assert len(moon_rows(april_rows)) == len(april_reference)


def test_no_moon_aspect_is_listed_on_consecutive_days(april_rows):
    dates = {}
    for row in moon_rows(april_rows):
        dates.setdefault(key(row), []).append(datetime.date.fromisoformat(row["Date"]))
    for k, ds in dates.items():
        ds.sort()
        for a, b in zip(ds, ds[1:]):
            assert (b - a).days > 1, f"Moon {k[1]} {k[0]} listed on {a} and {b}"


def test_exact_time_is_rounded_to_the_nearest_minute_not_truncated(april_rows, april_reference):
    # Perfections whose seconds are well past :30, so truncating would list them a minute early.
    late = [(t, o, a) for t, o, a in april_reference if 35 <= t.second <= 55]
    assert len(late) >= 5
    for exact, other, aspect in late:
        [row] = find_rows(april_rows, other, aspect, to_minute(exact).date().isoformat())
        assert listed_time(row) == to_minute(exact), f"Moon {aspect} {other} at {exact}: {row['Exact Time']}"


def test_aspect_perfecting_just_after_midnight_is_listed_on_the_next_day_only(april_rows, april_reference):
    # Moon opposite Neptune perfects about 28 s after midnight starting 2026-04-01.
    [exact] = [t for t, o, a in april_reference if (o, a) == ("Neptune", "Opposition")
               and t.date() == datetime.date(2026, 4, 1)]
    assert exact.hour == 0 and exact.minute == 0
    march_31 = [r for r in compute_aspects.compute_aspects(3, 2026) if r["Date"] == "2026-03-31"]
    assert find_rows(march_31, "Neptune", "Opposition", "2026-03-31") == []
    [row] = find_rows(april_rows, "Neptune", "Opposition", "2026-04-01")
    assert row["Exact Time"] == "12:00 AM PDT"
