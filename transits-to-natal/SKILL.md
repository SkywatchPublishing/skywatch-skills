---
name: transits-to-natal
description: >
  Scan the sky against a natal chart.json and export a daily CSV of transiting aspects to the
  natal bodies and angles, using Swiss Ephemeris. One row per day per active transit, within a
  1° orb, with orb, applying/separating, and retrograde flag. Slow bodies (Jupiter through Pluto,
  Chiron, Node) by default; Sun through Mars and the Moon by flag. Use this skill whenever the
  user asks about transits, what is hitting their chart, a transit report, a specific transit
  such as "Saturn transit to my Sun", upcoming transits, what is coming up astrologically, or
  what "this year" or "this month" looks like for them — even if they never say "transit". It
  reads the chart.json written by the natal-chart skill; cast one first if it does not exist.
---

# Transits to Natal Skill

Compare the moving sky against a cast birth chart, day by day, and write the hits as a CSV in the same shape as the `astrology-ephemeris` skill's output. The input is a `chart.json` from the `natal-chart` skill; the output is a table the user can read, filter, or feed to a write-up.

---

## What this skill produces

A CSV file, by default `transits_<start>_<end>.csv`, with one row per day per transiting body within 1° of an exact aspect to a natal point:

| Column | Description |
|---|---|
| Date | YYYY-MM-DD, in the natal location's timezone |
| Time | Always `12:00`: the local-noon sample |
| UTC Offset | Offset of that day's noon in the chart's timezone, e.g. `-04:00`. Per row, so it changes on the right day when the range crosses a DST switch |
| Transit | The moving body |
| Aspect | Conjunction / Sextile / Square / Trine / Quincunx / Opposition |
| Natal | The natal body or angle being aspected |
| Orb (°) | Distance from exact at noon, 0.000 to 1.000 |
| Applying | `yes` if the transiting body is closing on exact, `no` if separating, blank if stationary |
| Retrograde | `yes` if the transiting body is moving backwards that day |

The header is the first line and there are no comment lines, so `csv.DictReader` and `pandas.read_csv` read it as is.

Transiting bodies:

| Set | Bodies | On by |
|---|---|---|
| Slow (default) | Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Node (true or mean, following `meta.node` in the chart) | always |
| Fast | Sun, Mercury, Venus, Mars | `--fast` |
| Moon | Moon | `--moon` |

Natal targets: every body in `chart.json` (Sun through Pluto, Chiron, Node) plus the Ascendant, MC, Descendant, and IC. The angles are included only when the chart has a known birth time; a chart with `meta.time_unknown: true` is scanned against its bodies alone.

Aspects: conjunction 0°, sextile 60°, square 90°, trine 120°, quincunx 150°, opposition 180°, all with a flat 1° orb. The zodiac follows the chart (`meta.zodiac`), so a sidereal chart is scanned against sidereal transits.

---

## How to run

### Step 1 — Have a chart.json

This skill does not take birth data. If the user has no `chart.json` yet, cast one with the `natal-chart` skill first and note where it was written. Unknown birth time is fine; the angles are simply left out.

### Step 2 — Install the dependency

Requires Python 3.11 or newer.

```bash
pip install pyswisseph --quiet
```

### Step 3 — Run the script

Script paths in these steps are relative to the skill folder: either run them from the skill directory, or write the full path as `<skill dir>/scripts/transits.py`.

```bash
python scripts/transits.py chart.json --start 2026-01-01 --end 2026-12-31
```

| Argument | Default | Notes |
|---|---|---|
| `chart` | required | Path to a `chart.json` with `schema_version` 1 |
| `--start`, `--end` | required | ISO dates, inclusive on both ends |
| `--fast` | off | Add Sun, Mercury, Venus, Mars |
| `--moon` | off | Add the Moon (see the caveat below) |
| `--out` | `transits_<start>_<end>.csv` | Any path |

Exit codes: `0` success, `1` bad input (`--end` before `--start`, or a chart that is not `schema_version` 1), with the reason on stderr.

**Examples:**
```bash
# A year of slow transits
python scripts/transits.py chart.json --start 2026-01-01 --end 2026-12-31

# One month including the fast planets
python scripts/transits.py chart.json --start 2026-04-01 --end 2026-04-30 --fast

# Everything, to a chosen file
python scripts/transits.py chart.json --start 2026-04-01 --end 2026-04-07 --fast --moon --out week.csv
```

The script prints `Wrote N rows to <path>` on success.

### Step 4 — Present the transits

See "Presenting the transits" below.

---

## The noon snapshot rule

Every row is the sky at 12:00 local time in the chart's timezone, once a day, the same rule the `astrology-ephemeris` skill uses for the slow bodies. The orb shown is the orb at that noon, not the orb at the exact moment the aspect perfects, and the `Date` is the day of the sample, not necessarily the day of exactness. What this means per body group:

- **Slow bodies (default).** Jupiter moves well under a degree a day and the outer planets far less, so a transit within a 1° orb appears on many consecutive rows: Jupiter for a week or two, Saturn for weeks, Uranus through Pluto for months (and three times across a retrograde loop). The day the orb is smallest is the day of exactness to within a day. This is the reliable part of the output.
- **Fast bodies (`--fast`).** The Sun moves about 1° a day and Mercury, Venus, and Mars can move more, so a transit may show on one or two rows only, or slip between two noon samples and be missed entirely on a fast day. Over a long range these bodies also produce a great many rows. Use `--fast` for a month or a few weeks, not a year.
- **Moon (`--moon`).** The Moon moves about 13° a day, so a single noon sample with a 1° orb catches only the Moon aspects that happen to be near exact at noon, roughly one in thirteen, and the orb on those rows is the noon orb, not the moment of exactness. It is off by default because at one sample a day it is noise. When the user wants Moon transits with exact times, use the `astrology-ephemeris` skill instead, which scans the Moon in 10-minute steps.

---

## Ephemeris files

The script looks for Swiss Ephemeris data files in its own `ephe/` folder first, then in a sibling `natal-chart/ephe/` (the usual case when the skills are installed together and `natal-chart/scripts/fetch_ephemeris.py` has been run). With neither present it falls back to the built-in Moshier ephemeris: the planets and Node are still computed, slightly less precisely, and Chiron is dropped from the transiting set with a note on stderr (`Chiron skipped: seas_18.se1 not found`). Tell the user Chiron is missing when you see that note; do not treat it as an error.

---

## Presenting the transits

The CSV is the deliverable, but the conversation needs a summary. From the file:

1. **Group by transit.** Collapse consecutive rows for the same transit, aspect, and natal point into one event: first date, last date, and the date of smallest orb (the exact day). A year of slow transits is a few dozen events, not hundreds of rows.
2. **Lead with the exact ones.** Name the events whose smallest orb is under about 0.25°, then the rest. Say which are applying (building) and which are separating (fading) at the end of the range, and note any retrograde pass, since a retrograde outer planet will return to the same point.
3. **Say what was scanned.** State the body set (slow only, or with `--fast`/`--moon`), the date range, the 1° orb, and that times are local noon in the chart's timezone. If the chart has no birth time, say the angles were not scanned, so no transits to the Ascendant or MC appear.
4. **Deliver the file.** Hand over the CSV with whatever file-sharing mechanism the environment provides.

Do not infer exact clock times from this output. For a specific Moon transit the user cares about, point to `astrology-ephemeris`.

---

## Technical notes

| Setting | Value | Where |
|---|---|---|
| Sample time | 12:00 local in `meta.timezone`, every day | `noon_jd()` |
| Orb | 1° for every aspect, quincunx included | `ORB` at the top of `scripts/transits.py` |
| Aspects | The six-entry `ASPECTS` dict, copied from `natal-chart/scripts/aspects.py` | top of `scripts/transits.py` |
| Bodies | `DEFAULT_BODIES` and `FAST_BODIES` lists | top of `scripts/transits.py` |
| Applying | From the transiting body's speed alone, since the natal point is fixed | `is_applying()` |
| Zodiac and node | Follow `meta.zodiac` and `meta.node` of the chart | `sky_at()` |
| Ephemeris | `ephe/` here, else `natal-chart/ephe/`, else Moshier without Chiron | `EPHE_CANDIDATES` |

- The script imports nothing from the other skill folders; it copies the two helpers it needs so the folder is self-contained.
- The offset label is recomputed for each day, so a range across a DST change (for example March to April in New York) carries `-05:00` on the early rows and `-04:00` on the later ones.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: swisseph` | Run `pip install pyswisseph` (it compiles from source; on Debian upgrade `setuptools` inside a venv first) |
| `Chiron skipped: seas_18.se1 not found` | Run `python natal-chart/scripts/fetch_ephemeris.py` (or copy the files into `ephe/` here); if the network is blocked, tell the user Chiron is omitted |
| `unsupported schema_version` | The file is not a `chart.json` from the natal-chart skill; cast one with that skill |
| `--end must not be before --start` | Swap the dates |
| No rows at all | Normal for a short range with the slow bodies only; widen the range or add `--fast` |
| Thousands of rows | `--fast` or `--moon` over a long range; narrow the range or drop the flag |
| No transits to the Ascendant or MC | The chart has `time_unknown: true`; the angles are not scanned without a birth time |
| A Moon transit the user expected is missing | Expected at one noon sample a day; use `astrology-ephemeris` for Moon aspects with exact times |
