# Returns and Composite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add two skills, `returns` (solar, lunar, Mars, Jupiter, Saturn, Uranus, Chiron return charts over a date range) and `composite` (midpoint composite and Davison charts), per `docs/plans/2026-10-11-returns-composite-design.md`.

**Architecture:** Both skills delegate every real chart cast to the sibling `natal-chart/scripts/natal_chart.py`, located and run exactly as `synastry/scripts/synastry.py` does. `returns` finds return moments with pyswisseph and bisection; `composite` computes midpoints itself and derives houses from the composite MC with pyswisseph's ARMC house routine. A two-key contract addition (`meta.chart_type`, `meta.derived_from`) is made to natal-chart first.

**Tech Stack:** Python 3.11+, pyswisseph 2.10, timezonefinder, pytest. No cross-folder imports; helpers are copied as in synastry.

---

## Before you start

Read the design document and `natal-chart/CONTRACT.md`. Read `synastry/scripts/synastry.py` in full: `find_natal_script`, `Parser`, `DelegationFailed`, `cast_chart`, `load_chart` and the `main` error handling are the patterns to copy verbatim into both new scripts (copy, do not import). Environment:

```bash
cd skywatch-skills
python3 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip setuptools wheel && pip install pyswisseph timezonefinder pytest
python natal-chart/scripts/fetch_ephemeris.py
for d in natal-chart chart-wheel transits-to-natal synastry; do python -m pytest $d/tests -q || exit 1; done
```

Facts verified during design, with the numbers the tests below rely on:

- `swe.houses_armc(armc, lat, eps, code)` reproduces `swe.houses` cusps exactly when `armc = atan2(sin(mc)·cos(eps), cos(mc))` in degrees mod 360 and `eps = swe.calc_ut(jd, swe.ECL_NUT)[0][0]`. For 1990-06-15 16:00 UT at New York, MC 71.226 gives ARMC 69.6698 and Ascendant 163.8869 either way.
- Daily sampling of the wrapped Sun-minus-natal difference, sign change detection, and 60 bisection steps finds the 2027 solar return for that chart at 2027-06-15 14.56034 h UT with a residual of 3e-10°.
- Great-circle midpoint of New York (40.7143, -74.006) and Tokyo (35.6895, 139.6917) is (69.66, -153.66); the arithmetic mean is (38.20, 32.84).
- `dt.time.fromisoformat("14:33:37")` works, so natal-chart accepts seconds already.

Commit after every task with imperative messages. Never commit `ephe/`, `.venv/`, or stray outputs.

---

### Task 1: Contract addition in natal-chart

**Files:**
- Modify: `natal-chart/scripts/chart.py` (the `meta` dict in `build_chart`)
- Modify: `natal-chart/CONTRACT.md` (meta table)
- Modify: `natal-chart/examples/chart.json`, `synastry/examples/chart_b.json` (regenerate)
- Test: `natal-chart/tests/test_chart.py`

**Step 1: Write the failing test** (append to test_chart.py)

```python
def test_meta_carries_chart_type_and_derivation():
    c = ch.build_chart("Test", dt.date(1990, 6, 15), dt.time(12, 0), "America/New_York", NY, "placidus")
    assert c["meta"]["chart_type"] == "natal"
    assert c["meta"]["derived_from"] == []
```

**Step 2: Run** `.venv/bin/python -m pytest natal-chart/tests/test_chart.py -q` → 1 failed (KeyError).

**Step 3: Implement.** In `build_chart`'s `meta` dict add, after `"name": name,`:

```python
            "chart_type": "natal",
            "derived_from": [],
```

Add two rows to the `meta` table in CONTRACT.md:

```
| `chart_type` | string | `natal` from natal-chart. Derived charts rewrite it: `solar_return`, `lunar_return`, `mars_return`, `jupiter_return`, `saturn_return`, `uranus_return`, `chiron_return`, `composite`, `davison`. |
| `derived_from` | array of string | Names of the source charts a derived chart was built from; `[]` for natal. |
```

Regenerate the two examples with their documented commands (natal-chart README and synastry README say which). Run every folder's tests; synastry's round-trip and the wheel tests must still pass.

**Step 4: Run all four test folders** → all pass.

**Step 5: Commit** `git commit -m "Add chart_type and derived_from to chart.json meta"`

---

### Task 2: chart-wheel caption shows the chart type

**Files:**
- Modify: `chart-wheel/scripts/chart_wheel.py` (`captions`)
- Test: `chart-wheel/tests/test_wheel.py`

**Step 1: Failing test**

```python
def test_caption_names_derived_chart_type(tmp_path):
    chart = json.loads(EXAMPLE.read_text())
    chart["meta"]["chart_type"] = "solar_return"
    chart["meta"]["derived_from"] = ["Example"]
    svg = chart_wheel.render(chart)
    assert "Solar return for Example" in svg
    natal = json.loads(EXAMPLE.read_text())
    assert "Solar return" not in chart_wheel.render(natal)
```

(Import `chart_wheel` at the top of the test file via the conftest sys.path, as the geometry tests import `wheel_geometry`.)

**Step 2: Run** → fails.

**Step 3: Implement.** In `captions`, build the title line as: name, then for `chart_type` not in (`None`, `"natal"`) a prefix `f"{chart_type.replace('_', ' ').capitalize()} for {', '.join(derived_from)}"` when `derived_from` is non-empty, else just the humanised type; keep the datetime and timezone as now. Escape everything.

**Step 4: Run** `chart-wheel/tests` → pass. **Step 5: Commit** `git commit -m "Show derived chart type in wheel caption"`

---

### Task 3: returns scaffolding and the return-moment search

**Files:**
- Create: `returns/tests/conftest.py` (copy of natal-chart's), `returns/scripts/returns.py`
- Test: `returns/tests/test_search.py`

**Step 1: Failing test**

```python
import datetime as dt
import pytest
import swisseph as swe
import returns as rt

NATAL_JD = 2448058.1666667  # 1990-06-15 16:00 UT


def test_body_table():
    assert rt.BODIES["sun"] == ("Sun", swe.SUN)
    assert set(rt.BODIES) == {"sun", "moon", "mars", "jupiter", "saturn", "uranus", "chiron"}


def test_wrapped_difference():
    assert rt.wrapped(10.0, 350.0) == pytest.approx(20.0)
    assert rt.wrapped(350.0, 10.0) == pytest.approx(-20.0)


def test_solar_return_2027_matches_reference():
    natal_sun = swe.calc_ut(NATAL_JD, swe.SUN, swe.FLG_SWIEPH)[0][0]
    hits = rt.find_returns(swe.SUN, natal_sun, dt.date(2027, 1, 1), dt.date(2027, 12, 31))
    assert len(hits) == 1
    jd = hits[0]
    y, m, d, h = swe.revjul(jd)
    assert (y, m, d) == (2027, 6, 15) and h == pytest.approx(14.56034, abs=1e-4)
    assert abs(rt.wrapped(swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)[0][0], natal_sun)) < 0.001


def test_lunar_returns_in_a_year():
    natal_moon = swe.calc_ut(NATAL_JD, swe.MOON, swe.FLG_SWIEPH)[0][0]
    hits = rt.find_returns(swe.MOON, natal_moon, dt.date(2027, 1, 1), dt.date(2027, 12, 31))
    assert len(hits) in (13, 14)
    gaps = [b - a for a, b in zip(hits, hits[1:])]
    assert all(26.5 < g < 28.5 for g in gaps)


def test_mars_retrograde_year_gives_three_crossings():
    # Pick a natal Mars longitude inside Mars's 2027 retrograde loop so the loop crosses it three times.
    # Find the loop first: Mars is retrograde when its daily speed is negative.
    jd0 = swe.julday(2026, 9, 1, 0)
    speeds = [(jd0 + i, swe.calc_ut(jd0 + i, swe.MARS, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]) for i in range(0, 300)]
    retro = [j for j, p in speeds if p[3] < 0]
    assert retro, "expected a Mars retrograde in the window"
    mid = retro[len(retro) // 2]
    target = swe.calc_ut(mid, swe.MARS, swe.FLG_SWIEPH)[0][0]
    hits = rt.find_returns(swe.MARS, target, dt.date(2026, 9, 1), dt.date(2027, 6, 30))
    assert len(hits) == 3


def test_precession_shift_grows_with_age():
    shift = rt.precession_shift(NATAL_JD, swe.julday(2027, 6, 15, 14.0))
    assert 0.50 < shift < 0.53  # ~37 years × ~50.3"/yr ≈ 0.517°
```

**Step 2: Run** `.venv/bin/python -m pytest returns/tests -q` → ModuleNotFoundError.

**Step 3: Implement** the search half of `returns/scripts/returns.py`:

```python
#!/usr/bin/env python3
"""
Cast return charts (solar, lunar, Mars, Jupiter, Saturn, Uranus, Chiron) for a date range.

Usage:
    python returns.py chart.json --body sun --start 2027-01-01 --end 2027-12-31 --city "Austin, TX"
    python returns.py chart.json --body moon --start 2027-01-01 --end 2027-03-31 --geonameid 5128581
    python returns.py chart.json --start 2027-01-01 --end 2027-12-31            # natal place, flagged

Each return is cast by the sibling natal-chart script, so the output files are ordinary chart.json
files that chart-wheel, transits-to-natal and synastry read unchanged. Exit 2 means an ambiguous
city (candidates printed); re-run with --geonameid.
"""
import argparse
import datetime as dt
import json
import math
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

for _ephe in (Path(__file__).resolve().parents[1] / "ephe", Path(__file__).resolve().parents[2] / "natal-chart" / "ephe"):
    if (_ephe / "seas_18.se1").exists():
        swe.set_ephe_path(str(_ephe))
        break

BODIES = {
    "sun": ("Sun", swe.SUN), "moon": ("Moon", swe.MOON), "mars": ("Mars", swe.MARS),
    "jupiter": ("Jupiter", swe.JUPITER), "saturn": ("Saturn", swe.SATURN),
    "uranus": ("Uranus", swe.URANUS), "chiron": ("Chiron", swe.CHIRON),
}
FLAGS = swe.FLG_SWIEPH


def wrapped(lon: float, target: float) -> float:
    """Signed difference lon - target in (-180, 180]."""
    return ((lon - target + 180.0) % 360.0) - 180.0


def longitude(jd: float, body: int, sidereal: bool = False) -> float:
    flags = FLAGS | (swe.FLG_SIDEREAL if sidereal else 0)
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
    return swe.calc_ut(jd, body, flags)[0][0]


def precession_shift(natal_jd: float, jd: float) -> float:
    """Ayanamsa drift between two moments (Lahiri), in degrees; add to the tropical target."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    return swe.get_ayanamsa_ut(jd) - swe.get_ayanamsa_ut(natal_jd)


def find_returns(body: int, target: float, start: dt.date, end: dt.date, sidereal: bool = False,
                 shift_fn=None) -> list[float]:
    """Julian days (UT) at which `body` crosses `target` longitude between start 00:00 and end 24:00 UT.

    Samples daily, detects sign changes of the wrapped difference (ignoring the 180° wrap), and
    bisects each to about 1e-10 day. Retrograde loops give one hit per crossing. `shift_fn(jd)`,
    when given, is added to the target at each evaluation (precession correction).
    """
    def diff(jd: float) -> float:
        t = target + (shift_fn(jd) if shift_fn else 0.0)
        return wrapped(longitude(jd, body, sidereal), t)

    jd = swe.julday(start.year, start.month, start.day, 0.0)
    last = swe.julday(end.year, end.month, end.day, 24.0)
    hits = []
    prev = diff(jd)
    while jd < last:
        nxt = min(jd + 1.0, last)
        cur = diff(nxt)
        if prev == 0.0:
            hits.append(jd)
        elif (prev < 0 < cur or prev > 0 > cur) and abs(cur - prev) < 180.0:
            lo, hi, flo = jd, nxt, prev
            for _ in range(60):
                mid = (lo + hi) / 2
                fm = diff(mid)
                if (fm < 0) == (flo < 0):
                    lo, flo = mid, fm
                else:
                    hi = mid
            hits.append((lo + hi) / 2)
        jd, prev = nxt, cur
    return hits
```

**Step 4: Run** `returns/tests` → 6 passed (the Mars test may take a few seconds). **Step 5: Commit** `git commit -m "Add return-moment search"`

---

### Task 4: returns delegation and summary

**Files:**
- Modify: `returns/scripts/returns.py` (CLI, delegation, summary)
- Test: `returns/tests/test_cli.py`

**Step 1: Failing test**

```python
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "returns.py"
EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"


def run(*args, cwd):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)


def test_solar_return_cast_at_natal_place_when_no_place_given(tmp_path):
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-12-31", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    files = sorted(tmp_path.glob("sun_return_*.json"))
    assert [f.name for f in files] == ["sun_return_2027-06-15.json"]
    c = json.loads(files[0].read_text())
    assert c["meta"]["chart_type"] == "solar_return"
    assert c["meta"]["derived_from"] == ["Example"]
    assert "return_place_natal" in c["meta"]["flags"]
    assert c["meta"]["location"]["geonameid"] == 5128581
    assert abs(c["bodies"]["Sun"]["longitude"] - json.loads(EXAMPLE.read_text())["bodies"]["Sun"]["longitude"]) < 0.001
    assert (tmp_path / "returns_summary.md").exists()
    assert "2027-06-15" in (tmp_path / "returns_summary.md").read_text()


def test_lunar_returns_relocated(tmp_path):
    r = run(str(EXAMPLE), "--body", "moon", "--start", "2027-01-01", "--end", "2027-02-28",
            "--lat", "30.2672", "--lon", "-97.7431", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    files = sorted(tmp_path.glob("moon_return_*.json"))
    assert len(files) == 2
    c = json.loads(files[0].read_text())
    assert c["meta"]["chart_type"] == "lunar_return"
    assert c["meta"]["timezone"] == "America/Chicago"
    assert "return_place_natal" not in c["meta"]["flags"]


def test_ambiguous_city_exits_2(tmp_path):
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-12-31", "--city", "Paris", cwd=tmp_path)
    assert r.returncode == 2 and "geonameid" in r.stdout


def test_untimed_chart_is_refused_for_angles_but_cast(tmp_path):
    chart = json.loads(EXAMPLE.read_text())
    chart["meta"]["time_unknown"] = True
    p = tmp_path / "u.json"; p.write_text(json.dumps(chart))
    r = run(str(p), "--start", "2027-01-01", "--end", "2027-12-31", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "natal_time_unknown" in json.loads(next(tmp_path.glob("sun_return_*.json")).read_text())["meta"]["flags"]
```

**Step 2: Run** → fails (no CLI).

**Step 3: Implement** the second half of `returns.py`. Copy `find_natal_script`, `Parser`, `DelegationFailed` and the error handling from synastry. Then:

```python
def chart_type_for(key: str) -> str:
    return {"sun": "solar_return", "moon": "lunar_return"}.get(key, f"{key}_return")


def local_datetime(jd: float, tz: ZoneInfo) -> dt.datetime:
    y, m, d, h = swe.revjul(jd)
    seconds = round(h * 3600)
    utc = dt.datetime(y, m, d, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)
    return utc.astimezone(tz)


def cast_return(natal_script: Path, chart: dict, jd: float, place_args: list[str], out: Path,
                body_key: str, extra_flags: list[str]) -> dict:
    """Run natal-chart for one return moment and rewrite the derived-chart keys."""
    tz_name = resolve_timezone(place_args)          # see below
    local = local_datetime(jd, ZoneInfo(tz_name))
    meta = chart["meta"]
    args = [sys.executable, "-I", str(natal_script),
            "--name", meta["name"], "--date", local.date().isoformat(),
            "--time", local.time().replace(microsecond=0).isoformat(),
            *place_args,
            "--houses", meta.get("house_system") or "placidus",
            "--zodiac", "sidereal" if str(meta.get("zodiac", "")).startswith("sidereal") else "tropical",
            "--node", meta.get("node", "true"),
            "--out", str(out)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise DelegationFailed(r.returncode, r.stdout, r.stderr)
    result = json.loads(out.read_text(encoding="utf-8"))
    result["meta"]["chart_type"] = chart_type_for(body_key)
    result["meta"]["derived_from"] = [meta["name"]]
    result["meta"]["return_utc"] = local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result["meta"]["flags"] = sorted(set(result["meta"]["flags"]) | set(extra_flags))
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
```

`resolve_timezone(place_args)`: when the place is `--lat/--lon` without `--tz`, use `timezonefinder` to get the zone (natal-chart would do the same, but the script needs it first to compute the local time); when `--tz` is present use it; when `--city`/`--geonameid`, run natal-chart once in "probe" mode on the natal date to learn the resolved timezone and geonameid from its output `meta.timezone` (this also surfaces ambiguity as exit 2 before any return is searched). Keep it simple: a helper `probe_place(natal_script, chart, place_args) -> str` that casts the natal chart at the given place into a temp file and returns `meta["timezone"]`.

`main`: parse `chart`, `--body` (default sun), `--start`, `--end`, place flags, `--precessed`, `--out-dir` (default cwd). Load and validate the chart (schema 1, body present in `bodies`; `chiron` missing → exit 1 with message). Place: if none given, use `--geonameid` from the chart's location when it has one, else `--lat/--lon/--tz` from the chart; add flag `return_place_natal`. If the chart is `time_unknown`, still cast but add flag `natal_time_unknown`. Target = natal longitude; `shift_fn = lambda jd: precession_shift(natal_jd, jd)` when `--precessed`, plus flag `precession_corrected`. For each hit: out name `f"{body_key}_return_{local_date}.json"` (append `_2`, `_3` for same-day duplicates), cast, collect. Write `returns_summary.md`: a table with columns Return, UTC moment, Local time, Place, ASC, MC, DSC, IC, Return Moon sign, and a line per return comparing the return Ascendant sign and Moon sign to the natal ones. Print `Wrote N return chart(s) and returns_summary.md`. Exit codes 0/1/2 as natal-chart.

**Step 4: Run** `returns/tests` → all pass. **Step 5: Commit** `git commit -m "Cast return charts through natal-chart"`

---

### Task 5: returns docs and example

**Files:** `returns/SKILL.md`, `returns/README.md`, `returns/examples/sun_return_2027-06-15.json`, `returns/examples/returns_summary.md`

SKILL.md in the house style (read `transits-to-natal/SKILL.md` as the closest model): triggers (solar return, lunar return, birthday chart, my return chart this year, Saturn return, Jupiter return, Chiron return, Mars return, "where should I be for my birthday"); the two-step workflow (chart.json first, then returns); the place question Claude must ask when the user has not said where they will be, since houses depend on it; the flags `return_place_natal`, `natal_time_unknown`, `precession_corrected`; that every output is a normal chart.json so the wheel and transits apply; the Mercury/Venus deferral; exit codes. Generate the example from `natal-chart/examples/chart.json` for 2027 at the natal place and record the command in the README.

**Commit** `git commit -m "Document returns skill with example"`

---

### Task 6: composite helpers and the midpoint chart

**Files:**
- Create: `composite/tests/conftest.py`, `composite/scripts/composite.py`
- Test: `composite/tests/test_midpoint.py`

Copy from natal-chart into `composite.py`: `SIGNS`, `sign_of`, `format_degree`, `house_of` (chart.py) and `ASPECTS`, `ORBS`, `LUMINARY_BONUS`, `LUMINARIES`, `max_orb`, `separation`, `find_aspects` (aspects.py; `applying` is not needed since every composite aspect has `applying: None`, so copy `find_aspects` with `"applying": None`).

**Step 1: Failing test**

```python
import json
import math
from pathlib import Path
import pytest
import swisseph as swe
import composite as cp

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"
PARTNER = Path(__file__).resolve().parents[2] / "synastry" / "examples" / "chart_b.json"


def test_short_arc_midpoint():
    assert cp.midpoint(350.0, 10.0) == pytest.approx(0.0)
    assert cp.midpoint(10.0, 350.0) == pytest.approx(0.0)
    assert cp.midpoint(0.0, 180.0) in (pytest.approx(90.0), pytest.approx(270.0))
    assert cp.midpoint(100.0, 140.0) == pytest.approx(120.0)


def test_armc_from_mc_reproduces_swisseph_houses():
    jd = swe.julday(1990, 6, 15, 16.0)
    cusps, ascmc = swe.houses(jd, 40.7143, -74.006, b"P")
    eps = cp.obliquity(jd)
    houses = cp.houses_from_mc(ascmc[1], 40.7143, eps, "placidus")
    assert houses["angles"]["ascendant"] == pytest.approx(ascmc[0], abs=1e-3)
    assert houses["cusps"][1] == pytest.approx(cusps[1], abs=1e-3)


def test_self_composite_is_identity():
    a = json.loads(EXAMPLE.read_text())
    c = cp.midpoint_chart(a, a, reference=a["meta"]["location"], house_system="placidus")
    for name, body in a["bodies"].items():
        assert c["bodies"][name]["longitude"] == pytest.approx(body["longitude"], abs=1e-3)
    assert c["angles"]["mc"] == pytest.approx(a["angles"]["mc"], abs=1e-3)
    assert c["angles"]["ascendant"] == pytest.approx(a["angles"]["ascendant"], abs=0.05)
    assert c["meta"]["chart_type"] == "composite" and c["meta"]["derived_from"] == ["Example", "Example"]
    assert all(x["applying"] is None for x in c["aspects"])


def test_untimed_side_drops_houses():
    a = json.loads(EXAMPLE.read_text()); b = json.loads(PARTNER.read_text())
    b["meta"]["time_unknown"] = True; b["angles"] = None; b["houses"] = None
    c = cp.midpoint_chart(a, b, reference=a["meta"]["location"], house_system="placidus")
    assert c["angles"] is None and c["houses"] is None
    assert {"time_unknown", "moon_uncertain"} <= set(c["meta"]["flags"])
```

**Step 2: Run** → ModuleNotFoundError.

**Step 3: Implement** (in addition to the copied helpers):

```python
def midpoint(a: float, b: float) -> float:
    """Midpoint on the shorter arc, in [0, 360)."""
    d = ((b - a + 180.0) % 360.0) - 180.0
    return (a + d / 2.0) % 360.0


def obliquity(jd: float) -> float:
    return swe.calc_ut(jd, swe.ECL_NUT)[0][0]


def armc_from_mc(mc: float, eps: float) -> float:
    m, e = math.radians(mc), math.radians(eps)
    return math.degrees(math.atan2(math.sin(m) * math.cos(e), math.cos(m))) % 360.0


HOUSE_CODES = {"placidus": b"P", "koch": b"K", "equal": b"E", "porphyry": b"O", "whole_sign": b"W"}


def houses_from_mc(mc: float, latitude: float, eps: float, system: str) -> dict:
    """Cusps and angles for a given MC at a latitude; whole-sign fallback at polar latitudes."""
    flags = []
    armc = armc_from_mc(mc, eps)
    try:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES[system])
    except swe.Error:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES["whole_sign"])
        system, flags = "whole_sign", ["polar_fallback_whole_sign"]
    asc, mc_out = ascmc[0] % 360, ascmc[1] % 360
    return {"system": system, "cusps": [c % 360 for c in cusps[:12]],
            "angles": {"ascendant": asc, "mc": mc_out, "descendant": (asc + 180) % 360, "ic": (mc_out + 180) % 360},
            "flags": flags}
```

`midpoint_chart(a, b, reference, house_system)`: bodies = intersection of both body dicts in natal order; each gets longitude = midpoint, sign/sign_degree/formatted from it, speed = mean of speeds, retrograde False, latitude = mean, house filled after houses are known. If either side is time_unknown: angles/houses None, flags `time_unknown`, `moon_uncertain`, `moon_range` None. Else eps at the mean of the two `julian_day_ut`, MC = midpoint of MCs, houses from `houses_from_mc` at `reference["latitude"]`. Aspects via `find_aspects` over bodies plus Ascendant/MC when present, excluding the Asc-MC pair, all `applying: None`. `meta`: name `f"{a.name} & {b.name}"`, chart_type `composite`, derived_from both names, datetime fields null, `julian_day_ut` the mean, `timezone` null, `location` = reference, zodiac/node/house_system carried from A, flags, `source` from A plus `"method": "midpoint"`. Sidereal note: if A and B disagree on zodiac or node, exit 1 with a message.

**Step 4: Run** → 4 passed. **Step 5: Commit** `git commit -m "Add midpoint composite chart"`

---

### Task 7: Davison

**Files:** modify `composite/scripts/composite.py`; test `composite/tests/test_davison.py`

**Step 1: Failing test**

```python
import datetime as dt
import json
from pathlib import Path
import pytest
import composite as cp

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"


def test_great_circle_midpoint():
    lat, lon = cp.great_circle_midpoint(40.7143, -74.006, 35.6895, 139.6917)
    assert lat == pytest.approx(69.66, abs=0.05) and lon == pytest.approx(-153.66, abs=0.05)
    lat, lon = cp.great_circle_midpoint(10.0, 179.0, 10.0, -179.0)
    assert lon == pytest.approx(180.0, abs=1e-6) or lon == pytest.approx(-180.0, abs=1e-6)


def test_davison_inputs_of_self_are_self():
    a = json.loads(EXAMPLE.read_text())
    when, lat, lon = cp.davison_inputs(a, a)
    assert when == dt.datetime(1990, 6, 15, 16, 0, tzinfo=dt.timezone.utc)
    assert (lat, lon) == pytest.approx((a["meta"]["location"]["latitude"], a["meta"]["location"]["longitude"]))


def test_davison_inputs_mean_time():
    a = json.loads(EXAMPLE.read_text()); b = json.loads(EXAMPLE.read_text())
    b["meta"]["datetime_utc"] = "1992-06-15T16:00:00Z"
    when, _, _ = cp.davison_inputs(a, b)
    # 731 days apart (1992 is a leap year), so the midpoint is 365.5 days after 1990-06-15 16:00 UT.
    assert when == dt.datetime(1991, 6, 16, 4, 0, tzinfo=dt.timezone.utc)
```

**Step 2: Run** → fails. **Step 3: Implement**

```python
def great_circle_midpoint(lat1, lon1, lat2, lon2) -> tuple[float, float]:
    p1, l1, p2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    bx = math.cos(p2) * math.cos(l2 - l1)
    by = math.cos(p2) * math.sin(l2 - l1)
    lat = math.atan2(math.sin(p1) + math.sin(p2), math.sqrt((math.cos(p1) + bx) ** 2 + by ** 2))
    lon = l1 + math.atan2(by, math.cos(p1) + bx)
    return math.degrees(lat), ((math.degrees(lon) + 540.0) % 360.0) - 180.0


def davison_inputs(a: dict, b: dict) -> tuple[dt.datetime, float, float]:
    ta = dt.datetime.strptime(a["meta"]["datetime_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    tb = dt.datetime.strptime(b["meta"]["datetime_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    when = ta + (tb - ta) / 2
    la, lb = a["meta"]["location"], b["meta"]["location"]
    lat, lon = great_circle_midpoint(la["latitude"], la["longitude"], lb["latitude"], lb["longitude"])
    return when.replace(microsecond=0), lat, lon
```

`cast_davison(natal_script, a, b, out)`: timezone from `timezonefinder` at the midpoint (fall back to `UTC` with flag `davison_timezone_utc` if none, e.g. mid-ocean); local time from `when`; if either chart is time_unknown, omit `--time` so natal-chart casts at noon and flags it; delegate with `--name "A & B"`, `--lat/--lon/--tz`, A's houses/zodiac/node; then set chart_type `davison`, derived_from, and `meta["source"]["method"] = "davison"`.

**Step 4: Run** → pass. **Step 5: Commit** `git commit -m "Add Davison chart inputs"`

---

### Task 8: composite CLI

**Files:** modify `composite/scripts/composite.py`; test `composite/tests/test_cli.py`

Interface: `composite.py (--a A.json --b B.json | --a-birth "..." --b-birth "...") [--method midpoint|davison] [--city/--geonameid/--lat --lon [--tz]] [--houses ...] [--out composite.json] [--grid ...]`. Copy synastry's delegation and loading. Tests via subprocess: midpoint of the two examples writes `composite.json` and `composite.md` with `chart_type == "composite"`; davison writes `davison.json` whose `meta.location` is the great-circle midpoint of New York and London (about 52.4, -41.0) and whose `chart_type == "davison"`; raw birth strings round-trip equal to the file inputs (compare everything except `config`-like provenance); ambiguous city in a birth string exits 2; `--out` equal to `--grid` exits 1. The reference place for midpoint houses defaults to A's location; `--city` etc. override it and are recorded in `meta.location`.

**Commit** `git commit -m "Add composite command line"`

---

### Task 9: composite docs and examples

**Files:** `composite/SKILL.md`, `composite/README.md`, `composite/examples/composite.json`, `composite.md`, `davison.json`, `davison.md`

SKILL.md triggers: composite chart, relationship chart, our chart as a couple, Davison, midpoint chart, "chart of the relationship". Explain the midpoint-versus-Davison difference in two sentences each, the reference-place question for midpoint houses, that a Davison chart is a real moment so transits apply while a midpoint composite's transits are deferred, the untimed-side behaviour, and that both inputs must share zodiac and node. Examples from `natal-chart/examples/chart.json` and `synastry/examples/chart_b.json`, commands recorded in the README.

**Commit** `git commit -m "Document composite skill with examples"`

---

### Task 10: README, contract, and final verification

**Files:** `README.md`, `natal-chart/CONTRACT.md` (consumer list sentence), `chart-wheel/SKILL.md` (caption note)

Add two rows to the root Skills table and extend the install note. In CONTRACT.md's opening paragraph, add returns and composite to the consumers and say that derived charts set `chart_type`. Run all six test folders:

```bash
for d in natal-chart chart-wheel transits-to-natal synastry returns composite; do .venv/bin/python -m pytest $d/tests -q || exit 1; done
```

Fresh-copy smoke test in the scratchpad: copy all six folders alone, fetch ephemeris, cast a natal chart, run a solar return for 2027, a lunar return month, a midpoint composite and a Davison, then feed the solar return and the Davison through chart-wheel, transits-to-natal (one month) and synastry (return against natal), and print OK.

**Commit** `git commit -m "Add returns and composite to portfolio README"`

---

## Out of scope

Mercury and Venus returns, progressions, relocated natal charts as a skill, transits to a midpoint composite, published-return golden tests.
