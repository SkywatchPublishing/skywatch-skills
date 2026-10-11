import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "returns.py"
EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"
NATAL = Path(__file__).resolve().parents[2] / "natal-chart" / "scripts" / "natal_chart.py"


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


def test_untimed_chart_is_cast_with_flag(tmp_path):
    chart = json.loads(EXAMPLE.read_text())
    chart["meta"]["time_unknown"] = True
    p = tmp_path / "u.json"; p.write_text(json.dumps(chart))
    r = run(str(p), "--start", "2027-01-01", "--end", "2027-12-31", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "natal_time_unknown" in json.loads(next(tmp_path.glob("sun_return_*.json")).read_text())["meta"]["flags"]


def test_wrote_line_mentions_aspects_sidecar(tmp_path):
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-12-31", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "_aspects.md" in r.stdout and "Wrote 1" in r.stdout
    assert (tmp_path / "sun_return_2027-06-15_aspects.md").exists()


def test_empty_range_writes_zero_and_summary(tmp_path):
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-01-02", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Wrote 0" in r.stdout
    assert not list(tmp_path.glob("sun_return_*.json"))
    assert (tmp_path / "returns_summary.md").exists()


def test_geonameid_as_return_place(tmp_path):
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-12-31", "--geonameid", "4671654", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    c = json.loads(next(tmp_path.glob("sun_return_*.json")).read_text())
    assert c["meta"]["location"]["geonameid"] == 4671654
    assert c["meta"]["timezone"] == "America/Chicago"
    assert "return_place_natal" not in c["meta"]["flags"]


def test_city_with_geonameid_is_rejected(tmp_path):
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-12-31",
            "--city", "Austin, TX", "--geonameid", "4671654", cwd=tmp_path)
    assert r.returncode == 1
    assert "--city" in r.stderr and "--geonameid" in r.stderr
    assert not list(tmp_path.glob("sun_return_*.json"))


def test_rerun_uses_next_free_name_and_keeps_existing(tmp_path):
    seed = tmp_path / "sun_return_2027-06-15.json"
    seed.write_text("seed")
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-12-31", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert seed.read_text() == "seed"
    assert sorted(f.name for f in tmp_path.glob("sun_return_*.json")) == \
        ["sun_return_2027-06-15.json", "sun_return_2027-06-15_2.json"]
    assert "sun_return_2027-06-15_2.json" in r.stdout
    assert "sun_return_2027-06-15_2" in (tmp_path / "returns_summary.md").read_text()


def test_precessed_rejected_for_sidereal_chart(tmp_path):
    cast = subprocess.run([sys.executable, "-I", str(NATAL), "--name", "S", "--date", "1990-06-15", "--time", "12:00",
                           "--geonameid", "5128581", "--zodiac", "sidereal", "--out", "s.json"],
                          cwd=tmp_path, capture_output=True, text=True)
    assert cast.returncode == 0, cast.stderr
    assert json.loads((tmp_path / "s.json").read_text())["meta"]["zodiac"] == "sidereal_lahiri"
    r = run("s.json", "--start", "2027-01-01", "--end", "2027-12-31", "--precessed", cwd=tmp_path)
    assert r.returncode == 1
    assert "--precessed applies to tropical charts only; a sidereal chart's returns are already precession-free" in r.stderr
    assert not list(tmp_path.glob("sun_return_*.json"))
