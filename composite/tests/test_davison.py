import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import composite as cp

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"
PARTNER = Path(__file__).resolve().parents[2] / "synastry" / "examples" / "chart_b.json"
NATAL = Path(__file__).resolve().parents[2] / "natal-chart" / "scripts" / "natal_chart.py"


def test_great_circle_midpoint():
    lat, lon = cp.great_circle_midpoint(40.7143, -74.006, 35.6895, 139.6917)
    assert lat == pytest.approx(69.66, abs=0.05) and lon == pytest.approx(-153.66, abs=0.05)
    lat, lon = cp.great_circle_midpoint(10.0, 179.0, 10.0, -179.0)
    assert lon == pytest.approx(180.0, abs=1e-6) or lon == pytest.approx(-180.0, abs=1e-6)


def test_great_circle_midpoint_antipodal_raises():
    with pytest.raises(ValueError, match="antipodal"):
        cp.great_circle_midpoint(0.0, 0.0, 0.0, 180.0)


def test_cast_davison_antipodal_raises(tmp_path):
    a = json.loads(EXAMPLE.read_text()); b = json.loads(EXAMPLE.read_text())
    a["meta"]["location"] = {"name": "x", "latitude": 0.0, "longitude": 0.0, "geonameid": None}
    b["meta"]["location"] = {"name": "y", "latitude": 0.0, "longitude": 180.0, "geonameid": None}
    with pytest.raises(ValueError, match="birthplaces are antipodal; no unique midpoint"):
        cp.cast_davison(NATAL, a, b, tmp_path / "anti.json")


def test_davison_inputs_of_self_are_self():
    a = json.loads(EXAMPLE.read_text())
    when, lat, lon = cp.davison_inputs(a, a)
    assert when == dt.datetime(1990, 6, 15, 16, 0, tzinfo=dt.timezone.utc)
    assert (lat, lon) == pytest.approx((a["meta"]["location"]["latitude"], a["meta"]["location"]["longitude"]))


def test_davison_inputs_mean_time():
    a = json.loads(EXAMPLE.read_text()); b = json.loads(EXAMPLE.read_text())
    b["meta"]["datetime_utc"] = "1992-06-15T16:00:00Z"
    when, _, _ = cp.davison_inputs(a, b)
    # 731 days apart (1992 is a leap year), so the midpoint is 365.5 days after 1990-06-15 16:00 UT.
    assert when == dt.datetime(1991, 6, 16, 4, 0, tzinfo=dt.timezone.utc)


def test_cast_davison_of_examples(tmp_path):
    a = json.loads(EXAMPLE.read_text()); b = json.loads(PARTNER.read_text())
    out = tmp_path / "davison.json"
    c = cp.cast_davison(NATAL, a, b, out)
    assert json.loads(out.read_text()) == c
    m = c["meta"]
    assert m["chart_type"] == "davison"
    assert m["derived_from"] == ["Example", "Partner"]
    assert m["name"] == "Example & Partner"
    assert m["source"]["method"] == "davison"
    assert m["location"]["latitude"] == pytest.approx(52.37, abs=0.05)
    assert m["location"]["longitude"] == pytest.approx(-41.29, abs=0.05)
    assert m["timezone"] == "Etc/GMT+3"
    assert "davison_timezone_utc" not in m["flags"]
    when, _, _ = cp.davison_inputs(a, b)
    assert m["datetime_utc"] == when.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert m["house_system"] == a["meta"]["house_system"]
    assert c["angles"] is not None and c["houses"] is not None


def test_cast_davison_prefers_requested_house_system(tmp_path):
    # A polar natal chart records whole_sign as used but the system the user asked for as requested;
    # the Davison midpoint (here ~52°N) can use the requested one.
    a = json.loads(EXAMPLE.read_text()); b = json.loads(PARTNER.read_text())
    a["meta"].update(house_system="whole_sign", house_system_requested="koch")
    c = cp.cast_davison(NATAL, a, b, tmp_path / "davison.json")
    assert c["meta"]["house_system"] == "koch"
    assert c["meta"]["house_system_requested"] == "koch"


def test_cast_davison_without_requested_field_uses_house_system(tmp_path):
    a = json.loads(EXAMPLE.read_text()); b = json.loads(PARTNER.read_text())
    a["meta"].pop("house_system_requested", None)   # a chart written before the field existed
    a["meta"]["house_system"] = "koch"
    c = cp.cast_davison(NATAL, a, b, tmp_path / "davison.json")
    assert c["meta"]["house_system"] == "koch"


def test_cast_davison_of_self_reproduces_sun(tmp_path):
    a = json.loads(EXAMPLE.read_text())
    c = cp.cast_davison(NATAL, a, a, tmp_path / "self.json")
    assert c["bodies"]["Sun"]["longitude"] == pytest.approx(a["bodies"]["Sun"]["longitude"], abs=0.001)
    assert c["meta"]["datetime_utc"] == a["meta"]["datetime_utc"]
    assert c["meta"]["timezone"] == a["meta"]["timezone"]
    assert c["meta"]["location"]["latitude"] == pytest.approx(a["meta"]["location"]["latitude"], abs=1e-4)
    assert c["meta"]["location"]["longitude"] == pytest.approx(a["meta"]["location"]["longitude"], abs=1e-4)


def test_cast_davison_utc_fallback_where_no_zone(tmp_path, monkeypatch):
    from timezonefinder import TimezoneFinder
    monkeypatch.setattr(TimezoneFinder, "timezone_at", lambda self, **kw: None)
    a = json.loads(EXAMPLE.read_text()); b = json.loads(PARTNER.read_text())
    c = cp.cast_davison(NATAL, a, b, tmp_path / "utc.json")
    m = c["meta"]
    assert m["timezone"] == "UTC"
    assert "davison_timezone_utc" in m["flags"]
    when, _, _ = cp.davison_inputs(a, b)
    assert m["datetime_local"] == when.strftime("%Y-%m-%dT%H:%M:%S")
    assert m["datetime_utc"] == when.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_cast_davison_untimed_side_casts_at_noon(tmp_path):
    a = json.loads(EXAMPLE.read_text()); b = json.loads(PARTNER.read_text())
    b["meta"]["time_unknown"] = True; b["angles"] = None; b["houses"] = None
    c = cp.cast_davison(NATAL, a, b, tmp_path / "untimed.json")
    assert c["meta"]["time_unknown"] is True
    assert c["angles"] is None and c["houses"] is None
    assert "time_unknown" in c["meta"]["flags"]
    assert c["meta"]["chart_type"] == "davison"
    # Not the mean instant itself: local noon at the midpoint place on the mean instant's local date.
    when, _, _ = cp.davison_inputs(a, b)
    local_date = when.astimezone(ZoneInfo(c["meta"]["timezone"])).strftime("%Y-%m-%d")
    assert local_date == "1989-04-09"
    assert c["meta"]["datetime_local"] == f"{local_date}T12:00:00"
