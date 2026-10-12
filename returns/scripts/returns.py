#!/usr/bin/env python3
"""
Cast return charts (solar, lunar, Mars, Jupiter, Saturn, Uranus, Chiron) for a date range.

Usage:
    python returns.py chart.json --body sun --start 2027-01-01 --end 2027-12-31 --city "Austin, TX"
    python returns.py chart.json --body moon --start 2027-01-01 --end 2027-03-31 --geonameid 5128581
    python returns.py chart.json --start 2027-01-01 --end 2027-12-31            # natal place, flagged

Each return is cast by the sibling natal-chart script, so the output files are ordinary chart.json
files that chart-wheel, transits-to-natal and synastry read unchanged. Exit 2 means an ambiguous
city (candidates printed); re-run with --geonameid.
"""
import argparse
import datetime as dt
import json
import math
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

for _ephe in (Path(__file__).resolve().parents[1] / "ephe", Path(__file__).resolve().parents[2] / "natal-chart" / "ephe"):
    if (_ephe / "seas_18.se1").exists():
        swe.set_ephe_path(str(_ephe))
        break

BODIES = {
    "sun": ("Sun", swe.SUN), "moon": ("Moon", swe.MOON), "mars": ("Mars", swe.MARS),
    "jupiter": ("Jupiter", swe.JUPITER), "saturn": ("Saturn", swe.SATURN),
    "uranus": ("Uranus", swe.URANUS), "chiron": ("Chiron", swe.CHIRON),
}
FLAGS = swe.FLG_SWIEPH
# Lahiri is the project-wide ayanamsa (natal-chart casts sidereal charts with it). For the
# precession correction any ayanamsa would do: they differ by a constant, so the drift between
# two moments is the same.
swe.set_sid_mode(swe.SIDM_LAHIRI)


def wrapped(lon: float, target: float) -> float:
    """Signed difference lon - target in (-180, 180]."""
    return ((lon - target + 180.0) % 360.0) - 180.0


def longitude(jd: float, body: int, sidereal: bool = False) -> float:
    flags = FLAGS | (swe.FLG_SIDEREAL if sidereal else 0)
    return swe.calc_ut(jd, body, flags)[0][0]


def precession_shift(natal_jd: float, jd: float) -> float:
    """Ayanamsa drift between two moments (Lahiri), in degrees; add to the tropical target."""
    return swe.get_ayanamsa_ut(jd) - swe.get_ayanamsa_ut(natal_jd)


def find_returns(body: int, target: float, start: dt.date, end: dt.date, sidereal: bool = False,
                 shift_fn=None) -> list[float]:
    """Julian days (UT) at which `body` crosses `target` longitude between start 00:00 and end 24:00 UT.

    Samples daily, detects sign changes of the wrapped difference (ignoring the 180° wrap), and
    bisects each to about 1e-10 day. Retrograde loops give one hit per crossing. `shift_fn(jd)`,
    when given, is added to the target at each evaluation (precession correction).

    Limitation: two crossings within one daily sample (a station within a day of the target
    longitude) leave the sign unchanged and both are missed.
    """
    def diff(jd: float) -> float:
        t = target + (shift_fn(jd) if shift_fn else 0.0)
        return wrapped(longitude(jd, body, sidereal), t)

    jd = swe.julday(start.year, start.month, start.day, 0.0)
    last = swe.julday(end.year, end.month, end.day, 24.0)
    hits = []
    prev = diff(jd)
    while jd < last:
        nxt = min(jd + 1.0, last)
        cur = diff(nxt)
        if prev == 0.0:
            hits.append(jd)
        elif (prev < 0 < cur or prev > 0 > cur) and abs(cur - prev) < 180.0:
            lo, hi, flo = jd, nxt, prev
            for _ in range(60):
                mid = (lo + hi) / 2
                fm = diff(mid)
                if (fm < 0) == (flo < 0):
                    lo, flo = mid, fm
                else:
                    hi = mid
            hits.append((lo + hi) / 2)
        jd, prev = nxt, cur
    if prev == 0.0:
        hits.append(jd)
    return hits


# --- delegation to natal-chart --------------------------------------------------------

SCHEMA_VERSION = 1
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
NATAL_MISSING = "returns needs the natal-chart skill installed beside it to cast return charts"


def sign_of(lon: float) -> tuple[str, float]:
    lon %= 360
    return SIGNS[int(lon // 30)], lon % 30


def format_degree(lon: float) -> str:
    # Round the whole longitude to the nearest arc-minute first so a value a
    # hair under a sign boundary rolls over into the next sign (never "30°00'").
    total_minutes = round(lon % 360 * 60) % (360 * 60)
    sign = SIGNS[total_minutes // (30 * 60)]
    whole, minutes = divmod(total_minutes % (30 * 60), 60)
    return f"{whole}°{minutes:02d}' {sign}"


def find_natal_script() -> Path | None:
    """The sibling natal-chart script: beside this skill, then the user and project skill folders."""
    rel = Path("natal-chart") / "scripts" / "natal_chart.py"
    candidates = [
        Path(__file__).resolve().parents[2] / rel,
        Path.home() / ".claude" / "skills" / rel,
        Path.cwd() / ".claude" / "skills" / rel,
    ]
    return next((c for c in candidates if c.is_file()), None)


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on usage errors; that code is passed through from natal-chart, so exit 1."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        sys.exit(1)


class DelegationFailed(Exception):
    def __init__(self, code: int, stdout: str, stderr: str):
        super().__init__(f"natal_chart.py exited {code}")
        self.code, self.stdout, self.stderr = code, stdout, stderr


def load_chart(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        try:
            chart = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(chart, dict):
        raise ValueError(f"{path}: expected a chart object")
    if chart.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{path}: expected schema_version {SCHEMA_VERSION}, got {chart.get('schema_version')!r}")
    if not isinstance(chart.get("meta"), dict) or not chart["meta"].get("name"):
        raise ValueError(f"{path}: missing meta.name")
    if not isinstance(chart.get("bodies"), dict) or not chart["bodies"]:
        raise ValueError(f"{path}: missing bodies")
    return chart


def chart_type_for(key: str) -> str:
    return {"sun": "solar_return", "moon": "lunar_return"}.get(key, f"{key}_return")


def local_datetime(jd: float, tz: ZoneInfo) -> dt.datetime:
    y, m, d, h = swe.revjul(jd)
    seconds = round(h * 3600)
    utc = dt.datetime(y, m, d, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)
    return utc.astimezone(tz)


def _is_sidereal(meta: dict) -> bool:
    return str(meta.get("zodiac", "")).startswith("sidereal")


def _settings_args(meta: dict) -> list[str]:
    """The natal chart's house system, zodiac and node, as natal-chart flags."""
    return ["--houses", meta.get("house_system") or "placidus",
            "--zodiac", "sidereal" if _is_sidereal(meta) else "tropical",
            "--node", meta.get("node", "true")]


def _run_natal(natal_script: Path, args: list[str]) -> None:
    r = subprocess.run([sys.executable, "-I", str(natal_script), *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise DelegationFailed(r.returncode, r.stdout, r.stderr)
    sys.stderr.write(r.stderr)


def probe_place(natal_script: Path, chart: dict, place_args: list[str]) -> str:
    """Cast the natal chart once at the given place and return the timezone natal-chart resolved.

    This also surfaces an ambiguous or unknown city (exit 2 / 1) before any return is searched.
    """
    meta = chart["meta"]
    with tempfile.TemporaryDirectory(prefix="returns-") as tmp:
        out = Path(tmp) / "probe.json"
        _run_natal(natal_script, ["--name", meta["name"], "--date", meta["datetime_local"][:10],
                                  *place_args, *_settings_args(meta), "--out", str(out)])
        return json.loads(out.read_text(encoding="utf-8"))["meta"]["timezone"]


def resolve_timezone(natal_script: Path, chart: dict, place_args: list[str]) -> str:
    """IANA zone of the return place, needed before natal-chart runs to express the moment in local time."""
    if "--tz" in place_args:
        return place_args[place_args.index("--tz") + 1]
    if "--lat" in place_args:
        from timezonefinder import TimezoneFinder
        lat = float(place_args[place_args.index("--lat") + 1])
        lon = float(place_args[place_args.index("--lon") + 1])
        tz = TimezoneFinder().timezone_at(lat=lat, lng=lon)
        if not tz:
            raise ValueError("No timezone found for those coordinates; pass --tz")
        return tz
    return probe_place(natal_script, chart, place_args)


def cast_return(natal_script: Path, chart: dict, jd: float, place_args: list[str], tz_name: str, out: Path,
                body_key: str, extra_flags: list[str]) -> dict:
    """Run natal-chart for one return moment and rewrite the derived-chart keys."""
    local = local_datetime(jd, ZoneInfo(tz_name))
    meta = chart["meta"]
    # At a DST fall-back the wall-clock time repeats; --fold 1 tells natal-chart this is the second one.
    fold = ["--fold", "1"] if local.fold == 1 else []
    _run_natal(natal_script, ["--name", meta["name"], "--date", local.date().isoformat(),
                              "--time", local.time().replace(microsecond=0).isoformat(), *fold,
                              *place_args, *_settings_args(meta), "--out", str(out)])
    result = json.loads(out.read_text(encoding="utf-8"))
    if abs(result["meta"]["julian_day_ut"] - jd) * 86400 > 2:
        raise ValueError(f"{out}: natal-chart cast {result['meta']['datetime_utc']} but the return is at "
                         f"{local.astimezone(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} (timezone {tz_name}); "
                         "the local time was reinterpreted, probably across a DST change")
    result["meta"]["chart_type"] = chart_type_for(body_key)
    result["meta"]["derived_from"] = [meta["name"]]
    result["meta"]["return_utc"] = local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result["meta"]["flags"] = sorted(set(result["meta"]["flags"]) | set(extra_flags))
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


# --- summary --------------------------------------------------------------------------

def _natal_time_unknown(chart: dict) -> bool:
    meta = chart["meta"]
    return bool(meta.get("time_unknown")) or "time_unknown" in (meta.get("flags") or [])


def _compare(label: str, ret_lon: float, natal_lon: float | None, natal_note: str) -> str:
    ret_sign = sign_of(ret_lon)[0]
    if natal_lon is None:
        return f"{label} {format_degree(ret_lon)} ({natal_note})"
    natal_sign = sign_of(natal_lon)[0]
    verdict = "same sign as natal" if ret_sign == natal_sign else f"natal {natal_sign}"
    return f"{label} {format_degree(ret_lon)} ({verdict})"


def render_summary(natal: dict, body_key: str, returns: list[tuple[Path, dict]], precessed: bool) -> str:
    body_name = BODIES[body_key][0]
    meta = natal["meta"]
    untimed = _natal_time_unknown(natal)
    natal_angles = natal.get("angles") if not untimed else None
    natal_moon = natal["bodies"]["Moon"]["longitude"]
    lines = [f"# {body_name} returns for {meta['name']}", ""]
    lines.append(f"Natal {body_name} {format_degree(natal['bodies'][body_name]['longitude'])}"
                 + (" (precession-corrected target)" if precessed else "") + ".")
    if natal_angles:
        lines.append(f"Natal Ascendant {format_degree(natal_angles['ascendant'])}, "
                     f"natal Moon {format_degree(natal_moon)}.")
    else:
        lines.append("Natal time unknown: natal angles are unavailable and the natal Moon position is uncertain.")
    lines += ["", "| Return | UTC moment | Local time | Place | ASC | MC | DSC | IC | Return Moon sign |",
              "|---|---|---|---|---|---|---|---|---|"]
    for path, c in returns:
        m, a = c["meta"], c["angles"]
        lines.append(f"| {path.stem} | {m['return_utc']} | {m['datetime_local']} ({m['timezone']}) | {m['location']['name']} | "
                     f"{format_degree(a['ascendant'])} | {format_degree(a['mc'])} | {format_degree(a['descendant'])} | "
                     f"{format_degree(a['ic'])} | {c['bodies']['Moon']['formatted']} |")
    lines.append("")
    for path, c in returns:
        asc = _compare("Ascendant", c["angles"]["ascendant"],
                       natal_angles["ascendant"] if natal_angles else None, "natal Ascendant unknown")
        moon = _compare("Moon", c["bodies"]["Moon"]["longitude"],
                        None if untimed else natal_moon, "natal Moon uncertain")
        lines.append(f"- {path.stem}: {asc}; {moon}.")
    flags = sorted({f for _, c in returns for f in c["meta"]["flags"]})
    if flags:
        lines += ["", "Flags: " + ", ".join(flags)]
    return "\n".join(lines) + "\n"


# --- command line ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("chart", type=Path, help="natal chart.json")
    p.add_argument("--body", default="sun", choices=list(BODIES))
    p.add_argument("--start", required=True, type=dt.date.fromisoformat)
    p.add_argument("--end", required=True, type=dt.date.fromisoformat)
    p.add_argument("--city", help='return place, e.g. "Austin, TX"')
    p.add_argument("--geonameid", type=int)
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)
    p.add_argument("--tz", help="IANA timezone override for --lat/--lon")
    p.add_argument("--precessed", action="store_true", help="correct the target for precession since birth (Lahiri)")
    p.add_argument("--out-dir", type=Path, default=Path("."))
    return p


def place_arguments(args, chart: dict) -> tuple[list[str], list[str]]:
    """natal-chart place flags for the return place, plus the flags the choice adds to every return."""
    if args.city or args.geonameid or args.lat is not None or args.lon is not None:
        if args.city:
            return ["--city", args.city], []
        if args.geonameid:
            return ["--geonameid", str(args.geonameid)], []
        place = ["--lat", str(args.lat), "--lon", str(args.lon)]
        if args.tz:
            place += ["--tz", args.tz]
        return place, []
    loc = chart["meta"]["location"]
    if loc.get("geonameid"):
        return ["--geonameid", str(loc["geonameid"])], ["return_place_natal"]
    return ["--lat", str(loc["latitude"]), "--lon", str(loc["longitude"]), "--tz", chart["meta"]["timezone"]], \
        ["return_place_natal"]


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.end < args.start:
        parser.error(f"--end {args.end} is before --start {args.start}")
    if args.city and args.geonameid:
        parser.error("pass either --city or --geonameid, not both")
    if (args.city or args.geonameid) and (args.lat is not None or args.lon is not None):
        parser.error("pass exactly one of --city, --geonameid, or --lat/--lon, not a mix")
    if (args.lat is None) != (args.lon is None):
        parser.error("--lat and --lon must be given together")
    if args.tz and args.lat is None:
        parser.error("--tz only applies with --lat/--lon")

    natal_script = find_natal_script()
    if natal_script is None:
        print(NATAL_MISSING, file=sys.stderr)
        return 1

    try:
        chart = load_chart(args.chart)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    if chart["meta"].get("datetime_local") is None or chart["meta"].get("timezone") is None:
        print(f"returns: this chart has no real moment (chart_type {chart['meta'].get('chart_type', 'natal')}); "
              "returns need a natal, return or Davison chart", file=sys.stderr)
        return 1
    body_name, body_id = BODIES[args.body]
    if body_name not in chart["bodies"]:
        hint = " (flagged chiron_unavailable)" if args.body == "chiron" else ""
        print(f"{args.chart}: no {body_name} in bodies{hint}; cannot cast {body_name} returns", file=sys.stderr)
        return 1
    meta = chart["meta"]
    if args.precessed and _is_sidereal(meta):
        print("--precessed applies to tropical charts only; a sidereal chart's returns are already precession-free",
              file=sys.stderr)
        return 1
    natal_jd = meta["julian_day_ut"]
    target = chart["bodies"][body_name]["longitude"]

    place_args, extra_flags = place_arguments(args, chart)
    if _natal_time_unknown(chart):
        extra_flags.append("natal_time_unknown")
    shift_fn = None
    if args.precessed:
        shift_fn = lambda jd: precession_shift(natal_jd, jd)  # noqa: E731
        extra_flags.append("precession_corrected")

    try:
        tz_name = resolve_timezone(natal_script, chart, place_args)
        if "--lat" in place_args and "--tz" not in place_args:
            place_args += ["--tz", tz_name]   # every cast uses this zone instead of looking it up again
        hits = find_returns(body_id, target, args.start, args.end, _is_sidereal(meta), shift_fn)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for jd in hits:
            local_date = local_datetime(jd, ZoneInfo(tz_name)).date().isoformat()
            base = f"{args.body}_return_{local_date}"
            out, n = args.out_dir / f"{base}.json", 1
            while out.exists():   # never overwrite: an earlier run, or a second crossing on the same day
                n += 1
                out = args.out_dir / f"{base}_{n}.json"
            if n > 1:
                print(f"Note: {base}.json already exists; writing {out.name} instead")
            results.append((out, cast_return(natal_script, chart, jd, place_args, tz_name, out, args.body, extra_flags)))
    except DelegationFailed as exc:
        # Exit 2 (ambiguous city) carries the candidate table on stdout; pass both through.
        sys.stdout.write(exc.stdout)
        sys.stderr.write(exc.stderr)
        return exc.code
    except subprocess.TimeoutExpired:
        print("natal_chart.py did not finish within 120 seconds", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    summary, n = args.out_dir / "returns_summary.md", 1
    while summary.exists():   # never overwrite, as with the charts
        n += 1
        summary = args.out_dir / f"returns_summary_{n}.md"
    if n > 1:
        print(f"Note: returns_summary.md already exists; writing {summary.name} instead")
    summary.write_text(render_summary(chart, args.body, results, args.precessed), encoding="utf-8")
    print(f"Wrote {len(results)} return chart(s), each with a _aspects.md aspect-grid sidecar, and {summary}")
    for flag in sorted(set(extra_flags)):
        print(f"Note: {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
