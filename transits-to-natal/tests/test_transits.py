import csv
import datetime as dt

import swisseph as swe

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
    assert set(hit) == {"date", "utc_offset", "transit", "aspect", "natal", "orb", "applying", "retrograde"}
    assert hit["date"] == dt.date(2026, 4, 16)
    assert hit["utc_offset"] == "-07:00"
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
    tr.write_csv(rows, out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "Date,Time,UTC Offset,Transit,Aspect,Natal,Orb (°),Applying,Retrograde"
    assert lines[1].startswith("2026-04-15,12:00,-07:00,Mars,Sextile,Pluto,")
    assert len(lines) == 4


def test_csv_offset_follows_dst_per_row(tmp_path):
    # 2026-10-28 to 2026-11-03 in New York: EDT (-04:00) until Nov 1, EST (-05:00) after.
    chart = {"meta": {"time_unknown": True, "timezone": "America/New_York"}, "bodies": {}, "angles": None}
    sky = tr.sky_at(dt.date(2026, 10, 31), "America/New_York", ["Pluto"])
    chart["bodies"]["Pluto"] = {"longitude": sky["Pluto"]["longitude"]}  # Pluto barely moves, so every day hits
    rows = list(tr.scan(chart, dt.date(2026, 10, 28), dt.date(2026, 11, 3), ["Pluto"]))
    out = tmp_path / "dst.csv"
    tr.write_csv(rows, out)
    with open(out, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames[0] == "Date"
        parsed = list(reader)
    assert {r["UTC Offset"] for r in parsed} == {"-04:00", "-05:00"}
    assert all(r["Time"] == "12:00" for r in parsed)
    by_date = {r["Date"]: r["UTC Offset"] for r in parsed}
    assert by_date["2026-10-31"] == "-04:00"
    assert by_date["2026-11-01"] == "-05:00"


def test_sidereal_lahiri_shifts_saturn_by_ayanamsa():
    date = dt.date(2026, 4, 16)
    trop = tr.sky_at(date, "UTC", ["Saturn"])["Saturn"]["longitude"]
    sid = tr.sky_at(date, "UTC", ["Saturn"], zodiac="sidereal_lahiri")["Saturn"]["longitude"]
    # Lahiri ayanamsa is roughly 24° in the 2020s (24.2° in 2026).
    assert 23.5 < (trop - sid) % 360 < 24.5
    # and the chart's meta.zodiac drives hits_for_day the same way
    chart = {"meta": {"time_unknown": True, "timezone": "UTC", "zodiac": "sidereal_lahiri"},
             "bodies": {"Saturn": {"longitude": sid}}, "angles": None}
    hits = tr.hits_for_day(date, chart, ["Saturn"])
    assert any(h["transit"] == "Saturn" and h["aspect"] == "Conjunction" and h["orb"] < 0.001 for h in hits)


def test_mean_node_matches_swisseph():
    date = dt.date(2026, 4, 16)
    jd = tr.noon_jd(date, "UTC")
    (expected, *_), _ = swe.calc_ut(jd, swe.MEAN_NODE, tr.FLAGS)
    got = tr.sky_at(date, "UTC", ["Node"], node="mean")["Node"]["longitude"]
    assert abs(got - expected % 360) < 1e-9
    true_node = tr.sky_at(date, "UTC", ["Node"])["Node"]["longitude"]
    assert abs(got - true_node) > 0.01  # true and mean node do differ


def test_main_rejects_end_before_start(tmp_path, capsys):
    chart = tmp_path / "chart.json"
    chart.write_text("{}", encoding="utf-8")
    assert tr.main([str(chart), "--start", "2026-04-16", "--end", "2026-04-15"]) == 1
    assert "--end must not be before --start" in capsys.readouterr().err


def test_aspect_table_and_orb_are_the_documented_constants():
    assert tr.ASPECTS == {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Quincunx": 150, "Opposition": 180}
    assert tr.ORB == 1.0
