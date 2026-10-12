import json
import subprocess
import sys
from pathlib import Path

import pytest

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


COMPOSITE = Path(__file__).resolve().parents[2] / "composite" / "examples" / "composite.json"
WHEEL = Path(__file__).resolve().parents[2] / "chart-wheel" / "scripts" / "chart_wheel.py"
TRANSITS = Path(__file__).resolve().parents[2] / "transits-to-natal" / "scripts" / "transits.py"
SYNASTRY = Path(__file__).resolve().parents[2] / "synastry" / "scripts" / "synastry.py"


def test_midpoint_composite_is_refused_via_main(tmp_path, capsys, monkeypatch):
    import returns as rt
    monkeypatch.chdir(tmp_path)
    code = rt.main([str(COMPOSITE), "--start", "2027-01-01", "--end", "2027-12-31"])
    err = capsys.readouterr().err
    assert code == 1
    assert "returns: this chart has no real moment (chart_type composite); returns need a natal, return or Davison chart" in err
    assert not list(tmp_path.glob("*.json"))


def test_progressed_chart_is_refused(tmp_path, capsys):
    import returns as rt
    chart = json.loads(EXAMPLE.read_text())
    chart["meta"]["chart_type"] = "secondary_progressed"
    p = tmp_path / "p.json"
    p.write_text(json.dumps(chart))
    assert rt.main([str(p), "--start", "2027-01-01", "--end", "2027-12-31", "--out-dir", str(tmp_path)]) == 1
    assert "progressed or directed" in capsys.readouterr().err
    assert not list(tmp_path.glob("*_return_*.json"))


def test_summary_takes_next_free_name_and_keeps_existing(tmp_path):
    seed = tmp_path / "returns_summary.md"
    seed.write_text("seed")
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-12-31", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert seed.read_text() == "seed"
    assert (tmp_path / "returns_summary_2.md").exists()
    assert "2027-06-15" in (tmp_path / "returns_summary_2.md").read_text()
    assert "Note: returns_summary.md already exists; writing returns_summary_2.md instead" in r.stdout
    assert "returns_summary_2.md" in [line for line in r.stdout.splitlines() if line.startswith("Wrote")][0]


def test_solar_return_round_trips_through_sibling_skills(tmp_path):
    r = run(str(EXAMPLE), "--start", "2027-01-01", "--end", "2027-12-31", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    ret = tmp_path / "sun_return_2027-06-15.json"
    assert ret.exists()

    def sibling(script, *args):
        if not script.is_file():
            pytest.skip(f"sibling skill absent: {script}")
        p = subprocess.run([sys.executable, "-I", str(script), *args], cwd=tmp_path, capture_output=True, text=True)
        assert p.returncode == 0, f"{script.name}: {p.stderr}"

    sibling(WHEEL, str(ret), "--out", "wheel.svg")
    assert (tmp_path / "wheel.svg").exists()
    sibling(TRANSITS, str(ret), "--start", "2027-06-15", "--end", "2027-07-15", "--out", "t.csv")
    assert (tmp_path / "t.csv").exists()
    sibling(SYNASTRY, "--a", str(EXAMPLE), "--b", str(ret), "--out", "syn.json", "--grid", "syn.md")
    assert (tmp_path / "syn.json").exists()
