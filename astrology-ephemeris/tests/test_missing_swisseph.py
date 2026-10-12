"""A missing pyswisseph is reported, never installed.

The script runs in a child interpreter where `import swisseph` raises ImportError and every way
of starting a process is replaced by a recorder that refuses, so the test installs nothing and
touches no network even against a script that tries to.
"""
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compute_aspects.py"

WRAPPER = r"""
import os, runpy, subprocess, sys

def refuse(*args, **kwargs):
    print(f"INSTALL ATTEMPTED: {args!r}", file=sys.stderr)
    raise SystemExit(99)

sys.modules["swisseph"] = None              # `import swisseph` now raises ImportError
sys.modules["pip"] = sys.modules["ensurepip"] = None
subprocess.Popen = refuse                   # check_call, call, run and check_output all go through Popen
os.system = refuse
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def test_missing_swisseph_exits_1_with_install_hint_and_installs_nothing(tmp_path):
    env = {**os.environ, "PIP_NO_INDEX": "1"}  # a second guard: pip could not reach an index anyway
    r = subprocess.run([sys.executable, "-I", "-c", WRAPPER, str(SCRIPT), "4", "2026", "out.csv"],
                       cwd=tmp_path, env=env, capture_output=True, text=True)
    assert "INSTALL ATTEMPTED" not in r.stderr, r.stderr
    assert r.returncode == 1, r.stderr
    assert r.stdout == ""
    message = r.stderr.strip()
    assert "\n" not in message and "Traceback" not in message, message
    assert "pyswisseph" in message and "pip install pyswisseph" in message
    assert "SKILL.md" in message
    assert not (tmp_path / "out.csv").exists()
