# chart.json contract (schema_version 1)

`natal_chart.py` writes `chart.json`. The consumer skills (chart-wheel, transits-to-natal,
synastry, returns, composite, progressions) read it and nothing else; returns, composite and
progressions also write it, as derived charts whose `meta.chart_type` says what they are.
Check `schema_version == 1` before reading anything.
All longitudes are ecliptic degrees in `[0, 360)`, rounded to 4 decimals. Keys are always
present; some carry `null` as described below. `chart_type` and `derived_from` were added later,
so files written before them may omit both: consumers read them with `.get`, treating a missing
`chart_type` as `natal` and a missing `derived_from` as `[]`.

## Top level

| key | type | meaning |
|---|---|---|
| `schema_version` | int | Always `1`. |
| `meta` | object | Birth data, settings and provenance (below). |
| `angles` | object or null | `null` when `meta.time_unknown` is true. |
| `houses` | object or null | `null` when `meta.time_unknown` is true. |
| `bodies` | object | Body name -> position (below). |
| `aspects` | array | Natal aspects (below). |

Consumers must test truthiness (`if chart["angles"]:`), not key presence. transits-to-natal
refuses a chart whose `meta.timezone` is null (a midpoint `composite`), since it has no moment to scan from.
returns and composite refuse progressed and directed charts (`meta.chart_type` `secondary_progressed` or
`solar_arc_directed`, or any chart carrying `meta.progression`): cast returns and composites from the natal charts.

## `meta`

| key | type | meaning |
|---|---|---|
| `name` | string | Chart owner's name as given on the command line. |
| `chart_type` | string | `natal` from natal-chart. Derived charts rewrite it: `solar_return`, `lunar_return`, `mars_return`, `jupiter_return`, `saturn_return`, `uranus_return`, `chiron_return`, `composite`, `davison`, `secondary_progressed`, `solar_arc_directed`. |
| `derived_from` | array of string | Names of the source charts a derived chart was built from; `[]` for natal. |
| `datetime_local` | string or null | ISO 8601 local wall-clock time, no offset, e.g. `1990-06-15T12:00:00`. Noon when the time is unknown. A wall-clock time that occurs twice at a DST fall-back is disambiguated by `--fold` (0 first occurrence, 1 second); `utc_offset` and `datetime_utc` show which was used. A midpoint `composite` chart has no real moment and carries `null` here and in `timezone`, `datetime_utc` and `utc_offset`; `davison` and every return carry real values. On progressed and directed charts this and the other birth timestamps are the natal values, not the chart's moment; see `progression`. |
| `timezone` | string or null | IANA zone used, e.g. `America/New_York`. `null` for a midpoint `composite`. |
| `datetime_utc` | string or null | ISO 8601 UTC with trailing `Z`. `null` for a midpoint `composite`. |
| `utc_offset` | string or null | Offset in force at birth, `+HH:MM` / `-HH:MM`. `null` for a midpoint `composite`. |
| `return_utc` | string | ISO 8601 UTC with trailing `Z`, present only on return charts: the exact return moment, which `datetime_utc` matches to the second. It never appears on progressed or directed charts. |
| `progression` | object or absent | Written only by progressions, on `secondary_progressed` and `solar_arc_directed` charts; absent on every other chart type. `{target_date, age_years, solar_arc, angles_method}`: `target_date` is the ISO date the chart is read for, e.g. `2027-06-15`, a local date in `meta.timezone`; the chart is computed for local noon of that date, or for the birth moment when that noon comes before it (age 0). `age_years` is the age at that date in tropical years; `solar_arc` the true solar arc in degrees (progressed Sun minus natal Sun), in `[0, 360)`; both are rounded to 4 decimals. `angles_method` is `solar-arc` or `naibod` for a progressed chart with a known birth time, and `null` for a directed chart and for a progressed chart cast from an untimed natal chart. On progressed and directed charts `datetime_local`, `datetime_utc`, `utc_offset`, `timezone` and `julian_day_ut` are the natal birth values unchanged and are not the chart's moment; the chart describes `progression.target_date`; read them only for the birth timezone. |
| `julian_day_ut` | float | Julian day (UT), 7 decimals. |
| `time_unknown` | bool | True when no `--time` was given; the chart was cast at local noon. |
| `moon_range` | object or null | `{start, end}` Moon longitudes in degrees at 00:00 and 23:59 local; present when `time_unknown`, else `null`, except a midpoint `composite`, where it is `null` even when `time_unknown` (there is no day to span). On a progressed chart cast from an untimed natal chart it is the progressed Moon for a birth at each of those two moments of the birth date, and on a directed chart the natal range moved by the solar arc. The span may wrap through 0° (`start` > `end`, e.g. 355 -> 8). |
| `location` | object | `{name: string, latitude: float, longitude: float, geonameid: int or null}`. `geonameid` is `null` for `--lat/--lon` input; `name` is then `"lat, lon"`. |
| `zodiac` | string | `"tropical"` or `"sidereal_lahiri"`. |
| `house_system` | string or null | `placidus`, `koch`, `equal`, `porphyry` or `whole_sign` as actually used (after any polar fallback); `null` when `time_unknown`. |
| `node` | string | `"true"` or `"mean"`: which lunar node the `Node` body holds. |
| `flags` | array of string | Caveats, see below. Empty array when none. |
| `source` | object | `{library: "pyswisseph", version: string, ephemeris_files: bool}`. `ephemeris_files` false means the built-in Moshier ephemeris was used (slightly lower precision); on progressed and directed charts it describes the progressions run, not the natal cast. Composite charts add `method`: `"midpoint"` or `"davison"`; absent on every other chart type. |

### `flags` values

| flag | meaning |
|---|---|
| `time_unknown` | No birth time; `angles`, `houses` and every `bodies.*.house` are `null`; aspects to angles are absent. |
| `moon_uncertain` | Always accompanies `time_unknown`: the Moon moves ~12-15° per day, so use `meta.moon_range`, not `bodies.Moon`, for sign claims. |
| `chiron_unavailable` | Chiron could not be computed (ephemeris file or date range); the `Chiron` key is absent from `bodies`. |
| `polar_fallback_whole_sign` | The requested house system failed at this latitude; whole-sign houses were used and `meta.house_system` says `whole_sign`. |
| `return_place_natal` | Return charts: no place was given, so the return was cast at the natal location; the houses assume the person is at the birthplace. |
| `natal_time_unknown` | Return charts: the natal chart has no birth time, so the target longitude is the noon position; a lunar return's moment is uncertain by about half a day. |
| `precession_corrected` | Return charts: `--precessed` was used; the target was shifted by the precession accumulated since birth (Lahiri). |
| `davison_timezone_utc` | Davison charts: the midpoint has no timezone (open ocean, Antarctica), so the chart is cast in UTC; positions are unaffected. |

## `angles`

`{ascendant, mc, descendant, ic}`, each a float longitude. `descendant = ascendant + 180`,
`ic = mc + 180` (mod 360). `null` when `time_unknown`.

## `houses`

`{system: string, cusps: [12 floats]}`. `cusps[0]` is the 1st-house cusp and `cusps[9]` the 10th;
for quadrant systems these equal `angles.ascendant` and `angles.mc`, for `whole_sign` and `equal` they need not. A house
runs from `cusps[i]` forward to `cusps[(i+1) % 12]`, wrapping through 0°. `null` when `time_unknown`.

## `bodies`

An object whose keys appear in this fixed order (JSON preserves it; do not rely on sorting):

`Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Node`

`Chiron` is omitted when `chiron_unavailable` is flagged. The lunar node is always under the
single key `Node`, whether true or mean; `meta.node` says which. Each value:

| key | type | meaning |
|---|---|---|
| `longitude` | float | Ecliptic longitude `[0, 360)`. |
| `sign` | string | English sign name, `Aries` .. `Pisces`. |
| `sign_degree` | float | `longitude % 30`, 4 decimals. |
| `formatted` | string | `D°MM' Sign`, e.g. `24°17' Gemini`; rounded to the arc-minute, rolling into the next sign at 30°00'. |
| `speed` | float or null | Daily motion in degrees/day; negative when retrograde. `null` in `solar_arc_directed` charts because a directed position has no daily motion (`retrograde` is then false). |
| `retrograde` | bool | `speed < 0`. |
| `house` | int or null | 1..12 by `houses.cusps`; `null` when `time_unknown`. |
| `latitude` | float | Ecliptic latitude in degrees. |

## `aspects`

At most one entry per pair (aspect angles are 30° apart and orbs at most 10°, so only one can match). Pairs are
every two bodies, plus each body with `Ascendant` and `MC` when angles exist (never
Ascendant-MC). `body1`/`body2` follow the body order above, angles last.

| key | type | meaning |
|---|---|---|
| `body1`, `body2` | string | Body names, or `Ascendant` / `MC`. |
| `aspect` | string | `Conjunction` (0), `Sextile` (60), `Square` (90), `Trine` (120), `Quincunx` (150), `Opposition` (180). |
| `angle` | int | The exact angle for `aspect`, in degrees. |
| `orb` | float | Unsigned distance from exact, degrees, 3 decimals. It never says which side of exact the pair sits on. |
| `max_orb` | float | The limit applied to this pair: base orb for the aspect (8° for conjunction/opposition/square/trine, 6° sextile, 3° quincunx) plus 2° when either body is the Sun or Moon. `orb <= max_orb` always. |
| `applying` | bool or null | `true` when the pair is closing on exact, `false` when separating. `null` when it cannot be decided: aspects to `Ascendant`/`MC` (angles carry no speed), two bodies with identical speed, and every aspect in a `solar_arc_directed` chart (directed bodies carry no speed). |

## Exit codes of `natal_chart.py`

`0` success; `1` invalid arguments or unknown location (one line on stderr);
`2` ambiguous city (candidate table on stdout, re-run with `--geonameid`).
