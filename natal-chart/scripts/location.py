"""City lookup against data/cities.csv (GeoNames cities15000, reduced)."""
import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TABLE = Path(__file__).resolve().parents[1] / "data" / "cities.csv"


@dataclass(frozen=True)
class City:
    geonameid: int
    name: str
    asciiname: str
    country: str
    admin1: str
    latitude: float
    longitude: float
    timezone: str
    population: int

    @property
    def label(self) -> str:
        parts = [self.name, self.admin1, self.country]
        return ", ".join(p for p in parts if p)


class UnknownLocation(LookupError):
    pass


class AmbiguousLocation(LookupError):
    def __init__(self, query: str, candidates: list[City]):
        super().__init__(f"{len(candidates)} places match {query!r}")
        self.query = query
        self.candidates = candidates


def load_table(path: Path = DEFAULT_TABLE) -> list[City]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [
            City(int(r["geonameid"]), r["name"], r["asciiname"], r["country"], r["admin1"],
                 float(r["latitude"]), float(r["longitude"]), r["timezone"], int(r["population"] or 0))
            for r in csv.DictReader(fh)
        ]


def lookup(query: str, table: list[City]) -> City:
    name, _, region = (part.strip() for part in query.partition(","))
    key = name.casefold()
    region = region.upper()
    hits = [c for c in table if key in (c.name.casefold(), c.asciiname.casefold())]
    if region:
        hits = [c for c in hits if region in (c.country.upper(), c.admin1.upper())]
    hits.sort(key=lambda c: -c.population)
    if not hits:
        raise UnknownLocation(f"No city over 15,000 people matches {query!r}; pass --lat/--lon/--tz instead")
    if len(hits) > 1:
        raise AmbiguousLocation(query, hits)
    return hits[0]


def lookup_id(geonameid: int, table: list[City]) -> City:
    for c in table:
        if c.geonameid == geonameid:
            return c
    raise UnknownLocation(f"No city with geonameid {geonameid}")
