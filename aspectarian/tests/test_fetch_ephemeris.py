from pathlib import Path

import pytest

import fetch_ephemeris as fe


def test_file_and_url():
    assert fe.FILES == ["de440s.bsp"]
    assert fe.url_for("de440s.bsp") == "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp"


def test_default_dir_is_sibling_ephe():
    assert fe.default_dir() == Path(fe.__file__).resolve().parents[1] / "ephe"


def test_missing_lists_only_absent_files(tmp_path):
    assert fe.missing(tmp_path) == ["de440s.bsp"]
    (tmp_path / "de440s.bsp").write_bytes(b"x")
    assert fe.missing(tmp_path) == []


class _FakeResponse:
    def __init__(self, data: bytes, fail: bool = False):
        self._data = data
        self._fail = fail

    def read(self, size=-1):
        if self._fail:
            raise ConnectionResetError("connection dropped")
        chunk, self._data = (self._data[:size], self._data[size:]) if size > 0 else (self._data, b"")
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
    assert fe.fetch(tmp_path) == ["de440s.bsp"]
    assert calls == [(fe.url_for("de440s.bsp"), 60)]
    assert (tmp_path / "de440s.bsp").read_bytes() == b"ephemeris bytes"
    assert not list(tmp_path.glob("*.part"))


def test_fetch_skips_a_file_already_present(tmp_path, monkeypatch):
    (tmp_path / "de440s.bsp").write_bytes(b"x")
    monkeypatch.setattr(fe.urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded again"))
    assert fe.fetch(tmp_path) == []


def test_fetch_dropped_connection_leaves_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(fe.urllib.request, "urlopen", lambda url, timeout=None: _FakeResponse(b"x", fail=True))
    with pytest.raises(ConnectionResetError):
        fe.fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_fetch_rejects_empty_download(tmp_path, monkeypatch):
    monkeypatch.setattr(fe.urllib.request, "urlopen", lambda url, timeout=None: _FakeResponse(b""))
    with pytest.raises(OSError):
        fe.fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []
