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
    files, raw = (json.loads((tmp_path / n).read_text()) for n in ("files.json", "raw.json"))
    assert files["config"]["a"]["source"] == str(EXAMPLE) and raw["config"]["a"]["source"] == "birth data"
    files.pop("config"); raw.pop("config")
    assert files == raw


def test_ambiguous_city_passes_through_exit_2(tmp_path):
    r = run("--a-birth", "--name A --date 1990-06-15 --city Paris", "--b", str(EXAMPLE), cwd=tmp_path)
    assert r.returncode == 2
    assert "geonameid" in r.stdout


def _natal_flagged_chart(tmp_path):
    c = json.loads(EXAMPLE.read_text())
    c["meta"]["flags"] = ["polar_fallback_whole_sign"]
    p = tmp_path / "polar.json"
    p.write_text(json.dumps(c))
    return p


def test_natal_flags_surface_in_result_and_notes(tmp_path):
    p = _natal_flagged_chart(tmp_path)
    r = run("--a", str(p), "--b", str(EXAMPLE), "--out", "s.json", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    s = json.loads((tmp_path / "s.json").read_text())
    assert "a_polar_fallback_whole_sign" in s["flags"]
    assert "Note: a_polar_fallback_whole_sign" in r.stdout
    assert s["config"]["a"] == {"source": str(p), "house_system": "placidus"}
    assert s["config"]["orb_reduction"] == 2.0


def test_birth_data_config_source(tmp_path):
    birth = "--name Example --date 1990-06-15 --time 12:00 --geonameid 5128581"
    r = run("--a-birth", birth, "--b", str(EXAMPLE), "--out", "s.json", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    s = json.loads((tmp_path / "s.json").read_text())
    assert s["config"]["a"]["source"] == "birth data"
    assert s["config"]["b"]["source"] == str(EXAMPLE)


def test_quoted_name_round_trips(tmp_path):
    birth = '--name "Ada Lovelace" --date 1990-06-15 --time 12:00 --geonameid 5128581'
    r = run("--a-birth", birth, "--b", str(EXAMPLE), "--out", "s.json", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert json.loads((tmp_path / "s.json").read_text())["a"] == "Ada Lovelace"


def test_bad_shell_string_exits_1(tmp_path):
    r = run("--a-birth", '--name "Ada', "--b", str(EXAMPLE), cwd=tmp_path)
    assert r.returncode == 1
    assert '--name "Ada' in r.stderr and "Traceback" not in r.stderr


def test_user_grid_in_birth_string_stays_out_of_cwd(tmp_path):
    birth = "--name X --date 1990-06-15 --time 12:00 --geonameid 5128581 --grid evil.md"
    r = run("--a-birth", birth, "--b", str(EXAMPLE), "--out", "s.json", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert not (tmp_path / "evil.md").exists()


def test_grid_equal_to_out_is_rejected(tmp_path):
    r = run("--a", str(EXAMPLE), "--b", str(EXAMPLE), "--out", "s.json", "--grid", "s.json", cwd=tmp_path)
    assert r.returncode == 1 and "--grid" in r.stderr
    assert not (tmp_path / "s.json").exists()


def test_invalid_chart_gives_one_line_error(tmp_path):
    for missing in ("meta", "bodies", "schema_version"):
        c = json.loads(EXAMPLE.read_text())
        if missing == "meta":
            c["meta"].pop("name")
        else:
            c.pop(missing)
        p = tmp_path / f"{missing}.json"
        p.write_text(json.dumps(c))
        r = run("--a", str(p), "--b", str(EXAMPLE), "--out", "s.json", cwd=tmp_path)
        assert r.returncode == 1, missing
        assert "Traceback" not in r.stderr and str(p) in r.stderr and len(r.stderr.strip().splitlines()) == 1


def test_missing_natal_script_exits_1(tmp_path):
    import os
    import shutil
    home = tmp_path / "home"; home.mkdir()
    alone = tmp_path / "alone"; alone.mkdir()
    script = alone / "synastry.py"
    shutil.copy(SCRIPT, script)
    env = {**os.environ, "HOME": str(home)}
    r = subprocess.run([sys.executable, "-I", str(script), "--a-birth", "--name A --date 1990-06-15",
                        "--b", str(EXAMPLE)], cwd=alone, capture_output=True, text=True, env=env)
    assert r.returncode == 1
    assert "natal-chart" in r.stderr and "Traceback" not in r.stderr
