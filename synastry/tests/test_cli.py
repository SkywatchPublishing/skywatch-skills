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
