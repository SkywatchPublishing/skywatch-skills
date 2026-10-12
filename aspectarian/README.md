# aspectarian

Builds the two timing tables a datebook prints for every month, as CSV: an aspectarian with every exact major aspect at the minute it perfects, and a void-of-course Moon table that ends at each of the Moon's sign ingresses. Computed from NASA JPL's DE440 ephemeris with [Skyfield](https://rhodesmill.org/skyfield/), with no Swiss Ephemeris dependency, so the output can be published under any license.

**Bodies:** Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto; Sun through Saturn with `--traditional`
**Aspects:** conjunction, sextile, square, trine, opposition, each at the moment it is exact
**Extra:** any IANA time zone, rounded to the minute, with the exact UTC second on every row

## Example output

Aspectarian, 15 April 2026, Pacific time:

| Date | Time | Body 1 | Aspect | Body 2 | UTC |
|---|---|---|---|---|---|
| 2026-04-15 | 06:07 AM PDT | Moon | Sextile | Uranus | 2026-04-15T13:07:13Z |
| 2026-04-15 | 08:16 AM PDT | Moon | Conjunction | Mercury | 2026-04-15T15:15:49Z |
| 2026-04-15 | 11:45 AM PDT | Moon | Conjunction | Neptune | 2026-04-15T18:44:50Z |
| 2026-04-15 | 03:08 PM PDT | Moon | Conjunction | Mars | 2026-04-15T22:08:25Z |

Void-of-course Moon:

| Begins Date | Begins Time | Last Aspect | Moon Enters | Ingress Date | Ingress Time | Duration |
|---|---|---|---|---|---|---|
| 2026-04-17 | 04:52 AM PDT | Moon Conjunction Sun | Taurus | 2026-04-17 | 08:58 AM PDT | 4h 06m |
| 2026-04-19 | 08:45 AM PDT | Moon Conjunction Uranus | Gemini | 2026-04-19 | 09:18 AM PDT | 0h 33m |
| 2026-04-19 | 10:17 PM PDT | Moon Sextile Mars | Cancer | 2026-04-21 | 10:00 AM PDT | 35h 43m |

The full month is in [`examples/aspectarian_2026_04.csv`](examples/aspectarian_2026_04.csv) (95 aspects, 77 of them the Moon's) and [`examples/voc_2026_04.csv`](examples/voc_2026_04.csv) (13 voids). The void table also carries the exact UTC moments, left out above for width.

Examples are produced by: `python scripts/aspectarian.py 4 2026 --out-dir examples`

## Install

```bash
# Claude Code, project scope
cp -r aspectarian .claude/skills/

# Claude Code, user scope
cp -r aspectarian ~/.claude/skills/

# once, wherever it was copied: the 32 MB JPL ephemeris
pip install skyfield
python ~/.claude/skills/aspectarian/scripts/fetch_ephemeris.py
```

Then ask Claude "when is the Moon void of course in May", "give me the aspectarian for June 2026", or "the void-of-course table for the datebook, Eastern time".

## Run the script directly

```bash
pip install skyfield
python scripts/fetch_ephemeris.py
python scripts/aspectarian.py 4 2026
python scripts/aspectarian.py 4 2026 --tz America/New_York --out-dir datebook/eastern
python scripts/aspectarian.py 4 2026 --traditional
```

Options: `--tz` any IANA zone (default `America/Los_Angeles`), `--traditional` for Sun through Saturn only (files get a `_traditional` suffix), `--out-dir` for the folder, `--ephemeris` for another JPL file such as `de440.bsp` (1550 to 2650). Exit code `1` means bad input or a missing ephemeris, with the reason on stderr.

Requires Python 3.10 or newer.

## How it works

- Positions are the apparent geocentric ecliptic longitudes of date that an ephemeris prints, computed by Skyfield from JPL DE440: light time, aberration, precession and nutation applied, tropical zodiac.
- Every body is sampled hourly across the month plus four days either side. Wherever the distance of a pair from an exact aspect changes sign, the moment is bisected to a tenth of a second, all pairs at once. The Moon's sign ingresses are found the same way.
- The Moon is void from its last exact aspect in a sign until it enters the next one. If it makes no aspect in a whole sign, the void runs on from the sign before, through two signs.
- Times are rounded to the nearest minute, and an event belongs to the date and month its rounded local time shows. Durations are counted in real time, so a void across a daylight-saving change is the right length.

## Tests

```bash
pip install skyfield pytest
python aspectarian/scripts/fetch_ephemeris.py
python -m pytest aspectarian/tests -q
```

- All 50 lunar phases of 2026 are checked against the times the U.S. Naval Observatory publishes, to the minute.
- When `pyswisseph` is installed, positions through 2026 and every April 2026 event are checked against the Swiss Ephemeris as an independent oracle. With the Swiss data files in `natal-chart/ephe/` the two agree to within 0.01 arcseconds. The skill itself never imports it.
- The April 2026 run is compared with the committed examples.

The April 2026 Moon times were also checked by hand against the `astrology-ephemeris` example: the same 77 aspects at the same minutes. No test spans the two folders, so each stays copyable on its own.

Tests that need the ephemeris are skipped until `fetch_ephemeris.py` has been run.

## Licensing your output

The code is MIT, like the rest of this repository. Skyfield and jplephem are MIT-licensed, and NASA distributes DE440 freely, so nothing in the pipeline restricts what you do with the tables. Exact times of astronomical events are facts, which United States copyright does not cover (*Feist v. Rural Telephone*, 1991).

To publish them openly:

- Mark the CSVs CC0 1.0, a public-domain dedication.
- Mark a designed page or PDF CC BY 4.0, reuse with credit.
- Credit the source as "Computed from NASA JPL's DE440 ephemeris with Skyfield".
- Avoid NonCommercial licenses if the aim is reach: many open projects and teachers cannot reuse NC material.

## Why it exists

Void-of-course times and an aspectarian are the most-consulted pages of a datebook, and they are usually bought from, or copied out of, a commercial ephemeris. This skill computes them from public NASA data with open-source code, checked against an independent source, so a publisher can print them, share them, or release them for anyone to use.
