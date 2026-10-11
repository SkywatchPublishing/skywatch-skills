#!/usr/bin/env python3
"""
Reduce the GeoNames cities15000 dump to the columns natal-chart needs.

Usage:
    python build_cities.py [--src cities15000.txt | --src cities15000.zip] [--out ../data/cities.csv]

Get the dump from https://download.geonames.org/export/dump/cities15000.zip (CC BY 4.0).
"""
import argparse
import csv
import sys
import zipfile
from pathlib import Path

HEADER = ["geonameid", "name", "asciiname", "country", "admin1", "latitude", "longitude", "timezone", "population"]
KEEP = [0, 1, 2, 8, 10, 4, 5, 17, 14]


def reduce_row(fields: list[str]) -> list[str]:
    return [fields[i] for i in KEEP]


def build(src: Path, out: Path) -> int:
    if src.suffix == ".zip":
        with zipfile.ZipFile(src) as z:
            text = z.read("cities15000.txt").decode("utf-8")
    else:
        text = src.read_text(encoding="utf-8")
    rows = [reduce_row(line.split("\t")) for line in text.splitlines() if line.strip()]
    rows.sort(key=lambda r: -int(r[8] or 0))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return len(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, default=Path("cities15000.zip"))
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "cities.csv")
    args = parser.parse_args(argv)
    n = build(args.src, args.out)
    print(f"Wrote {n} cities to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
