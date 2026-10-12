import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

NATAL_SCRIPT = Path(__file__).resolve().parents[2] / "natal-chart" / "scripts" / "natal_chart.py"


@pytest.fixture(scope="session")
def cast(tmp_path_factory):
    """cast(*natal_chart.py args) -> chart dict, cast once per distinct argument list."""
    cache, folder = {}, tmp_path_factory.mktemp("natal")

    def run(*args):
        if args not in cache:
            out = folder / f"chart{len(cache)}.json"
            subprocess.run([sys.executable, "-I", str(NATAL_SCRIPT), "--name", "T", *args, "--out", str(out)],
                           check=True, capture_output=True)
            cache[args] = out.read_text(encoding="utf-8")
        return json.loads(cache[args])
    return run
