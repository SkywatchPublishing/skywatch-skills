import pytest
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


class _FakeResponse:
    def __init__(self, data: bytes, fail_after: int | None = None):
        self._data = data
        self._fail_after = fail_after
        self._reads = 0

    def read(self, size=-1):
        if self._fail_after is not None and self._reads >= self._fail_after:
            raise ConnectionResetError("connection dropped")
        self._reads += 1
        chunk, self._data = self._data[:size] if size > 0 else self._data, self._data[size:] if size > 0 else b""
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_downloads_to_final_name_without_part_file(tmp_path, monkeypatch):
    calls = []

    def fake_urlopen(url, timeout=None):
        calls.append((url, timeout))
        return _FakeResponse(b"ephemeris bytes")

    monkeypatch.setattr(fe.urllib.request, "urlopen", fake_urlopen)
    fetched = fe.fetch(tmp_path)
    assert fetched == fe.FILES
    assert [u for u, _ in calls] == [fe.url_for(f) for f in fe.FILES]
    assert all(t == 60 for _, t in calls)
    for name in fe.FILES:
        assert (tmp_path / name).read_bytes() == b"ephemeris bytes"
    assert not list(tmp_path.glob("*.part"))
    assert fe.missing(tmp_path) == []


def test_fetch_dropped_connection_leaves_no_files(tmp_path, monkeypatch):
    def fake_urlopen(url, timeout=None):
        return _FakeResponse(b"partial", fail_after=0)

    monkeypatch.setattr(fe.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ConnectionResetError):
        fe.fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert fe.missing(tmp_path) == fe.FILES


def test_fetch_rejects_empty_download(tmp_path, monkeypatch):
    monkeypatch.setattr(fe.urllib.request, "urlopen", lambda url, timeout=None: _FakeResponse(b""))
    with pytest.raises(Exception):
        fe.fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []
