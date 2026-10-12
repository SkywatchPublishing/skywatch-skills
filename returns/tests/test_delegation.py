"""How returns launches natal_chart.py: -P keeps user site-packages, -I would hide them."""
import json
import sys

import returns as rt

# Stands in for natal_chart.py: records how it was launched in a minimal chart at --out.
STAND_IN = """\
import json, sys
out = sys.argv[max(i for i, a in enumerate(sys.argv) if a == "--out") + 1]
launch = {"argv": sys.orig_argv, "no_user_site": sys.flags.no_user_site, "safe_path": sys.flags.safe_path}
chart = {"schema_version": 1, "meta": {"name": "stand-in", "launch": launch}, "bodies": {"Sun": {"longitude": 0.0}}}
open(out, "w", encoding="utf-8").write(json.dumps(chart))
"""


def test_run_natal_launches_natal_chart_with_user_site_enabled(tmp_path):
    stand_in = tmp_path / "natal_chart.py"
    stand_in.write_text(STAND_IN)
    out = tmp_path / "probe.json"
    rt._run_natal(stand_in, ["--name", "A", "--date", "1990-06-15", "--out", str(out)])
    launch = json.loads(out.read_text())["meta"]["launch"]
    assert launch["argv"][:3] == [sys.executable, "-P", str(stand_in)]
    assert launch["no_user_site"] == 0      # pyswisseph from `pip install --user` stays importable
    assert launch["safe_path"] is True      # still no cwd or script dir prepended to sys.path
