---
name: astrology-ephemeris
description: >
  Generate a complete daily planetary aspect list for any month/year using Swiss Ephemeris,
  exported as a CSV. Covers all 10 bodies (Sun through Pluto including Moon), major aspects
  (conjunction, sextile, square, trine, opposition) within a 1° orb, with exact PST/PDT
  times for Moon aspects. Use this skill whenever the user asks for planetary aspects,
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
| Orb (°) | Distance from exact (0.000–1.000) |
| Exact Time | PST/PDT time aspect perfects — Moon aspects only |

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
- **Moon**: Moves ~13°/day. The script scans in 10-minute steps across the full day to find the time of closest exactness within orb. Returns PST/PDT time formatted as `HH:MM AM/PM PST` or `HH:MM AM/PM PDT`.
- **Aspect orb logic**: Orb is the absolute angular distance from the exact aspect angle, rounded to 3 decimal places.

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
- **Moon resolution**: Change `MOON_STEP_MIN` for finer/coarser exact-time precision.
