# returns

Casts return charts from a natal `chart.json`: solar returns (the birthday chart), lunar returns, and Mars, Jupiter, Saturn, Uranus and Chiron returns. Finds every moment in a date range when the transiting body is back on its natal degree, to the second, and casts the sky for that moment at the place the person will be, through the `natal-chart` skill. Takes the `chart.json` produced by `natal-chart`.

**Bodies:** Sun (default), Moon, Mars, Jupiter, Saturn, Uranus, Chiron
**Place:** `--city`, `--geonameid` or `--lat/--lon [--tz]`; without one the natal place is used and flagged
**Output:** one `<body>_return_<date>.json` per return with its aspect grid, plus `returns_summary.md`
**Extra:** `--precessed` for precession-corrected returns; retrograde loops give one chart per crossing

## Example output

The 2027 solar return of the natal-chart example chart (1990-06-15, New York City), cast at the natal place, is in [`examples/sun_return_2027-06-15.json`](examples/sun_return_2027-06-15.json) with its grid in [`examples/sun_return_2027-06-15_aspects.md`](examples/sun_return_2027-06-15_aspects.md). The run's [`examples/returns_summary.md`](examples/returns_summary.md) holds this row:

| Return | UTC moment | Local time | Place | ASC | MC | DSC | IC | Return Moon sign |
|---|---|---|---|---|---|---|---|---|
| sun_return_2027-06-15 | 2027-06-15T14:33:34Z | 2027-06-15T10:33:34 (America/New_York) | New York City, NY, US | 26°52' Leo | 20°29' Taurus | 26°52' Aquarius | 20°29' Scorpio | 15°08' Scorpio |

followed by the comparison line: Ascendant 26°52' Leo (natal Virgo); Moon 15°08' Scorpio (natal Pisces). The return Sun sits at the natal 24°17' Gemini in the return's tenth house, and the file carries `chart_type: solar_return`, `derived_from: ["Example"]`, `return_utc` and the flag `return_place_natal`.

Examples are produced by: `python returns/scripts/returns.py natal-chart/examples/chart.json --start 2027-01-01 --end 2027-12-31 --out-dir returns/examples` run from the repository root.

## Install

```bash
# Claude Code, project scope
cp -r returns .claude/skills/

# Claude Code, user scope
cp -r returns ~/.claude/skills/
```

Install `natal-chart` alongside it (same parent folder, `~/.claude/skills/`, or `./.claude/skills/`): this skill reads the `chart.json` that one writes and runs its script to cast each return, and it borrows that skill's Swiss Ephemeris files from `natal-chart/ephe/`. Without the files the planets use the built-in Moshier ephemeris and Chiron returns are unavailable.

Then ask Claude "what does my solar return look like this year", "cast my lunar returns for the spring", "when is my Saturn return", or "where should I be for my birthday". Claude will ask where you will be, because the houses depend on it.

## Run the script directly

```bash
pip install pyswisseph timezonefinder
python scripts/returns.py chart.json --start 2027-01-01 --end 2027-12-31 --city "Austin, TX"
python scripts/returns.py chart.json --body moon --start 2027-01-01 --end 2027-03-31 --geonameid 5128581
python scripts/returns.py chart.json --body saturn --start 2019-01-01 --end 2020-12-31 --lat 30.2672 --lon -97.7431
python scripts/returns.py chart.json --start 2027-01-01 --end 2027-12-31 --out-dir returns-2027   # natal place, flagged
```

Options: `--body` picks the returning body (`sun` by default), `--start` and `--end` are inclusive ISO dates, one of `--city`, `--geonameid` or `--lat/--lon [--tz]` gives the return place (`--city` with `--geonameid`, or either with coordinates, is refused), `--precessed` shifts the target by the precession since birth (Lahiri; tropical charts only, a sidereal chart is refused with `--precessed applies to tropical charts only`), `--out-dir` is where the files go (current directory by default). On success it prints `Wrote N return chart(s), each with a _aspects.md aspect-grid sidecar, and <dir>/returns_summary.md`. Existing files are never overwritten: a rerun into the same folder writes `<name>_2.json`, `_3.json` and prints a `Note:` saying so. Exit code `1` means bad input or a missing `natal-chart`; `2` means an ambiguous city, with the candidate table on stdout to re-run with `--geonameid`.

Requires Python 3.11 or newer.

## How it works

- The target is the body's natal longitude from `chart.json` (sidereal longitude for a sidereal chart). The transiting body is sampled once a day across the range; each sign change of the wrapped difference is refined by sixty bisection steps, to well under a second.
- Every crossing is a return, so a retrograde loop of Mars through Uranus or Chiron across the natal degree writes one chart per pass. Lunar returns come every 27.3 days.
- `--precessed` adds the ayanamsa accumulated between birth and the sample to the target. The ayanamsa's zero point cancels in the difference, so Lahiri gives the same drift any other ayanamsa would.
- Each return moment is converted to local time at the return place (`--tz`, `timezonefinder` for coordinates, or one probe run of natal-chart for a city, which also surfaces an ambiguous name before any search) and passed to `natal_chart.py` with the date, the time to the second, the place, and the natal chart's house system, zodiac and node. A moment in the repeated hour of a DST fall-back goes with `--fold 1` so natal-chart picks the second occurrence, and the cast is checked against the return instant.
- `chart.json` keeps longitudes to 4 decimals, so the target degree is rounded; that bounds the return moment at about 4 seconds for the Sun and 1 second for the Moon, however finely the search bisects. The result's `meta` is then rewritten with `chart_type`, `derived_from`, `return_utc` and the flags `return_place_natal`, `natal_time_unknown`, `precession_corrected` as they apply.
- Because each output is a complete `chart.json`, `chart-wheel` draws it, `synastry` lays it over the natal chart, and `transits-to-natal` scans against it, with no changes.
- Mercury and Venus are left out: their retrograde loops can give zero or three returns in a year, which needs different wording than "your return this year".
- The script imports nothing from the other skill folders; the helpers it needs are copied from `synastry`.

## Why it exists

A solar return is the most-asked-for chart after the natal chart itself, and the one most often cast wrong: for the birthday rather than the exact moment, or for the birthplace rather than where the person is. This finds the moment to the second, asks for the place, and hands back a chart the rest of the toolkit already understands.
