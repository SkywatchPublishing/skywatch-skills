---
name: astrology-ephemeris
description: >
  Generate a complete daily planetary aspect list for any month/year using Swiss Ephemeris,
  exported as a CSV. Covers all 10 bodies (Sun through Pluto including Moon), major aspects
  (conjunction, sextile, square, trine, opposition) within a 1° orb, plus every aspect the
  Moon perfects each day with its exact PST/PDT time. Use this skill whenever the user asks for planetary aspects,
  an ephemeris, a monthly aspect list, astrology aspect data, or wants to know what aspects
  are active on any given day or month — even if they don't say "ephemeris" explicitly.
  Also use when the user asks to generate astrology content, a datebook, or daily aspect
  write-ups that would benefit from structured aspect data as a source.
---

# Astrology Ephemeris Skill

Generate a structured, exportable daily aspect list for any calendar month using Swiss Ephemeris.

---

## What this skill produces

A CSV file with one row per active aspect per day, containing:

| Column | Description |
|---|---|
| Date | YYYY-MM-DD |
| Planet 1 | First planet in the pair |
| Aspect | Conjunction / Sextile / Square / Trine / Opposition |
| Planet 2 | Second planet in the pair |
| Orb (°) | Distance from exact at noon Pacific (0.000–1.000); `0.0` on Moon rows, which are listed at the moment they perfect |
| Exact Time | PST/PDT time the aspect perfects, to the nearest minute — Moon aspects only |

---

## Planets included

Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto

## Aspects included

| Aspect | Angle | Orb |
|---|---|---|
| Conjunction | 0° | ±1° |
| Sextile | 60° | ±1° |
| Square | 90° | ±1° |
| Trine | 120° | ±1° |
| Opposition | 180° | ±1° |

---

## How to run

### Step 1 — Install dependency

```bash
pip install pyswisseph --quiet
```

### Step 2 — Run the script

```bash
python scripts/compute_aspects.py <month> <year> [output_filename.csv]
```

**Examples:**
```bash
# May 2026, auto-named output
python scripts/compute_aspects.py 5 2026

# April 2026, custom filename
python scripts/compute_aspects.py 4 2026 april_2026_aspects.csv
```

The script auto-names the output `aspects_<month>_<year>.csv` if no filename is given.

### Step 3 — Present the file

After the script runs, deliver the CSV to the user with whatever file-sharing mechanism the current environment provides.

---

## Technical notes

- **Ephemeris source**: Swiss Ephemeris via `pyswisseph`. No API key needed; uses built-in ephemeris data.
- **Timezone**: All times are America/Los_Angeles (auto-switches PST ↔ PDT for DST).
- **Slow planets** (Sun–Pluto excl. Moon): Aspect checked at noon PST. An aspect appears on a given day if its orb is within 1° at noon. No exact time is listed (they move too slowly for intraday precision to matter).
- **Moon**: Moves ~13°/day, so a noon snapshot would catch only the few Moon aspects that happen to fall near noon (about one in six). Instead the script samples the Moon every hour across the Pacific calendar day, finds each moment its distance from an exact aspect changes sign, and bisects to the second. Every Moon aspect that perfects during the day gets a row, whatever the hour, with its time rounded to the nearest minute and formatted as `HH:MM AM/PM PST` or `HH:MM AM/PM PDT`. A month has roughly 70–80 of them.
- **Day boundaries**: A Moon row's date is the Pacific date of its rounded time, so an aspect at 11:59:45 PM is listed at 12:00 AM on the next day. Days that change daylight saving time are 23 or 25 hours long and every row carries its own PST/PDT label.
- **Aspect orb logic**: Orb is the absolute angular distance from the exact aspect angle, rounded to 3 decimal places.

---

## Related skill

For a chronological aspectarian with exact times for every body (not only the Moon), Moon sign ingresses, and a void-of-course Moon table, use the `aspectarian` skill. It computes from NASA JPL's DE440 ephemeris instead of the Swiss Ephemeris; for April 2026 the two list the same 77 Moon aspects at the same minutes.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: swisseph` | Run `pip install pyswisseph` |
| `zoneinfo` not found (Python < 3.9) | Run `pip install backports.zoneinfo` and change `from zoneinfo import ZoneInfo` to `from backports.zoneinfo import ZoneInfo` |
| Output missing some months' data | Verify the month integer is 1–12 and year is 4 digits |
| Moon times look off | Confirm your system clock is correct; the script uses `America/Los_Angeles` from the IANA tz database |

---

## Customization hooks (for future iterations)

- **Orb width**: Change `ORB = 1.0` at the top of the script to any value.
- **Add asteroids/points**: Add entries to the `PLANETS` dict using `swe.CHIRON`, `swe.TRUE_NODE`, etc.
- **Add minor aspects**: Add entries to the `ASPECTS` dict (e.g., `"Quincunx": 150`).
- **Change timezone**: Replace `"America/Los_Angeles"` with any IANA timezone string.
- **Moon sampling**: `MOON_SCAN_STEP_MIN` sets how often the Moon is sampled before bisection. Precision does not depend on it. The Moon always outruns every other body, so its separation from each one only grows and passes each aspect angle once a month; a step of an hour, or even several, cannot skip one.
