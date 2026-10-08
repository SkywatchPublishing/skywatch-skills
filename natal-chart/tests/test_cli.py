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


def test_cli_bad_date_exits_1_not_2(tmp_path):
    r = run("--name", "T", "--date", "1990-13-45", "--geonameid", "5128581", cwd=tmp_path)
    assert r.returncode == 1
    assert "--date" in r.stderr


def test_cli_bad_time_exits_1(tmp_path):
    r = run("--name", "T", "--date", "1990-06-15", "--time", "25:99", "--geonameid", "5128581", cwd=tmp_path)
    assert r.returncode == 1


def test_cli_time_with_utc_offset_rejected(tmp_path):
    r = run("--name", "T", "--date", "1990-06-15", "--time", "12:00+02:00", "--geonameid", "5128581", cwd=tmp_path)
    assert r.returncode == 1
    assert "offset" in r.stderr


def test_cli_unknown_timezone_exits_1(tmp_path):
    r = run("--name", "T", "--date", "1990-06-15", "--lat", "40.7", "--lon", "-74.0", "--tz", "Mars/Olympus", cwd=tmp_path)
    assert r.returncode == 1
    assert "Mars/Olympus" in r.stderr


def test_cli_latitude_out_of_range_exits_1(tmp_path):
    r = run("--name", "T", "--date", "1990-06-15", "--lat", "95", "--lon", "0", "--tz", "UTC", cwd=tmp_path)
    assert r.returncode == 1
    assert "--lat" in r.stderr


def test_cli_longitude_out_of_range_exits_1(tmp_path):
    r = run("--name", "T", "--date", "1990-06-15", "--lat", "0", "--lon", "181", "--tz", "UTC", cwd=tmp_path)
    assert r.returncode == 1
    assert "--lon" in r.stderr
