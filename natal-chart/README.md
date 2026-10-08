# natal-chart

Casts a natal chart from a date, local time, and place, and writes it as `chart.json` plus a Markdown aspect grid, using the Swiss Ephemeris.

**Bodies:** Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, lunar Node
**Houses and angles:** Placidus by default; Whole Sign, Koch, Equal, Porphyry by flag; Ascendant, MC, Descendant, IC
**Aspects:** conjunction, sextile, square, trine, quincunx, opposition, with per-aspect orbs, a 2° bonus for the Sun and Moon, and applying/separating from daily speeds
**Extra:** tropical or sidereal (Lahiri) zodiac, true or mean node, unknown birth time handled honestly

## Example output

For a chart cast for 1990-06-15 at 12:00 in New York City (Placidus, tropical, true node), `chart.json` holds each body like this:

```json
"Sun": {
  "longitude": 84.2887,
  "sign": "Gemini",
  "sign_degree": 24.2887,
  "formatted": "24°17' Gemini",
  "speed": 0.9551,
  "retrograde": false,
  "house": 10,
  "latitude": 0.0001
}
```

together with the angles, the twelve cusps, the resolved birth data (coordinates, `America/New_York`, UTC offset `-04:00`), and the aspect list. The companion `chart_aspects.md` is a grid:

| | Sun | Moon | Mercury | Venus | ... |
|---|---|---|---|---|---|
| Sun |  | □ 6.7a |  |  | |
| Moon | □ 6.7a |  |  | ⚹ 1.4a | |

`a` marks an applying aspect, `s` a separating one. The full file layout is documented in [`CONTRACT.md`](CONTRACT.md).

## Install

```bash
# Claude Code, project scope
cp -r natal-chart .claude/skills/

# Claude Code, user scope
cp -r natal-chart ~/.claude/skills/

# once, to fetch the Swiss Ephemeris data files (about 2 MB)
python ~/.claude/skills/natal-chart/scripts/fetch_ephemeris.py
```

Then ask Claude for "my birth chart, born 15 June 1990 at 2:30pm in London" or "where was my Moon".

The fetch step is optional. Without the files the planets use the built-in Moshier ephemeris (a little less precise) and Chiron is left out, with `chiron_unavailable` in the chart's flags.

## Run the script directly

```bash
pip install pyswisseph timezonefinder
python scripts/fetch_ephemeris.py
python scripts/natal_chart.py --name "Ada" --date 1990-06-15 --time 14:30 --city "London, GB"
python scripts/natal_chart.py --name "Ada" --date 1990-06-15 --geonameid 2643743          # unknown time
python scripts/natal_chart.py --name "Ada" --date 1990-06-15 --time 06:00 --lat 51.5 --lon -0.13
```

Options: `--houses placidus|koch|equal|porphyry|whole_sign`, `--zodiac tropical|sidereal`, `--node true|mean`, `--out chart.json`, `--grid aspects.md`. Exit code `2` means the city name matched several places; the candidates are printed as a table and the script should be re-run with `--geonameid`. Candidate labels show the raw GeoNames admin1 code, so Paris in France appears as "Paris, 11, FR".

Requires Python 3.11 or newer.

## How it works

- A city name is looked up in `data/cities.csv`, a reduced copy of the GeoNames cities15000 table (every place with population 15,000 or more). Coordinates skip the table; their timezone comes from `timezonefinder`. Historical offsets and daylight saving come from `zoneinfo`, so old births get the offset in force at the time.
- `scripts/ephemeris.py` is the only module that calls `pyswisseph`. It computes positions and houses, drops Chiron when its data file is missing, and falls back to Whole Sign houses at polar latitudes where Placidus fails.
- `scripts/aspects.py` holds the orb table as constants at the top, so the skill adapts without code surgery.
- With no birth time the chart is cast at local noon, houses and angles are omitted, and the Moon's range across the day is recorded instead of a single sign claim.

## Why it exists

A cast chart is the foundation everything else in chart work rests on. `chart.json` is a documented contract: `chart-wheel` draws it, `transits-to-natal` scans the sky against it, and `synastry` compares two of them. Keeping the casting in one place means the timezone, house, and orb rules are decided once and shared by every later skill.

## Data attribution

`data/cities.csv` is derived from the [GeoNames](https://www.geonames.org) cities15000 dataset, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See [`data/README.md`](data/README.md) for how it was built. Planetary positions come from the Swiss Ephemeris via `pyswisseph` (AGPL-3.0, Astrodienst).
