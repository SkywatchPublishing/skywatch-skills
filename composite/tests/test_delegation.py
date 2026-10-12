"""How composite launches natal_chart.py: -P keeps user site-packages, -I would hide them."""
import argparse
import json
import sys
from pathlib import Path

import composite as cp

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"
PARTNER = Path(__file__).resolve().parents[2] / "synastry" / "examples" / "chart_b.json"

# Stands in for natal_chart.py: records how it was launched in a minimal chart at --out.
STAND_IN = """\
import json, sys
out = sys.argv[max(i for i, a in enumerate(sys.argv) if a == "--out") + 1]
launch = {"argv": sys.orig_argv, "no_user_site": sys.flags.no_user_site, "safe_path": sys.flags.safe_path}
chart = {"schema_version": 1, "meta": {"name": "stand-in", "location": {"launch": launch}, "launch": launch},
         "bodies": {"Sun": {"longitude": 0.0}}}
open(out, "w", encoding="utf-8").write(json.dumps(chart))
"""


def _stand_in(tmp_path: Path) -> Path:
    path = tmp_path / "natal_chart.py"
    path.write_text(STAND_IN)
    return path


def _assert_launched_with_user_site(launch: dict, stand_in: Path) -> None:
    assert launch["argv"][:3] == [sys.executable, "-P", str(stand_in)]
    assert launch["no_user_site"] == 0      # pyswisseph from `pip install --user` stays importable
    assert launch["safe_path"] is True      # still no cwd or script dir prepended to sys.path


def test_cast_chart_launches_natal_chart_with_user_site_enabled(tmp_path):
    stand_in = _stand_in(tmp_path)
    chart = cp.cast_chart(stand_in, "--name A --date 1990-06-15", tmp_path / "a.json", "a")
    _assert_launched_with_user_site(chart["meta"]["launch"], stand_in)


def test_cast_davison_launches_natal_chart_with_user_site_enabled(tmp_path):
    stand_in = _stand_in(tmp_path)
    a, b = json.loads(EXAMPLE.read_text()), json.loads(PARTNER.read_text())
    chart = cp.cast_davison(stand_in, a, b, tmp_path / "davison.json")
    _assert_launched_with_user_site(chart["meta"]["launch"], stand_in)


def test_reference_probe_launches_natal_chart_with_user_site_enabled(tmp_path):
    stand_in = _stand_in(tmp_path)
    args = argparse.Namespace(lat=None, lon=None, city="Paris, FR", geonameid=None)
    location = cp.resolve_reference(args, json.loads(EXAMPLE.read_text()), stand_in, tmp_path)
    _assert_launched_with_user_site(location["launch"], stand_in)
