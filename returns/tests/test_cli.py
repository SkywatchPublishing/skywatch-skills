import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "returns.py"
EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"


def run(*args, cwd):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)


def test_solar_return_cast_at_natal_place_when_no_place_given(tmp_path):
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-12-31", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    files = sorted(tmp_path.glob("sun_return_*.json"))
    assert [f.name for f in files] == ["sun_return_2027-06-15.json"]
    c = json.loads(files[0].read_text())
    assert c["meta"]["chart_type"] == "solar_return"
    assert c["meta"]["derived_from"] == ["Example"]
    assert "return_place_natal" in c["meta"]["flags"]
    assert c["meta"]["location"]["geonameid"] == 5128581
    assert abs(c["bodies"]["Sun"]["longitude"] - json.loads(EXAMPLE.read_text())["bodies"]["Sun"]["longitude"]) < 0.001
    assert (tmp_path / "returns_summary.md").exists()
    assert "2027-06-15" in (tmp_path / "returns_summary.md").read_text()


def test_lunar_returns_relocated(tmp_path):
    r = run(str(EXAMPLE), "--body", "moon", "--start", "2027-01-01", "--end", "2027-02-28",
            "--lat", "30.2672", "--lon", "-97.7431", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    files = sorted(tmp_path.glob("moon_return_*.json"))
    assert len(files) == 2
    c = json.loads(files[0].read_text())
    assert c["meta"]["chart_type"] == "lunar_return"
    assert c["meta"]["timezone"] == "America/Chicago"
    assert "return_place_natal" not in c["meta"]["flags"]


def test_ambiguous_city_exits_2(tmp_path):
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-12-31", "--city", "Paris", cwd=tmp_path)
    assert r.returncode == 2 and "geonameid" in r.stdout


def test_untimed_chart_is_refused_for_angles_but_cast(tmp_path):
    chart = json.loads(EXAMPLE.read_text())
    chart["meta"]["time_unknown"] = True
    p = tmp_path / "u.json"; p.write_text(json.dumps(chart))
    r = run(str(p), "--start", "2027-01-01", "--end", "2027-12-31", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "natal_time_unknown" in json.loads(next(tmp_path.glob("sun_return_*.json")).read_text())["meta"]["flags"]
