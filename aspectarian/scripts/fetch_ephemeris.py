#!/usr/bin/env python3
"""
Download NASA JPL's DE440s planetary ephemeris into aspectarian/ephe/.

Usage:
    python fetch_ephemeris.py [--dir DIR]

File (32 MB, from JPL's NAIF server):
    de440s.bsp  Sun, Moon and planets, 1849 to 2150
DE440 is JPL's current planetary and lunar ephemeris (Park et al. 2021, AJ 161:105).
NASA distributes it freely; no license key or registration is involved.
"""
import argparse
import os
import shutil
import sys
import urllib.request
from pathlib import Path

FILES = ["de440s.bsp"]
BASE_URL = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/"


def url_for(name: str) -> str:
    return BASE_URL + name


def default_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "ephe"


def missing(directory: Path) -> list[str]:
    return [f for f in FILES if not (directory / f).exists()]


def download(url: str, dest: Path, timeout: float = 60) -> None:
    """Download url to dest atomically: write to dest.part, then rename.

    A dropped connection or empty response leaves no file behind, so missing()
    never mistakes a truncated download for a complete one.
    """
    part = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response, part.open("wb") as out:
            shutil.copyfileobj(response, out)
        if part.stat().st_size == 0:
            raise OSError(f"Empty response from {url}")
        os.replace(part, dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def fetch(directory: Path) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    fetched = []
    for name in missing(directory):
        download(url_for(name), directory / name)
        fetched.append(name)
    return fetched


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=default_dir())
    args = parser.parse_args(argv)
    try:
        fetched = fetch(args.dir)
    except Exception as exc:  # network errors are the normal failure here
        print(f"Could not download the ephemeris: {exc}", file=sys.stderr)
        return 1
    print(f"Ephemeris ready in {args.dir} (downloaded {len(fetched)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
