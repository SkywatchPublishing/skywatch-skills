# natal-chart/data

## cities.csv

Reduced copy of the GeoNames **cities15000** dataset (every place with a
population of 15,000 or more), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) by
[GeoNames](https://www.geonames.org).

- **Source**: obtained from the `geonamescache` 3.0.2 redistribution on PyPI on
  2026-10-08, because download.geonames.org was unreachable from the build
  environment. Rebuilding from the official `cities15000.zip` with the same
  script should produce an equivalent file.
- **Reduction**: `scripts/build_cities.py`, which keeps the columns
  `geonameid,name,asciiname,country,admin1,latitude,longitude,timezone,population`
  and sorts rows by population descending.
- **Size**: 34,006 rows (plus the header).

Notes:

- `admin1` is the raw GeoNames first-level administrative code. For the US,
  Canada and a few others it is a familiar letter code (`TX`, `ON`); for many
  countries it is numeric (`11` for Île-de-France, `32` for Sichuan).
- GeoNames alternate names (local-language spellings, former names) are **not**
  included; lookup matches only `name` and `asciiname`.
- A few names contain commas (e.g. "Mianzhu, Deyang, Sichuan") and are quoted
  in the CSV; `location.lookup()` tries the whole query as a name before
  treating trailing comma-separated tokens as region filters.
