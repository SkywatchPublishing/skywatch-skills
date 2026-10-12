import csv
import datetime as dt
from pathlib import Path

import pytest

import aspectarian as A

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def utc(stamp):
    return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def assert_same_rows(got, expected, utc_columns):
    assert len(got) == len(expected)
    for g, e in zip(got, expected):
        assert list(g) == list(e)
        for key in g:
            if key in utc_columns:
                assert abs(utc(g[key]) - utc(e[key])) <= dt.timedelta(seconds=1), key
            else:
                assert g[key] == e[key], key


def test_april_2026_matches_the_committed_examples(sky, tmp_path, capsys):
    assert A.main(["4", "2026", "--out-dir", str(tmp_path)]) == 0
    assert_same_rows(read(tmp_path / "aspectarian_2026_04.csv"), read(EXAMPLES / "aspectarian_2026_04.csv"), {"UTC"})
    assert_same_rows(read(tmp_path / "voc_2026_04.csv"), read(EXAMPLES / "voc_2026_04.csv"),
                     {"Begins UTC", "Ingress UTC"})
    out = capsys.readouterr().out
    assert "Wrote 95 aspects to" in out and "Wrote 13 void-of-course periods to" in out


def test_headers(sky, tmp_path):
    A.main(["4", "2026", "--out-dir", str(tmp_path)])
    lines = (tmp_path / "aspectarian_2026_04.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "Date,Time,Body 1,Aspect,Body 2,UTC"
    lines = (tmp_path / "voc_2026_04.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == ("Begins Date,Begins Time,Last Aspect,Moon Enters,Ingress Date,Ingress Time,"
                        "Duration,Begins UTC,Ingress UTC")


def test_traditional_files_are_named_apart(sky, tmp_path):
    assert A.main(["4", "2026", "--traditional", "--out-dir", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "aspectarian_2026_04_traditional.csv", "voc_2026_04_traditional.csv"]


@pytest.mark.parametrize("argv, message", [
    (["13", "2026"], "month must be 1 to 12"),
    (["1", "1"], "year must be 2 to 9998"),
    (["4", "2026", "--tz", "Mars/Olympus_Mons"], "unknown time zone"),
])
def test_bad_input_exits_1(tmp_path, capsys, argv, message):
    assert A.main(argv + ["--out-dir", str(tmp_path)]) == 1
    assert message in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_a_month_outside_the_ephemeris_names_the_wider_file(sky, tmp_path, capsys):
    assert A.main(["4", "2200", "--out-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "2200-04 is outside de440s.bsp" in err and "de440.bsp" in err
    assert list(tmp_path.iterdir()) == []


def test_missing_ephemeris_names_the_fetch_script(tmp_path, capsys):
    assert A.main(["4", "2026", "--ephemeris", str(tmp_path / "nope.bsp"), "--out-dir", str(tmp_path)]) == 1
    assert "fetch_ephemeris.py" in capsys.readouterr().err
