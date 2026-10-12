"""How synastry launches natal_chart.py: -P keeps user site-packages, -I would hide them."""
import json
import os
import subprocess
import sys
from pathlib import Path

import synastry as sy

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "synastry.py"
EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"

# Stands in for natal_chart.py: records how it was launched in a minimal chart at --out.
STAND_IN = """\
import json, sys
out = sys.argv[max(i for i, a in enumerate(sys.argv) if a == "--out") + 1]
launch = {"argv": sys.orig_argv, "no_user_site": sys.flags.no_user_site, "safe_path": sys.flags.safe_path}
chart = {"schema_version": 1, "meta": {"name": "stand-in", "launch": launch}, "bodies": {"Sun": {"longitude": 0.0}}}
open(out, "w", encoding="utf-8").write(json.dumps(chart))
"""


def test_cast_chart_launches_natal_chart_with_user_site_enabled(tmp_path):
    stand_in = tmp_path / "natal_chart.py"
    stand_in.write_text(STAND_IN)
    launch = sy.cast_chart(stand_in, "--name A --date 1990-06-15", tmp_path / "a.json")["meta"]["launch"]
    assert launch["argv"][:3] == [sys.executable, "-P", str(stand_in)]
    assert launch["no_user_site"] == 0      # pyswisseph from `pip install --user` stays importable
    assert launch["safe_path"] is True      # still no cwd or script dir prepended to sys.path


def test_raw_birth_unchanged_with_user_site_enabled(tmp_path):
    # User site-packages switched on (an empty one): raw-birth casts still match the chart files.
    userbase = tmp_path / "userbase"
    userbase.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "PYTHONNOUSERSITE"}
    env["PYTHONUSERBASE"] = str(userbase)
    birth = "--name Example --date 1990-06-15 --time 12:00 --geonameid 5128581"
    files = subprocess.run([sys.executable, "-I", str(SCRIPT), "--a", str(EXAMPLE), "--b", str(EXAMPLE),
                            "--out", "files.json"], cwd=tmp_path, capture_output=True, text=True)
    raw = subprocess.run([sys.executable, "-I", str(SCRIPT), "--a-birth", birth, "--b-birth", birth,
                          "--out", "raw.json"], cwd=tmp_path, capture_output=True, text=True, env=env)
    assert files.returncode == 0 and raw.returncode == 0, files.stderr + raw.stderr
    f, r = (json.loads((tmp_path / n).read_text()) for n in ("files.json", "raw.json"))
    f.pop("config"); r.pop("config")
    assert f == r
