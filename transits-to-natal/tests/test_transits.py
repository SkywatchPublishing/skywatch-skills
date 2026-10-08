import datetime as dt

import transits as tr


def test_default_bodies_are_slow():
    assert tr.DEFAULT_BODIES == ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Chiron", "Node"]


def test_targets_include_angles_only_when_time_known():
    chart = {"meta": {"time_unknown": False}, "bodies": {"Sun": {"longitude": 10.0}},
             "angles": {"ascendant": 50.0, "mc": 320.0, "descendant": 230.0, "ic": 140.0}}
    assert tr.natal_targets(chart) == {"Sun": 10.0, "Ascendant": 50.0, "MC": 320.0, "Descendant": 230.0, "IC": 140.0}
    chart["meta"]["time_unknown"] = True
    chart["angles"] = None
    assert tr.natal_targets(chart) == {"Sun": 10.0}


def test_hits_for_one_day_against_known_sky():
    # Mars sextile Pluto was exact to 0.002 at noon Pacific on 2026-04-16 (astrology-ephemeris example row 30).
    # Treat natal Pluto as a fixed point at the transiting Pluto longitude of that moment and look for Mars.
    chart = {"meta": {"time_unknown": True, "timezone": "America/Los_Angeles"}, "bodies": {}, "angles": None}
    sky = tr.sky_at(dt.date(2026, 4, 16), "America/Los_Angeles", ["Mars", "Pluto"])
    chart["bodies"]["Pluto"] = {"longitude": sky["Pluto"]["longitude"]}
    hits = tr.hits_for_day(dt.date(2026, 4, 16), chart, ["Mars"])
    assert any(h["transit"] == "Mars" and h["aspect"] == "Sextile" and h["natal"] == "Pluto" and h["orb"] <= 0.01
               for h in hits)
    hit = next(h for h in hits if h["transit"] == "Mars" and h["natal"] == "Pluto")
    assert set(hit) == {"date", "transit", "aspect", "natal", "orb", "applying", "retrograde"}
    assert hit["date"] == dt.date(2026, 4, 16)
    assert hit["retrograde"] is False


def test_applying_from_transit_speed_only():
    assert tr.is_applying(lon_t=118.0, speed_t=0.5, lon_n=0.0, angle=120) is True
    assert tr.is_applying(lon_t=122.0, speed_t=0.5, lon_n=0.0, angle=120) is False
    # retrograde body past exact is closing again
    assert tr.is_applying(lon_t=122.0, speed_t=-0.5, lon_n=0.0, angle=120) is True
    # other side of the natal point (natal ahead of transit)
    assert tr.is_applying(lon_t=0.0, speed_t=0.5, lon_n=118.0, angle=120) is False
    assert tr.is_applying(lon_t=0.0, speed_t=0.5, lon_n=122.0, angle=120) is True
    # stationary transit: undecidable
    assert tr.is_applying(lon_t=118.0, speed_t=0.0, lon_n=0.0, angle=120) is None


def test_scan_and_write_csv(tmp_path):
    chart = {"meta": {"time_unknown": True, "timezone": "America/Los_Angeles"}, "bodies": {}, "angles": None}
    sky = tr.sky_at(dt.date(2026, 4, 16), "America/Los_Angeles", ["Pluto"])
    chart["bodies"]["Pluto"] = {"longitude": sky["Pluto"]["longitude"]}
    rows = list(tr.scan(chart, dt.date(2026, 4, 15), dt.date(2026, 4, 17), ["Mars"]))
    assert [r["date"] for r in rows] == [dt.date(2026, 4, 15), dt.date(2026, 4, 16), dt.date(2026, 4, 17)]
    out = tmp_path / "t.csv"
    tr.write_csv(rows, out, chart)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# noon in America/Los_Angeles (UTC-07:00)"
    assert lines[1] == "Date,Transit,Aspect,Natal,Orb (°),Applying,Retrograde"
    assert lines[2].startswith("2026-04-15,Mars,Sextile,Pluto,")
    assert len(lines) == 5
