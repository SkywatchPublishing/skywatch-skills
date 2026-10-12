# Progressions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `progressions` skill that writes secondary progressed and solar arc directed charts for a date, and a dated event timeline, per `docs/plans/2026-10-12-progressions-design.md`.

**Architecture:** One script, `progressions/scripts/progressions.py`, built up across Tasks 2 to 5. It reads a natal `chart.json`, computes progressed planets with pyswisseph at birth + age days, moves angles by solar arc or Naibod, and assembles ordinary schema-1 charts with copied helpers. The timeline samples target dates every 15 days and bisects each crossing to the minute, so printed local dates do not depend on the sample grid. No cross-folder imports.

**Tech Stack:** Python 3.11+, pyswisseph 2.10, pytest. Standard library otherwise.

---

## Before you start

Read the design, `natal-chart/CONTRACT.md`, and `composite/scripts/composite.py` (the closest model: copied helpers, house-from-ARMC). Environment:

```bash
cd skywatch-skills
python3 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip setuptools wheel && pip install pyswisseph timezonefinder pytest
python natal-chart/scripts/fetch_ephemeris.py
for d in natal-chart chart-wheel transits-to-natal synastry returns composite; do python -m pytest $d/tests -q || exit 1; done
```

Run test folders one at a time: several share a `test_cli.py` basename and collide in one pytest invocation.

Facts verified while designing, which the tests rely on (example chart: 1990-06-15 12:00 New York, `natal-chart/examples/chart.json`):

- Target 2027-06-15 (local noon): age 37.0001 years, true solar arc 35.2991°, progressed Sun 29°35' Cancer, progressed Moon 6°48' Leo.
- Solar-arc angles: progressed MC 106.525 = natal MC 71.226 + arc. Naibod angles: MC 104.868, 1.656° behind.
- Target = birth reproduces the natal chart: bodies exactly, angles and cusps within about 1e-4°, tropical or sidereal (the natal MC they start from and the natal cusps they are compared with are rounded to 4 decimals; 4.1e-5° for the example's Koch cusps, 9.7e-5° at 64° N).
- Timeline 2027-2036: 132 rows in about 1 s with solar-arc angles (140 with Naibod); worst secondary exact-date error 0.019°; progressed Moon sign ingresses 2.29, 2.43, 2.52 years apart; a lifetime scan finds progressed Pluto turning direct on 2030-11-05 and Mercury turning retrograde on 2061-05-17.

Commit after every task with the given imperative message.

---

### Task 1: Contract, wheel caption, and a returns guard

**Files:**
- Modify: `natal-chart/CONTRACT.md`, `chart-wheel/scripts/chart_wheel.py` (`captions`), `returns/scripts/returns.py` (`main`)
- Test: `chart-wheel/tests/test_wheel.py`, `returns/tests/test_cli.py`

**Step 1: Failing tests**

chart-wheel:

```python
def test_progressed_caption_shows_target_date():
    chart = load_example()
    chart["meta"]["chart_type"] = "secondary_progressed"
    chart["meta"]["derived_from"] = ["Example"]
    chart["meta"]["progression"] = {"target_date": "2027-06-15", "age_years": 37.0001,
                                    "solar_arc": 35.2991, "angles_method": "solar-arc"}
    svg = cw.render(chart)
    assert "Secondary progressed for Example  ·  2027-06-15" in svg
    assert "1990-06-15 12:00:00" not in svg
```

returns (via `main()` as the existing composite-refusal test does):

```python
def test_progressed_chart_is_refused(tmp_path, capsys):
    chart = json.loads(EXAMPLE.read_text())
    chart["meta"]["chart_type"] = "secondary_progressed"
    p = tmp_path / "p.json"; p.write_text(json.dumps(chart))
    assert rt.main([str(p), "--start", "2027-01-01", "--end", "2027-12-31", "--out-dir", str(tmp_path)]) == 1
    assert "progressed or directed" in capsys.readouterr().err
```

**Step 2: Run** both folders → the two new tests fail.

**Step 3: Implement.**
- `captions`: when `meta.get("progression")` is truthy, the moment segment is the bare `progression['target_date']` instead of the birth date-time and zone, like a return's date-time ("Secondary progressed for Example · 2027-06-15"). Keep `_join_names` and escaping.
- `returns.main`: after `load_chart`, if `meta.get("chart_type")` is `secondary_progressed` or `solar_arc_directed`, print `returns: this is a progressed or directed chart; cast returns from the natal chart` to stderr and return 1.
- `CONTRACT.md`: add `secondary_progressed` and `solar_arc_directed` to the `chart_type` row; add a `progression` row (object or absent; `{target_date, age_years, solar_arc, angles_method}`, written by progressions; `angles_method` null for a directed chart; the birth timestamps are kept); add progressions to the consumer paragraph.

**Step 4: Run** chart-wheel and returns tests → pass. **Step 5: Commit** `git commit -m "Add progressed chart types to the contract and wheel caption"`

---

### Task 2: Progression core (time key, solar arc, moved angles)

**Files:**
- Create: `progressions/tests/conftest.py` (copy of `natal-chart/tests/conftest.py`), `progressions/scripts/progressions.py`
- Test: `progressions/tests/test_core.py`

**Step 1: Failing test**

```python
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
```

**Step 2: Run** `python -m pytest progressions/tests -q` → collection error (no module).

**Step 3: Implement** the first part of `progressions/scripts/progressions.py`:

```python
#!/usr/bin/env python3
"""
Secondary progressions and solar arc directions from a natal chart.json.

Usage:
    python progressions.py chart.json --date 2027-06-15                      # secondary progressed chart
    python progressions.py chart.json --date 2027-06-15 --angles naibod      # Naibod angles
    python progressions.py chart.json --date 2027-06-15 --method solar-arc   # solar arc directed chart
    python progressions.py chart.json --timeline --start 2027-01-01 --end 2036-12-31

One day after birth stands for one tropical year of life. Charts are ordinary schema-1 chart.json
files that chart-wheel and synastry read unchanged; the timeline is a CSV of dated events.
"""
import datetime as dt
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

EPHE_DIRS = (Path(__file__).resolve().parents[1] / "ephe",
             Path(__file__).resolve().parents[2] / "natal-chart" / "ephe")
# The first folder holding the files, else this skill's own ephe/: without them pyswisseph falls back to its
# built-in Moshier ephemeris, which has no Chiron.
EPHE_DIR = next((d for d in EPHE_DIRS if (d / "seas_18.se1").exists()), EPHE_DIRS[0])
swe.set_ephe_path(str(EPHE_DIR))
# Lahiri is the project-wide ayanamsa, set once here (nothing in this script changes it); FLG_SIDEREAL on each
# call selects the zodiac.
swe.set_sid_mode(swe.SIDM_LAHIRI)

SCHEMA_VERSION = 1
YEAR = 365.24219                 # tropical year in days: one progressed day per year of life
NAIBOD = 0.9856473               # Naibod rate, 0°59'08" per year
BODIES = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO, "Chiron": swe.CHIRON, "Node": swe.TRUE_NODE,
}
HOUSE_CODES = {"placidus": b"P", "koch": b"K", "equal": b"E", "porphyry": b"O", "whole_sign": b"W"}


def ephemeris_files_present() -> bool:
    return (EPHE_DIR / "seas_18.se1").exists()


def wrapped(x: float) -> float:
    """x reduced to [-180, 180): the signed difference of two longitudes."""
    return ((x + 180.0) % 360.0) - 180.0


def local_jd(date: dt.date, time: dt.time, tz: str) -> float:
    """Julian day (UT) of a local wall-clock time on `date` in `tz`."""
    u = dt.datetime.combine(date, time, tzinfo=ZoneInfo(tz)).astimezone(dt.timezone.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600)


def target_jd(date: dt.date, tz: str) -> float:
    """Julian day (UT) of local noon on `date` in `tz`."""
    return local_jd(date, dt.time(12), tz)


def jd_to_local_date(jd: float, tz: str) -> dt.date:
    """Local date of a Julian day (UT). The time is rounded to the second first, so float error in revjul's
    hour cannot push an exact local midnight back into the previous day."""
    y, m, d, h = swe.revjul(jd)
    u = dt.datetime(y, m, d, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=round(h * 3600))
    return u.astimezone(ZoneInfo(tz)).date()


def progressed_jd(birth_jd: float, tjd: float) -> float:
    """Birth plus one day per tropical year of age."""
    return birth_jd + (tjd - birth_jd) / YEAR


def _flags(zodiac: str) -> int:
    f = swe.FLG_SWIEPH | swe.FLG_SPEED
    return f | swe.FLG_SIDEREAL if str(zodiac).startswith("sidereal") else f


def body_positions(jd: float, zodiac: str = "tropical", node: str = "true") -> dict[str, dict]:
    """Longitude, latitude, speed per body; Chiron omitted when its ephemeris file is missing."""
    out = {}
    for name, ident in BODIES.items():
        if name == "Node" and node == "mean":
            ident = swe.MEAN_NODE
        try:
            (lon, lat, _d, dlon, *_), _ = swe.calc_ut(jd, ident, _flags(zodiac))
        except swe.Error:
            if name == "Chiron":
                continue
            raise
        out[name] = {"longitude": lon % 360, "latitude": lat, "speed": dlon}
    return out


def sun_lon(jd: float, zodiac: str) -> float:
    return swe.calc_ut(jd, swe.SUN, _flags(zodiac))[0][0]


def solar_arc(birth_jd: float, tjd: float, zodiac: str = "tropical", natal_sun: float | None = None) -> float:
    """True solar arc: progressed Sun minus natal Sun, in [0, 360). Callers that need many arcs pass
    `natal_sun`, sun_lon(birth_jd, zodiac), so it is not recomputed each time."""
    if natal_sun is None:
        natal_sun = sun_lon(birth_jd, zodiac)
    return (sun_lon(progressed_jd(birth_jd, tjd), zodiac) - natal_sun) % 360


def obliquity(jd: float) -> float:
    return swe.calc_ut(jd, swe.ECL_NUT)[0][0]


def ayanamsa(jd: float, zodiac: str) -> float:
    """Lahiri ayanamsa with nutation, the value calc_ut and houses_ex subtract under FLG_SIDEREAL, so it
    matches natal-chart's sidereal output (get_ayanamsa_ut is the mean value, up to ~0.005° off); 0 for tropical."""
    if not str(zodiac).startswith("sidereal"):
        return 0.0
    return swe.get_ayanamsa_ex_ut(jd, swe.FLG_SWIEPH)[1]


def armc_from_mc(mc: float, eps: float) -> float:
    m, e = math.radians(mc), math.radians(eps)
    return math.degrees(math.atan2(math.sin(m) * math.cos(e), math.cos(m))) % 360.0


def whole_sign_cusps(ascendant: float) -> list[float]:
    """The 12 sign boundaries, starting with the sign the Ascendant is in."""
    start = ascendant // 30 * 30
    return [(start + 30 * i) % 360 for i in range(12)]


def houses_from_armc(armc: float, latitude: float, eps: float, system: str, shift: float = 0.0) -> dict:
    """Cusps and angles for an ARMC at a latitude; whole-sign fallback at polar latitudes.

    houses_armc is tropical: a sidereal chart passes its ayanamsa as `shift`, subtracted from the angles and
    cusps. Whole-sign cusps are then rebuilt from the shifted Ascendant's sign, since shifted tropical sign
    boundaries are not sidereal ones.
    """
    flags = []
    try:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES[system])
    except swe.Error:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES["whole_sign"])
        system, flags = "whole_sign", ["polar_fallback_whole_sign"]
    asc, mc = (ascmc[0] - shift) % 360, (ascmc[1] - shift) % 360
    cusps = whole_sign_cusps(asc) if system == "whole_sign" else [(c - shift) % 360 for c in cusps[:12]]
    return {"system": system, "cusps": cusps,
            "angles": {"ascendant": asc, "mc": mc, "descendant": (asc + 180) % 360, "ic": (mc + 180) % 360},
            "flags": flags}


def house_mover(natal: dict, method: str):
    """A function tjd -> progressed houses (see moved_houses), with the natal constants worked out once."""
    meta = natal["meta"]
    zodiac, birth_jd = meta["zodiac"], meta["julian_day_ut"]
    lat, system = meta["location"]["latitude"], natal["houses"]["system"]
    eps = obliquity(birth_jd)
    natal_mc_trop = (natal["angles"]["mc"] + ayanamsa(birth_jd, zodiac)) % 360
    natal_armc = armc_from_mc(natal_mc_trop, eps)
    natal_sun = sun_lon(birth_jd, "tropical")

    def at(tjd: float) -> dict:
        if method == "naibod":
            armc = (natal_armc + NAIBOD * (tjd - birth_jd) / YEAR) % 360
        else:
            armc = armc_from_mc((natal_mc_trop + solar_arc(birth_jd, tjd, "tropical", natal_sun)) % 360, eps)
        return houses_from_armc(armc, lat, eps, system, ayanamsa(progressed_jd(birth_jd, tjd), zodiac))
    return at


def moved_houses(natal: dict, tjd: float, method: str) -> dict:
    """Progressed houses at the birth latitude, in the natal zodiac.

    'solar-arc': MC = natal MC + true solar arc. 'naibod': natal ARMC + 0.9856473° per year.
    houses_armc has no sidereal mode, so the natal MC goes to tropical with the birth ayanamsa, the houses
    are worked out in tropical (with the tropical arc), and they come back to sidereal with the ayanamsa at
    the progressed instant, the moment the progressed bodies are computed for. A sidereal solar-arc MC is
    therefore natal MC + sidereal arc, as for the bodies.
    """
    return house_mover(natal, method)(tjd)
```

**Step 4: Run** → 7 passed. **Step 5: Commit** `git commit -m "Add progression time key, solar arc and moved angles"`

---

### Task 3: Progressed and directed charts

**Files:**
- Modify: `progressions/scripts/progressions.py` (append)
- Test: `progressions/tests/test_charts.py`

**Step 1: Failing test**

```python
import datetime as dt
import json
from pathlib import Path

import pytest
import progressions as pg

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"


@pytest.fixture
def natal():
    return json.loads(EXAMPLE.read_text())


def at(natal, y, m, d):
    return pg.target_jd(dt.date(y, m, d), natal["meta"]["timezone"])


def test_progressed_chart_example(natal):
    p = pg.progressed_chart(natal, at(natal, 2027, 6, 15))
    assert p["schema_version"] == 1
    assert p["meta"]["chart_type"] == "secondary_progressed"
    assert p["meta"]["derived_from"] == ["Example"]
    prog = p["meta"]["progression"]
    assert prog["target_date"] == "2027-06-15" and prog["angles_method"] == "solar-arc"
    assert prog["age_years"] == pytest.approx(37.0001, abs=1e-4)
    assert prog["solar_arc"] == pytest.approx(35.2991, abs=1e-3)
    assert p["bodies"]["Sun"]["formatted"] == "29°35' Cancer"
    assert p["bodies"]["Moon"]["formatted"] == "6°48' Leo"
    assert p["meta"]["datetime_local"] == natal["meta"]["datetime_local"]
    for b in p["bodies"].values():
        assert b["house"] == pg.house_of(b["longitude"], p["houses"]["cusps"])


def test_directed_chart_moves_everything_by_the_arc(natal):
    d = pg.directed_chart(natal, at(natal, 2027, 6, 15))
    arc = d["meta"]["progression"]["solar_arc"]
    assert d["meta"]["chart_type"] == "solar_arc_directed"
    assert d["meta"]["progression"]["angles_method"] is None
    for n, b in natal["bodies"].items():
        assert abs(pg.wrapped(d["bodies"][n]["longitude"] - (b["longitude"] + arc))) < 1e-3
        assert d["bodies"][n]["house"] == b["house"]
    for k in ("ascendant", "mc"):
        assert abs(pg.wrapped(d["angles"][k] - (natal["angles"][k] + arc))) < 1e-3
    assert all(a["applying"] is None for a in d["aspects"])


def test_solar_arc_angles_make_progressed_mc_equal_directed_mc(natal):
    t = at(natal, 2027, 6, 15)
    assert pg.progressed_chart(natal, t)["angles"]["mc"] == pytest.approx(pg.directed_chart(natal, t)["angles"]["mc"], abs=1e-3)


def test_identity_at_birth(natal):
    bj = natal["meta"]["julian_day_ut"]
    p, d = pg.progressed_chart(natal, bj), pg.directed_chart(natal, bj)
    for n, b in natal["bodies"].items():
        assert abs(pg.wrapped(p["bodies"][n]["longitude"] - b["longitude"])) < 1e-3
        assert abs(pg.wrapped(d["bodies"][n]["longitude"] - b["longitude"])) < 1e-3
    assert d["meta"]["progression"]["solar_arc"] == pytest.approx(0.0, abs=1e-6)


def test_untimed_natal(natal):
    natal["angles"] = None; natal["houses"] = None; natal["meta"]["time_unknown"] = True
    for chart in (pg.progressed_chart(natal, at(natal, 2027, 6, 15)), pg.directed_chart(natal, at(natal, 2027, 6, 15))):
        assert chart["angles"] is None and chart["houses"] is None
        assert chart["meta"]["progression"]["angles_method"] is None
        assert all(b["house"] is None for b in chart["bodies"].values())


def test_missing_chiron_stays_missing(natal):
    del natal["bodies"]["Chiron"]
    assert "Chiron" not in pg.progressed_chart(natal, at(natal, 2027, 6, 15))["bodies"]
```

**Step 2: Run** → fails (no `progressed_chart`).

**Step 3: Implement** (add `import copy` to the imports at the top, then append):

```python
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ASPECTS = {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Quincunx": 150, "Opposition": 180}
ORBS = {"Conjunction": 8.0, "Opposition": 8.0, "Square": 8.0, "Trine": 8.0, "Sextile": 6.0, "Quincunx": 3.0}
LUMINARY_BONUS = 2.0
LUMINARIES = {"Sun", "Moon"}


def sign_of(lon: float) -> tuple[str, float]:
    lon %= 360
    return SIGNS[int(lon // 30)], lon % 30


def format_degree(lon: float) -> str:
    # Round the whole longitude to the nearest arc-minute first so a value a
    # hair under a sign boundary rolls over into the next sign (never "30°00'").
    total_minutes = round(lon % 360 * 60) % (360 * 60)
    sign = SIGNS[total_minutes // (30 * 60)]
    whole, minutes = divmod(total_minutes % (30 * 60), 60)
    return f"{whole}°{minutes:02d}' {sign}"


def house_of(lon: float, cusps: list[float]) -> int:
    lon %= 360
    for i in range(12):
        start, end = cusps[i], cusps[(i + 1) % 12]
        inside = start <= lon < end if start < end else (lon >= start or lon < end)
        if inside:
            return i + 1
    return 12


def max_orb(aspect: str, b1: str, b2: str) -> float:
    return ORBS[aspect] + (LUMINARY_BONUS if (b1 in LUMINARIES or b2 in LUMINARIES) else 0.0)


def separation(lon1: float, lon2: float) -> float:
    d = abs(lon1 - lon2) % 360
    return min(d, 360 - d)


def applying(p1: dict, p2: dict, angle: float) -> bool | None:
    """Analytic applying test copied from natal-chart's aspects.py; None without relative motion."""
    if p1.get("speed") is None or p2.get("speed") is None:
        return None
    rel = p1["speed"] - p2["speed"]
    if abs(rel) < 1e-9:
        return None
    delta = ((p1["longitude"] - p2["longitude"] + 180) % 360) - 180
    target = angle if delta >= 0 else -angle
    return (delta - target) * rel < 0


def find_aspects(points: dict[str, dict]) -> list[dict]:
    names = list(points)
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]
             if not (a in ("Ascendant", "MC") and b in ("Ascendant", "MC"))]
    found = []
    for n1, n2 in pairs:
        p1, p2 = points[n1], points[n2]
        sep = separation(p1["longitude"], p2["longitude"])
        for aspect, angle in ASPECTS.items():
            limit = max_orb(aspect, n1, n2)
            if abs(sep - angle) <= limit:
                found.append({"body1": n1, "body2": n2, "aspect": aspect, "angle": angle,
                              "orb": round(abs(sep - angle), 3), "max_orb": limit,
                              "applying": applying(p1, p2, angle)})
                break
    return found


def _body(lon, speed, lat, cusps):
    sign, deg = sign_of(lon)
    return {"longitude": round(lon % 360, 4), "sign": sign, "sign_degree": round(deg, 4),
            "formatted": format_degree(lon), "speed": None if speed is None else round(speed, 4),
            "retrograde": bool(speed is not None and speed < 0),
            "house": house_of(lon, cusps) if cusps else None, "latitude": round(lat, 4)}


def birth_date(natal: dict) -> dt.date:
    meta = natal["meta"]
    return jd_to_local_date(meta["julian_day_ut"], meta["timezone"])


def day_edges(natal: dict) -> tuple[float, float]:
    """Julian days of 00:00 and 23:59 local on the birth date: the span natal-chart's moon_range covers."""
    day, tz = birth_date(natal), natal["meta"]["timezone"]
    return local_jd(day, dt.time(0, 0), tz), local_jd(day, dt.time(23, 59), tz)


def _moon_range(start: float, end: float) -> dict:
    return {"start": round(start % 360, 4), "end": round(end % 360, 4)}


def _assemble(natal: dict, raw: dict, houses: dict | None, chart_type: str, tjd: float, arc: float,
              angles_method: str | None, moon_range: dict | None) -> dict:
    """raw: name -> (longitude, speed or None, latitude). houses: moved houses or None (untimed).
    The natal meta is copied whole (keeping keys such as house_system_requested); the moving parts are replaced.
    A natal body missing from raw is Chiron without its ephemeris file, flagged as natal-chart flags it."""
    meta = copy.deepcopy(natal["meta"])
    meta["moon_range"] = moon_range
    cusps = houses["cusps"] if houses else None
    bodies = {n: _body(lon, sp, lat, cusps) for n, (lon, sp, lat) in raw.items()}
    points = {n: {"longitude": b["longitude"], "speed": b["speed"]} for n, b in bodies.items()}
    angles = None
    if houses:
        angles = {k: round(v, 4) for k, v in houses["angles"].items()}
        points["Ascendant"] = {"longitude": angles["ascendant"]}
        points["MC"] = {"longitude": angles["mc"]}
        meta["house_system"] = houses["system"]
    meta["chart_type"] = chart_type
    meta["derived_from"] = [natal["meta"]["name"]]
    lost = {"chiron_unavailable"} if set(natal["bodies"]) - set(raw) else set()
    meta["flags"] = sorted(set(meta.get("flags", [])) | set(houses["flags"] if houses else []) | lost)
    # The positions come from this run's pyswisseph, so its version and ephemeris replace the natal cast's.
    meta["source"] = {**(meta.get("source") or {}), "library": "pyswisseph", "version": swe.version,
                      "ephemeris_files": ephemeris_files_present()}
    meta["progression"] = {"target_date": jd_to_local_date(tjd, meta["timezone"]).isoformat(),
                           "age_years": round((tjd - meta["julian_day_ut"]) / YEAR, 4),
                           "solar_arc": round(arc, 4), "angles_method": angles_method}
    return {"schema_version": SCHEMA_VERSION, "meta": meta, "angles": angles,
            "houses": {"system": houses["system"], "cusps": [round(c, 4) for c in houses["cusps"]]} if houses else None,
            "bodies": bodies, "aspects": find_aspects(points)}


def progressed_chart(natal: dict, tjd: float, angles_method: str = "solar-arc") -> dict:
    """Secondary progressed chart for target Julian day `tjd` (a target before the birth moment is the birth)."""
    meta = natal["meta"]
    bj = meta["julian_day_ut"]
    tjd = max(tjd, bj)
    pos = body_positions(progressed_jd(bj, tjd), meta["zodiac"], meta.get("node", "true"))
    raw = {n: (p["longitude"], p["speed"], p["latitude"]) for n, p in pos.items() if n in natal["bodies"]}
    houses = moved_houses(natal, tjd, angles_method) if natal.get("angles") else None
    moon = None
    if meta.get("moon_range") is not None:
        # Untimed: the progressed Moon for a birth at each edge of the birth day, each progressed by its own age,
        # never below 0 (on the birth date, a birth at 23:59 has not happened by noon).
        moon = _moon_range(*(swe.calc_ut(progressed_jd(e, max(tjd, e)), swe.MOON, _flags(meta["zodiac"]))[0][0]
                             for e in day_edges(natal)))
    return _assemble(natal, raw, houses, "secondary_progressed", tjd, solar_arc(bj, tjd, meta["zodiac"]),
                     angles_method if houses else None, moon)


def directed_chart(natal: dict, tjd: float) -> dict:
    """Solar arc directed chart: every body, angle and cusp moves by the true solar arc (a target before the
    birth moment is the birth). Whole-sign cusps stay on sign boundaries, from the directed Ascendant's sign."""
    meta = natal["meta"]
    bj = meta["julian_day_ut"]
    tjd = max(tjd, bj)
    arc = solar_arc(bj, tjd, meta["zodiac"])
    raw = {n: ((b["longitude"] + arc) % 360, None, b.get("latitude", 0.0)) for n, b in natal["bodies"].items()}
    houses = None
    if natal.get("angles"):
        angles = {k: (v + arc) % 360 for k, v in natal["angles"].items()}
        system = natal["houses"]["system"]
        cusps = (whole_sign_cusps(angles["ascendant"]) if system == "whole_sign"
                 else [(c + arc) % 360 for c in natal["houses"]["cusps"]])
        houses = {"system": system, "cusps": cusps, "angles": angles, "flags": []}
    moon = None
    if meta.get("moon_range") is not None:
        moon = _moon_range(meta["moon_range"]["start"] + arc, meta["moon_range"]["end"] + arc)
    return _assemble(natal, raw, houses, "solar_arc_directed", tjd, arc, None, moon)
```

**Step 4: Run** → all pass. **Step 5: Commit** `git commit -m "Assemble progressed and directed charts"`

---

### Task 4: Event timeline

**Files:**
- Modify: `progressions/scripts/progressions.py` (append)
- Test: `progressions/tests/test_timeline.py`

**Step 1: Failing test**

```python
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
    assert any(m == "Pluto" and d.startswith("turns direct at ") and e.year == 2030 for e, m, d in stations)
    assert any(m == "Mercury" and d.startswith("turns retrograde at ") and e.year == 2061 for e, m, d in stations)


def test_untimed_chart(natal):
    u = json.loads(json.dumps(natal))
    u["angles"] = None; u["houses"] = None; u["meta"]["time_unknown"] = True
    rows = pg.timeline(u, START, END)
    assert not [r for r in rows if "Ascendant" in (r["moving"], r["target"]) or "MC" in (r["moving"], r["target"]) or r["event"] == "house"]
    assert all(r["uncertain"] for r in rows if r["technique"] == "secondary")
    fast = {"Moon", "Sun", "Mercury", "Venus", "Mars"}
    assert all(r["uncertain"] == bool(fast & {r["moving"], r["target"]}) for r in rows if r["technique"] == "solar_arc")
```

**Step 2: Run** → fails (no `timeline`).

**Step 3: Implement** (append):

```python
ORB = 1.0                  # timeline window, degrees either side of exact
STEP = 15.0                # days of real time between samples
TOL = 1 / 1440             # bisect to a minute so printed local dates do not depend on the sample grid
MARGIN = 5 * YEAR          # scan this far beyond the range so windows overlapping it are found
SLOW_MARGIN = 40 * YEAR    # the same for movers that can stall at a station: windows up to ~37 years (Mars)
EDGE_LIMIT = 60 * YEAR     # look this far past exact for a window's closing edge; beyond it the window is open
SECONDARY_MOVERS = ["Moon", "Sun", "Mercury", "Venus", "Mars"]
SLOW_MOVERS = {"Mercury", "Venus", "Mars"}
STATION_BODIES = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Chiron"]
# Natal positions a ±12 h birth-time error moves by about 0.4° (Mars) to 7° (the Moon): months of solar arc.
TIME_SENSITIVE = {"Moon", "Sun", "Mercury", "Venus", "Mars"}


def _bisect(f, lo: float, hi: float, flo) -> float:
    """f(lo) == flo and f(hi) != flo; narrow to TOL and return the midpoint."""
    while hi - lo > TOL:
        mid = (lo + hi) / 2
        if f(mid) == flo:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _grid(t0: float, t1: float) -> list[float]:
    ts, t = [t0], t0
    while t < t1:
        t = min(t + STEP, t1)
        ts.append(t)
    return ts


def _zero_crossings(g, ts, gs) -> list[float]:
    """Where g (values in [-180, 180)) crosses zero between samples, ignoring the ±180 seam."""
    out = []
    for (a, ga), (b, gb) in zip(zip(ts, gs), zip(ts[1:], gs[1:])):
        # A real crossing moves g far less than 90° between samples. The exception is within ~0.01° of the
        # polar circle, where the Ascendant can jump ~180° (natal-chart falls back to whole sign there): like
        # the ±180 seam, that jump is not a crossing.
        if (ga < 0 <= gb or ga >= 0 > gb) and abs(gb - ga) < 90:
            out.append(_bisect(lambda x: g(x) >= 0, a, b, ga >= 0))
    return out


def _edge(g, te: float, direction: int, bound: float) -> float | None:
    """First time from te toward `bound` (direction ±1) where |g| reaches ORB; None if it stays inside to bound."""
    t = te
    while (bound - t) * direction > 0:
        n = min(t + STEP, bound) if direction > 0 else max(t - STEP, bound)
        if abs(g(n)) >= ORB:
            lo, hi = (t, n) if direction > 0 else (n, t)
            return _bisect(lambda x: abs(g(x)) >= ORB, lo, hi, abs(g(lo)) >= ORB)
        t = n
    return None


def _aspect_events(technique: str, mover: str, m, targets: dict, ts: list[float], birth_jd: float) -> list[dict]:
    ms = [m(t) for t in ts]                      # evaluate the mover once per sample
    rows = []
    for tname, tlon in targets.items():
        if technique == "solar_arc" and tname == mover:
            continue
        for aname, angle in ASPECTS.items():
            for sgn in ((1,) if angle in (0, 180) else (1, -1)):
                off = tlon + sgn * angle
                g = lambda t, o=off: wrapped(m(t) - o)
                gs = [wrapped(v - off) for v in ms]
                for te in _zero_crossings(g, ts, gs):
                    if tname == mover and te - birth_jd < STEP:
                        continue         # a point leaving its own natal place; rounding makes it look like a pass
                    start = _edge(g, te, -1, birth_jd)
                    rows.append({"technique": technique, "event": "aspect", "moving": mover, "aspect": aname,
                                 "target": tname, "exact": te, "from": birth_jd if start is None else start,
                                 "to": _edge(g, te, +1, te + EDGE_LIMIT), "detail": ""})
    return rows


def _state_events(technique: str, event: str, mover: str, state, ts: list[float], describe) -> list[dict]:
    """Rows where state(t) changes between samples; describe(old, new, exact) gives the Detail."""
    rows = []
    vals = [state(t) for t in ts]
    for (a, va), (b, vb) in zip(zip(ts, vals), zip(ts[1:], vals[1:])):
        if va != vb:
            te = _bisect(state, a, b, va)
            rows.append({"technique": technique, "event": event, "moving": mover, "aspect": "", "target": "",
                         "exact": te, "from": None, "to": None, "detail": describe(va, vb, te)})
    return rows


def progressable(natal: dict) -> list[str]:
    """The natal bodies pyswisseph can progress here: Chiron drops out when its ephemeris file is missing."""
    meta = natal["meta"]
    pos = body_positions(meta["julian_day_ut"], meta["zodiac"], meta.get("node", "true"))
    return [n for n in natal["bodies"] if n in pos]


def overlaps(row: dict, start: dt.date, end: dt.date) -> bool:
    """Whether a timeline row, its dates already local, touches start..end, compared as whole days.

    An aspect's window runs from `from` to `to`, open on a side whose edge is None. Ingresses, house ingresses
    and stations have no window: they are point events on `exact`.
    """
    if row["event"] == "aspect":
        lo = row["from"] if row["from"] is not None else dt.date.min
        hi = row["to"] if row["to"] is not None else dt.date.max
    else:
        lo = hi = row["exact"]
    return lo <= end and hi >= start


def timeline(natal: dict, start: dt.date, end: dt.date, angles_method: str = "solar-arc") -> list[dict]:
    """Dated secondary and solar arc events whose 1° window overlaps [start, end], as whole local days."""
    meta = natal["meta"]
    tz, bj, zodiac, node = meta["timezone"], meta["julian_day_ut"], meta["zodiac"], meta.get("node", "true")
    timed = bool(natal.get("angles"))
    r0, r1 = max(target_jd(start, tz), bj), max(target_jd(end, tz), bj)   # never before the birth moment
    ts = _grid(max(bj, r0 - MARGIN), r1 + MARGIN)
    slow_ts = _grid(max(bj, r0 - SLOW_MARGIN), r1 + SLOW_MARGIN)
    targets = {n: b["longitude"] for n, b in natal["bodies"].items()}
    if timed:
        targets["Ascendant"], targets["MC"] = natal["angles"]["ascendant"], natal["angles"]["mc"]
    flags = _flags(zodiac)
    natal_sun = sun_lon(bj, zodiac)
    arcs: dict[float, float] = {}

    def arc(t):
        if t not in arcs:
            arcs[t] = solar_arc(bj, t, zodiac, natal_sun)
        return arcs[t]

    def prog_lon(name):
        ident = swe.MEAN_NODE if (name == "Node" and node == "mean") else BODIES[name]
        return lambda t: swe.calc_ut(progressed_jd(bj, t), ident, flags)[0][0]

    def prog_retro(name):
        return lambda t: swe.calc_ut(progressed_jd(bj, t), BODIES[name], flags)[0][3] < 0

    progressed = progressable(natal)
    rows = []
    for name in SECONDARY_MOVERS:
        if name in natal["bodies"]:
            rows += _aspect_events("secondary", name, prog_lon(name), targets,
                                   slow_ts if name in SLOW_MOVERS else ts, bj)
    if timed:
        # With solar-arc angles the progressed MC is the directed MC by definition; list it once, under solar arc.
        moving = (("Ascendant", "ascendant"),)
        if angles_method != "solar-arc":
            moving += (("MC", "mc"),)
        houses_at = house_mover(natal, angles_method)
        for ang, key in moving:
            rows += _aspect_events("secondary", ang, lambda t, k=key: houses_at(t)["angles"][k], targets, ts, bj)
    for name, lon in targets.items():
        # The directed Sun is the progressed Sun (the arc is the progressed Sun's travel); list it once, under
        # secondary.
        if name != "Sun":
            rows += _aspect_events("solar_arc", name, lambda t, l=lon: (l + arc(t)) % 360, targets, ts, bj)
    for name in progressed:
        f = prog_lon(name)
        rows += _state_events("secondary", "ingress", name, lambda t, f=f: int((f(t) % 360) // 30), ts,
                              lambda a, b, t: f"enters {SIGNS[b]}")
    if timed:
        cusps, f = natal["houses"]["cusps"], prog_lon("Moon")
        rows += _state_events("secondary", "house", "Moon", lambda t: house_of(f(t), cusps), ts,
                              lambda a, b, t: f"enters natal house {b}")
    for name in STATION_BODIES:
        if name in progressed:
            rows += _state_events("secondary", "station", name, prog_retro(name), ts,
                                  lambda a, b, t, f=prog_lon(name):
                                  f"turns {'retrograde' if b else 'direct'} at {format_degree(f(t))}")

    for r in rows:
        for k in ("exact", "from", "to"):
            r[k] = jd_to_local_date(r[k], tz) if r[k] is not None else None
    rows = [r for r in rows if overlaps(r, start, end)]
    for r in rows:
        # Untimed: a 12-hour error in the birth moment moves every secondary event by up to ~6 months (half a
        # progressed day). Solar arc rows move with the natal positions instead, so they are uncertain when
        # the Moon, Sun, Mercury, Venus or Mars is the mover or the target.
        r["uncertain"] = (not timed) and (r["technique"] == "secondary"
                                          or bool(TIME_SENSITIVE & {r["moving"], r["target"]}))
    rows.sort(key=lambda r: (r["exact"], r["technique"], r["moving"], r["target"]))
    return rows
```

**Step 4: Run** → all pass (the lifetime test takes a few seconds). **Step 5: Commit** `git commit -m "Add progression event timeline"`

---

### Task 5: Command line

**Files:**
- Modify: `progressions/scripts/progressions.py` (append CLI)
- Test: `progressions/tests/test_cli.py`

Interface:

```
progressions.py chart.json --date YYYY-MM-DD [--method secondary|solar-arc] [--angles solar-arc|naibod] [--out PATH] [--grid PATH]
progressions.py chart.json --timeline --start YYYY-MM-DD --end YYYY-MM-DD [--angles solar-arc|naibod] [--out PATH]
```

Behaviour:
- Exactly one of `--date` and `--timeline` (exit 1 otherwise). `--angles` only with secondary charts or the timeline; `--method solar-arc --angles ...` exits 1.
- Copy `Parser` (usage errors exit 1) and `load_chart` from `composite/scripts/composite.py`. Refuse any chart whose `meta.chart_type` is present and not `natal` (returns, composites, Davison, progressed and directed charts; a chart carrying `meta.progression` counts as progressed), naming the chart_type, and a natal chart without a real moment (`meta.julian_day_ut`, `datetime_utc` or `timezone` null), each with a one-line stderr message and exit 1.
- Refuse `--out` or `--grid` naming the input chart file (by any path or a hard link), naming a folder, or in a folder that does not exist, all before anything is computed (one stderr line naming the path, exit 1, nothing written).
- Chart mode: default out `secondary_progressed_<date>.json` or `solar_arc_directed_<date>.json`; grid default `<out stem>_aspects.md`, rendered with `render_grid` copied from `natal-chart/scripts/grid.py`; `--grid` equal to `--out` exits 1. Print `Wrote <out> and <grid>` and a `Note:` line per flag.
- Timeline mode: default out `progressions_timeline.csv`; `--end` before `--start` exits 1; a `--start` before birth is clamped to the birth date with a Note; ranges over 120 years exit 1. CSV header `Technique,Event,Moving,Aspect,Target,Exact,Orb from,Orb to,Detail,Uncertain`; Technique is `secondary` or `solar arc`; dates ISO; Uncertain is `yes` or blank. Print `Wrote N events to <out>`, plus `Note: chiron_unavailable` when the ephemeris files are missing (progressed Chiron's ingresses and stations are left out) and a Note when the chart is untimed.

**Tests** (subprocess with `sys.executable -I`, from a tmp cwd): chart mode defaults (both methods; file names, chart_type, grid present); `--angles naibod` recorded in `progression.angles_method`; `--method solar-arc --angles naibod` exits 1; both `--date` and `--timeline` exits 1; neither exits 1; a composite, a Davison chart and a solar return from the examples each exit 1 with one stderr line naming the chart_type; an already-progressed chart exits 1; `--out` or `--grid` over the input exits 1; `--date` equal to the birth date with an afternoon birth gives age 0; timeline writes the header and at least 100 rows for the example over 2027–2036 and parses with `csv.DictReader`; end before start exits 1; a start before birth is clamped with a Note; `--grid` equal to `--out` exits 1.

**Commit** `git commit -m "Add progressions command line"`

---

### Task 6: Docs and examples

**Files:** `progressions/SKILL.md`, `progressions/README.md`, `progressions/examples/secondary_progressed_2027-06-15.json` and `_aspects.md`, `progressions/examples/solar_arc_directed_2027-06-15.json` and `_aspects.md`, `progressions/examples/progressions_timeline_2027-2036.csv`.

SKILL.md in the house style (model on `returns/SKILL.md`): trigger description (progressions, progressed chart, progressed Moon, secondary progressions, solar arc, solar arc directions, "what's my progressed Moon doing", "what's coming up for me this decade", progressed Sun changing sign); the two modes and when to use each; the angle methods and that solar-arc is the default; the time key; the timeline columns and how to read windows; the untimed-birth ±6-month caveat stated plainly (and that solar arc events touching the Moon, Sun, Mercury, Venus or Mars are marked uncertain too); presenting results (lead with the progressed Moon's sign and house and the next two or three exact events; group a timeline by year; say which technique each event comes from); consumers (wheel and synastry read the charts; returns refuses them; transits to a progressed chart are unusual); exit codes; troubleshooting. README with "Examples are produced by:" and the exact commands, run from the repo root:

```
python progressions/scripts/progressions.py natal-chart/examples/chart.json --date 2027-06-15 --out progressions/examples/secondary_progressed_2027-06-15.json
python progressions/scripts/progressions.py natal-chart/examples/chart.json --date 2027-06-15 --method solar-arc --out progressions/examples/solar_arc_directed_2027-06-15.json
python progressions/scripts/progressions.py natal-chart/examples/chart.json --timeline --start 2027-01-01 --end 2036-12-31 --out progressions/examples/progressions_timeline_2027-2036.csv
```

Add `progressions_timeline*.csv` with an `!**/examples/` exception to `.gitignore`, mirroring the transits rule.

**Commit** `git commit -m "Document progressions skill with examples"`

---

### Task 7: README, round trip, final verification

**Files:** `README.md`, `progressions/tests/test_cli.py` (round-trip test), `chart-wheel/SKILL.md`, `synastry/SKILL.md` (one sentence each)

- Root README: a `progressions` row; install note (reads a natal chart.json; needs pyswisseph; no delegation).
- Round-trip test: the 2027-06-15 progressed and directed charts through chart-wheel, synastry (against the natal chart) and transits-to-natal by subprocess, each exit 0; returns and composite refuse both with exit 1; skip with a reason if a sibling is absent.
- Run all seven test folders one at a time. Fresh-copy smoke test in the scratchpad: copy the seven chart skill folders alone, fetch ephemeris, cast the example natal chart, write both charts and a ten-year timeline, render both charts with the wheel, run synastry progressed against natal, confirm returns refuses the progressed chart, print OK.

**Commit** `git commit -m "Add progressions to portfolio README"`

---

## Review fixes

A review round after Tasks 2-5 changed the code above in place (the blocks show the fixed code): the Lahiri
ayanamsa with nutation, as natal-chart uses; sidereal houses shifted back with the ayanamsa at the progressed
instant; sidereal and directed whole-sign cusps on sign boundaries from the Ascendant's sign; `moon_range`
recomputed on progressed and directed charts; targets before the birth moment clamped to age 0; non-natal
inputs and outputs over the input refused; Mercury, Venus and Mars scanned 40 years either side of the range;
no self-aspect at birth and no window before it; whole-day range overlap with open-ended windows; exact local
midnights kept on their date; natal constants cached; solar arc rows uncertain for untimed charts when the
Moon, Sun, Mercury, Venus or Mars is involved; station longitudes in Detail. Each has a test in
`progressions/tests`.

A second review round: crossings bisected to the minute (`TOL = 1 / 1440`) so printed local dates do not depend
on the sample grid; solar arc rows moving the Sun dropped (the directed Sun is the progressed Sun, listed under
secondary); missing ephemeris files handled as natal-chart does (`chiron_unavailable`, `meta.source.ephemeris_files`
for the run, progressed Chiron's timeline rows left out with a Note); every output's folder checked before anything
is computed; hard links to the input refused; the untimed `moon_range` edges clamped to age 0 on the birth date; an
empty or null `chart_type` refused. Each has a test in `progressions/tests`.

A final polish round: `meta.source.version` is the running pyswisseph's; a chart missing a key the computation
needs, or holding the wrong type, exits 1 with `progressions: <path>: malformed chart (<error>)` instead of a bare
key name or a traceback; the timeline prints the `--angles ignored` Note for an untimed chart as chart mode does;
the wheel caption reads "Secondary progressed for Example · 2027-06-15". The grid-phase test now shifts the scan
margins by fractions of a step instead of running ~43 one-day timelines, tests that need the Swiss files skip
without them, and a test runs the README commands and compares the output with the committed examples byte for
byte.

## Out of scope

Tertiary and minor progressions, converse progressions and directions, the progressed lunation cycle, progressed composites, primary directions, and a published golden check (on the open list).
