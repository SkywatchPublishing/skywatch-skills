import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import progressions as pg  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
NATAL_SCRIPT = ROOT / "natal-chart" / "scripts" / "natal_chart.py"
EXAMPLE = ROOT / "natal-chart" / "examples" / "chart.json"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "needs_ephemeris: needs the Swiss Ephemeris files (Chiron, or figures computed with them)")


def pytest_runtest_setup(item):
    if item.get_closest_marker("needs_ephemeris") and not pg.ephemeris_files_present():
        pytest.skip("needs the Swiss Ephemeris files, in progressions/ephe or natal-chart/ephe; "
                    "run python natal-chart/scripts/fetch_ephemeris.py")


@pytest.fixture(scope="session")
def rows():
    """The example chart's 2027-2036 timeline (the README example's range), computed once for the session.
    Shared by test_timeline.py and test_cli.py; treat the rows as read-only."""
    return pg.timeline(json.loads(EXAMPLE.read_text()), dt.date(2027, 1, 1), dt.date(2036, 12, 31))


@pytest.fixture(scope="session")
def cast(tmp_path_factory):
    """cast(*natal_chart.py args) -> chart dict, cast once per distinct argument list."""
    if not NATAL_SCRIPT.exists():
        pytest.skip(f"natal-chart is not installed beside progressions ({NATAL_SCRIPT} is missing)")
    cache, folder = {}, tmp_path_factory.mktemp("natal")

    def run(*args):
        if args not in cache:
            out = folder / f"chart{len(cache)}.json"
            subprocess.run([sys.executable, "-I", str(NATAL_SCRIPT), "--name", "T", *args, "--out", str(out)],
                           check=True, capture_output=True)
            cache[args] = out.read_text(encoding="utf-8")
        return json.loads(cache[args])
    return run


@pytest.fixture
def no_ephemeris(tmp_path_factory, monkeypatch):
    """Point progressions at an empty folder, as on a machine without the Swiss Ephemeris files: pyswisseph
    falls back to its built-in Moshier ephemeris, which has no Chiron."""
    import swisseph as swe
    empty, original = tmp_path_factory.mktemp("no_ephe"), pg.EPHE_DIR
    monkeypatch.setattr(pg, "EPHE_DIR", empty)
    swe.set_ephe_path(str(empty))
    yield empty
    swe.set_ephe_path(str(original))
