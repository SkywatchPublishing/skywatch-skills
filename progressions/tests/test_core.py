import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest
import swisseph as swe
import progressions as pg

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "natal-chart" / "examples" / "chart.json"


@pytest.fixture
def natal():
    return json.loads(EXAMPLE.read_text())


def tjd(natal, y, m, d):
    return pg.target_jd(dt.date(y, m, d), natal["meta"]["timezone"])


def test_wrapped():
    assert pg.wrapped(190.0) == pytest.approx(-170.0)
    assert pg.wrapped(-190.0) == pytest.approx(170.0)


def test_target_date_round_trip(natal):
    tz = natal["meta"]["timezone"]
    assert pg.jd_to_local_date(pg.target_jd(dt.date(2027, 6, 15), tz), tz) == dt.date(2027, 6, 15)


def test_age_and_solar_arc(natal):
    bj, t = natal["meta"]["julian_day_ut"], tjd(natal, 2027, 6, 15)
    assert (t - bj) / pg.YEAR == pytest.approx(37.0001, abs=1e-4)
    assert pg.solar_arc(bj, t) == pytest.approx(35.2991, abs=1e-3)
    sun = swe.calc_ut(pg.progressed_jd(bj, t), swe.SUN, swe.FLG_SWIEPH)[0][0]
    assert pg.body_positions(pg.progressed_jd(bj, t))["Sun"]["longitude"] == pytest.approx(sun, abs=1e-9)


def test_solar_arc_and_naibod_angles(natal):
    bj, t = natal["meta"]["julian_day_ut"], tjd(natal, 2027, 6, 15)
    sa = pg.moved_houses(natal, t, "solar-arc")
    nb = pg.moved_houses(natal, t, "naibod")
    assert sa["angles"]["mc"] == pytest.approx((natal["angles"]["mc"] + pg.solar_arc(bj, t)) % 360, abs=1e-3)
    assert pg.wrapped(nb["angles"]["mc"] - sa["angles"]["mc"]) == pytest.approx(-1.656, abs=0.01)


@pytest.mark.parametrize("method", ["solar-arc", "naibod"])
def test_identity_at_birth(natal, method):
    h = pg.moved_houses(natal, natal["meta"]["julian_day_ut"], method)
    assert abs(pg.wrapped(h["angles"]["ascendant"] - natal["angles"]["ascendant"])) < 1e-3
    assert abs(pg.wrapped(h["cusps"][1] - natal["houses"]["cusps"][1])) < 1e-3


def test_sidereal_identity(tmp_path):
    out = tmp_path / "sid.json"
    subprocess.run([sys.executable, "-I", str(ROOT / "natal-chart" / "scripts" / "natal_chart.py"),
                    "--name", "S", "--date", "1990-06-15", "--time", "12:00", "--geonameid", "5128581",
                    "--zodiac", "sidereal", "--out", str(out)], check=True, capture_output=True)
    s = json.loads(out.read_text())
    h = pg.moved_houses(s, s["meta"]["julian_day_ut"], "solar-arc")
    assert abs(pg.wrapped(h["angles"]["ascendant"] - s["angles"]["ascendant"])) < 1e-3
