from pathlib import Path
import fetch_ephemeris as fe


def test_file_list_and_url():
    assert fe.FILES == ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]
    assert fe.url_for("seas_18.se1") == (
        "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/seas_18.se1"
    )


def test_default_dir_is_sibling_ephe():
    assert fe.default_dir() == Path(fe.__file__).resolve().parents[1] / "ephe"


def test_missing_lists_only_absent_files(tmp_path):
    (tmp_path / "sepl_18.se1").write_bytes(b"x")
    assert fe.missing(tmp_path) == ["semo_18.se1", "seas_18.se1"]
