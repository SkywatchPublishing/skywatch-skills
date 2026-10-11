# Chart Core Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add four self-contained skills (`natal-chart`, `chart-wheel`, `transits-to-natal`, `synastry`) that share one `chart.json` contract, per `docs/plans/2026-10-08-chart-core-design.md`.

**Architecture:** `natal-chart/scripts/natal_chart.py` computes positions, houses, and aspects with pyswisseph and writes `chart.json` plus a Markdown aspect grid. The other three skills are standard-library scripts that read `chart.json` (transits also uses pyswisseph for the moving sky). No shared package: each skill folder is copyable on its own; `synastry` finds its sibling `natal-chart` script only when handed raw birth data.

**Tech Stack:** Python 3.11+, pyswisseph 2.10, timezonefinder (natal-chart only, for raw coordinates), pytest, zoneinfo, csv/json/xml from the standard library.

---

## Before you start

Read the design document first. Then set up a working environment:

```bash
cd skywatch-skills
python3 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip setuptools wheel      # system setuptools on Debian breaks the pyswisseph build
pip install pyswisseph timezonefinder pytest
```

This works in the cloud container too: pyswisseph has no wheel, but it compiles from source once setuptools is upgraded inside a venv (the system setuptools on Debian fails with `AttributeError: install_layout`).

Verify: `python -c "import swisseph as swe; print(swe.version)"` prints `2.10.03` or newer.

Facts verified during design that shape the tasks below:

- `swe.calc_ut(jd, swe.CHIRON, ...)` raises `swisseph.Error` mentioning `seas_18.se1` when ephemeris files are absent. Planets silently use the Moshier fallback (return flag 260 instead of 258).
- `swe.houses(jd, 70.0, 20.0, b'P')` raises `swisseph.Error: swisseph.houses: error`. Whole Sign (`b'W'`) succeeds at the same latitude.
- Reference values: Sun at 2000-01-01 12:00 UT = 280.3689° tropical, 256.516° sidereal Lahiri (ayanamsa 23.857°); mean node at J2000 = 125.041°; Chiron at 1990-06-15 12:00 UT = 106.0605° (files present); Mars/Pluto sextile orb at 2026-04-16 19:00 UT = 0.002°; Moon on 1990-06-15 in New York runs from 340.92° at 00:00 to 354.34° at 23:59 local.
- `timezonefinder` resolves (40.7143, -74.006) to `America/New_York`.
- `download.geonames.org` may be blocked by a cloud session's network policy. Task 3 is written so the raw zip can be fetched on any machine and the reduced CSV committed.

Commit after every task. Commit messages use the imperative mood ("Add natal chart aspect engine"). Do not commit `ephe/`, `*.se1`, `cities15000.zip`, or `.venv/`.

---

### Task 1: Repo scaffolding and gitignore

**Files:**
- Modify: `.gitignore`
- Create: `natal-chart/tests/conftest.py`

Do not add `__init__.py` files to `tests/` or `scripts/`: pytest is run one folder at a time, and package-style test folders with the same name collide when someone runs two folders in one command.

**Step 1: Extend `.gitignore`**

Append:

```
# Swiss Ephemeris data files, fetched by natal-chart/scripts/fetch_ephemeris.py
ephe/
*.se1
# raw GeoNames dump, reduced to natal-chart/data/cities.csv by build_cities.py
cities15000.zip
cities15000.txt
.pytest_cache/
```

**Step 2: Add the conftest so tests can import the script as a module**

`natal-chart/tests/conftest.py`:

```python
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
```

**Step 3: Run pytest on the empty folder**

Run: `python -m pytest natal-chart/tests -q`
Expected: `no tests ran` with exit code 5. That proves collection works.

**Step 4: Commit**

```bash
git add .gitignore natal-chart/tests/conftest.py
git commit -m "Scaffold natal-chart skill folder"
```

---

### Task 2: Ephemeris file fetcher

**Files:**
- Create: `natal-chart/scripts/fetch_ephemeris.py`
- Test: `natal-chart/tests/test_fetch_ephemeris.py`

**Step 1: Write the failing test**

```python
from pathlib import Path
import fetch_ephemeris as fe


def test_file_list_and_url():
    assert fe.FILES == ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]
    assert fe.url_for("seas_18.se1") == (
        "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/seas_18.se1"
    )


def test_default_dir_is_sibling_ephe():
    assert fe.default_dir() == Path(fe.__file__).resolve().parents[1] / "ephe"


def test_missing_lists_only_absent_files(tmp_path):
    (tmp_path / "sepl_18.se1").write_bytes(b"x")
    assert fe.missing(tmp_path) == ["semo_18.se1", "seas_18.se1"]
```

**Step 2: Run to verify it fails**

Run: `python -m pytest natal-chart/tests/test_fetch_ephemeris.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'fetch_ephemeris'`.

**Step 3: Implement**

`natal-chart/scripts/fetch_ephemeris.py`:

```python
#!/usr/bin/env python3
"""
Download the Swiss Ephemeris data files natal-chart needs into natal-chart/ephe/.

Usage:
    python fetch_ephemeris.py [--dir DIR]

Files (about 2 MB total, AGPL-3.0 from Astrodienst):
    sepl_18.se1  planets 1800-2400
    semo_18.se1  Moon    1800-2400
    seas_18.se1  asteroids incl. Chiron 1800-2400
Without them the planets use the built-in Moshier ephemeris and Chiron is omitted.
"""
import argparse
import sys
import urllib.request
from pathlib import Path

FILES = ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]
BASE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/"


def url_for(name: str) -> str:
    return BASE_URL + name


def default_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "ephe"


def missing(directory: Path) -> list[str]:
    return [f for f in FILES if not (directory / f).exists()]


def fetch(directory: Path) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    fetched = []
    for name in missing(directory):
        urllib.request.urlretrieve(url_for(name), directory / name)
        fetched.append(name)
    return fetched


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=default_dir())
    args = parser.parse_args(argv)
    try:
        fetched = fetch(args.dir)
    except Exception as exc:  # network errors are the normal failure here
        print(f"Could not download ephemeris files: {exc}", file=sys.stderr)
        return 1
    print(f"Ephemeris files ready in {args.dir} (downloaded {len(fetched)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run tests, then the script for real**

Run: `python -m pytest natal-chart/tests/test_fetch_ephemeris.py -q` → 3 passed.
Run: `python natal-chart/scripts/fetch_ephemeris.py` → `Ephemeris files ready in .../natal-chart/ephe (downloaded 3)`. `git status` must not show `ephe/`.

**Step 5: Commit**

```bash
git add natal-chart/scripts/fetch_ephemeris.py natal-chart/tests/test_fetch_ephemeris.py
git commit -m "Add Swiss Ephemeris file fetcher"
```

---

### Task 3: City table build script and committed data

**Files:**
- Create: `natal-chart/scripts/build_cities.py`
- Create: `natal-chart/data/cities.csv` (generated, committed)
- Test: `natal-chart/tests/test_build_cities.py`

GeoNames `cities15000.txt` is tab-separated with 19 columns. The ones we keep, by zero-based index: 0 geonameid, 1 name, 2 asciiname, 4 latitude, 5 longitude, 8 country code, 10 admin1 code, 14 population, 17 timezone.

**Step 1: Write the failing test**

```python
import csv
import build_cities as bc

ROW = "\t".join([
    "5128581", "New York City", "New York City", "NYC,Nueva York", "40.71427", "-74.00597",
    "P", "PPL", "US", "", "NY", "", "", "", "8804190", "", "10", "America/New_York", "2022-03-09",
])


def test_reduce_row():
    assert bc.reduce_row(ROW.split("\t")) == [
        "5128581", "New York City", "New York City", "US", "NY",
        "40.71427", "-74.00597", "America/New_York", "8804190",
    ]


def test_build_writes_sorted_csv(tmp_path):
    src = tmp_path / "cities15000.txt"
    src.write_text(ROW + "\n" + ROW.replace("5128581", "1").replace("8804190", "20000") + "\n", encoding="utf-8")
    out = tmp_path / "cities.csv"
    bc.build(src, out)
    rows = list(csv.reader(out.open(encoding="utf-8")))
    assert rows[0] == bc.HEADER
    assert rows[1][0] == "5128581"   # larger population first
    assert len(rows) == 3
```

**Step 2: Run to verify it fails**

Run: `python -m pytest natal-chart/tests/test_build_cities.py -q` → `ModuleNotFoundError`.

**Step 3: Implement**

```python
#!/usr/bin/env python3
"""
Reduce the GeoNames cities15000 dump to the columns natal-chart needs.

Usage:
    python build_cities.py [--src cities15000.txt | --zip cities15000.zip] [--out ../data/cities.csv]

Get the dump from https://download.geonames.org/export/dump/cities15000.zip (CC BY 4.0).
"""
import argparse
import csv
import io
import sys
import zipfile
from pathlib import Path

HEADER = ["geonameid", "name", "asciiname", "country", "admin1", "latitude", "longitude", "timezone", "population"]
KEEP = [0, 1, 2, 8, 10, 4, 5, 17, 14]


def reduce_row(fields: list[str]) -> list[str]:
    return [fields[i] for i in KEEP]


def build(src: Path, out: Path) -> int:
    if src.suffix == ".zip":
        with zipfile.ZipFile(src) as z:
            text = z.read("cities15000.txt").decode("utf-8")
    else:
        text = src.read_text(encoding="utf-8")
    rows = [reduce_row(line.split("\t")) for line in text.splitlines() if line.strip()]
    rows.sort(key=lambda r: -int(r[8] or 0))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return len(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, default=Path("cities15000.zip"))
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "cities.csv")
    args = parser.parse_args(argv)
    n = build(args.src, args.out)
    print(f"Wrote {n} cities to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run tests, then generate the real table**

Run: `python -m pytest natal-chart/tests/test_build_cities.py -q` → 2 passed.
Run, on a machine that can reach geonames.org:

```bash
curl -L -o /tmp/cities15000.zip https://download.geonames.org/export/dump/cities15000.zip
python natal-chart/scripts/build_cities.py --src /tmp/cities15000.zip
```

Expected: `Wrote 3xxxx cities to .../natal-chart/data/cities.csv`, file size roughly 2 to 3 MB. Spot check: `grep -c "" natal-chart/data/cities.csv` matches the count plus one, and `grep "^5128581," natal-chart/data/cities.csv` shows New York.

**Step 5: Commit**

```bash
git add natal-chart/scripts/build_cities.py natal-chart/tests/test_build_cities.py natal-chart/data/cities.csv
git commit -m "Add GeoNames city table and its build script"
```

---

### Task 4: Location lookup

**Files:**
- Create: `natal-chart/scripts/location.py`
- Test: `natal-chart/tests/test_location.py`

Lookup rules: the whole query is first matched case-insensitively against `name` or `asciiname` (so names containing commas such as "Mianzhu, Deyang, Sichuan" resolve); otherwise the query is split on commas into a name plus trailing region tokens, each of which must equal a candidate's country code or admin1 code (so "Paris, FR", "Paris, TX" and the printed label "Paris, TX, US" all work). A name match whose region tokens do not fit raises `UnknownLocation` naming the city and up to five candidate labels. One match returns it. Several matches raise `AmbiguousLocation` carrying the candidates, sorted by population. None raise `UnknownLocation`.

**Step 1: Write the failing test**

```python
import pytest
import location as loc

CSV = """geonameid,name,asciiname,country,admin1,latitude,longitude,timezone,population
2988507,Paris,Paris,FR,11,48.85341,2.3488,Europe/Paris,2138551
4717560,Paris,Paris,US,TX,33.66094,-95.55551,America/Chicago,24000
5128581,New York City,New York City,US,NY,40.71427,-74.00597,America/New_York,8804190
"""


@pytest.fixture
def table(tmp_path):
    p = tmp_path / "cities.csv"
    p.write_text(CSV, encoding="utf-8")
    return loc.load_table(p)


def test_unique_match(table):
    city = loc.lookup("new york city", table)
    assert city.geonameid == 5128581
    assert city.timezone == "America/New_York"
    assert city.label == "New York City, NY, US"


def test_ambiguous_raises_with_candidates(table):
    with pytest.raises(loc.AmbiguousLocation) as info:
        loc.lookup("Paris", table)
    assert [c.geonameid for c in info.value.candidates] == [2988507, 4717560]


def test_suffix_disambiguates(table):
    assert loc.lookup("Paris, TX", table).geonameid == 4717560
    assert loc.lookup("Paris, FR", table).geonameid == 2988507


def test_by_geonameid(table):
    assert loc.lookup_id(4717560, table).label == "Paris, TX, US"


def test_unknown(table):
    with pytest.raises(loc.UnknownLocation):
        loc.lookup("Atlantis", table)
```

**Step 2: Run to verify it fails**

Run: `python -m pytest natal-chart/tests/test_location.py -q` → `ModuleNotFoundError: No module named 'location'`.

**Step 3: Implement**

```python
"""City lookup against data/cities.csv (GeoNames cities15000, reduced)."""
import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TABLE = Path(__file__).resolve().parents[1] / "data" / "cities.csv"


@dataclass(frozen=True)
class City:
    geonameid: int
    name: str
    asciiname: str
    country: str
    admin1: str
    latitude: float
    longitude: float
    timezone: str
    population: int

    @property
    def label(self) -> str:
        parts = [self.name, self.admin1, self.country]
        return ", ".join(p for p in parts if p)


class UnknownLocation(LookupError):
    pass


class AmbiguousLocation(LookupError):
    def __init__(self, query: str, candidates: list[City]):
        super().__init__(f"{len(candidates)} places match {query!r}")
        self.query = query
        self.candidates = candidates


def load_table(path: Path = DEFAULT_TABLE) -> list[City]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [
            City(int(r["geonameid"]), r["name"], r["asciiname"], r["country"], r["admin1"],
                 float(r["latitude"]), float(r["longitude"]), r["timezone"], int(r["population"] or 0))
            for r in csv.DictReader(fh)
        ]


def lookup(query: str, table: list[City]) -> City:
    name, _, region = (part.strip() for part in query.partition(","))
    key = name.casefold()
    region = region.upper()
    hits = [c for c in table if key in (c.name.casefold(), c.asciiname.casefold())]
    if region:
        hits = [c for c in hits if region in (c.country.upper(), c.admin1.upper())]
    hits.sort(key=lambda c: -c.population)
    if not hits:
        raise UnknownLocation(f"No city over 15,000 people matches {query!r}; pass --lat/--lon/--tz instead")
    if len(hits) > 1:
        raise AmbiguousLocation(query, hits)
    return hits[0]


def lookup_id(geonameid: int, table: list[City]) -> City:
    for c in table:
        if c.geonameid == geonameid:
            return c
    raise UnknownLocation(f"No city with geonameid {geonameid}")
```

**Step 4: Run tests** → 5 passed.

**Step 5: Commit**

```bash
git add natal-chart/scripts/location.py natal-chart/tests/test_location.py
git commit -m "Add city lookup with ambiguity handling"
```

---

### Task 5: Ephemeris wrapper (positions, Chiron fallback, houses, polar fallback)

**Files:**
- Create: `natal-chart/scripts/ephemeris.py`
- Test: `natal-chart/tests/test_ephemeris.py`

This module is the only place pyswisseph is called in `natal-chart`.

**Step 1: Write the failing test**

```python
import datetime as dt
from zoneinfo import ZoneInfo
import pytest
import ephemeris as eph


def test_julian_day_from_aware_datetime():
    d = dt.datetime(2000, 1, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
    assert eph.julian_day(d) == pytest.approx(2451545.0)


def test_sun_j2000_reference():
    pos = eph.body_positions(2451545.0)
    assert pos["Sun"]["longitude"] == pytest.approx(280.3689, abs=0.001)
    assert pos["Sun"]["speed"] > 0
    assert pos["Node"]["longitude"] >= 0


def test_sidereal_and_mean_node_options():
    pos = eph.body_positions(2451545.0, zodiac="sidereal", node="mean")
    assert pos["Sun"]["longitude"] == pytest.approx(256.516, abs=0.01)
    assert pos["Node"]["longitude"] == pytest.approx(125.041 - 23.857, abs=0.01)


def test_chiron_reference_or_flag():
    pos = eph.body_positions(eph.julian_day(dt.datetime(1990, 6, 15, 12, tzinfo=ZoneInfo("UTC"))))
    if eph.ephemeris_files_present():
        assert pos["Chiron"]["longitude"] == pytest.approx(106.0605, abs=0.01)
    else:
        assert "Chiron" not in pos


def test_placidus_new_york():
    jd = eph.julian_day(dt.datetime(1990, 6, 15, 12, tzinfo=ZoneInfo("UTC")))
    houses, flags = eph.houses(jd, 40.7, -74.0, "placidus")
    assert houses["system"] == "placidus"
    assert len(houses["cusps"]) == 12
    assert houses["angles"]["ascendant"] == pytest.approx(116.596, abs=0.01)
    assert houses["angles"]["mc"] == pytest.approx(10.349, abs=0.01)
    assert flags == []


def test_polar_falls_back_to_whole_sign():
    jd = eph.julian_day(dt.datetime(1990, 6, 15, 12, tzinfo=ZoneInfo("UTC")))
    houses, flags = eph.houses(jd, 70.0, 20.0, "placidus")
    assert houses["system"] == "whole_sign"
    assert houses["cusps"][0] % 30 == pytest.approx(0.0)
    assert flags == ["polar_fallback_whole_sign"]


def test_sidereal_houses_match_sidereal_planets():
    tropical, _ = eph.houses(2451545.0, 40.7, -74.0, "placidus")
    sidereal, flags = eph.houses(2451545.0, 40.7, -74.0, "placidus", zodiac="sidereal")
    assert flags == []
    assert tropical["angles"]["ascendant"] == pytest.approx(274.26, abs=0.01)
    assert sidereal["angles"]["ascendant"] == pytest.approx(250.40, abs=0.01)
    assert (tropical["angles"]["ascendant"] - sidereal["angles"]["ascendant"]) == pytest.approx(23.857, abs=0.01)
    assert (tropical["cusps"][9] - sidereal["cusps"][9]) % 360 == pytest.approx(23.857, abs=0.01)


def test_sidereal_whole_sign_cusps_use_sidereal_sign_boundaries():
    whole, _ = eph.houses(2451545.0, 40.7, -74.0, "whole_sign", zodiac="sidereal")
    asc = whole["angles"]["ascendant"]
    assert asc == pytest.approx(250.40, abs=0.01)
    assert whole["cusps"][0] % 30 == pytest.approx(0.0)
    assert whole["cusps"][0] == pytest.approx((asc // 30) * 30)


def test_sidereal_polar_falls_back_to_whole_sign():
    houses, flags = eph.houses(2451545.0, 70.0, 20.0, "placidus", zodiac="sidereal")
    assert houses["system"] == "whole_sign"
    assert houses["cusps"][0] % 30 == pytest.approx(0.0)
    assert flags == ["polar_fallback_whole_sign"]


def test_chiron_is_dropped_when_only_its_file_is_missing(monkeypatch):
    import swisseph as swe
    real = swe.calc_ut

    def fake(jd, ident, flags):
        if ident == swe.CHIRON:
            raise swe.Error("SwissEph file 'seas_18.se1' not found")
        return real(jd, ident, flags)

    monkeypatch.setattr(swe, "calc_ut", fake)
    pos = eph.body_positions(2451545.0)
    assert "Chiron" not in pos
    assert pos["Sun"]["longitude"] == pytest.approx(280.3689, abs=0.001)


def test_error_for_another_body_is_reraised(monkeypatch):
    import swisseph as swe
    real = swe.calc_ut

    def fake(jd, ident, flags):
        if ident == swe.MARS:
            raise swe.Error("boom")
        return real(jd, ident, flags)

    monkeypatch.setattr(swe, "calc_ut", fake)
    with pytest.raises(swe.Error):
        eph.body_positions(2451545.0)
```

**Step 2: Run to verify it fails** → `ModuleNotFoundError: No module named 'ephemeris'`.

**Step 3: Implement**

```python
"""Thin wrapper over pyswisseph: positions, houses, and the two fallbacks the design requires."""
import datetime as dt
from pathlib import Path

import swisseph as swe

EPHE_DIR = Path(__file__).resolve().parents[1] / "ephe"
swe.set_ephe_path(str(EPHE_DIR))

BODIES = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO, "Chiron": swe.CHIRON, "Node": swe.TRUE_NODE,
}
HOUSE_CODES = {"placidus": b"P", "koch": b"K", "equal": b"E", "porphyry": b"O", "whole_sign": b"W"}
FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED


def ephemeris_files_present() -> bool:
    return (EPHE_DIR / "seas_18.se1").exists()


def julian_day(when: dt.datetime) -> float:
    u = when.astimezone(dt.timezone.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600)


def body_positions(jd: float, zodiac: str = "tropical", node: str = "true") -> dict[str, dict]:
    """Longitude, latitude, speed for every body. Chiron is omitted when its file is missing.
    zodiac: 'tropical' or 'sidereal' (Lahiri). node: 'true' or 'mean'."""
    flags = FLAGS
    # FLG_SIDEREAL on this call selects the zodiac; set_sid_mode only picks the ayanamsa process-wide,
    # and `flags |=` rebinds the local name without mutating the module constant FLAGS.
    if zodiac == "sidereal":
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL
    out = {}
    for name, ident in BODIES.items():
        if name == "Node" and node == "mean":
            ident = swe.MEAN_NODE
        try:
            (lon, lat, _dist, dlon, *_), _ = swe.calc_ut(jd, ident, flags)
        except swe.Error:
            if name == "Chiron":
                continue
            raise
        out[name] = {"longitude": lon % 360, "latitude": lat, "speed": dlon}
    return out


def houses(jd: float, latitude: float, longitude: float, system: str,
           zodiac: str = "tropical") -> tuple[dict, list[str]]:
    """Cusps and angles in the same zodiac as body_positions. Falls back to Whole Sign where the
    requested system fails (polar latitudes)."""
    flags = []
    house_flags = 0
    if zodiac == "sidereal":
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        house_flags = swe.FLG_SIDEREAL  # houses_ex with this flag returns sidereal cusps and angles
    try:
        cusps, ascmc = swe.houses_ex(jd, latitude, longitude, HOUSE_CODES[system], house_flags)
    except swe.Error:
        if system == "whole_sign":
            raise
        cusps, ascmc = swe.houses_ex(jd, latitude, longitude, HOUSE_CODES["whole_sign"], house_flags)
        system = "whole_sign"
        flags.append("polar_fallback_whole_sign")
    asc, mc = ascmc[0] % 360, ascmc[1] % 360
    return {
        "system": system,
        "cusps": [c % 360 for c in cusps[:12]],
        "angles": {"ascendant": asc, "mc": mc, "descendant": (asc + 180) % 360, "ic": (mc + 180) % 360},
    }, flags
```

**Step 4: Run tests** → 11 passed (run once with `ephe/` present, once with it renamed away, to exercise both Chiron branches).

**Step 5: Commit**

```bash
git add natal-chart/scripts/ephemeris.py natal-chart/tests/test_ephemeris.py
git commit -m "Add ephemeris wrapper with Chiron and polar fallbacks"
```

---

### Task 6: Aspect engine (orbs, luminary bonus, applying/separating)

**Files:**
- Create: `natal-chart/scripts/aspects.py`
- Test: `natal-chart/tests/test_aspects.py`

**Step 1: Write the failing test**

```python
import pytest
import aspects as asp


def body(lon, speed=1.0):
    return {"longitude": lon, "speed": speed}


def test_orb_table_and_luminary_bonus():
    assert asp.max_orb("Trine", "Mercury", "Venus") == 8.0
    assert asp.max_orb("Trine", "Sun", "Venus") == 10.0
    assert asp.max_orb("Sextile", "Moon", "Moon") == 8.0
    assert asp.max_orb("Quincunx", "Mars", "Venus") == 3.0


def test_finds_trine_within_orb():
    found = asp.find_aspects({"Sun": body(10), "Mars": body(132, 0.5)})
    assert len(found) == 1
    a = found[0]
    assert (a["body1"], a["body2"], a["aspect"]) == ("Sun", "Mars", "Trine")
    assert a["orb"] == pytest.approx(2.0)
    assert a["max_orb"] == 10.0


def test_outside_orb_is_not_listed():
    assert asp.find_aspects({"Mercury": body(0), "Venus": body(68)}) == []


def test_quincunx_has_its_own_tight_orb():
    assert asp.find_aspects({"Mercury": body(0), "Venus": body(152)})[0]["aspect"] == "Quincunx"
    assert asp.find_aspects({"Mercury": body(0), "Venus": body(154)}) == []


def test_applying_when_separation_closes_on_exact():
    # Sun at 10 moving 1/day, Mars at 132 moving 0.5/day: separation 122 shrinking toward 120.
    a = asp.find_aspects({"Sun": body(10, 1.0), "Mars": body(132, 0.5)})[0]
    assert a["applying"] is True
    # Reverse the speeds: separation grows away from 120.
    b = asp.find_aspects({"Sun": body(10, 0.5), "Mars": body(132, 1.0)})[0]
    assert b["applying"] is False


def test_applying_is_null_without_speed():
    a = asp.find_aspects({"Sun": body(10), "Ascendant": {"longitude": 70}})[0]
    assert a["applying"] is None


def test_synastry_orbs_are_natal_minus_two():
    assert asp.max_orb("Conjunction", "Mars", "Venus", reduction=2.0) == 6.0


def test_applying_fast_pair_that_overshoots_within_an_hour():
    # Moon-speed body 0.1 short of an exact trine: approaching, even though it passes exact within the hour.
    assert asp.applying(body(0, 13.2), body(120.1, 0.0), 120) is True


def test_separating_fast_pair_just_past_exact():
    assert asp.applying(body(120.1, 13.2), body(0, 0.0), 120) is False


def test_applying_conjunction_across_the_zero_wrap():
    assert asp.applying(body(359, 1.0), body(1, 0.0), 0) is True


def test_applying_retrograde_conjunction_across_the_zero_wrap():
    assert asp.applying(body(1, -1.0), body(359, 0.0), 0) is True


def test_applying_opposition_from_either_side():
    assert asp.applying(body(179, 1.0), body(0, 0.0), 180) is True
    # delta = -179 with the first body moving slower: rel < 0, still closing on 180.
    assert asp.applying(body(0, 0.0), body(179, 1.0), 180) is True
    # Moving away from the opposition.
    assert asp.applying(body(179, 0.0), body(0, 1.0), 180) is False


def test_applying_is_null_for_equal_speeds():
    assert asp.applying(body(10, 1.0), body(130, 1.0), 120) is None


def test_applying_is_null_when_speed_is_none():
    assert asp.applying(body(10, None), body(130, 1.0), 120) is None
    assert asp.applying(body(10, 1.0), body(130, None), 120) is None
```

**Step 2: Run to verify it fails** → `ModuleNotFoundError: No module named 'aspects'`.

**Step 3: Implement**

```python
"""Aspect detection shared in spirit (copied, not imported) by synastry."""
import itertools

# Config block from the design document. synastry copies these and subtracts 2.
ASPECTS = {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Quincunx": 150, "Opposition": 180}
ORBS = {"Conjunction": 8.0, "Opposition": 8.0, "Square": 8.0, "Trine": 8.0, "Sextile": 6.0, "Quincunx": 3.0}
LUMINARY_BONUS = 2.0
LUMINARIES = {"Sun", "Moon"}


def max_orb(aspect: str, b1: str, b2: str, reduction: float = 0.0) -> float:
    bonus = LUMINARY_BONUS if (b1 in LUMINARIES or b2 in LUMINARIES) else 0.0
    return ORBS[aspect] + bonus - reduction


def separation(lon1: float, lon2: float) -> float:
    d = abs(lon1 - lon2) % 360
    return min(d, 360 - d)


def applying(p1: dict, p2: dict, angle: float) -> bool | None:
    """True when the pair is closing on the exact aspect, False when moving away from it,
    None when a speed is missing or the bodies move at the same rate.
    Uses the signed separation and relative speed analytically, so a fast body that reaches
    exact within the hour (the Moon, say) is still reported as applying."""
    if p1.get("speed") is None or p2.get("speed") is None:
        return None
    rel = p1["speed"] - p2["speed"]
    if abs(rel) < 1e-9:
        return None
    delta = ((p1["longitude"] - p2["longitude"] + 180) % 360) - 180  # signed, in (-180, 180]
    target = angle if delta >= 0 else -angle  # nearest exact aspect on delta's side (0 stays 0)
    return (delta - target) * rel < 0


def find_aspects(bodies: dict[str, dict], reduction: float = 0.0, pairs=None) -> list[dict]:
    """bodies: name -> {longitude, speed?}. pairs: optional iterable of (name1, name2); default all combinations."""
    pairs = pairs if pairs is not None else itertools.combinations(bodies, 2)
    found = []
    for n1, n2 in pairs:
        p1, p2 = bodies[n1], bodies[n2]
        sep = separation(p1["longitude"], p2["longitude"])
        for aspect, angle in ASPECTS.items():
            limit = max_orb(aspect, n1, n2, reduction)
            orb = abs(sep - angle)
            if orb <= limit:
                found.append({"body1": n1, "body2": n2, "aspect": aspect, "angle": angle,
                              "orb": round(orb, 3), "max_orb": limit, "applying": applying(p1, p2, angle)})
                break
    return found
```

**Step 4: Run tests** → 14 passed.

**Step 5: Commit**

```bash
git add natal-chart/scripts/aspects.py natal-chart/tests/test_aspects.py
git commit -m "Add aspect engine with per-aspect orbs and applying detection"
```

---

### Task 7: Chart assembly and `chart.json`

**Files:**
- Create: `natal-chart/scripts/chart.py`
- Test: `natal-chart/tests/test_chart.py`

**Step 1: Write the failing test**

```python
import datetime as dt
import pytest
import chart as ch

NY = {"name": "New York City, NY, US", "latitude": 40.7143, "longitude": -74.006, "geonameid": 5128581}


def test_sign_formatting():
    assert ch.sign_of(84.1296) == ("Gemini", pytest.approx(24.1296))
    assert ch.format_degree(84.1296) == "24°08' Gemini"
    assert ch.format_degree(359.99) == "29°59' Pisces"


def test_house_of():
    cusps = [116.6, 140.1, 165.2, 190.3, 219.4, 254.3, 296.6, 320.1, 345.2, 10.3, 39.4, 74.3]
    assert ch.house_of(84.1, cusps) == 12
    assert ch.house_of(117.0, cusps) == 1
    assert ch.house_of(5.0, cusps) == 9


def test_build_chart_known_time():
    c = ch.build_chart("Test", dt.date(1990, 6, 15), dt.time(12, 0), "America/New_York", NY, "placidus")
    assert c["schema_version"] == 1
    assert c["meta"]["time_unknown"] is False
    assert c["meta"]["datetime_utc"] == "1990-06-15T16:00:00Z"
    assert c["meta"]["utc_offset"] == "-04:00"
    assert c["meta"]["zodiac"] == "tropical" and c["meta"]["node"] == "true"
    assert list(c["bodies"])[:3] == ["Sun", "Moon", "Mercury"]
    assert c["bodies"]["Sun"]["sign"] == "Gemini"
    assert c["houses"]["system"] == "placidus"
    assert 1 <= c["bodies"]["Sun"]["house"] <= 12
    assert any(a["aspect"] for a in c["aspects"])


def test_build_chart_unknown_time():
    c = ch.build_chart("Test", dt.date(1990, 6, 15), None, "America/New_York", NY, "placidus")
    assert c["meta"]["time_unknown"] is True
    assert c["meta"]["datetime_local"] == "1990-06-15T12:00:00"
    assert c["angles"] is None and c["houses"] is None
    assert c["bodies"]["Sun"]["house"] is None
    assert set(c["meta"]["flags"]) >= {"time_unknown", "moon_uncertain"}
    rng = c["meta"]["moon_range"]
    assert rng["start"] == pytest.approx(340.92, abs=0.05) and rng["end"] == pytest.approx(354.34, abs=0.05)


def test_build_chart_sidereal():
    c = ch.build_chart("Test", dt.date(2000, 1, 1), dt.time(12, 0), "UTC", NY, "placidus", zodiac="sidereal")
    assert c["meta"]["zodiac"] == "sidereal_lahiri"
    assert c["bodies"]["Sun"]["longitude"] == pytest.approx(256.516, abs=0.01)
```

**Step 2: Run to verify it fails** → `ModuleNotFoundError: No module named 'chart'`.

**Step 3: Implement**

```python
"""Assemble chart.json (schema version 1) from birth data."""
import datetime as dt
from zoneinfo import ZoneInfo

import swisseph as swe

import aspects as asp
import ephemeris as eph

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
BODY_ORDER = list(eph.BODIES)


def sign_of(lon: float) -> tuple[str, float]:
    lon %= 360
    return SIGNS[int(lon // 30)], lon % 30


def format_degree(lon: float) -> str:
    sign, deg = sign_of(lon)
    whole = int(deg)
    minutes = int(round((deg - whole) * 60))
    if minutes == 60:
        whole, minutes = whole + 1, 0
    return f"{whole}°{minutes:02d}' {sign}"


def house_of(lon: float, cusps: list[float]) -> int:
    lon %= 360
    for i in range(12):
        start, end = cusps[i], cusps[(i + 1) % 12]
        inside = start <= lon < end if start < end else (lon >= start or lon < end)
        if inside:
            return i + 1
    return 12


def moon_range(date: dt.date, tz: ZoneInfo, zodiac: str) -> dict:
    """Moon longitude at the first and last minute of the local day; used when the time is unknown."""
    first = dt.datetime.combine(date, dt.time(0, 0), tzinfo=tz)
    last = dt.datetime.combine(date, dt.time(23, 59), tzinfo=tz)
    return {"start": round(eph.body_positions(eph.julian_day(first), zodiac)["Moon"]["longitude"], 4),
            "end": round(eph.body_positions(eph.julian_day(last), zodiac)["Moon"]["longitude"], 4)}


def build_chart(name: str, date: dt.date, time: dt.time | None, timezone: str, location: dict, house_system: str,
                zodiac: str = "tropical", node: str = "true") -> dict:
    flags = []
    tz = ZoneInfo(timezone)
    moon = None
    if time is None:
        time = dt.time(12, 0)
        flags += ["time_unknown", "moon_uncertain"]
        moon = moon_range(date, tz, zodiac)
    local = dt.datetime.combine(date, time, tzinfo=tz)
    jd = eph.julian_day(local)
    positions = eph.body_positions(jd, zodiac, node)
    if "Chiron" not in positions:
        flags.append("chiron_unavailable")

    houses = angles = None
    if "time_unknown" not in flags:
        houses, house_flags = eph.houses(jd, location["latitude"], location["longitude"], house_system, zodiac)
        flags += house_flags
        angles = houses.pop("angles")

    bodies = {}
    for n in BODY_ORDER:
        if n not in positions:
            continue
        p = positions[n]
        sign, deg = sign_of(p["longitude"])
        bodies[n] = {
            "longitude": round(p["longitude"], 4), "sign": sign, "sign_degree": round(deg, 4),
            "formatted": format_degree(p["longitude"]), "speed": round(p["speed"], 4),
            "retrograde": p["speed"] < 0, "house": house_of(p["longitude"], houses["cusps"]) if houses else None,
            "latitude": round(p["latitude"], 4),
        }

    aspect_input = {n: {"longitude": b["longitude"], "speed": b["speed"]} for n, b in bodies.items()}
    if angles:
        aspect_input["Ascendant"] = {"longitude": angles["ascendant"]}
        aspect_input["MC"] = {"longitude": angles["mc"]}
    pairs = [(a, b) for i, a in enumerate(aspect_input) for b in list(aspect_input)[i + 1:]
             if not (a in ("Ascendant", "MC") and b in ("Ascendant", "MC"))]

    return {
        "schema_version": 1,
        "meta": {
            "name": name,
            "datetime_local": local.replace(tzinfo=None).isoformat(),
            "timezone": timezone,
            "datetime_utc": local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "utc_offset": local.isoformat()[-6:],
            "julian_day_ut": round(jd, 7),
            "time_unknown": "time_unknown" in flags,
            "moon_range": moon,
            "location": location,
            "zodiac": "sidereal_lahiri" if zodiac == "sidereal" else "tropical",
            "house_system": houses["system"] if houses else None,
            "node": node,
            "flags": flags,
            "source": {"library": "pyswisseph", "version": swe.version, "ephemeris_files": eph.ephemeris_files_present()},
        },
        "angles": {k: round(v, 4) for k, v in angles.items()} if angles else None,
        "houses": {"system": houses["system"], "cusps": [round(c, 4) for c in houses["cusps"]]} if houses else None,
        "bodies": bodies,
        "aspects": asp.find_aspects(aspect_input, pairs=pairs),
    }
```

**Step 4: Run tests** → 5 passed.

**Step 5: Commit**

```bash
git add natal-chart/scripts/chart.py natal-chart/tests/test_chart.py
git commit -m "Assemble chart.json from positions, houses, and aspects"
```

---

### Task 8: Aspect grid renderer

**Files:**
- Create: `natal-chart/scripts/grid.py`
- Test: `natal-chart/tests/test_grid.py`

The grid is a Markdown table: bodies down the left, bodies across the top (same order), each cell holds the aspect symbol and orb, e.g. `△ 2.3a` (a = applying, s = separating). Symbols: ☌ ⚹ □ △ ☍.

**Step 1: Write the failing test**

```python
import grid


def test_grid_cells_and_symbols():
    chart = {
        "bodies": {"Sun": {}, "Moon": {}, "Mars": {}},
        "angles": None,
        "aspects": [{"body1": "Sun", "body2": "Mars", "aspect": "Trine", "orb": 2.31, "applying": True}],
    }
    md = grid.render(chart)
    lines = md.splitlines()
    assert lines[0].startswith("| | Sun | Moon | Mars |")
    assert "| Sun |  |  | △ 2.3a |" in md
    assert "| Mars | △ 2.3a |  |  |" in md


def test_grid_includes_angles_when_known():
    chart = {"bodies": {"Sun": {}}, "angles": {"ascendant": 1, "mc": 2},
             "aspects": [{"body1": "Sun", "body2": "MC", "aspect": "Square", "orb": 0.5, "applying": None}]}
    md = grid.render(chart)
    assert "| MC |" in md.splitlines()[0]
    assert "□ 0.5" in md
```

**Step 2: Run to verify it fails** → `ModuleNotFoundError: No module named 'grid'`.

**Step 3: Implement**

```python
"""Markdown aspect grid from chart.json."""
SYMBOLS = {"Conjunction": "☌", "Sextile": "⚹", "Square": "□", "Trine": "△", "Quincunx": "⚻", "Opposition": "☍"}


def _cell(a: dict) -> str:
    suffix = {True: "a", False: "s", None: ""}[a["applying"]]
    return f"{SYMBOLS[a['aspect']]} {a['orb']:.1f}{suffix}"


def render(chart: dict) -> str:
    names = list(chart["bodies"])
    if chart.get("angles"):
        names += ["Ascendant", "MC"]
    lookup = {}
    for a in chart["aspects"]:
        lookup[(a["body1"], a["body2"])] = lookup[(a["body2"], a["body1"])] = _cell(a)
    lines = ["| | " + " | ".join(names) + " |", "|" + "---|" * (len(names) + 1)]
    for row in names:
        cells = [lookup.get((row, col), "") for col in names]
        lines.append(f"| {row} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
```

**Step 4: Run tests** → 2 passed.

**Step 5: Commit**

```bash
git add natal-chart/scripts/grid.py natal-chart/tests/test_grid.py
git commit -m "Render Markdown aspect grid"
```

---

### Task 9: `natal_chart.py` command line

**Files:**
- Create: `natal-chart/scripts/natal_chart.py`
- Test: `natal-chart/tests/test_cli.py`

Interface:

```
python natal_chart.py --name "Ada" --date 1990-06-15 [--time 14:30] \
    (--city "Paris, FR" | --geonameid 2988507 | --lat 48.85 --lon 2.35 [--tz Europe/Paris]) \
    [--houses placidus] [--zodiac tropical|sidereal] [--node true|mean] [--out chart.json] [--grid aspects.md]
```

With raw coordinates the timezone comes from `timezonefinder` unless `--tz` overrides it. Historic offsets then come from `zoneinfo`.

Exit codes: 0 success, 2 ambiguous city (candidates printed as a table on stdout), 1 any other error. The grid defaults to `<out stem>_aspects.md`.

**Step 1: Write the failing test**

```python
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "natal_chart.py"


def run(*args, cwd):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)


def test_cli_writes_chart_and_grid(tmp_path):
    r = run("--name", "T", "--date", "1990-06-15", "--time", "12:00",
            "--lat", "40.7143", "--lon", "-74.006", "--out", "c.json", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    c = json.loads((tmp_path / "c.json").read_text())
    assert c["bodies"]["Sun"]["sign"] == "Gemini"
    assert c["meta"]["timezone"] == "America/New_York"   # from timezonefinder
    assert (tmp_path / "c_aspects.md").exists()


def test_cli_ambiguous_city_exits_2(tmp_path):
    r = run("--name", "T", "--date", "1990-06-15", "--city", "Paris", cwd=tmp_path)
    assert r.returncode == 2
    assert "geonameid" in r.stdout and "2988507" in r.stdout


def test_cli_unknown_time_flag(tmp_path):
    r = run("--name", "T", "--date", "1990-06-15", "--geonameid", "5128581", "--out", "c.json", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "time_unknown" in json.loads((tmp_path / "c.json").read_text())["meta"]["flags"]
```

**Step 2: Run to verify it fails** → FileNotFoundError or non-zero return.

**Step 3: Implement**

```python
#!/usr/bin/env python3
"""
Cast a natal chart and write chart.json plus a Markdown aspect grid.

Usage:
    python natal_chart.py --name "Ada" --date 1990-06-15 --time 14:30 --city "London, GB"
    python natal_chart.py --name "Ada" --date 1990-06-15 --geonameid 2643743
    python natal_chart.py --name "Ada" --date 1990-06-15 --lat 51.5 --lon -0.13   # timezone from coordinates

Omit --time when the birth time is unknown: the chart is cast at noon with no houses.
Exit code 2 means the city was ambiguous; the candidates are printed. Re-run with --geonameid.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chart as ch          # noqa: E402
import grid                 # noqa: E402
import location as loc      # noqa: E402


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--date", required=True, type=dt.date.fromisoformat)
    p.add_argument("--time", type=dt.time.fromisoformat, help="HH:MM local; omit if unknown")
    p.add_argument("--city", help='e.g. "Paris, FR" or "Paris, TX"')
    p.add_argument("--geonameid", type=int)
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)
    p.add_argument("--tz", help="IANA timezone override for --lat/--lon (default: looked up from the coordinates)")
    p.add_argument("--houses", default="placidus", choices=["placidus", "koch", "equal", "porphyry", "whole_sign"])
    p.add_argument("--zodiac", default="tropical", choices=["tropical", "sidereal"])
    p.add_argument("--node", default="true", choices=["true", "mean"])
    p.add_argument("--out", type=Path, default=Path("chart.json"))
    p.add_argument("--grid", type=Path)
    return p.parse_args(argv)


def resolve_location(args):
    if args.lat is not None or args.lon is not None:
        if args.lat is None or args.lon is None:
            raise SystemExit("--lat and --lon must be given together")
        tz = args.tz
        if not tz:
            from timezonefinder import TimezoneFinder
            tz = TimezoneFinder().timezone_at(lat=args.lat, lng=args.lon)
            if not tz:
                raise SystemExit("No timezone found for those coordinates; pass --tz")
        return {"name": f"{args.lat:.4f}, {args.lon:.4f}", "latitude": args.lat, "longitude": args.lon, "geonameid": None}, tz
    table = loc.load_table()
    city = loc.lookup_id(args.geonameid, table) if args.geonameid else loc.lookup(args.city, table)
    return {"name": city.label, "latitude": city.latitude, "longitude": city.longitude, "geonameid": city.geonameid}, city.timezone


def main(argv=None) -> int:
    args = parse_args(argv)
    if not (args.city or args.geonameid or args.lat is not None):
        print("Give --city, --geonameid, or --lat/--lon/--tz", file=sys.stderr)
        return 1
    try:
        location, tz = resolve_location(args)
    except loc.AmbiguousLocation as exc:
        print(f"{len(exc.candidates)} places match {exc.query!r}. Re-run with --geonameid:\n")
        print("| geonameid | place | population | timezone |\n|---|---|---|---|")
        for c in exc.candidates[:10]:
            print(f"| {c.geonameid} | {c.label} | {c.population} | {c.timezone} |")
        return 2
    except loc.UnknownLocation as exc:
        print(exc, file=sys.stderr)
        return 1

    result = ch.build_chart(args.name, args.date, args.time, tz, location, args.houses, args.zodiac, args.node)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    grid_path = args.grid or args.out.with_name(args.out.stem + "_aspects.md")
    grid_path.write_text(grid.render(result), encoding="utf-8")
    print(f"Wrote {args.out} and {grid_path}")
    for flag in result["meta"]["flags"]:
        print(f"Note: {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run tests** → 3 passed. Run the whole folder: `python -m pytest natal-chart/tests -q` → all pass.

**Step 5: Commit**

```bash
git add natal-chart/scripts/natal_chart.py natal-chart/tests/test_cli.py
git commit -m "Add natal_chart command line"
```

---

### Task 10: Golden chart test and example output

**Files:**
- Create: `natal-chart/tests/test_golden.py`
- Create: `natal-chart/examples/chart.json`, `natal-chart/examples/chart_aspects.md`

Pick one published reference chart with a known birth time and positions you can cite (an Astrodienst "chart of the moment" screenshot you take yourself is acceptable; record the source in a comment). Bodies must agree to 0.1° and cusps to 0.5°, the tolerances the design sets.

**Step 1: Write the failing test** (fill in the values you looked up)

```python
import datetime as dt
import pytest
import chart as ch

# Source: <URL or publication>, accessed <date>. Tropical, Placidus, true node.
REFERENCE = {
    "Sun": 0.0, "Moon": 0.0, "Ascendant": 0.0, "MC": 0.0,   # replace with published degrees
    "cusps": [0.0] * 12,                                      # published Placidus cusps
}
BIRTH = dict(name="Reference", date=dt.date(1900, 1, 1), time=dt.time(0, 0),
             timezone="UTC", location={"name": "X", "latitude": 0.0, "longitude": 0.0, "geonameid": None}, house_system="placidus")


def test_golden_chart_matches_published_positions():
    c = ch.build_chart(**BIRTH)
    for body in ("Sun", "Moon"):
        assert c["bodies"][body]["longitude"] == pytest.approx(REFERENCE[body], abs=0.1)
    assert c["angles"]["ascendant"] == pytest.approx(REFERENCE["Ascendant"], abs=0.5)
    assert c["angles"]["mc"] == pytest.approx(REFERENCE["MC"], abs=0.5)
    for got, want in zip(c["houses"]["cusps"], REFERENCE["cusps"]):
        assert got == pytest.approx(want, abs=0.5)
```

**Step 2: Run, confirm it fails on the placeholder zeros.**

**Step 3: Replace the placeholders with the published values, run again** → 1 passed. If a value disagrees by more than the tolerance, check the timezone and DST for the birth date before suspecting the ephemeris.

**Step 4: Generate the example**

```bash
python natal-chart/scripts/natal_chart.py --name "Example" --date 1990-06-15 --time 12:00 --geonameid 5128581 --out natal-chart/examples/chart.json
```

**Step 5: Commit**

```bash
git add natal-chart/tests/test_golden.py natal-chart/examples
git commit -m "Add golden chart test and example output"
```

---

### Task 11: `natal-chart` SKILL.md and README

**Files:**
- Create: `natal-chart/SKILL.md`, `natal-chart/README.md`

Follow `astrology-ephemeris/SKILL.md` exactly in shape: front matter with `name` and a trigger-rich `description`, then sections "What this skill produces", "How to run" (install pyswisseph, run `fetch_ephemeris.py` once, run `natal_chart.py`), "Handling an ambiguous city" (exit code 2: show the table to the user, ask, re-run with `--geonameid`), "Unknown birth time" (explain the noon cast, no houses, caveat Moon aspects), "Presenting the chart" (render a positions table in conversation from `chart.json`, deliver the aspect grid, point to `chart-wheel` for the SVG), "Technical notes" (the table in design section 3), "Troubleshooting".

Description triggers to include: natal chart, birth chart, where was my Moon, rising sign, ascendant, houses, aspects in my chart, cast a chart, "born on".

README mirrors `astrology-ephemeris/README.md`: what it produces, example output, install, run directly, how it works, why it exists (foundation for the other chart skills).

**Verify:** `grep -c "" natal-chart/SKILL.md` > 60; front matter parses (first line `---`, has `name: natal-chart`).

**Commit:** `git commit -m "Document natal-chart skill"`

---

### Task 12: `chart-wheel` geometry helpers

**Files:**
- Create: `chart-wheel/scripts/wheel_geometry.py`, `chart-wheel/tests/conftest.py` (same as Task 1)
- Test: `chart-wheel/tests/test_geometry.py`

Convention: Ascendant at 9 o'clock, zodiac runs counter-clockwise. With Ascendant longitude A, a point at longitude L sits at screen angle `theta = 180 + (L - A)` degrees measured counter-clockwise from 3 o'clock (so longitudes just past the Ascendant fall below the horizon, where house 1 belongs); in SVG coordinates (y down) that is `x = cx + r*cos(theta)`, `y = cy - r*sin(theta)`.

**Step 1: Write the failing test**

```python
import math
import pytest
import wheel_geometry as g


def test_ascendant_sits_at_left():
    x, y = g.point(asc=100.0, lon=100.0, cx=0, cy=0, r=10)
    assert (x, y) == (pytest.approx(-10), pytest.approx(0))


def test_descendant_sits_at_right_and_mc_above_when_square():
    x, y = g.point(asc=100.0, lon=280.0, cx=0, cy=0, r=10)
    assert (x, y) == (pytest.approx(10), pytest.approx(0))
    x, y = g.point(asc=100.0, lon=10.0, cx=0, cy=0, r=10)   # 90 degrees before the ascendant: top of the wheel
    assert (x, y) == (pytest.approx(0), pytest.approx(-10))


def test_spread_labels_pushes_apart_close_longitudes():
    out = g.spread([10.0, 10.5, 11.0, 200.0], min_gap=4.0)
    assert out[3] == pytest.approx(200.0)
    gaps = [out[i + 1] - out[i] for i in range(2)]
    assert all(gap >= 4.0 - 1e-9 for gap in gaps)
    assert out[1] == pytest.approx(10.5)   # middle one stays, outer two move
```

**Step 2: Run to verify it fails** → `ModuleNotFoundError`.

**Step 3: Implement**

```python
"""Pure geometry for the wheel. No SVG here."""
import math


def point(asc: float, lon: float, cx: float, cy: float, r: float) -> tuple[float, float]:
    theta = math.radians(180.0 + (lon - asc))
    return cx + r * math.cos(theta), cy - r * math.sin(theta)


def spread(longitudes: list[float], min_gap: float) -> list[float]:
    """Nudge display longitudes apart so glyphs do not overlap. Order is preserved; clusters stay centred."""
    order = sorted(range(len(longitudes)), key=lambda i: longitudes[i])
    vals = [longitudes[i] for i in order]
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] - vals[j] < min_gap:
            j += 1
        if j > i:
            centre = sum(longitudes[order[k]] for k in range(i, j + 1)) / (j - i + 1)
            start = centre - min_gap * (j - i) / 2
            for k in range(i, j + 1):
                vals[k] = start + min_gap * (k - i)
        i = j + 1
    out = [0.0] * len(longitudes)
    for pos, idx in enumerate(order):
        out[idx] = vals[pos]
    return out
```

**Step 4: Run tests** → 3 passed.

**Step 5: Commit** `git commit -m "Add chart-wheel geometry helpers"`

---

### Task 13: `chart-wheel` SVG renderer and command line

**Files:**
- Create: `chart-wheel/scripts/chart_wheel.py`
- Test: `chart-wheel/tests/test_wheel.py`

Rendering spec (all in one 800×800 SVG, `viewBox="0 0 800 800"`, centre 400,400):

| Ring | Radius | Content |
|---|---|---|
| Outer sign ring | 380 to 340 | 12 sectors, alternating light fills, sign glyph (♈♉♊♋♌♍♎♏♐♑♒♓) at sector centre |
| House ring | 340 to 300 | cusp lines from r=300 to 380; ASC and MC lines bolder, extended to 390; house numbers at the cusp midpoints at r=320 |
| Planet ring | glyph at r=270, degree label at r=240, tick at r=300 | glyphs ☉ ☽ ☿ ♀ ♂ ♃ ♄ ♅ ♆ ♇ ⚷ ☊, label like `24°07'`, ℞ appended when retrograde |
| Aspect wheel | lines between points at r=210 | stroke colour: Conjunction none (skip), Opposition and Square `#c0392b`, Trine and Sextile `#2e86c1`, Quincunx `#7f8c8d`; opacity 0.8, width 1.5; applying aspects solid, separating dashed |
| Caption | text at (400, 40) and (400, 770) | name and local datetime on top; location, house system, and any flags at the bottom |

Unknown time: skip the house ring and the ASC/MC lines, use `asc = 0.0` so 0° Aries sits at the left, and put "Birth time unknown: houses not shown, Moon approximate" in the bottom caption.

**Step 1: Write the failing test**

```python
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "chart_wheel.py"
EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"


def test_renders_well_formed_svg(tmp_path):
    out = tmp_path / "wheel.svg"
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), str(EXAMPLE), "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    root = ET.parse(out).getroot()
    assert root.tag.endswith("svg")
    text = out.read_text(encoding="utf-8")
    assert "☉" in text and "♈" in text
    assert text.count("<line") >= 12            # at least the cusps


def test_unknown_time_has_no_house_numbers(tmp_path):
    chart = json.loads(EXAMPLE.read_text())
    chart["angles"] = chart["houses"] = None
    chart["meta"]["time_unknown"] = True
    chart["meta"]["flags"] = ["time_unknown", "moon_uncertain"]
    for b in chart["bodies"].values():
        b["house"] = None
    src = tmp_path / "c.json"
    src.write_text(json.dumps(chart))
    out = tmp_path / "wheel.svg"
    subprocess.run([sys.executable, "-I", str(SCRIPT), str(src), "--out", str(out)], check=True)
    text = out.read_text(encoding="utf-8")
    assert "Birth time unknown" in text
    assert 'class="house-number"' not in text
```

**Step 2: Run to verify it fails.**

**Step 3: Implement** `chart_wheel.py` as a standard-library script. Structure it as: `svg_header()`, `sign_ring(asc)`, `house_ring(chart, asc)`, `planet_ring(chart, asc)` (uses `wheel_geometry.spread` with `min_gap=6.0` on display longitudes, keeps ticks at the true longitude), `aspect_lines(chart, asc)`, `captions(chart)`, and `render(chart) -> str` that concatenates them. Give every house number `class="house-number"` and every planet glyph `class="planet"`. Use `xml.sax.saxutils.escape` on all text from the chart. The CLI takes the chart path and `--out` (default `wheel.svg`). Add `sys.path.insert(0, str(Path(__file__).resolve().parent))` before `import wheel_geometry`.

**Step 4: Run tests** → 2 passed. Open the SVG in a browser and check by eye: Ascendant on the left, houses numbered counter-clockwise, no overlapping glyphs in the example chart, aspect lines visible.

**Step 5: Commit** `git commit -m "Render chart wheel SVG from chart.json"`

---

### Task 14: `chart-wheel` docs and example

**Files:**
- Create: `chart-wheel/SKILL.md`, `chart-wheel/README.md`, `chart-wheel/examples/wheel.svg`

SKILL.md: triggers (chart wheel, draw my chart, birth chart image, SVG of the chart, show the chart); the single step "run `chart_wheel.py <chart.json>` and deliver the SVG"; what to tell the user if no `chart.json` exists (run `natal-chart` first). Generate the example from `natal-chart/examples/chart.json`. README embeds the example with `![wheel](examples/wheel.svg)`.

**Commit:** `git commit -m "Document chart-wheel skill with example"`

---

### Task 15: `transits-to-natal` engine

**Files:**
- Create: `transits-to-natal/scripts/transits.py`, `transits-to-natal/tests/conftest.py` (same as Task 1)
- Test: `transits-to-natal/tests/test_transits.py`

Copy `separation` and the `ASPECTS` dict from `natal-chart/scripts/aspects.py` into this script (no import across folders). Orb is a flat 1°. Per day: noon in `meta.timezone`, positions of the chosen transiting bodies via pyswisseph with the same `set_ephe_path` convention (its own `ephe/` folder, falling back to a sibling `natal-chart/ephe/` if present), compared against every natal body longitude and, unless `time_unknown`, the four angles. Applying is decided from the transiting body's speed alone (natal points are fixed).

**Step 1: Write the failing test**

```python
import datetime as dt
import pytest
import transits as tr


def test_default_bodies_are_slow():
    assert tr.DEFAULT_BODIES == ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Chiron", "Node"]


def test_targets_include_angles_only_when_time_known():
    chart = {"meta": {"time_unknown": False}, "bodies": {"Sun": {"longitude": 10.0}},
             "angles": {"ascendant": 50.0, "mc": 320.0, "descendant": 230.0, "ic": 140.0}}
    assert tr.natal_targets(chart) == {"Sun": 10.0, "Ascendant": 50.0, "MC": 320.0, "Descendant": 230.0, "IC": 140.0}
    chart["meta"]["time_unknown"] = True
    assert tr.natal_targets(chart) == {"Sun": 10.0}


def test_hits_for_one_day_against_known_sky():
    # Mars sextile Pluto was exact to 0.002 at noon Pacific on 2026-04-16 (astrology-ephemeris example row 30).
    # Treat natal Pluto as a fixed point at the transiting Pluto longitude of that moment and look for Mars.
    chart = {"meta": {"time_unknown": True, "timezone": "America/Los_Angeles"}, "bodies": {}, "angles": None}
    sky = tr.sky_at(dt.date(2026, 4, 16), "America/Los_Angeles", ["Mars", "Pluto"])
    chart["bodies"]["Pluto"] = {"longitude": sky["Pluto"]["longitude"]}
    hits = tr.hits_for_day(dt.date(2026, 4, 16), chart, ["Mars"])
    assert any(h["transit"] == "Mars" and h["aspect"] == "Sextile" and h["natal"] == "Pluto" and h["orb"] <= 0.01 for h in hits)


def test_applying_from_transit_speed_only():
    assert tr.is_applying(lon_t=118.0, speed_t=0.5, lon_n=0.0, angle=120) is True
    assert tr.is_applying(lon_t=122.0, speed_t=0.5, lon_n=0.0, angle=120) is False
```

**Step 2: Run to verify it fails.**

**Step 3: Implement** `transits.py` with: `DEFAULT_BODIES`, `FAST_BODIES = ["Sun", "Mercury", "Venus", "Mars"]`, `natal_targets(chart)`, `sky_at(date, tz, names) -> {name: {longitude, speed}}`, `is_applying(lon_t, speed_t, lon_n, angle)` (the analytic signed form of `aspects.applying()` with the natal speed at 0: `delta = ((lon_t - lon_n + 180) % 360) - 180`, `target = angle if delta >= 0 else -angle`, applying is `(delta - target) * speed_t < 0`, `None` when `abs(speed_t) < 1e-9`; do not use a finite one-hour step, it was found wrong in review), `hits_for_day(date, chart, names) -> list[dict]` with keys date, utc_offset, transit, aspect, natal, orb, applying, retrograde, `scan(chart, start, end, names)` that yields rows across the range, and `write_csv(rows, path)` with header `Date,Time,UTC Offset,Transit,Aspect,Natal,Orb (°),Applying,Retrograde` and no comment lines (so `csv.DictReader` and `pandas.read_csv` parse it directly). Time is always `12:00`; UTC Offset is that day's noon offset in `meta.timezone` (`-04:00` form), computed per row so a range crossing a DST change is labelled correctly on every row. Chiron is omitted silently from the transiting set when its file is missing. Use the 1° orb for every aspect in the ASPECTS dict, quincunx included. CLI:

```
python transits.py chart.json --start 2026-01-01 --end 2026-12-31 [--fast] [--moon] [--out transits.csv]
```

Default `--out` is `transits_<start>_<end>.csv`. Chiron is skipped with a stderr note if the ephemeris file is absent.

**Step 4: Run tests** → 4 passed. Then a real run on the example chart for one month and eyeball the CSV: Pluto and Neptune rows should persist for many consecutive days, Jupiter rows for a week or two.

**Step 5: Commit** `git commit -m "Add transits-to-natal daily snapshot scan"`

---

### Task 16: `transits-to-natal` docs and example

**Files:**
- Create: `transits-to-natal/SKILL.md`, `transits-to-natal/README.md`, `transits-to-natal/examples/transits_2026-04-01_2026-04-30.csv`

SKILL.md triggers: transits, what is hitting my chart, transit report, Saturn transit to my Sun, upcoming transits, "this year for me". Document the slow-body default and the two flags, the noon snapshot rule (same as the ephemeris skill), and that the Moon is off by default because at one sample a day it is noise. Generate the example from `natal-chart/examples/chart.json` for April 2026. Add `transits_*.csv` with an examples exception to `.gitignore`, as done for `aspects_*.csv`.

**Commit:** `git commit -m "Document transits-to-natal skill with example"`

---

### Task 17: `synastry` engine

**Files:**
- Create: `synastry/scripts/synastry.py`, `synastry/tests/conftest.py` (same as Task 1)
- Test: `synastry/tests/test_synastry.py`

Copy `ASPECTS`, `ORBS`, `LUMINARY_BONUS`, `max_orb`, `separation`, and `house_of` into this script. Synastry orbs use `reduction=2.0`. Inter-aspects pair every body (and angle when known) of A against every body (and angle when known) of B; `applying` is `null` throughout, since the two charts do not move relative to each other. House overlays: for each body of A, the house it falls in by B's cusps (only if B has houses), and the reverse.

**Step 1: Write the failing test**

```python
import json
import synastry as sy


def chart(bodies, cusps=None, angles=None, flags=()):
    return {"schema_version": 1,
            "meta": {"name": "X", "time_unknown": cusps is None, "flags": list(flags)},
            "bodies": {n: {"longitude": lon} for n, lon in bodies.items()},
            "houses": {"system": "placidus", "cusps": cusps} if cusps else None,
            "angles": angles}


CUSPS = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]


def test_inter_aspects_use_reduced_orbs():
    a = chart({"Mars": 10.0}); b = chart({"Venus": 15.5})
    result = sy.compare(a, b)
    assert result["inter_aspects"] == []          # 5.5 > conjunction 8 - 2
    b = chart({"Venus": 15.0})
    hits = sy.compare(a, b)["inter_aspects"]
    assert hits[0]["aspect"] == "Conjunction" and hits[0]["max_orb"] == 6.0 and hits[0]["applying"] is None


def test_overlays_only_where_host_has_houses():
    a = chart({"Sun": 45.0}, cusps=CUSPS, angles={"ascendant": 0.0, "mc": 270.0})
    b = chart({"Moon": 100.0})
    result = sy.compare(a, b)
    assert result["overlays"]["b_in_a_houses"] == {"Moon": 4}
    assert result["overlays"]["a_in_b_houses"] is None
    assert "b_time_unknown" in result["flags"]


def test_moon_aspects_flagged_uncertain_for_untimed_partner():
    a = chart({"Sun": 45.0}, cusps=CUSPS, angles={"ascendant": 0.0, "mc": 270.0})
    b = chart({"Moon": 45.0, "Mars": 135.0})
    hits = {(h["a"], h["b"]): h for h in sy.compare(a, b)["inter_aspects"]}
    assert hits[("Sun", "Moon")]["uncertain"] is True
    assert hits[("Sun", "Mars")]["uncertain"] is False


def test_angles_only_from_timed_chart():
    a = chart({"Sun": 45.0}, cusps=CUSPS, angles={"ascendant": 44.0, "mc": 270.0})
    b = chart({"Moon": 224.0})
    hits = sy.compare(a, b)["inter_aspects"]
    assert any(h["a"] == "Ascendant" and h["b"] == "Moon" and h["aspect"] == "Opposition" for h in hits)


def test_grid_has_a_down_and_b_across():
    a = chart({"Sun": 0.0, "Moon": 90.0}); b = chart({"Mars": 120.0})
    md = sy.render_grid(sy.compare(a, b), a, b)
    assert md.splitlines()[0] == "| A \\ B | Mars |"
    assert "| Sun | △ 0.0 |" in md
```

**Step 2: Run to verify it fails.**

**Step 3: Implement** `compare(a, b) -> dict` returning `{"schema_version": 1, "a": a["meta"]["name"], "b": b["meta"]["name"], "flags": [...], "inter_aspects": [{"a": ..., "b": ..., "aspect", "angle", "orb", "max_orb", "applying": None}], "overlays": {"a_in_b_houses": {...}|None, "b_in_a_houses": {...}|None}}`, with flags `a_time_unknown`/`b_time_unknown` added when the respective chart carries `time_unknown`. Each inter-aspect carries `uncertain: true` when it involves the Moon of an untimed chart, false otherwise. `render_grid(result, a, b)` matches Task 8's format with header `| A \ B | ... |` and no applying suffix; cells for `uncertain` aspects end in `?`.

**Step 4: Run tests** → 5 passed.

**Step 5: Commit** `git commit -m "Add synastry inter-aspects and house overlays"`

---

### Task 18: `synastry` command line with raw birth data delegation

**Files:**
- Modify: `synastry/scripts/synastry.py` (add CLI)
- Test: `synastry/tests/test_cli.py`

Interface:

```
python synastry.py --a chartA.json --b chartB.json [--out synastry.json] [--grid synastry.md]
python synastry.py --a-birth '--name Ada --date 1990-06-15 --time 14:30 --geonameid 2643743' \
                   --b-birth '--name Bob --date 1988-02-02 --geonameid 5128581'
```

`--a-birth`/`--b-birth` are shell-style strings handed verbatim (via `shlex.split`) to the sibling natal script, found as `Path(__file__).resolve().parents[2] / "natal-chart" / "scripts" / "natal_chart.py"`, then `~/.claude/skills/natal-chart/scripts/natal_chart.py`, then `.claude/skills/natal-chart/scripts/natal_chart.py` under the current directory. If none exists, exit 1 with "synastry needs the natal-chart skill installed beside it to accept raw birth data; pass chart files instead". The natal script's exit code 2 (ambiguous city) is passed through along with its stdout. Each delegated chart is written to a temp directory and then loaded.

**Step 1: Write the failing test**

```python
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "synastry.py"
EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"


def run(*args, cwd):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)


def test_from_files(tmp_path):
    r = run("--a", str(EXAMPLE), "--b", str(EXAMPLE), "--out", "s.json", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    s = json.loads((tmp_path / "s.json").read_text())
    assert any(h["a"] == "Sun" and h["b"] == "Sun" and h["aspect"] == "Conjunction" for h in s["inter_aspects"])
    assert (tmp_path / "s.md").exists()


def test_round_trip_files_equal_raw(tmp_path):
    birth = "--name Example --date 1990-06-15 --time 12:00 --geonameid 5128581"
    r1 = run("--a", str(EXAMPLE), "--b", str(EXAMPLE), "--out", "files.json", cwd=tmp_path)
    r2 = run("--a-birth", birth, "--b-birth", birth, "--out", "raw.json", cwd=tmp_path)
    assert r1.returncode == 0 and r2.returncode == 0, r1.stderr + r2.stderr
    assert json.loads((tmp_path / "files.json").read_text()) == json.loads((tmp_path / "raw.json").read_text())


def test_ambiguous_city_passes_through_exit_2(tmp_path):
    r = run("--a-birth", "--name A --date 1990-06-15 --city Paris", "--b", str(EXAMPLE), cwd=tmp_path)
    assert r.returncode == 2
    assert "geonameid" in r.stdout
```

**Step 2: Run to verify it fails.**

**Step 3: Implement** the CLI per the interface above. Note the round-trip test depends on `natal-chart/examples/chart.json` having been generated with exactly the birth string in the test (Task 10 step 4); keep them in sync.

**Step 4: Run tests** → 3 passed.

**Step 5: Commit** `git commit -m "Add synastry command line with natal delegation"`

---

### Task 19: `synastry` docs and example

**Files:**
- Create: `synastry/SKILL.md`, `synastry/README.md`, `synastry/examples/synastry.json`, `synastry/examples/synastry.md`

SKILL.md triggers: synastry, compatibility, relationship chart, compare our charts, how do our charts interact, his Mars on my Venus. Steps: if the user gives two chart files, run with `--a/--b`; if raw birth data, run with `--a-birth/--b-birth` and handle exit 2 as `natal-chart` does; present the grid and a short reading of overlays. Document the one-unknown-time behaviour. For the example, generate a second chart with different birth data (any date you like, documented in the README) so the example is not a chart against itself.

**Commit:** `git commit -m "Document synastry skill with example"`

---

### Task 20: Portfolio README and final verification

**Files:**
- Modify: `README.md`

**Step 1:** Add four rows to the Skills table (same style as the existing row) and a sentence after the install block: "The chart skills need the Swiss Ephemeris data files once; run `python natal-chart/scripts/fetch_ephemeris.py` after copying." Update the licensing paragraph to mention the GeoNames table (CC BY 4.0, https://www.geonames.org) alongside pyswisseph, and put the same attribution in `natal-chart/README.md`.

**Step 2: Run every test folder**

```bash
for d in natal-chart chart-wheel transits-to-natal synastry; do python -m pytest $d/tests -q || exit 1; done
```

Expected: all pass. Then rename `natal-chart/ephe` away and re-run `natal-chart/tests` to prove the `chiron_unavailable` path, then restore it.

**Step 3: Fresh-install smoke test**

```bash
rm -rf /tmp/skills && mkdir /tmp/skills && for d in natal-chart chart-wheel transits-to-natal synastry; do cp -r $d /tmp/skills/; done
cd /tmp/skills && python natal-chart/scripts/fetch_ephemeris.py \
  && python natal-chart/scripts/natal_chart.py --name Smoke --date 1990-06-15 --time 12:00 --geonameid 5128581 --out /tmp/smoke.json \
  && python chart-wheel/scripts/chart_wheel.py /tmp/smoke.json --out /tmp/smoke.svg \
  && python transits-to-natal/scripts/transits.py /tmp/smoke.json --start 2026-01-01 --end 2026-01-31 --out /tmp/smoke.csv \
  && python synastry/scripts/synastry.py --a /tmp/smoke.json --b /tmp/smoke.json --out /tmp/smoke_syn.json && echo OK
```

Expected: `OK`. This proves the folders are copyable on their own.

**Step 4: Commit**

```bash
git add README.md .gitignore
git commit -m "Add chart skills to portfolio README"
```

---

## Out of scope for this plan

Composite and Davison charts, returns, progressions, the sky-calendar skills (lunar phases, void-of-course Moon, ingresses, stations, eclipses), Sabian and fixed-star lookups, interpretation scaffolds, Lilith and asteroid flags, and any shared package. If a task seems to need one of these, stop and raise it rather than adding it.
