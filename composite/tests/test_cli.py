import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "composite" / "scripts" / "composite.py"
EXAMPLE = ROOT / "natal-chart" / "examples" / "chart.json"
PARTNER = ROOT / "synastry" / "examples" / "chart_b.json"
A_BIRTH = "--name Example --date 1990-06-15 --time 12:00 --geonameid 5128581"
B_BIRTH = "--name Partner --date 1988-02-02 --time 09:15 --geonameid 2643743"


def run(*args, cwd):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)


def test_midpoint_of_examples_writes_defaults(tmp_path):
    proc = run("--a", str(EXAMPLE), "--b", str(PARTNER), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "Wrote composite.json and composite.md" in proc.stdout
    chart = json.loads((tmp_path / "composite.json").read_text())
    assert chart["meta"]["chart_type"] == "composite"
    assert chart["meta"]["derived_from"] == ["Example", "Partner"]
    assert chart["meta"]["location"]["geonameid"] == 5128581
    grid = (tmp_path / "composite.md").read_text()
    assert grid.startswith("| | Sun |") and "| Ascendant |" in grid


def test_davison_of_examples(tmp_path):
    proc = run("--a", str(EXAMPLE), "--b", str(PARTNER), "--method", "davison", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "Wrote davison.json and davison.md" in proc.stdout
    chart = json.loads((tmp_path / "davison.json").read_text())
    assert chart["meta"]["chart_type"] == "davison"
    assert chart["meta"]["location"]["latitude"] == pytest.approx(52.37, abs=0.05)
    assert chart["meta"]["location"]["longitude"] == pytest.approx(-41.29, abs=0.05)
    assert (tmp_path / "davison.md").exists()
    assert not (tmp_path / "davison_aspects.md").exists()


def _write_a(tmp_path, drop_requested=False, **meta):
    a = json.loads(EXAMPLE.read_text())
    a["meta"].update(meta)
    if drop_requested:   # a chart written before meta.house_system_requested existed
        a["meta"].pop("house_system_requested", None)
    (tmp_path / "a.json").write_text(json.dumps(a))
    return "a.json"


def test_midpoint_default_prefers_requested_house_system(tmp_path):
    a = _write_a(tmp_path, house_system="whole_sign", house_system_requested="koch")
    proc = run("--a", a, "--b", str(PARTNER), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    meta = json.loads((tmp_path / "composite.json").read_text())["meta"]
    assert meta["house_system"] == "koch"
    assert meta["house_system_requested"] == "koch"


def test_midpoint_default_without_requested_field_uses_house_system(tmp_path):
    a = _write_a(tmp_path, drop_requested=True, house_system="koch")
    proc = run("--a", a, "--b", str(PARTNER), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    meta = json.loads((tmp_path / "composite.json").read_text())["meta"]
    assert meta["house_system"] == meta["house_system_requested"] == "koch"


def test_davison_default_prefers_requested_and_houses_flag_overrides_it(tmp_path):
    a = _write_a(tmp_path, house_system="whole_sign", house_system_requested="koch")
    proc = run("--a", a, "--b", str(PARTNER), "--method", "davison", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert json.loads((tmp_path / "davison.json").read_text())["meta"]["house_system"] == "koch"
    proc = run("--a", a, "--b", str(PARTNER), "--method", "davison", "--houses", "equal", "--out", "eq.json",
               cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    meta = json.loads((tmp_path / "eq.json").read_text())["meta"]
    assert meta["house_system"] == meta["house_system_requested"] == "equal"


def test_davison_antipodal_birthplaces_exits_1(tmp_path):
    a = json.loads(EXAMPLE.read_text()); b = json.loads(EXAMPLE.read_text())
    a["meta"]["location"] = {"name": "x", "latitude": 0.0, "longitude": 0.0, "geonameid": None}
    b["meta"]["location"] = {"name": "y", "latitude": 0.0, "longitude": 180.0, "geonameid": None}
    (tmp_path / "a.json").write_text(json.dumps(a)); (tmp_path / "b.json").write_text(json.dumps(b))
    proc = run("--a", "a.json", "--b", "b.json", "--method", "davison", cwd=tmp_path)
    assert proc.returncode == 1
    assert "birthplaces are antipodal; no unique midpoint" in proc.stderr
    assert not (tmp_path / "davison.json").exists()


PROGRESSED_META = [
    {"chart_type": "secondary_progressed"},
    {"chart_type": "solar_arc_directed"},
    {"progression": {"target_date": "2027-06-15", "age_years": 37.0001, "solar_arc": 35.2991,
                     "angles_method": None}},
]


@pytest.mark.parametrize("method", ["midpoint", "davison"])
@pytest.mark.parametrize("extra_meta", PROGRESSED_META, ids=["progressed", "directed", "progression-key"])
def test_progressed_or_directed_chart_is_refused(tmp_path, method, extra_meta):
    chart = json.loads(EXAMPLE.read_text())
    chart["meta"].update(extra_meta)
    (tmp_path / "p.json").write_text(json.dumps(chart))
    proc = run("--a", str(EXAMPLE), "--b", "p.json", "--method", method, cwd=tmp_path)
    assert proc.returncode == 1
    assert proc.stderr.strip() == \
        "composite: progressed and directed charts can't be composited; use the natal charts"
    assert not list(tmp_path.glob("composite*")) and not list(tmp_path.glob("davison*"))


def _strip(chart: dict) -> dict:
    chart = json.loads(json.dumps(chart))
    chart["meta"].pop("source", None)
    return chart


def test_raw_birth_strings_match_file_inputs(tmp_path):
    files = run("--a", str(EXAMPLE), "--b", str(PARTNER), "--out", "files.json", cwd=tmp_path)
    births = run("--a-birth", A_BIRTH, "--b-birth", B_BIRTH, "--out", "births.json", cwd=tmp_path)
    assert files.returncode == 0, files.stderr
    assert births.returncode == 0, births.stderr
    assert _strip(json.loads((tmp_path / "files.json").read_text())) == \
        _strip(json.loads((tmp_path / "births.json").read_text()))
    assert (tmp_path / "births.md").exists()


def test_ambiguous_city_in_birth_string_exits_2(tmp_path):
    proc = run("--a-birth", "--name X --date 1990-06-15 --city Paris", "--b", str(PARTNER), cwd=tmp_path)
    assert proc.returncode == 2
    assert "geonameid" in proc.stdout


def test_grid_equal_to_out_exits_1(tmp_path):
    proc = run("--a", str(EXAMPLE), "--b", str(PARTNER), "--out", "x.md", "--grid", "x.md", cwd=tmp_path)
    assert proc.returncode == 1
    assert "--grid" in proc.stderr


def test_mixing_file_and_birth_exits_1(tmp_path):
    proc = run("--a", str(EXAMPLE), "--a-birth", A_BIRTH, "--b", str(PARTNER), cwd=tmp_path)
    assert proc.returncode == 1


def test_city_reference_moves_houses_not_bodies(tmp_path):
    default = run("--a", str(EXAMPLE), "--b", str(PARTNER), "--out", "ny.json", cwd=tmp_path)
    paris = run("--a", str(EXAMPLE), "--b", str(PARTNER), "--city", "Paris, FR", "--out", "paris.json", cwd=tmp_path)
    assert default.returncode == 0, default.stderr
    assert paris.returncode == 0, paris.stderr
    ny, fr = (json.loads((tmp_path / f).read_text()) for f in ("ny.json", "paris.json"))
    assert fr["meta"]["location"]["name"].startswith("Paris")
    assert fr["meta"]["location"]["latitude"] == pytest.approx(48.85, abs=0.05)
    assert fr["houses"]["cusps"] != ny["houses"]["cusps"]
    assert fr["angles"]["mc"] == pytest.approx(ny["angles"]["mc"], abs=1e-3)
    assert fr["angles"]["ascendant"] != pytest.approx(ny["angles"]["ascendant"], abs=0.1)
    for name in ny["bodies"]:
        assert fr["bodies"][name]["longitude"] == ny["bodies"][name]["longitude"]


def test_ambiguous_reference_city_exits_2(tmp_path):
    proc = run("--a", str(EXAMPLE), "--b", str(PARTNER), "--city", "Paris", cwd=tmp_path)
    assert proc.returncode == 2
    assert "geonameid" in proc.stdout


def test_davison_grid_in_subdir_leaves_no_aspects_file(tmp_path):
    (tmp_path / "sub").mkdir()
    proc = run("--a", str(EXAMPLE), "--b", str(PARTNER), "--method", "davison",
               "--grid", "sub/g.md", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "sub" / "g.md").exists()
    assert not list(tmp_path.rglob("*_aspects.md"))


def test_davison_default_run_leaves_unrelated_aspects_file_alone(tmp_path):
    stray = tmp_path / "davison_aspects.md"
    stray.write_text("unrelated\n")
    proc = run("--a", str(EXAMPLE), "--b", str(PARTNER), "--method", "davison", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert stray.read_text() == "unrelated\n"
    assert (tmp_path / "davison.md").read_text().startswith("|")


def test_untimed_a_with_city_reference_exits_0(tmp_path):
    proc = run("--a-birth", "--name X --date 1990-06-15 --geonameid 5128581", "--b", str(PARTNER),
               "--city", "Paris, FR", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    chart = json.loads((tmp_path / "composite.json").read_text())
    assert chart["houses"] is None
    assert "time_unknown" in chart["meta"]["flags"]
    assert chart["meta"]["location"]["geonameid"] == 2988507


def test_untimed_note_printed_once(tmp_path):
    proc = run("--a-birth", "--name X --date 1990-06-15 --geonameid 5128581", "--b", str(PARTNER), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("Note: time_unknown") == 1


def test_out_with_empty_stem_exits_1(tmp_path):
    proc = run("--a", str(EXAMPLE), "--b", str(PARTNER), "--out", ".json", cwd=tmp_path)
    assert proc.returncode == 1
    assert "--out" in proc.stderr
    assert len(proc.stderr.strip().splitlines()) == 1


def test_houses_ignored_note_for_untimed_composite(tmp_path):
    proc = run("--a-birth", "--name X --date 1990-06-15 --geonameid 5128581", "--b", str(PARTNER),
               "--houses", "koch", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "Note: --houses ignored because the composite has no houses (an untimed side)" in proc.stdout


WHEEL = ROOT / "chart-wheel" / "scripts" / "chart_wheel.py"
TRANSITS = ROOT / "transits-to-natal" / "scripts" / "transits.py"
SYNASTRY = ROOT / "synastry" / "scripts" / "synastry.py"


def test_davison_round_trips_through_sibling_skills(tmp_path):
    proc = run("--a", str(EXAMPLE), "--b", str(PARTNER), "--method", "davison", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    dav = tmp_path / "davison.json"

    def sibling(script, *args):
        if not script.is_file():
            pytest.skip(f"sibling skill absent: {script}")
        p = subprocess.run([sys.executable, "-I", str(script), *args], cwd=tmp_path, capture_output=True, text=True)
        assert p.returncode == 0, f"{script.name}: {p.stderr}"

    sibling(WHEEL, str(dav), "--out", "wheel.svg")
    assert (tmp_path / "wheel.svg").exists()
    sibling(TRANSITS, str(dav), "--start", "2027-01-01", "--end", "2027-01-31", "--out", "t.csv")
    assert (tmp_path / "t.csv").exists()
    sibling(SYNASTRY, "--a", str(EXAMPLE), "--b", str(dav), "--out", "syn.json", "--grid", "syn.md")
    assert (tmp_path / "syn.json").exists()
