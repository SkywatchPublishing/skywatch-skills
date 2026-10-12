import csv
import datetime as dt
import json
import shlex
import subprocess
import sys
from pathlib import Path

from zoneinfo import ZoneInfo

import pytest
import swisseph as swe
import progressions as pg

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "progressions" / "scripts" / "progressions.py"
EXAMPLE = ROOT / "natal-chart" / "examples" / "chart.json"
EXAMPLES = ROOT / "progressions" / "examples"
COMPOSITE = ROOT / "composite" / "examples" / "composite.json"
DAVISON = ROOT / "composite" / "examples" / "davison.json"
SOLAR_RETURN = ROOT / "returns" / "examples" / "sun_return_2027-06-15.json"
HEADER = "Technique,Event,Moving,Aspect,Target,Exact,Orb from,Orb to,Detail,Uncertain"


def run(*args, cwd):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)], cwd=cwd, capture_output=True, text=True)


def write_chart(tmp_path, name, edit):
    chart = json.loads(EXAMPLE.read_text())
    edit(chart)
    path = tmp_path / name
    path.write_text(json.dumps(chart))
    return path


# natal-chart's moon_range for the example birth cast without a time: 1990-06-15 in New York, so at noon, the
# moment of the example chart.
UNTIMED_MOON_RANGE = {"start": 340.9237, "end": 354.3375}


def untimed(chart):
    chart["angles"] = None
    chart["houses"] = None
    chart["meta"].update(time_unknown=True, house_system=None, flags=["time_unknown", "moon_uncertain"],
                         moon_range=dict(UNTIMED_MOON_RANGE))


def edge_moons(chart, day):
    """The progressed Moon at local noon on `day` for a birth at 00:00 and at 23:59 on the natal birth date."""
    tz = chart["meta"]["timezone"]
    t, born = pg.target_jd(day, tz), dt.date.fromisoformat(chart["meta"]["datetime_local"][:10])
    moons = []
    for clock in (dt.time(0, 0), dt.time(23, 59)):
        u = dt.datetime.combine(born, clock, tzinfo=ZoneInfo(tz)).astimezone(dt.timezone.utc)
        e = swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60)
        moons.append(swe.calc_ut(e + (t - e) / pg.YEAR, swe.MOON, swe.FLG_SWIEPH)[0][0])
    return moons


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --- chart mode ---------------------------------------------------------------------------------

# Without the ephemeris files a progressed chart has no Chiron and also prints Note: chiron_unavailable.
@pytest.mark.parametrize("extra, chart_type", [
    pytest.param([], "secondary_progressed", marks=pytest.mark.needs_ephemeris),
    pytest.param(["--method", "secondary"], "secondary_progressed", marks=pytest.mark.needs_ephemeris),
    (["--method", "solar-arc"], "solar_arc_directed"),
])
def test_chart_mode_defaults(tmp_path, extra, chart_type):
    proc = run(EXAMPLE, "--date", "2027-06-15", *extra, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    out, grid = f"{chart_type}_2027-06-15.json", f"{chart_type}_2027-06-15_aspects.md"
    assert proc.stdout.splitlines() == [f"Wrote {out} and {grid}"]
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([out, grid])
    chart = json.loads((tmp_path / out).read_text(encoding="utf-8"))
    assert chart["meta"]["chart_type"] == chart_type
    assert chart["meta"]["progression"]["target_date"] == "2027-06-15"
    natal = json.loads(EXAMPLE.read_text())
    tjd = pg.target_jd(dt.date(2027, 6, 15), natal["meta"]["timezone"])
    expected = pg.directed_chart(natal, tjd) if chart_type == "solar_arc_directed" else pg.progressed_chart(natal, tjd)
    assert chart == json.loads(json.dumps(expected))
    text = (tmp_path / grid).read_text(encoding="utf-8")
    assert text == pg.render_grid(chart)
    assert text.startswith("| | Sun |") and "| MC |" in text


@pytest.mark.needs_ephemeris
def test_angles_naibod_recorded(tmp_path):
    proc = run(EXAMPLE, "--date", "2027-06-15", "--angles", "naibod", "--out", "n.json", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == ["Wrote n.json and n_aspects.md"]
    chart = json.loads((tmp_path / "n.json").read_text(encoding="utf-8"))
    assert chart["meta"]["progression"]["angles_method"] == "naibod"
    natal = json.loads(EXAMPLE.read_text())
    sa = pg.progressed_chart(natal, pg.target_jd(dt.date(2027, 6, 15), natal["meta"]["timezone"]))
    assert pg.wrapped(chart["angles"]["mc"] - sa["angles"]["mc"]) == pytest.approx(-1.656, abs=0.01)


@pytest.mark.parametrize("angles", ["naibod", "solar-arc"])
def test_directed_chart_rejects_explicit_angles(tmp_path, angles):
    proc = run(EXAMPLE, "--date", "2027-06-15", "--method", "solar-arc", "--angles", angles, cwd=tmp_path)
    assert proc.returncode == 1
    assert "--angles" in proc.stderr
    assert not list(tmp_path.iterdir())


def test_grid_equal_to_out_exits_1(tmp_path):
    proc = run(EXAMPLE, "--date", "2027-06-15", "--out", "x.json", "--grid", "x.json", cwd=tmp_path)
    assert proc.returncode == 1
    assert "--grid" in proc.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.needs_ephemeris
def test_untimed_chart_prints_a_note_per_flag(tmp_path):
    path = write_chart(tmp_path, "u.json", untimed)
    proc = run(path, "--date", "2027-06-15", "--angles", "naibod", "--out", "p.json", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    assert lines[:3] == ["Wrote p.json and p_aspects.md", "Note: moon_uncertain", "Note: time_unknown"]
    assert len(lines) == 4 and lines[3].startswith("Note: --angles ignored")
    chart = json.loads((tmp_path / "p.json").read_text(encoding="utf-8"))
    assert chart["angles"] is None and chart["meta"]["progression"]["angles_method"] is None


def test_untimed_charts_move_the_moon_range(tmp_path):
    path = write_chart(tmp_path, "u.json", untimed)
    for method in ("secondary", "solar-arc"):
        proc = run(path, "--date", "2027-06-15", "--method", method, "--out", f"{method}.json", cwd=tmp_path)
        assert proc.returncode == 0, proc.stderr
    progressed, directed = (json.loads((tmp_path / f"{m}.json").read_text(encoding="utf-8"))["meta"]
                            for m in ("secondary", "solar-arc"))
    # Progressed: recomputed for a birth at each edge of the birth day. Directed: the natal range plus the arc.
    for got, want in zip((progressed["moon_range"]["start"], progressed["moon_range"]["end"]),
                         edge_moons(json.loads(path.read_text()), dt.date(2027, 6, 15))):
        assert abs(pg.wrapped(got - want)) < 1e-4
    arc = directed["progression"]["solar_arc"]
    assert arc > 30
    for k in ("start", "end"):
        assert abs(pg.wrapped(progressed["moon_range"][k] - UNTIMED_MOON_RANGE[k])) > 1
        assert abs(pg.wrapped(directed["moon_range"][k] - (UNTIMED_MOON_RANGE[k] + arc))) < 1e-3


def test_date_before_birth_exits_1(tmp_path):
    proc = run(EXAMPLE, "--date", "1990-06-14", cwd=tmp_path)
    assert proc.returncode == 1
    assert "before the birth date" in proc.stderr
    assert not list(tmp_path.iterdir())


def test_main_writes_chart_in_cwd(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert pg.main([str(EXAMPLE), "--date", "2027-06-15", "--method", "solar-arc"]) == 0
    assert capsys.readouterr().out == \
        "Wrote solar_arc_directed_2027-06-15.json and solar_arc_directed_2027-06-15_aspects.md\n"
    assert (tmp_path / "solar_arc_directed_2027-06-15.json").exists()


# --- refusals and usage errors ------------------------------------------------------------------

@pytest.mark.parametrize("args", [
    ["--date", "2027-06-15", "--timeline", "--start", "2027-01-01", "--end", "2027-12-31"],
    [],
])
def test_exactly_one_of_date_and_timeline(tmp_path, args):
    proc = run(EXAMPLE, *args, cwd=tmp_path)
    assert proc.returncode == 1
    assert "--date" in proc.stderr and "--timeline" in proc.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("args", [
    ["--date", "2027-13-01"],
    ["--date", "2027-06-15", "--method", "tertiary"],
    ["--date", "2027-06-15", "--angles", "placidus"],
    ["--date", "2027-06-15", "--start", "2027-01-01"],
    ["--timeline", "--start", "2027-01-01"],
    ["--timeline", "--start", "2027-01-01", "--end", "2027-12-31", "--method", "solar-arc"],
    ["--timeline", "--start", "2027-01-01", "--end", "2027-12-31", "--grid", "g.md"],
])
def test_usage_errors_exit_1(tmp_path, args):
    proc = run(EXAMPLE, *args, cwd=tmp_path)
    assert proc.returncode == 1
    assert "usage:" in proc.stderr
    assert not list(tmp_path.iterdir())


def test_usage_error_from_main_exits_1(capsys):
    with pytest.raises(SystemExit) as exc:
        pg.main([str(EXAMPLE), "--date", "2027-06-15", "--method", "solar-arc", "--angles", "naibod"])
    assert exc.value.code == 1
    assert "--angles" in capsys.readouterr().err


MODES = [["--date", "2027-06-15"], ["--timeline", "--start", "2027-01-01", "--end", "2027-12-31"]]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("path, chart_type", [
    (COMPOSITE, "composite"), (DAVISON, "davison"), (SOLAR_RETURN, "solar_return"),
])
def test_derived_charts_are_refused(tmp_path, mode, path, chart_type):
    assert json.loads(path.read_text())["meta"]["chart_type"] == chart_type
    proc = run(path, *mode, cwd=tmp_path)
    assert proc.returncode == 1
    assert len(proc.stderr.splitlines()) == 1
    assert f"this is a {chart_type} chart" in proc.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("key", ["julian_day_ut", "datetime_utc", "timezone"])
def test_chart_without_a_moment_is_refused(tmp_path, key):
    path = write_chart(tmp_path, "c.json", lambda c: c["meta"].update({key: None}))
    proc = run(path, "--date", "2027-06-15", cwd=tmp_path)
    assert proc.returncode == 1
    assert len(proc.stderr.splitlines()) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.json"]


@pytest.mark.parametrize("method", ["secondary", "solar-arc"])
def test_already_progressed_chart_is_refused(tmp_path, method):
    first = run(EXAMPLE, "--date", "2027-06-15", "--method", method, "--out", "p.json", cwd=tmp_path)
    assert first.returncode == 0, first.stderr
    for mode in (["--date", "2030-01-01", "--out", "again.json"],
                 ["--timeline", "--start", "2027-01-01", "--end", "2027-12-31", "--out", "again.csv"]):
        proc = run("p.json", *mode, cwd=tmp_path)
        assert proc.returncode == 1
        assert len(proc.stderr.splitlines()) == 1
        kind = "solar_arc_directed" if method == "solar-arc" else "secondary_progressed"
        assert f"this is a {kind} chart" in proc.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["p.json", "p_aspects.md"]


def test_chart_carrying_a_progression_is_refused(tmp_path):
    path = write_chart(tmp_path, "c.json", lambda c: c["meta"].update(progression={"target_date": "2027-06-15"}))
    proc = run(path, "--date", "2027-06-15", cwd=tmp_path)
    assert proc.returncode == 1
    assert len(proc.stderr.splitlines()) == 1 and "progress" in proc.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.json"]


@pytest.mark.parametrize("args", [
    ["--date", "2027-06-15", "--out", "chart.json"],
    ["--date", "2027-06-15", "--out", "p.json", "--grid", "./chart.json"],
    ["--timeline", "--start", "2027-01-01", "--end", "2027-12-31", "--out", "chart.json"],
])
def test_output_over_the_input_chart_exits_1(tmp_path, args):
    path = write_chart(tmp_path, "chart.json", lambda c: None)
    before = path.read_text()
    proc = run("chart.json", *args, cwd=tmp_path)
    assert proc.returncode == 1
    assert len(proc.stderr.splitlines()) == 1 and "input chart" in proc.stderr
    assert path.read_text() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["chart.json"]


@pytest.mark.parametrize("args", [
    ["--date", "2027-06-15", "--out", "out.json"],
    ["--date", "2027-06-15", "--out", "p.json", "--grid", "out.json"],
    ["--timeline", "--start", "2027-01-01", "--end", "2027-12-31", "--out", "out.json"],
])
def test_output_hard_linked_to_the_input_chart_exits_1(tmp_path, args):
    path = write_chart(tmp_path, "chart.json", lambda c: None)
    (tmp_path / "out.json").hardlink_to(path)
    before = path.read_text()
    proc = run("chart.json", *args, cwd=tmp_path)
    assert proc.returncode == 1
    assert len(proc.stderr.splitlines()) == 1 and "input chart" in proc.stderr
    assert path.read_text() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["chart.json", "out.json"]


@pytest.mark.parametrize("args, bad", [
    (["--date", "2027-06-15", "--out", "p.json", "--grid", "missing/p.md"], "missing/p.md"),
    (["--date", "2027-06-15", "--out", "missing/p.json"], "missing/p.json"),
    (["--date", "2027-06-15", "--out", "p.json", "--grid", "subdir"], "subdir"),
    (["--timeline", "--start", "2027-01-01", "--end", "2027-12-31", "--out", "missing/t.csv"], "missing/t.csv"),
])
def test_output_without_a_folder_exits_1_before_writing(tmp_path, args, bad):
    (tmp_path / "subdir").mkdir()
    proc = run(EXAMPLE, *args, cwd=tmp_path)
    assert proc.returncode == 1
    assert len(proc.stderr.splitlines()) == 1 and bad in proc.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["subdir"]
    assert not list((tmp_path / "subdir").iterdir())


def test_chart_without_a_chart_type_is_natal(tmp_path):
    path = write_chart(tmp_path, "old.json", lambda c: c["meta"].pop("chart_type"))
    proc = run(path, "--date", "2027-06-15", "--out", "p.json", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert json.loads((tmp_path / "p.json").read_text(encoding="utf-8"))["meta"]["chart_type"] == "secondary_progressed"


@pytest.mark.parametrize("value, shown", [("", '""'), (None, "null")])
def test_empty_or_null_chart_type_is_refused(tmp_path, value, shown):
    path = write_chart(tmp_path, "c.json", lambda c: c["meta"].update(chart_type=value))
    for mode in MODES:
        proc = run(path, *mode, cwd=tmp_path)
        assert proc.returncode == 1
        assert len(proc.stderr.splitlines()) == 1 and f"this is a {shown} chart, not a natal one" in proc.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.json"]


def test_missing_ephemeris_files_note_chiron(tmp_path, monkeypatch, capsys, no_ephemeris):
    monkeypatch.chdir(tmp_path)
    assert pg.main([str(EXAMPLE), "--date", "2027-06-15", "--out", "p.json"]) == 0
    assert capsys.readouterr().out.splitlines() == ["Wrote p.json and p_aspects.md", "Note: chiron_unavailable"]
    chart = json.loads((tmp_path / "p.json").read_text(encoding="utf-8"))
    assert "Chiron" not in chart["bodies"] and chart["meta"]["source"]["ephemeris_files"] is False
    assert pg.main([str(EXAMPLE), "--timeline", "--start", "2027-01-01", "--end", "2028-12-31"]) == 0
    rows = read_csv(tmp_path / "progressions_timeline.csv")
    assert capsys.readouterr().out.splitlines() == [f"Wrote {len(rows)} events to progressions_timeline.csv",
                                                    "Note: chiron_unavailable"]
    assert rows and not [r for r in rows if r["Moving"] == "Chiron" and r["Technique"] == "secondary"]


def test_birth_date_with_an_afternoon_birth_is_age_zero(tmp_path, cast):
    path = tmp_path / "late.json"
    path.write_text(json.dumps(cast("--date", "1990-06-15", "--time", "18:30", "--geonameid", "5128581")))
    for method in ("secondary", "solar-arc"):
        proc = run(path, "--date", "1990-06-15", "--method", method, "--out", f"{method}.json", cwd=tmp_path)
        assert proc.returncode == 0, proc.stderr
        prog = json.loads((tmp_path / f"{method}.json").read_text(encoding="utf-8"))["meta"]["progression"]
        assert prog["age_years"] == 0.0 and prog["solar_arc"] == 0.0
    proc = run(path, "--timeline", "--start", "1990-06-15", "--end", "1991-06-15", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    rows = read_csv(tmp_path / "progressions_timeline.csv")
    assert rows and all(r[k] == "" or r[k] >= "1990-06-15" for r in rows for k in ("Exact", "Orb from", "Orb to"))


@pytest.mark.parametrize("content", [None, "{not json"])
def test_unreadable_chart_exits_1(tmp_path, content):
    if content is not None:
        (tmp_path / "bad.json").write_text(content)
    proc = run("bad.json", "--date", "2027-06-15", cwd=tmp_path)
    assert proc.returncode == 1
    assert "bad.json" in proc.stderr


# --- timeline mode ------------------------------------------------------------------------------

@pytest.mark.needs_ephemeris          # without Chiron the run also prints Note: chiron_unavailable
def test_timeline_csv(tmp_path, rows):
    # `rows` is the library's timeline for the same chart and range (conftest.py).
    proc = run(EXAMPLE, "--timeline", "--start", "2027-01-01", "--end", "2036-12-31", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    out = tmp_path / "progressions_timeline.csv"
    assert out.read_text(encoding="utf-8").splitlines()[0] == HEADER
    written = read_csv(out)
    assert len(written) >= 100
    assert proc.stdout.splitlines() == [f"Wrote {len(written)} events to progressions_timeline.csv"]
    assert {r["Technique"] for r in written} == {"secondary", "solar arc"}
    assert {r["Event"] for r in written} >= {"aspect", "ingress"}
    assert {r["Uncertain"] for r in written} == {""}
    for r in written:
        dt.date.fromisoformat(r["Exact"])
        for k in ("Orb from", "Orb to"):
            assert r[k] == "" or dt.date.fromisoformat(r[k])
    assert all(r["Orb from"] == r["Orb to"] == "" for r in written if r["Event"] != "aspect")
    assert [(r["Exact"], r["Moving"], r["Target"]) for r in written] == \
        [(r["exact"].isoformat(), r["moving"], r["target"]) for r in rows]


def test_end_before_start_exits_1(tmp_path):
    proc = run(EXAMPLE, "--timeline", "--start", "2030-01-01", "--end", "2029-12-31", cwd=tmp_path)
    assert proc.returncode == 1
    assert "--end" in proc.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.needs_ephemeris
def test_start_before_birth_is_clamped(tmp_path):
    proc = run(EXAMPLE, "--timeline", "--start", "1980-01-01", "--end", "1992-12-31", "--out", "early.csv", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    notes = [line for line in proc.stdout.splitlines() if line.startswith("Note:")]
    assert len(notes) == 1 and "1980-01-01" in notes[0] and "1990-06-15" in notes[0]
    birth = run(EXAMPLE, "--timeline", "--start", "1990-06-15", "--end", "1992-12-31", "--out", "birth.csv", cwd=tmp_path)
    assert birth.returncode == 0, birth.stderr
    assert (tmp_path / "early.csv").read_text(encoding="utf-8") == (tmp_path / "birth.csv").read_text(encoding="utf-8")
    assert min(r["Exact"] for r in read_csv(tmp_path / "early.csv")) >= "1990-06-15"


def test_end_before_birth_exits_1(tmp_path):
    proc = run(EXAMPLE, "--timeline", "--start", "1980-01-01", "--end", "1989-12-31", cwd=tmp_path)
    assert proc.returncode == 1
    assert "before the birth date" in proc.stderr
    assert not list(tmp_path.iterdir())


def test_range_over_120_years_exits_1(tmp_path):
    proc = run(EXAMPLE, "--timeline", "--start", "1990-06-15", "--end", "2110-06-16", cwd=tmp_path)
    assert proc.returncode == 1
    assert "120 years" in proc.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.needs_ephemeris
def test_untimed_timeline_marks_uncertain_and_notes(tmp_path):
    path = write_chart(tmp_path, "u.json", untimed)
    proc = run(path, "--timeline", "--start", "2027-01-01", "--end", "2030-12-31", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    rows = read_csv(tmp_path / "progressions_timeline.csv")
    assert rows and {r["Uncertain"] for r in rows} <= {"yes", ""}
    assert all(r["Uncertain"] == "yes" for r in rows if r["Technique"] == "secondary")
    assert not [r for r in rows if "Ascendant" in (r["Moving"], r["Target"]) or r["Event"] == "house"]
    lines = proc.stdout.splitlines()
    assert lines[0] == f"Wrote {len(rows)} events to progressions_timeline.csv"
    assert len(lines) == 2 and lines[1].startswith("Note:") and "six months" in lines[1]


def test_main_passes_clamped_start_and_angles(tmp_path, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(pg, "timeline", lambda natal, start, end, angles: seen.append((start, end, angles)) or [])
    monkeypatch.chdir(tmp_path)
    # 1900-2050 spans 150 years, but only 60 of them after the birth date; the limit applies after clamping.
    assert pg.main([str(EXAMPLE), "--timeline", "--start", "1900-01-01", "--end", "2050-12-31"]) == 0
    assert pg.main([str(EXAMPLE), "--timeline", "--start", "2027-01-01", "--end", "2027-12-31", "--angles", "naibod"]) == 0
    assert seen == [(dt.date(1990, 6, 15), dt.date(2050, 12, 31), "solar-arc"),
                    (dt.date(2027, 1, 1), dt.date(2027, 12, 31), "naibod")]
    assert (tmp_path / "progressions_timeline.csv").read_text(encoding="utf-8").splitlines() == [HEADER]
    assert "Wrote 0 events to progressions_timeline.csv" in capsys.readouterr().out


# --- committed examples -----------------------------------------------------------------------------

def readme_commands():
    """The README's "Examples are produced by" commands, as argument lists after the script path."""
    lines = (ROOT / "progressions" / "README.md").read_text(encoding="utf-8").splitlines()
    return [shlex.split(line)[2:] for line in lines if line.startswith("python progressions/scripts/progressions.py ")]


@pytest.mark.needs_ephemeris
def test_readme_commands_reproduce_the_committed_examples(tmp_path, capsys):
    commands = readme_commands()
    assert len(commands) == 3
    for args in commands:
        # The README runs from the repository root and writes into progressions/examples; write to tmp_path.
        args = [str(ROOT / a) if a.endswith("chart.json") else a for a in args]
        i = args.index("--out") + 1
        assert args[i].startswith("progressions/examples/")
        args[i] = str(tmp_path / Path(args[i]).name)
        assert pg.main(args) == 0
    assert "Wrote 132 events to" in capsys.readouterr().out
    written = sorted(p.name for p in tmp_path.iterdir())
    assert written == sorted(p.name for p in EXAMPLES.iterdir()) and len(written) == 5
    for name in written:
        assert (tmp_path / name).read_bytes() == (EXAMPLES / name).read_bytes(), name


# --- round trip through the other chart skills ----------------------------------------------------

def sibling(folder, script):
    path = ROOT / folder / "scripts" / script
    if not path.exists():
        pytest.skip(f"{folder} is not installed beside progressions ({path} is missing)")
    return path


def run_sibling(path, *args, cwd):
    return subprocess.run([sys.executable, "-I", str(path), *map(str, args)], cwd=cwd, capture_output=True, text=True)


@pytest.mark.parametrize("method, caption", [
    ("secondary", "Secondary progressed for Example"), ("solar-arc", "Solar arc directed for Example"),
])
def test_round_trip_through_wheel_synastry_and_transits(tmp_path, method, caption):
    wheel = sibling("chart-wheel", "chart_wheel.py")
    synastry = sibling("synastry", "synastry.py")
    transits = sibling("transits-to-natal", "transits.py")
    proc = run(EXAMPLE, "--date", "2027-06-15", "--method", method, "--out", "p.json", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr

    proc = run_sibling(wheel, "p.json", "--out", "p.svg", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    svg = (tmp_path / "p.svg").read_text(encoding="utf-8")
    assert caption in svg and "for 2027-06-15" in svg

    proc = run_sibling(synastry, "--a", "p.json", "--b", EXAMPLE, "--out", "syn.json", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    syn = json.loads((tmp_path / "syn.json").read_text(encoding="utf-8"))
    assert syn["inter_aspects"] and syn["overlays"]["a_in_b_houses"]
    if method == "secondary":
        # The progressed Moon, in the natal 11th, a month from its exact opposition to the natal Node.
        assert syn["overlays"]["a_in_b_houses"]["Moon"] == 11
        assert [a for a in syn["inter_aspects"] if (a["a"], a["aspect"], a["b"]) == ("Moon", "Opposition", "Node")]

    proc = run_sibling(transits, "p.json", "--start", "2027-06-01", "--end", "2027-06-30", "--out", "tr.csv",
                       cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert read_csv(tmp_path / "tr.csv")


@pytest.mark.parametrize("method", ["secondary", "solar-arc"])
def test_returns_and_composite_refuse_progressed_charts(tmp_path, method):
    returns = sibling("returns", "returns.py")
    composite = sibling("composite", "composite.py")
    sibling("natal-chart", "natal_chart.py")       # returns looks for it before reading the chart
    proc = run(EXAMPLE, "--date", "2027-06-15", "--method", method, "--out", "p.json", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    proc = run_sibling(returns, "p.json", "--start", "2027-01-01", "--end", "2027-12-31", "--out-dir", ".",
                       cwd=tmp_path)
    assert proc.returncode == 1
    assert "returns: this is a progressed or directed chart" in proc.stderr
    proc = run_sibling(composite, "--a", "p.json", "--b", EXAMPLE, "--out", "c.json", cwd=tmp_path)
    assert proc.returncode == 1
    assert "composite: progressed and directed charts can't be composited" in proc.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["p.json", "p_aspects.md"]
