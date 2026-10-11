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


def _name_matches(key: str, city: City) -> bool:
    return key in (city.name.casefold(), city.asciiname.casefold())


def lookup(query: str, table: list[City]) -> City:
    """Resolve a city query.

    The whole query is first matched case-insensitively against name/asciiname,
    so names that themselves contain commas ("Mianzhu, Deyang, Sichuan") work.
    Otherwise the query is split on commas into a name plus trailing region
    tokens, each of which must equal the candidate's country or admin1 code, so
    "Paris, TX", "Paris, FR" and the printed label "Paris, TX, US" all resolve.
    """
    whole = query.strip().casefold()
    hits = [c for c in table if _name_matches(whole, c)]
    regions: list[str] = []
    if not hits:
        name, *regions = (part.strip() for part in query.split(","))
        regions = [r.upper() for r in regions if r]
        key = name.casefold()
        by_name = [c for c in table if _name_matches(key, c)]
        hits = [c for c in by_name
                if all(r in (c.country.upper(), c.admin1.upper()) for r in regions)]
        if by_name and not hits:
            by_name.sort(key=lambda c: -c.population)
            labels = ", ".join(c.label for c in by_name[:5])
            raise UnknownLocation(
                f"Found {by_name[0].name!r} but the region {', '.join(regions)!r} did not match. "
                f"Use a country code like FR or a region code like TX; candidates: {labels}")
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
