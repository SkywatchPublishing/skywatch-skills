# transits-to-natal

Scans the moving sky against a cast natal chart and writes the transiting aspects as a daily CSV, in the same one-row-per-hit style as the astrology-ephemeris CSV, using the Swiss Ephemeris. Takes the `chart.json` produced by the `natal-chart` skill.

**Transiting bodies:** Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Node by default; Sun, Mercury, Venus, Mars with `--fast`; Moon with `--moon`
**Natal targets:** every body in the chart plus the Ascendant, MC, Descendant, and IC when the birth time is known
**Aspects:** conjunction, sextile, square, trine, quincunx, opposition, within a 1° orb, with applying/separating and a retrograde flag
**Extra:** timestamps in the natal location's timezone, with the UTC offset on every row

## Example output

| Date | Time | UTC Offset | Transit | Aspect | Natal | Orb (°) | Applying | Retrograde |
|---|---|---|---|---|---|---|---|---|
| 2026-04-03 | 12:00 | -04:00 | Jupiter | Conjunction | Jupiter | 0.039 | no | no |
| 2026-04-03 | 12:00 | -04:00 | Saturn | Sextile | Mercury | 0.098 | yes | no |
| 2026-04-03 | 12:00 | -04:00 | Node | Sextile | Uranus | 0.406 | yes | yes |

A full month for the natal-chart example chart (1990-06-15, New York City) is in [`examples/transits_2026-04-01_2026-04-30.csv`](examples/transits_2026-04-01_2026-04-30.csv): a Jupiter return exact on April 2, Saturn sextile Mercury, Pluto trine Mercury, and the Node sextile Uranus, each persisting across consecutive days as the slow bodies crawl through the orb.

Examples are produced by: `python scripts/transits.py ../natal-chart/examples/chart.json --start 2026-04-01 --end 2026-04-30 --out examples/transits_2026-04-01_2026-04-30.csv`

## Install

```bash
# Claude Code, project scope
cp -r transits-to-natal .claude/skills/

# Claude Code, user scope
cp -r transits-to-natal ~/.claude/skills/
```

Install `natal-chart` alongside it: this skill reads the `chart.json` that one writes, and it borrows that skill's Swiss Ephemeris files from `natal-chart/ephe/` when its own `ephe/` folder is empty. Without either set of files the planets use the built-in Moshier ephemeris and Chiron is skipped with a note.

Then ask Claude "what transits are hitting my chart this year", "when does Saturn square my Sun", or "what is coming up for me astrologically in May".

## Run the script directly

```bash
pip install pyswisseph
python scripts/transits.py chart.json --start 2026-01-01 --end 2026-12-31
python scripts/transits.py chart.json --start 2026-04-01 --end 2026-04-30 --fast
python scripts/transits.py chart.json --start 2026-04-01 --end 2026-04-07 --fast --moon --out week.csv
```

Options: `--fast` adds Sun through Mars, `--moon` adds the Moon, `--out` names the file (default `transits_<start>_<end>.csv`). Exit code `1` means bad input: `--end` before `--start`, or a chart that is not `schema_version` 1.

Requires Python 3.11 or newer.

## How it works

- Every day in the range is sampled once, at 12:00 local time in the chart's timezone, the same rule the `astrology-ephemeris` skill uses for the slow bodies. A row is written when a transiting body is within 1° of an exact aspect to a natal point at that moment; the orb is the noon orb, not the orb at exactness.
- The slow bodies are the default because at one sample a day they are the ones the sample describes well: each transit shows on consecutive rows for weeks or months and the smallest orb marks the exact day. The fast planets can slip between two noon samples and flood a long range, so they are opt-in. The Moon, at 13° a day, is caught only when it happens to be near exact at noon; for Moon aspects with exact times use `astrology-ephemeris`.
- The UTC offset is computed per day, so a range that crosses a daylight-saving change is labelled correctly on every row.
- Applying or separating comes from the transiting body's speed alone, since the natal point does not move.
- Angles are scanned only when the chart carries a known birth time; an untimed chart is compared against its bodies alone.
- The zodiac and node type follow the chart, so a sidereal or mean-node chart is scanned on the same terms it was cast.
- Ephemeris files are looked for in `ephe/` here, then in the sibling `natal-chart/ephe/`, then the Moshier fallback is used with Chiron omitted. The aspect table and bodies are constants at the top of `scripts/transits.py`.

## Why it exists

A natal chart is a still picture; transits are what the sky is doing to it now. This is the Solar Fire transit listing as a one-line request: cast the chart once with `natal-chart`, then scan any date range against it and hand the result to a write-up, a datebook, or a timing question.
