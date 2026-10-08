#!/usr/bin/env python3
"""
Cast a natal chart and write chart.json plus a Markdown aspect grid.

Usage:
    python natal_chart.py --name "Ada" --date 1990-06-15 --time 14:30 --city "London, GB"
    python natal_chart.py --name "Ada" --date 1990-06-15 --geonameid 2643743
    python natal_chart.py --name "Ada" --date 1990-06-15 --lat 51.5 --lon -0.13   # timezone from coordinates

Omit --time when the birth time is unknown: the chart is cast at noon with no houses.
Exit codes: 0 success; 1 bad arguments or unknown location (message on stderr);
2 the city was ambiguous; the candidates are printed. Re-run with --geonameid.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chart as ch          # noqa: E402
import grid                 # noqa: E402
import location as loc      # noqa: E402


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on usage errors; that code is reserved for an ambiguous city, so exit 1."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(1)


def parse_args(argv):
    p = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--date", required=True, type=dt.date.fromisoformat)
    p.add_argument("--time", type=dt.time.fromisoformat, help="HH:MM local; omit if unknown")
    p.add_argument("--city", help='e.g. "Paris, FR" or "Paris, TX"')
    p.add_argument("--geonameid", type=int)
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)
    p.add_argument("--tz", help="IANA timezone override for --lat/--lon (default: looked up from the coordinates)")
    p.add_argument("--houses", default="placidus", choices=["placidus", "koch", "equal", "porphyry", "whole_sign"])
    p.add_argument("--zodiac", default="tropical", choices=["tropical", "sidereal"])
    p.add_argument("--node", default="true", choices=["true", "mean"])
    p.add_argument("--out", type=Path, default=Path("chart.json"))
    p.add_argument("--grid", type=Path)
    return p.parse_args(argv)


def validate_args(args) -> str | None:
    """Return an error message for an invalid combination, or None."""
    if args.time is not None and args.time.utcoffset() is not None:
        return "--time must be a local wall-clock time without a UTC offset"
    if args.lat is not None and not -90 <= args.lat <= 90:
        return f"--lat must be between -90 and 90, got {args.lat}"
    if args.lon is not None and not -180 <= args.lon <= 180:
        return f"--lon must be between -180 and 180, got {args.lon}"
    if args.tz:
        try:
            ZoneInfo(args.tz)
        except (ZoneInfoNotFoundError, ValueError):
            return f"Unknown timezone {args.tz!r}; use an IANA name such as Europe/London"
    return None


def resolve_location(args):
    if args.lat is not None or args.lon is not None:
        if args.lat is None or args.lon is None:
            raise SystemExit("--lat and --lon must be given together")
        tz = args.tz
        if not tz:
            from timezonefinder import TimezoneFinder
            tz = TimezoneFinder().timezone_at(lat=args.lat, lng=args.lon)
            if not tz:
                raise SystemExit("No timezone found for those coordinates; pass --tz")
        return {"name": f"{args.lat:.4f}, {args.lon:.4f}", "latitude": args.lat, "longitude": args.lon, "geonameid": None}, tz
    table = loc.load_table()
    city = loc.lookup_id(args.geonameid, table) if args.geonameid else loc.lookup(args.city, table)
    return {"name": city.label, "latitude": city.latitude, "longitude": city.longitude, "geonameid": city.geonameid}, city.timezone


def main(argv=None) -> int:
    args = parse_args(argv)
    if not (args.city or args.geonameid or args.lat is not None):
        print("Give --city, --geonameid, or --lat/--lon/--tz", file=sys.stderr)
        return 1
    if (err := validate_args(args)) is not None:
        print(err, file=sys.stderr)
        return 1
    try:
        location, tz = resolve_location(args)
    except loc.AmbiguousLocation as exc:
        print(f"{len(exc.candidates)} places match {exc.query!r}. Re-run with --geonameid:\n")
        print("| geonameid | place | population | timezone |\n|---|---|---|---|")
        for c in exc.candidates[:10]:
            print(f"| {c.geonameid} | {c.label} | {c.population} | {c.timezone} |")
        return 2
    except loc.UnknownLocation as exc:
        print(exc, file=sys.stderr)
        return 1

    result = ch.build_chart(args.name, args.date, args.time, tz, location, args.houses, args.zodiac, args.node)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    grid_path = args.grid or args.out.with_name(args.out.stem + "_aspects.md")
    grid_path.write_text(grid.render(result), encoding="utf-8")
    print(f"Wrote {args.out} and {grid_path}")
    for flag in result["meta"]["flags"]:
        print(f"Note: {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
