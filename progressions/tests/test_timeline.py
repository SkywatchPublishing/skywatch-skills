import datetime as dt
import json
import time
from pathlib import Path

import pytest
import swisseph as swe
import progressions as pg

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"
START, END = dt.date(2027, 1, 1), dt.date(2036, 12, 31)
BORN = dt.date(1990, 6, 15)
NY = ("--geonameid", "5128581")
D = dt.date


@pytest.fixture(scope="module")
def natal():
    return json.loads(EXAMPLE.read_text())


@pytest.fixture(scope="module")
def rows(natal):
    t = time.time()
    out = pg.timeline(natal, START, END)
    assert time.time() - t < 10
    return out


@pytest.fixture(scope="module")
def naibod_rows(natal):
    return pg.timeline(natal, START, END, "naibod")


@pytest.fixture(scope="module")
def life(natal):
    return pg.timeline(natal, dt.date(1990, 6, 16), dt.date(2080, 12, 31))


def flags_for(natal):
    if natal["meta"]["zodiac"].startswith("sidereal"):
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        return swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    return swe.FLG_SWIEPH | swe.FLG_SPEED


def natal_points(natal):
    points = {n: b["longitude"] for n, b in natal["bodies"].items()}
    if natal.get("angles"):
        points.update(Ascendant=natal["angles"]["ascendant"], MC=natal["angles"]["mc"])
    return points


def moving_lon(natal, r, date, angles="solar-arc"):
    """Where the row's moving point is at local noon on `date`, worked out from pyswisseph directly."""
    meta = natal["meta"]
    bj, t = meta["julian_day_ut"], pg.target_jd(date, meta["timezone"])
    pj = pg.progressed_jd(bj, t)
    sun = lambda jd, flags=flags_for(natal): swe.calc_ut(jd, swe.SUN, flags)[0][0]
    if r["technique"] == "solar_arc":
        return natal_points(natal)[r["moving"]] + sun(pj) - sun(bj)
    if r["moving"] in ("Ascendant", "MC"):
        # Tropical angles from the ARMC, then sidereal with the ayanamsa at the progressed instant.
        aya = (lambda jd: swe.get_ayanamsa_ex_ut(jd, swe.FLG_SWIEPH)[1]) if meta["zodiac"] != "tropical" else (lambda jd: 0.0)
        eps = swe.calc_ut(bj, swe.ECL_NUT)[0][0]
        right_ascension = lambda lon: swe.cotrans((lon, 0.0, 1.0), -eps)[0]
        mc = natal["angles"]["mc"] + aya(bj)
        if angles == "naibod":
            armc = right_ascension(mc) + pg.NAIBOD * (t - bj) / pg.YEAR
        else:
            armc = right_ascension(mc + sun(pj, swe.FLG_SWIEPH) - sun(bj, swe.FLG_SWIEPH))
        code = pg.HOUSE_CODES[natal["houses"]["system"]]
        asc, mc = swe.houses_armc(armc % 360, meta["location"]["latitude"], eps, code)[1][:2]
        return (asc if r["moving"] == "Ascendant" else mc) - aya(pj)
    return swe.calc_ut(pj, pg.BODIES[r["moving"]], flags_for(natal))[0][0]


def orb(natal, r, date, angles="solar-arc"):
    lon, a = moving_lon(natal, r, date, angles) - natal_points(natal)[r["target"]], pg.ASPECTS[r["aspect"]]
    return min(abs(pg.wrapped(lon - a)), abs(pg.wrapped(lon + a)))


def test_sorted_and_overlapping(rows):
    assert rows == sorted(rows, key=lambda r: (r["exact"], r["technique"], r["moving"], r["target"]))
    assert all(pg.overlaps(r, START, END) for r in rows)


def test_secondary_exact_dates_are_exact(natal, rows):
    bj, tz = natal["meta"]["julian_day_ut"], natal["meta"]["timezone"]
    targets = {n: b["longitude"] for n, b in natal["bodies"].items()}
    targets.update(Ascendant=natal["angles"]["ascendant"], MC=natal["angles"]["mc"])
    checked = 0
    for r in rows:
        if r["technique"] == "secondary" and r["event"] == "aspect" and r["moving"] in pg.SECONDARY_MOVERS:
            lon = swe.calc_ut(pg.progressed_jd(bj, pg.target_jd(r["exact"], tz)), pg.BODIES[r["moving"]], pg._flags("tropical"))[0][0]
            a = pg.ASPECTS[r["aspect"]]
            err = min(abs(pg.wrapped(lon - targets[r["target"]] - a)), abs(pg.wrapped(lon - targets[r["target"]] + a)))
            assert err < 0.05
            checked += 1
    assert checked > 20


def test_solar_arc_and_angle_rows_are_exact(natal, rows, naibod_rows):
    arcs = [r for r in rows if r["technique"] == "solar_arc"]
    asc = [r for r in rows if r["technique"] == "secondary" and r["moving"] == "Ascendant"]
    mc = [r for r in naibod_rows if r["technique"] == "secondary" and r["moving"] == "MC"]
    assert len(arcs) > 20 and asc and mc
    for r in arcs + asc:
        assert orb(natal, r, r["exact"]) < 0.05
    for r in mc:
        assert orb(natal, r, r["exact"], "naibod") < 0.05


def test_window_edges_are_one_degree_from_exact(natal, rows):
    checked = 0
    for r in rows:
        if r["event"] == "aspect":
            for k in ("from", "to"):
                if r[k] is not None and r[k] > BORN:
                    assert abs(orb(natal, r, r[k]) - pg.ORB) < 0.1, (r, k)
                    checked += 1
    assert checked > 100


def test_moon_house_ingresses(natal, rows):
    cusps, bj, tz = natal["houses"]["cusps"], natal["meta"]["julian_day_ut"], natal["meta"]["timezone"]
    moon = lambda d: swe.calc_ut(pg.progressed_jd(bj, pg.target_jd(d, tz)), swe.MOON, swe.FLG_SWIEPH)[0][0]
    houses = [r for r in rows if r["event"] == "house"]
    assert len(houses) >= 3
    for r in houses:
        new = int(r["detail"].removeprefix("enters natal house "))
        previous = (new - 2) % 12 + 1
        day = r["exact"]
        assert pg.house_of(moon(day + dt.timedelta(days=1)), cusps) == new
        assert pg.house_of(moon(day - dt.timedelta(days=1)), cusps) == previous
        assert pg.house_of(moon(day - dt.timedelta(days=pg.STEP)), cusps) == previous


def test_moon_enters_aries_from_pisces(natal):
    bj, tz = natal["meta"]["julian_day_ut"], natal["meta"]["timezone"]
    moon = lambda d: swe.calc_ut(pg.progressed_jd(bj, pg.target_jd(d, tz)), swe.MOON, swe.FLG_SWIEPH)[0][0]
    hits = [r for r in pg.timeline(natal, D(2018, 1, 1), D(2018, 12, 31))
            if r["event"] == "ingress" and r["moving"] == "Moon"]
    assert [r["detail"] for r in hits] == ["enters Aries"]
    day = hits[0]["exact"]
    assert pg.sign_of(moon(day - dt.timedelta(days=1)))[0] == "Pisces"
    assert pg.sign_of(moon(day + dt.timedelta(days=1)))[0] == "Aries"


def test_moon_ingresses_about_two_and_a_half_years_apart(rows):
    dates = [r["exact"] for r in rows if r["event"] == "ingress" and r["moving"] == "Moon"]
    assert len(dates) >= 3
    assert all(2.0 < (b - a).days / 365.25 < 2.8 for a, b in zip(dates, dates[1:]))


def test_mc_listed_once_with_solar_arc_angles(rows, naibod_rows):
    assert not [r for r in rows if r["technique"] == "secondary" and r["moving"] == "MC"]
    assert [r for r in naibod_rows if r["technique"] == "secondary" and r["moving"] == "MC"]


def test_sun_listed_once_under_secondary(rows, naibod_rows):
    # The directed Sun is the progressed Sun (the arc is the progressed Sun's travel), so its aspects are listed
    # once, under secondary.
    assert not [r for r in rows + naibod_rows if r["technique"] == "solar_arc" and r["moving"] == "Sun"]
    for timeline_rows in (rows, naibod_rows):
        sun = [(r["aspect"], r["target"], r["exact"], r["from"], r["to"]) for r in timeline_rows
               if r["technique"] == "secondary" and r["event"] == "aspect" and r["moving"] == "Sun"]
        assert sun == [("Sextile", "Mercury", D(2034, 2, 20), D(2033, 2, 3), D(2035, 3, 9)),
                       ("Opposition", "Node", D(2036, 5, 20), D(2035, 5, 4), D(2037, 6, 6)),
                       ("Quincunx", "Uranus", D(2036, 6, 2), D(2035, 5, 17), D(2037, 6, 19))]


def test_lifetime_stations(life):
    stations = [(r["exact"], r["moving"], r["detail"]) for r in life if r["event"] == "station"]
    assert any(m == "Pluto" and d.startswith("turns direct at ") and d.endswith(" Scorpio") and e.year == 2030
               for e, m, d in stations)
    assert any(m == "Mercury" and d.startswith("turns retrograde at ") and e.year == 2061 for e, m, d in stations)


def test_stations_match_a_change_in_progressed_speed(natal, life):
    bj, tz = natal["meta"]["julian_day_ut"], natal["meta"]["timezone"]

    def progressed(body, day):
        return swe.calc_ut(pg.progressed_jd(bj, pg.target_jd(day, tz)), pg.BODIES[body], swe.FLG_SWIEPH | swe.FLG_SPEED)[0]

    stations = [r for r in life if r["event"] == "station"]
    assert len(stations) >= 2
    for r in stations:
        before, after = (progressed(r["moving"], r["exact"] + dt.timedelta(days=d))[3] for d in (-1, 1))
        retro = r["detail"].startswith("turns retrograde")
        assert (before > 0 > after) if retro else (before < 0 < after)
        lon = progressed(r["moving"], r["exact"])[0]
        assert r["detail"] == f"turns {'retrograde' if retro else 'direct'} at {pg.format_degree(lon)}"


def test_untimed_chart(natal):
    u = json.loads(json.dumps(natal))
    u["angles"] = None; u["houses"] = None; u["meta"]["time_unknown"] = True
    rows = pg.timeline(u, START, END)
    assert not [r for r in rows if "Ascendant" in (r["moving"], r["target"]) or "MC" in (r["moving"], r["target"]) or r["event"] == "house"]
    assert all(r["uncertain"] for r in rows if r["technique"] == "secondary")
    # A ±12 h birth-time error moves the natal Moon, Sun, Mercury, Venus and Mars by ~0.4-7°, months of arc.
    fast = {"Moon", "Sun", "Mercury", "Venus", "Mars"}
    arcs = [r for r in rows if r["technique"] == "solar_arc"]
    assert any(r["uncertain"] for r in arcs) and not all(r["uncertain"] for r in arcs)
    assert all(r["uncertain"] == bool(fast & {r["moving"], r["target"]}) for r in arcs)


def test_timed_chart_rows_are_never_uncertain(rows, naibod_rows):
    assert rows and not [r for r in rows + naibod_rows if r["uncertain"]]


def test_no_spurious_self_aspect_at_birth_and_no_window_before_it(natal):
    early = pg.timeline(natal, BORN, D(1993, 6, 15))
    assert early
    assert not [r for r in early if r["event"] == "aspect" and r["moving"] == r["target"] and r["exact"] == BORN]
    assert all(r[k] is None or r[k] >= BORN for r in early for k in ("from", "to", "exact"))
    lunar_return = [r for r in pg.timeline(natal, D(2017, 1, 1), D(2017, 12, 31))
                    if (r["technique"], r["moving"], r["aspect"], r["target"]) == ("secondary", "Moon", "Conjunction", "Moon")]
    assert [r["exact"] for r in lunar_return] == [D(2017, 9, 6)]


def test_slow_mover_window_overlapping_the_range_is_listed(cast):
    # Progressed Mercury turns direct in 1968 just past the natal Sun: in orb from 1964 to 1973 and exact
    # twice, retrograde in 1967 and direct in 1970, the second more than five years after this range ends.
    u = cast("--date", "1953-07-20", *NY)
    end = D(1964, 6, 30)
    hits = [r for r in pg.timeline(u, D(1960, 1, 1), end)
            if (r["technique"], r["moving"], r["aspect"], r["target"]) == ("secondary", "Mercury", "Conjunction", "Sun")]
    assert len(hits) == 2
    assert all(r["from"] <= end for r in hits)
    assert hits[-1]["exact"] > end + dt.timedelta(days=5 * 366)


def row(event, exact, frm=None, to=None):
    return {"event": event, "exact": exact, "from": frm, "to": to}


def test_overlaps_compares_whole_local_days():
    s, e = D(2030, 1, 1), D(2030, 12, 31)
    assert pg.overlaps(row("aspect", D(2029, 6, 1), D(2028, 1, 1), s), s, e)          # window ends on the start date
    assert pg.overlaps(row("aspect", D(2031, 6, 1), e, D(2032, 1, 1)), s, e)          # opens on the end date
    assert not pg.overlaps(row("aspect", D(2029, 6, 1), D(2028, 1, 1), D(2029, 12, 31)), s, e)
    assert not pg.overlaps(row("aspect", D(2031, 6, 1), D(2031, 1, 1), D(2032, 1, 1)), s, e)
    assert pg.overlaps(row("aspect", D(2040, 1, 1), None, D(2041, 1, 1)), s, e)       # in orb back to the scan limit
    assert pg.overlaps(row("aspect", D(2020, 1, 1), D(2019, 1, 1), None), s, e)       # still in orb at the scan limit
    for event in ("station", "ingress", "house"):
        assert pg.overlaps(row(event, s), s, e) and pg.overlaps(row(event, e), s, e)
        assert not pg.overlaps(row(event, D(2029, 12, 31)), s, e)
        assert not pg.overlaps(row(event, D(2031, 1, 1)), s, e)
    assert pg.overlaps(row("station", s), s, s)


def test_printed_dates_do_not_depend_on_the_sample_grid(natal):
    # The sample grid starts five years (forty for Mercury, Venus and Mars) before the range, so every range
    # samples at a different phase. A one-day range on any of a row's dates must still list that row with the
    # same dates. One date per row, rotating through the three columns, keeps this to ~43 timeline runs.
    key = ("technique", "event", "moving", "aspect", "target", "exact", "from", "to")
    sample = pg.timeline(natal, D(2027, 1, 1), D(2031, 12, 31))[::2]
    checked = set()
    for i, r in enumerate(sample):
        column = ("exact", "from", "to")[i % 3]
        column = column if r[column] is not None else "exact"
        day = r[column]
        assert tuple(r[k] for k in key) in {tuple(x[k] for k in key) for x in pg.timeline(natal, day, day)}, \
            (column, r)
        checked.add(column)
    assert len(sample) >= 40 and checked == {"exact", "from", "to"}


def test_sidereal_timeline_is_exact(cast):
    sid = cast("--date", "1990-06-15", "--time", "12:00", *NY, "--zodiac", "sidereal")
    rows = pg.timeline(sid, D(2027, 1, 1), D(2030, 12, 31))
    aspects = [r for r in rows if r["event"] == "aspect"]
    assert len([r for r in aspects if r["technique"] == "secondary"]) > 5
    assert len([r for r in aspects if r["technique"] == "solar_arc"]) > 5
    assert [r for r in aspects if r["moving"] == "Ascendant"]
    for r in aspects:
        assert orb(sid, r, r["exact"]) < 0.05


def test_sidereal_naibod_timeline_is_exact(cast):
    sid = cast("--date", "1990-06-15", "--time", "12:00", *NY, "--zodiac", "sidereal")
    rows = pg.timeline(sid, D(2027, 1, 1), D(2030, 12, 31), "naibod")
    aspects = [r for r in rows if r["event"] == "aspect"]
    assert [r for r in aspects if r["technique"] == "secondary" and r["moving"] == "MC"]
    assert [r for r in aspects if r["technique"] == "secondary" and r["moving"] == "Ascendant"]
    for r in aspects:
        assert orb(sid, r, r["exact"], "naibod") < 0.05, r


# Born 20 days before Chiron turned retrograde on 1990-11-09: progressed Chiron stations in 2009.
CHIRON_STATION = ("--date", "1990-10-20", "--time", "12:00", *NY)


@pytest.fixture(scope="module")
def chiron_natal(cast):
    return cast(*CHIRON_STATION)


@pytest.fixture(scope="module")
def chiron_rows(chiron_natal):
    # Module scope: built with the ephemeris files, before a function-scoped no_ephemeris takes them away.
    return pg.timeline(chiron_natal, D(2008, 1, 1), D(2012, 12, 31))


def test_missing_ephemeris_files_leave_out_progressed_chiron(chiron_natal, chiron_rows, no_ephemeris):
    # Moshier has no Chiron: progressed Chiron's ingresses and stations are left out. Directed Chiron (natal
    # Chiron plus the arc) and aspects to natal Chiron need no ephemeris file and stay.
    progressed_chiron = [r for r in chiron_rows if r["moving"] == "Chiron" and r["technique"] == "secondary"]
    assert [(r["event"], r["exact"]) for r in progressed_chiron] == [("station", D(2009, 5, 26))]
    rows = pg.timeline(chiron_natal, D(2008, 1, 1), D(2012, 12, 31))
    key = lambda r: (r["technique"], r["event"], r["moving"], r["aspect"], r["target"])
    assert sorted(map(key, rows)) == sorted(key(r) for r in chiron_rows if r not in progressed_chiron)
    assert [r for r in rows if "Chiron" in (r["moving"], r["target"])]
