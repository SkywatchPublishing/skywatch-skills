#!/usr/bin/env python3
"""
Download the Swiss Ephemeris data files natal-chart needs into natal-chart/ephe/.

Usage:
    python fetch_ephemeris.py [--dir DIR]

Files (about 2 MB total, AGPL-3.0 from Astrodienst):
    sepl_18.se1  planets 1800-2400
    semo_18.se1  Moon    1800-2400
    seas_18.se1  asteroids incl. Chiron 1800-2400
Without them the planets use the built-in Moshier ephemeris and Chiron is omitted.
"""
import argparse
import sys
import urllib.request
from pathlib import Path

FILES = ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]
BASE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/"


def url_for(name: str) -> str:
    return BASE_URL + name


def default_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "ephe"


def missing(directory: Path) -> list[str]:
    return [f for f in FILES if not (directory / f).exists()]


def fetch(directory: Path) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    fetched = []
    for name in missing(directory):
        urllib.request.urlretrieve(url_for(name), directory / name)
        fetched.append(name)
    return fetched


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=default_dir())
    args = parser.parse_args(argv)
    try:
        fetched = fetch(args.dir)
    except Exception as exc:  # network errors are the normal failure here
        print(f"Could not download ephemeris files: {exc}", file=sys.stderr)
        return 1
    print(f"Ephemeris files ready in {args.dir} (downloaded {len(fetched)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
