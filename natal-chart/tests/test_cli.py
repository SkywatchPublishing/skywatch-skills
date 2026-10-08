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
