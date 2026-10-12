import datetime as dt
import json
import time
from pathlib import Path

import pytest
import swisseph as swe
import progressions as pg

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"
START, END = dt.date(2027, 1, 1), dt.date(2036, 12, 31)


@pytest.fixture(scope="module")
def natal():
    return json.loads(EXAMPLE.read_text())


@pytest.fixture(scope="module")
def rows(natal):
    t = time.time()
    out = pg.timeline(natal, START, END)
    assert time.time() - t < 10
    return out


def test_sorted_and_overlapping(rows):
    assert rows == sorted(rows, key=lambda r: (r["exact"], r["technique"], r["moving"], r["target"]))
    for r in rows:
        lo, hi = r["from"] or r["exact"], r["to"] or r["exact"]
        assert hi >= START and lo <= END


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


def test_moon_ingresses_about_two_and_a_half_years_apart(rows):
    dates = [r["exact"] for r in rows if r["event"] == "ingress" and r["moving"] == "Moon"]
    assert len(dates) >= 3
    assert all(2.0 < (b - a).days / 365.25 < 2.8 for a, b in zip(dates, dates[1:]))


def test_mc_listed_once_with_solar_arc_angles(natal, rows):
    assert not [r for r in rows if r["technique"] == "secondary" and r["moving"] == "MC"]
    naibod = pg.timeline(natal, START, END, "naibod")
    assert [r for r in naibod if r["technique"] == "secondary" and r["moving"] == "MC"]


def test_lifetime_stations(natal):
    life = pg.timeline(natal, dt.date(1990, 6, 16), dt.date(2080, 12, 31))
    stations = [(r["exact"], r["moving"], r["detail"]) for r in life if r["event"] == "station"]
    assert any(m == "Pluto" and d == "turns direct" and e.year == 2030 for e, m, d in stations)
    assert any(m == "Mercury" and d == "turns retrograde" and e.year == 2061 for e, m, d in stations)


def test_untimed_chart(natal):
    u = json.loads(json.dumps(natal))
    u["angles"] = None; u["houses"] = None; u["meta"]["time_unknown"] = True
    rows = pg.timeline(u, START, END)
    assert not [r for r in rows if "Ascendant" in (r["moving"], r["target"]) or "MC" in (r["moving"], r["target"]) or r["event"] == "house"]
    assert all(r["uncertain"] for r in rows if r["technique"] == "secondary")
    assert all(r["uncertain"] == ("Moon" in (r["moving"], r["target"])) for r in rows if r["technique"] == "solar_arc")
