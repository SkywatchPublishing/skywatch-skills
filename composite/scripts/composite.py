#!/usr/bin/env python3
"""
Composite charts: the midpoint composite and the Davison relationship chart.

Midpoint: every body shared by the two charts is placed at the midpoint of its two positions on
the shorter arc; the composite MC is the midpoint of the two MCs and the houses are derived from
it at a reference latitude (default: chart A's place) with pyswisseph's ARMC house routine. There
is no real sky behind it, so speeds are averaged, ``retrograde`` is false and every aspect has
``applying: null``. If either side has an unknown time the composite has no angles or houses.

Davison: the mean of the two UTC instants cast at the great-circle midpoint of the two
birthplaces; a real moment, delegated to the sibling natal-chart script.

The small helpers (sign formatting, house placement, the aspect table and ``find_aspects``) are
copied from natal-chart/scripts, as synastry does; nothing is imported across skill folders.

Usage:
    python composite.py --a chartA.json --b chartB.json [--method midpoint|davison] [--out composite.json]
    python composite.py --a-birth '--name Ada --date 1990-06-15 --time 14:30 --geonameid 2643743' \
                        --b-birth '--name Bob --date 1988-02-02 --geonameid 5128581' --city "Paris, FR"

``--a-birth``/``--b-birth`` are shell-style strings handed verbatim to the natal-chart script.
``--city``/``--geonameid``/``--lat --lon`` set the reference place for midpoint houses (default:
chart A's place); a Davison chart's place is computed, so they are rejected there.
Exit codes: 0 success; 1 bad arguments or inputs; 2 an ambiguous city (candidates on stdout).
"""

import argparse
import datetime as dt
import itertools
import json
import math
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

for _ephe in (Path(__file__).resolve().parents[1] / "ephe",
              Path(__file__).resolve().parents[2] / "natal-chart" / "ephe"):
    if (_ephe / "seas_18.se1").exists():
        swe.set_ephe_path(str(_ephe))
        break

SCHEMA_VERSION = 1

# --- copied from natal-chart/scripts/chart.py -------------------------------------------

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
BODY_ORDER = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus",
              "Neptune", "Pluto", "Chiron", "Node"]
ANGLE_NAMES = ("Ascendant", "MC")


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


def house_of(lon: float, cusps: list[float]) -> int:
    lon %= 360
    for i in range(12):
        start, end = cusps[i], cusps[(i + 1) % 12]
        inside = start <= lon < end if start < end else (lon >= start or lon < end)
        if inside:
            return i + 1
    return 12


# --- copied from natal-chart/scripts/aspects.py (``applying`` dropped: a composite does not move)

ASPECTS = {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Quincunx": 150, "Opposition": 180}
ORBS = {"Conjunction": 8.0, "Opposition": 8.0, "Square": 8.0, "Trine": 8.0, "Sextile": 6.0, "Quincunx": 3.0}
LUMINARY_BONUS = 2.0
LUMINARIES = {"Sun", "Moon"}


def max_orb(aspect: str, b1: str, b2: str, reduction: float = 0.0) -> float:
    bonus = LUMINARY_BONUS if (b1 in LUMINARIES or b2 in LUMINARIES) else 0.0
    return ORBS[aspect] + bonus - reduction


def separation(lon1: float, lon2: float) -> float:
    d = abs(lon1 - lon2) % 360
    return min(d, 360 - d)


def find_aspects(bodies: dict[str, dict], reduction: float = 0.0, pairs=None) -> list[dict]:
    """bodies: name -> {longitude}. pairs: optional iterable of (name1, name2); default all combinations.
    Every hit carries ``applying: None`` because composite positions have no motion."""
    pairs = pairs if pairs is not None else itertools.combinations(bodies, 2)
    found = []
    for n1, n2 in pairs:
        p1, p2 = bodies[n1], bodies[n2]
        sep = separation(p1["longitude"], p2["longitude"])
        for aspect, angle in ASPECTS.items():
            limit = max_orb(aspect, n1, n2, reduction)
            orb = abs(sep - angle)
            if orb <= limit:
                found.append({"body1": n1, "body2": n2, "aspect": aspect, "angle": angle,
                              "orb": round(orb, 3), "max_orb": limit, "applying": None})
                break
    return found


# --- copied from natal-chart/scripts/grid.py ------------------------------------------------

SYMBOLS = {"Conjunction": "☌", "Sextile": "⚹", "Square": "□", "Trine": "△", "Quincunx": "⚻", "Opposition": "☍"}


def _cell(a: dict) -> str:
    suffix = {True: "a", False: "s", None: ""}[a["applying"]]
    return f"{SYMBOLS[a['aspect']]} {a['orb']:.1f}{suffix}"


def render_grid(chart: dict) -> str:
    names = list(chart["bodies"])
    if chart.get("angles"):
        names += ["Ascendant", "MC"]
    lookup = {}
    for a in chart["aspects"]:
        lookup[(a["body1"], a["body2"])] = lookup[(a["body2"], a["body1"])] = _cell(a)
    lines = ["| | " + " | ".join(names) + " |", "|" + "---|" * (len(names) + 1)]
    for row in names:
        cells = [lookup.get((row, col), "") for col in names]
        lines.append(f"| {row} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


# --- midpoint geometry ---------------------------------------------------------------------

def midpoint(a: float, b: float) -> float:
    """Midpoint on the shorter arc, in [0, 360); symmetric in its arguments.

    Computed from the sorted pair so swapping A and B gives the identical float. An exactly
    antipodal pair has no shorter arc; the tie goes to ``min(a, b) + 90`` in either order.
    """
    lo, hi = sorted((a % 360.0, b % 360.0))
    diff = hi - lo
    if diff == 180.0:
        return (lo + 90.0) % 360.0
    if diff < 180.0:
        return lo + diff / 2.0
    return (hi + (360.0 - diff) / 2.0) % 360.0


def obliquity(jd: float) -> float:
    return swe.calc_ut(jd, swe.ECL_NUT)[0][0]


def armc_from_mc(mc: float, eps: float) -> float:
    m, e = math.radians(mc), math.radians(eps)
    return math.degrees(math.atan2(math.sin(m) * math.cos(e), math.cos(m))) % 360.0


HOUSE_CODES = {"placidus": b"P", "koch": b"K", "equal": b"E", "porphyry": b"O", "whole_sign": b"W"}


def requested_house_system(meta: dict) -> str:
    """The house system the user asked for. ``house_system`` is the one used, which is whole-sign
    after a polar fallback and null when untimed; charts written before ``house_system_requested``
    existed fall back to it, then to Placidus."""
    return meta.get("house_system_requested") or meta.get("house_system") or "placidus"


def houses_from_mc(mc: float, latitude: float, eps: float, system: str) -> dict:
    """Cusps and angles for a given MC at a latitude; whole-sign fallback at polar latitudes."""
    flags = []
    armc = armc_from_mc(mc, eps)
    try:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES[system])
    except swe.Error:
        cusps, ascmc = swe.houses_armc(armc, latitude, eps, HOUSE_CODES["whole_sign"])
        system, flags = "whole_sign", ["polar_fallback_whole_sign"]
    asc, mc_out = ascmc[0] % 360, ascmc[1] % 360
    return {"system": system, "cusps": [c % 360 for c in cusps[:12]],
            "angles": {"ascendant": asc, "mc": mc_out, "descendant": (asc + 180) % 360, "ic": (mc_out + 180) % 360},
            "flags": flags}


# --- midpoint composite --------------------------------------------------------------------

def _time_unknown(chart: dict) -> bool:
    # Unlike synastry's copy, missing angles also count as untimed so the MC lookup cannot KeyError.
    meta = chart.get("meta") or {}
    return (bool(meta.get("time_unknown")) or "time_unknown" in (meta.get("flags") or [])
            or not chart.get("angles"))


def midpoint_chart(a: dict, b: dict, reference: dict, house_system: str) -> dict:
    """A midpoint composite of two chart.json dicts as a chart.json dict.

    ``reference`` is a contract ``location`` object whose latitude places the houses.
    Raises ValueError when the two charts disagree on zodiac or lunar node.
    """
    ma, mb = a["meta"], b["meta"]
    for key in ("zodiac", "node"):
        if ma.get(key) != mb.get(key):
            raise ValueError(f"charts disagree on {key}: {ma.get(key)!r} vs {mb.get(key)!r}; "
                             f"recast one of them so both match")

    flags: list[str] = []
    untimed = _time_unknown(a) or _time_unknown(b)
    jd = (ma["julian_day_ut"] + mb["julian_day_ut"]) / 2.0

    angles = houses = None
    if untimed:
        flags += ["time_unknown", "moon_uncertain"]
    else:
        mc = midpoint(a["angles"]["mc"], b["angles"]["mc"])
        derived = houses_from_mc(mc, reference["latitude"], obliquity(jd), house_system)
        flags += derived["flags"]
        angles = {k: round(v, 4) for k, v in derived["angles"].items()}
        houses = {"system": derived["system"], "cusps": [round(c, 4) for c in derived["cusps"]]}

    bodies = {}
    for name in BODY_ORDER:
        if name not in a["bodies"] or name not in b["bodies"]:
            continue
        pa, pb = a["bodies"][name], b["bodies"][name]
        lon = midpoint(pa["longitude"], pb["longitude"])
        sign, deg = sign_of(lon)
        bodies[name] = {
            "longitude": round(lon, 4), "sign": sign, "sign_degree": round(deg, 4),
            "formatted": format_degree(lon),
            "speed": round((pa["speed"] + pb["speed"]) / 2.0, 4), "retrograde": False,
            "house": house_of(lon, houses["cusps"]) if houses else None,
            "latitude": round((pa["latitude"] + pb["latitude"]) / 2.0, 4),
        }
    if "Chiron" not in bodies:
        flags.append("chiron_unavailable")

    aspect_input = {n: {"longitude": body["longitude"]} for n, body in bodies.items()}
    if angles:
        aspect_input["Ascendant"] = {"longitude": angles["ascendant"]}
        aspect_input["MC"] = {"longitude": angles["mc"]}
    pairs = [(x, y) for i, x in enumerate(aspect_input) for y in list(aspect_input)[i + 1:]
             if not (x in ANGLE_NAMES and y in ANGLE_NAMES)]

    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "name": f"{ma['name']} & {mb['name']}",
            "chart_type": "composite",
            "derived_from": [ma["name"], mb["name"]],
            "datetime_local": None,
            "timezone": None,
            "datetime_utc": None,
            "utc_offset": None,
            "julian_day_ut": round(jd, 7),
            "time_unknown": untimed,
            "moon_range": None,
            "location": reference,
            "zodiac": ma.get("zodiac", "tropical"),
            "house_system": houses["system"] if houses else None,
            "house_system_requested": house_system,
            "node": ma.get("node", "true"),
            "flags": flags,
            "source": {**(ma.get("source") or {}), "method": "midpoint"},
        },
        "angles": angles,
        "houses": houses,
        "bodies": bodies,
        "aspects": find_aspects(aspect_input, pairs=pairs),
    }


# --- Davison -------------------------------------------------------------------------------

def great_circle_midpoint(lat1, lon1, lat2, lon2) -> tuple[float, float]:
    """Midpoint of the shorter great-circle arc between two places, in degrees (lon in [-180, 180)).

    Raises ValueError for antipodal places: every great circle through them is equally short, so
    there is no unique midpoint.
    """
    p1, l1, p2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    bx = math.cos(p2) * math.cos(l2 - l1)
    by = math.cos(p2) * math.sin(l2 - l1)
    denom = math.sqrt((math.cos(p1) + bx) ** 2 + by ** 2)
    if denom < 1e-9:
        raise ValueError("birthplaces are antipodal; no unique midpoint")
    lat = math.atan2(math.sin(p1) + math.sin(p2), denom)
    lon = l1 + math.atan2(by, math.cos(p1) + bx)
    return math.degrees(lat), ((math.degrees(lon) + 540.0) % 360.0) - 180.0


def davison_inputs(a: dict, b: dict) -> tuple[dt.datetime, float, float]:
    """The Davison moment (mean of the two UTC instants) and place (great-circle midpoint)."""
    ta = dt.datetime.strptime(a["meta"]["datetime_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    tb = dt.datetime.strptime(b["meta"]["datetime_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    when = ta + (tb - ta) / 2
    la, lb = a["meta"]["location"], b["meta"]["location"]
    lat, lon = great_circle_midpoint(la["latitude"], la["longitude"], lb["latitude"], lb["longitude"])
    return when.replace(microsecond=0), lat, lon


# --- delegation to natal-chart (copied from synastry/scripts/synastry.py) --------------------

NATAL_MISSING = ("composite needs the natal-chart skill installed beside it to cast a Davison chart; "
                 "use --method midpoint instead")


def find_natal_script() -> Path | None:
    """The sibling natal-chart script: beside this skill, then the user and project skill folders."""
    rel = Path("natal-chart") / "scripts" / "natal_chart.py"
    candidates = [
        Path(__file__).resolve().parents[2] / rel,
        Path.home() / ".claude" / "skills" / rel,
        Path.cwd() / ".claude" / "skills" / rel,
    ]
    return next((c for c in candidates if c.is_file()), None)


PRINTED_NOTES: set[str] = set()


def forward_notes(stdout: str) -> None:
    """Print natal-chart's ``Note:`` lines, remembering them so main does not repeat the flag."""
    for line in stdout.splitlines():
        if line.startswith("Note:"):
            PRINTED_NOTES.add(line[len("Note:"):].strip())
            print(line)


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


def _is_sidereal(meta: dict) -> bool:
    """chart.json spells the zodiac "sidereal_lahiri"; natal-chart's --zodiac takes "sidereal".
    Copied from returns/scripts/returns.py."""
    return str(meta.get("zodiac", "")).startswith("sidereal")


def cast_davison(natal_script: Path, a: dict, b: dict, out: Path, grid: Path | None = None) -> dict:
    """Cast the Davison chart of two chart.json dicts through natal-chart, writing ``out`` and ``grid``
    (default: ``out`` with a ``.md`` suffix).

    The timezone comes from timezonefinder at the great-circle midpoint; where there is none
    (mid-ocean) the chart is cast in UTC and flagged ``davison_timezone_utc``.

    If either source has an unknown time, ``--time`` is omitted and natal-chart applies its own
    untimed convention: the chart is cast at local noon at the midpoint place on the local date of
    the mean instant (not at the mean of the two noons, and not at the mean instant itself), with
    ``time_unknown`` set and no angles or houses. natal-chart writes the aspect grid to ``grid``.

    Raises ValueError when the charts disagree on zodiac or node, or when the birthplaces are
    antipodal (no unique midpoint).
    """
    grid = grid or out.with_suffix(".md")
    ma, mb = a["meta"], b["meta"]
    for key in ("zodiac", "node"):
        if ma.get(key) != mb.get(key):
            raise ValueError(f"charts disagree on {key}: {ma.get(key)!r} vs {mb.get(key)!r}; "
                             f"recast one of them so both match")

    try:
        when, lat, lon = davison_inputs(a, b)
    except ValueError as exc:
        raise ValueError("birthplaces are antipodal; no unique midpoint") from exc
    from timezonefinder import TimezoneFinder
    tz = TimezoneFinder().timezone_at(lat=lat, lng=lon)
    extra_flags = []
    if not tz:
        tz, extra_flags = "UTC", ["davison_timezone_utc"]
    local = when.astimezone(ZoneInfo(tz))

    cmd = [sys.executable, "-I", str(natal_script),
           "--name", f"{ma['name']} & {mb['name']}",
           "--date", local.strftime("%Y-%m-%d")]
    if not (_time_unknown(a) or _time_unknown(b)):
        cmd += ["--time", local.strftime("%H:%M:%S")]
    cmd += ["--lat", f"{lat:.6f}", "--lon", f"{lon:.6f}", "--tz", tz,
            "--houses", requested_house_system(ma),
            "--zodiac", "sidereal" if _is_sidereal(ma) else "tropical", "--node", ma.get("node", "true"),
            "--out", str(out), "--grid", str(grid)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise DelegationFailed(proc.returncode, proc.stdout, proc.stderr)
    forward_notes(proc.stdout)
    sys.stderr.write(proc.stderr)

    chart = load_chart(out)
    meta = chart["meta"]
    meta["chart_type"] = "davison"
    meta["derived_from"] = [ma["name"], mb["name"]]
    meta["source"] = {**(meta.get("source") or {}), "method": "davison"}
    flags = list(meta.get("flags") or [])
    meta["flags"] = flags + [f for f in extra_flags if f not in flags]
    out.write_text(json.dumps(chart, indent=2, ensure_ascii=False), encoding="utf-8")
    return chart


# --- command line (copied from synastry/scripts/synastry.py) --------------------------------

BIRTH_MISSING = ("composite needs the natal-chart skill installed beside it to accept raw birth data "
                 "or a --city/--geonameid reference; pass chart files and --lat/--lon instead")
PROGRESSED_REFUSED = "composite: progressed and directed charts can't be composited; use the natal charts"


def is_progressed(chart: dict) -> bool:
    """A progressions chart: its bodies are read for a target date while its birth timestamps are natal."""
    meta = chart["meta"]
    return meta.get("chart_type") in ("secondary_progressed", "solar_arc_directed") or "progression" in meta


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on usage errors; that code is passed through from natal-chart, so exit 1."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    p = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--a", type=Path, help="chart.json for person A")
    p.add_argument("--b", type=Path, help="chart.json for person B")
    p.add_argument("--a-birth", help="raw birth arguments for A, as one shell-style string for natal_chart.py")
    p.add_argument("--b-birth", help="raw birth arguments for B, as one shell-style string for natal_chart.py")
    p.add_argument("--method", default="midpoint", choices=["midpoint", "davison"])
    p.add_argument("--city", help='reference place for midpoint houses, e.g. "Paris, FR" (default: A\'s place)')
    p.add_argument("--geonameid", type=int, help="reference place by GeoNames id")
    p.add_argument("--lat", type=float, help="reference latitude")
    p.add_argument("--lon", type=float, help="reference longitude")
    p.add_argument("--tz", help="accepted for symmetry with natal-chart; a midpoint composite has no clock time")
    p.add_argument("--houses", choices=list(HOUSE_CODES), help="house system (default: chart A's)")
    p.add_argument("--out", type=Path, help="output chart (default: composite.json or davison.json)")
    p.add_argument("--grid", type=Path, help="markdown grid path (default: <out stem>.md)")
    return p


def cast_chart(natal_script: Path, birth: str, out: Path) -> dict:
    """Run the natal script with the user's raw arguments, writing to ``out``, and load the result.

    ``--out`` and ``--grid`` come last so a user-supplied path in ``birth`` cannot write outside the
    temporary directory. The natal script's "Note:" lines and stderr are forwarded to the user.
    """
    try:
        words = shlex.split(birth)
    except ValueError as exc:
        raise ValueError(f"cannot parse birth arguments {birth!r}: {exc}") from exc
    cmd = [sys.executable, "-I", str(natal_script), *words,
           "--out", str(out), "--grid", str(out.with_suffix(".md"))]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise DelegationFailed(proc.returncode, proc.stdout, proc.stderr)
    forward_notes(proc.stdout)
    sys.stderr.write(proc.stderr)
    return load_chart(out)


def resolve_reference(args, a: dict, natal_script: Path | None, tmp: Path) -> dict:
    """The contract ``location`` for midpoint houses: A's place unless a place flag overrides it.

    ``--lat/--lon`` is used directly. ``--city``/``--geonameid`` is resolved by casting a probe
    chart at that place through natal-chart once and reading ``meta.location``; an ambiguous
    city therefore surfaces as natal-chart's exit 2 with its candidate table. The probe uses a
    fixed, untimed date (2000-01-01) since only the location is read; A's own date or time could
    be one the reference place rejects.
    """
    if args.lat is not None or args.lon is not None:
        if args.lat is None or args.lon is None:
            raise ValueError("--lat and --lon must be given together")
        if args.city or args.geonameid:
            raise ValueError("pass exactly one of --city, --geonameid, or --lat/--lon, not a mix")
        return {"name": f"{args.lat:.4f}, {args.lon:.4f}", "latitude": args.lat, "longitude": args.lon,
                "geonameid": None}
    if not (args.city or args.geonameid):
        return a["meta"]["location"]
    if natal_script is None:
        raise ValueError(BIRTH_MISSING)
    cmd = [sys.executable, "-I", str(natal_script), "--name", "probe", "--date", "2000-01-01"]
    cmd += ["--geonameid", str(args.geonameid)] if args.geonameid else ["--city", args.city]
    out = tmp / "reference.json"
    cmd += ["--out", str(out), "--grid", str(out.with_suffix(".md"))]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise DelegationFailed(proc.returncode, proc.stdout, proc.stderr)
    return load_chart(out)["meta"]["location"]


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    for side in "ab":
        file_arg, birth_arg = getattr(args, side), getattr(args, f"{side}_birth")
        if file_arg and birth_arg:
            parser.error(f"give --{side} or --{side}-birth, not both")
        if not file_arg and not birth_arg:
            parser.error(f"give --{side} or --{side}-birth")
    place_given = args.city or args.geonameid or args.lat is not None or args.lon is not None or args.tz
    if args.method == "davison" and place_given:
        parser.error("a Davison chart is cast at the great-circle midpoint of the two birthplaces; "
                     "the reference place flags apply to --method midpoint only")

    out = args.out or Path("davison.json" if args.method == "davison" else "composite.json")
    if out.name.startswith(".") and "." not in out.name[1:]:  # pathlib: ".json" has an empty stem
        print(f"--out needs a file name, not just an extension ({out})", file=sys.stderr)
        return 1
    grid_path = args.grid or out.with_suffix(".md")
    if grid_path.resolve() == out.resolve():
        print(f"--grid and --out are the same file ({out}); choose a different --grid", file=sys.stderr)
        return 1

    natal_script = find_natal_script()
    if natal_script is None and (args.a_birth or args.b_birth):
        print(BIRTH_MISSING, file=sys.stderr)
        return 1
    if natal_script is None and args.method == "davison":
        print(NATAL_MISSING, file=sys.stderr)
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="composite-") as tmp:
            charts = {}
            for side in "ab":
                birth = getattr(args, f"{side}_birth")
                if birth:
                    charts[side] = cast_chart(natal_script, birth, Path(tmp) / f"{side}.json")
                else:
                    charts[side] = load_chart(getattr(args, side))
                    if is_progressed(charts[side]):
                        raise ValueError(PROGRESSED_REFUSED)
            a, b = charts["a"], charts["b"]
            house_system = args.houses or requested_house_system(a["meta"])
            if args.method == "davison":
                a["meta"]["house_system_requested"] = house_system
                chart = cast_davison(natal_script, a, b, out, grid_path)
            else:
                reference = resolve_reference(args, a, natal_script, Path(tmp))
                chart = midpoint_chart(a, b, reference, house_system)
                out.write_text(json.dumps(chart, indent=2, ensure_ascii=False), encoding="utf-8")
                grid_path.write_text(render_grid(chart), encoding="utf-8")
    except DelegationFailed as exc:
        # Exit 2 (ambiguous city) carries the candidate table on stdout; pass both through.
        sys.stdout.write(exc.stdout)
        sys.stderr.write(exc.stderr)
        return exc.code
    except subprocess.TimeoutExpired:
        print("natal_chart.py did not finish within 120 seconds", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Wrote {out} and {grid_path}")
    for flag in chart["meta"]["flags"]:
        if flag not in PRINTED_NOTES:
            print(f"Note: {flag}")
    if args.houses and not chart.get("houses"):
        print("Note: --houses ignored because the composite has no houses (an untimed side)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
