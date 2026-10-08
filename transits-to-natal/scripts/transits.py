#!/usr/bin/env python3
"""Daily snapshot of transiting aspects to a natal chart.json (schema_version 1).

One row per day (noon in the chart's timezone) per transiting body within 1° of an exact
aspect to a natal body or angle. Copies the aspect table and separation helper from
natal-chart/scripts/aspects.py rather than importing across skill folders.
"""
import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

# Ephemeris files: this skill's own ephe/ folder, else the sibling natal-chart/ephe/ when present.
# Without either, pyswisseph falls back to Moshier for the planets and Chiron is unavailable.
_HERE = Path(__file__).resolve().parents[1]
EPHE_CANDIDATES = [_HERE / "ephe", _HERE.parent / "natal-chart" / "ephe"]
EPHE_DIR = next((d for d in EPHE_CANDIDATES if (d / "seas_18.se1").exists()), EPHE_CANDIDATES[0])
swe.set_ephe_path(str(EPHE_DIR))

# Copied from natal-chart/scripts/aspects.py. Orb here is a flat 1° for every aspect.
ASPECTS = {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Quincunx": 150, "Opposition": 180}
ORB = 1.0

BODIES = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO, "Chiron": swe.CHIRON, "Node": swe.TRUE_NODE,
}
DEFAULT_BODIES = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Chiron", "Node"]
FAST_BODIES = ["Sun", "Mercury", "Venus", "Mars"]
ANGLE_NAMES = {"ascendant": "Ascendant", "mc": "MC", "descendant": "Descendant", "ic": "IC"}
FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED


def separation(lon1: float, lon2: float) -> float:
    d = abs(lon1 - lon2) % 360
    return min(d, 360 - d)


def natal_targets(chart: dict) -> dict[str, float]:
    """Every natal body longitude, plus the four angles unless the birth time is unknown."""
    targets = {name: body["longitude"] for name, body in chart["bodies"].items()}
    if not chart["meta"].get("time_unknown") and chart.get("angles"):
        for key, label in ANGLE_NAMES.items():
            targets[label] = chart["angles"][key]
    return targets


def noon_jd(date: dt.date, tz: str) -> float:
    local = dt.datetime.combine(date, dt.time(12, 0), tzinfo=ZoneInfo(tz))
    u = local.astimezone(dt.timezone.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600)


def sky_at(date: dt.date, tz: str, names: list[str], zodiac: str = "tropical",
           node: str = "true") -> dict[str, dict]:
    """{name: {longitude, speed}} at local noon. Chiron is omitted silently when its file is missing.
    zodiac: 'tropical' or 'sidereal_lahiri' (as chart.json spells it); node: 'true' or 'mean'."""
    jd = noon_jd(date, tz)
    flags = FLAGS
    if zodiac.startswith("sidereal"):
        # set_sid_mode is process-global, but harmless: FLG_SIDEREAL selects the zodiac per call.
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL
    out = {}
    for name in names:
        ident = BODIES[name]
        if name == "Node" and node == "mean":
            ident = swe.MEAN_NODE
        try:
            (lon, _lat, _dist, dlon, *_), _ = swe.calc_ut(jd, ident, flags)
        except swe.Error:
            if name == "Chiron":
                continue
            raise
        out[name] = {"longitude": lon % 360, "speed": dlon}
    return out


def is_applying(lon_t: float, speed_t: float, lon_n: float, angle: float) -> bool | None:
    """Closing on exact? Decided from the transiting body's motion alone (the natal point is fixed).
    Same signed form as natal-chart's aspects.applying() with the natal speed at 0."""
    if abs(speed_t) < 1e-9:
        return None
    delta = ((lon_t - lon_n + 180) % 360) - 180  # signed, in (-180, 180]
    target = angle if delta >= 0 else -angle  # nearest exact aspect on delta's side (0 stays 0)
    return (delta - target) * speed_t < 0


def hits_for_day(date: dt.date, chart: dict, names: list[str]) -> list[dict]:
    meta = chart["meta"]
    sky = sky_at(date, meta["timezone"], names, meta.get("zodiac", "tropical"), meta.get("node", "true"))
    targets = natal_targets(chart)
    offset = utc_offset_label(date, meta["timezone"])
    hits = []
    for t_name, pos in sky.items():
        for n_name, n_lon in targets.items():
            sep = separation(pos["longitude"], n_lon)
            for aspect, angle in ASPECTS.items():
                orb = abs(sep - angle)
                if orb <= ORB:
                    hits.append({
                        "date": date, "utc_offset": offset, "transit": t_name, "aspect": aspect, "natal": n_name,
                        "orb": round(orb, 3),
                        "applying": is_applying(pos["longitude"], pos["speed"], n_lon, angle),
                        "retrograde": pos["speed"] < 0,
                    })
                    break
    return hits


def scan(chart: dict, start: dt.date, end: dt.date, names: list[str]):
    """Yield hit rows for every day from start to end inclusive."""
    day = start
    while day <= end:
        yield from hits_for_day(day, chart, names)
        day += dt.timedelta(days=1)


def utc_offset_label(date: dt.date, tz: str) -> str:
    """UTC offset of local noon on `date` in `tz`, as '-04:00'. Computed per day so DST changes land on the right row."""
    off = dt.datetime.combine(date, dt.time(12, 0), tzinfo=ZoneInfo(tz)).utcoffset()
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    hours, rem = divmod(abs(total), 3600)
    return f"{sign}{hours:02d}:{rem // 60:02d}"


def _flag(value) -> str:
    return "" if value is None else ("yes" if value else "no")


CSV_HEADER = ["Date", "Time", "UTC Offset", "Transit", "Aspect", "Natal", "Orb (°)", "Applying", "Retrograde"]


def write_csv(rows, path: Path) -> None:
    """Header-clean CSV (no comment lines) so csv.DictReader and pandas.read_csv parse it as is.
    Time is always 12:00 local; UTC Offset is that noon's offset, carried on each row by hits_for_day."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        for r in rows:
            w.writerow([r["date"].isoformat(), "12:00", r["utc_offset"], r["transit"], r["aspect"], r["natal"],
                        f"{r['orb']:.3f}", _flag(r["applying"]), _flag(r["retrograde"])])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Daily transits to a natal chart.json, as CSV.")
    p.add_argument("chart", type=Path, help="chart.json written by natal_chart.py")
    p.add_argument("--start", required=True, type=dt.date.fromisoformat)
    p.add_argument("--end", required=True, type=dt.date.fromisoformat)
    p.add_argument("--fast", action="store_true",
                   help="also Sun, Mercury, Venus, Mars (many rows over long ranges; a noon sample can "
                        "also miss an exact hit on a fast day)")
    p.add_argument("--moon", action="store_true",
                   help="also the Moon, noon-snapshot hits only: it moves about 13 degrees a day, so one "
                        "sample with a 1 degree orb misses most Moon aspects; use the astrology-ephemeris "
                        "skill for exact Moon times")
    p.add_argument("--out", type=Path, help="default transits_<start>_<end>.csv")
    a = p.parse_args(argv)
    if a.end < a.start:
        print("--end must not be before --start", file=sys.stderr)
        return 1
    chart = json.loads(a.chart.read_text(encoding="utf-8"))
    if chart.get("schema_version") != 1:
        print(f"{a.chart}: unsupported schema_version {chart.get('schema_version')!r}", file=sys.stderr)
        return 1
    names = list(DEFAULT_BODIES)
    if a.fast:
        names = FAST_BODIES + names
    if a.moon:
        names = ["Moon"] + names
    if "Chiron" in names and not (EPHE_DIR / "seas_18.se1").exists():
        print("Chiron skipped: seas_18.se1 not found (run natal-chart/scripts/fetch_ephemeris.py)", file=sys.stderr)
        names.remove("Chiron")
    out = a.out or Path(f"transits_{a.start.isoformat()}_{a.end.isoformat()}.csv")
    rows = list(scan(chart, a.start, a.end, names))
    write_csv(rows, out)
    print(f"Wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
