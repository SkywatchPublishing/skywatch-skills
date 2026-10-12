---
name: aspectarian
description: >
  Build a monthly aspectarian (every exact major aspect between the Sun, Moon and planets, with
  the minute it perfects, in time order) and a void-of-course Moon table with the Moon's sign
  ingresses, as two CSVs, computed from NASA JPL's DE440 ephemeris with Skyfield rather than the
  Swiss Ephemeris. Use this skill whenever the user asks for an aspectarian, void-of-course or
  VOC Moon times, when the Moon is void, when the Moon changes sign, exact aspect times for a
  month, timing tables for a datebook or calendar, or aspect data they want to publish or share
  under an open license — even if they never say "aspectarian". Times in any IANA time zone,
  Pacific by default; modern (Sun through Pluto) or traditional (Sun through Saturn) rules. For a
  day-by-day list of which slow aspects are within orb, use astrology-ephemeris instead.
---

# Aspectarian Skill

Produce the two timing tables a datebook prints for every month: an aspectarian, listing each aspect at the minute it is exact, and a void-of-course Moon table, listing each stretch from the Moon's last aspect in a sign to its entry into the next. Both are computed from NASA JPL's DE440 ephemeris with Skyfield, so the skill carries no Swiss Ephemeris (AGPL) dependency and its output can be published under any license the user chooses.

---

## What this skill produces

Two CSV files in the output folder (the current directory unless `--out-dir` is given). The header is the first line and there are no comment lines, so `csv.DictReader` and `pandas.read_csv` read them as is.

**`aspectarian_<year>_<month>.csv`**: one row per exact aspect, in time order.

| Column | Description |
|---|---|
| Date | YYYY-MM-DD, local date of the rounded time |
| Time | Local time to the nearest minute with its zone abbreviation, e.g. `07:12 PM PDT` |
| Body 1 | The body earlier in the order Moon, Sun, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto (roughly fastest first, so always the Moon when it is involved) |
| Aspect | Conjunction / Sextile / Square / Trine / Opposition |
| Body 2 | The slower body |
| UTC | The exact moment in UTC, to the second, e.g. `2026-04-02T02:11:57Z` |

**`voc_<year>_<month>.csv`**: one row per void-of-course period that touches the month, including one that began in the previous month or ends in the next.

| Column | Description |
|---|---|
| Begins Date, Begins Time | Local date and time of the Moon's last exact aspect in the sign |
| Last Aspect | That aspect, e.g. `Moon Sextile Mars` |
| Moon Enters | The sign the Moon enters when the void ends |
| Ingress Date, Ingress Time | Local date and time of that sign ingress |
| Duration | Elapsed time, e.g. `35h 43m`, counted in real time across a daylight-saving change |
| Begins UTC, Ingress UTC | The exact moments in UTC, to the second |

Every Moon sign ingress of the month ends a void, so the void table doubles as the Moon ingress table.

Bodies: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto. With `--traditional`: Sun through Saturn only, for both tables. Aspects: the five major (Ptolemaic) aspects, exact, with no orb.

---

## How to run

Script paths are relative to the skill folder: run them from the skill directory, or write the full path as `<skill dir>/scripts/...`.

### Step 1 — Install the dependency

Requires Python 3.10 or newer.

```bash
pip install skyfield --quiet
```

Skyfield brings `jplephem` and `numpy` with it. All three are MIT or BSD licensed.

### Step 2 — Fetch the ephemeris, once

```bash
python scripts/fetch_ephemeris.py
```

This downloads `de440s.bsp` (32 MB, covering 1849 to 2150) from NASA JPL's NAIF server into `ephe/`. Skip the step if `ephe/de440s.bsp` already exists.

### Step 3 — Run the script

```bash
python scripts/aspectarian.py <month> <year> [--tz ZONE] [--traditional] [--out-dir DIR]
```

| Argument | Default | Notes |
|---|---|---|
| `month`, `year` | required | 1–12; any year the ephemeris covers (1850–2149 with the default file) |
| `--tz` | `America/Los_Angeles` | Any IANA zone name, e.g. `America/New_York`, `Europe/London` |
| `--traditional` | off | Visible planets only; files get a `_traditional` suffix |
| `--out-dir` | current directory | Created if missing |
| `--ephemeris` | `ephe/de440s.bsp` | Another DE file, such as `de440.bsp` or `de441.bsp`, for a wider date range |

Exit codes: `0` success; `1` bad input (month, year, unknown zone) or a missing ephemeris file, with the reason on stderr. On success it prints `Wrote N aspects to <path>` and `Wrote N void-of-course periods to <path>`. A month has roughly 80–110 aspects, 70–80 of them the Moon's, and 12–14 voids.

**Examples:**
```bash
# April 2026, Pacific time
python scripts/aspectarian.py 4 2026

# The same month for an East Coast edition, into a folder
python scripts/aspectarian.py 4 2026 --tz America/New_York --out-dir datebook/eastern

# Traditional rules
python scripts/aspectarian.py 4 2026 --traditional
```

A datebook printed in two time zones needs two runs. Do not shift one file by a fixed number of hours: the date can change, and the zones change daylight saving time on different dates.

---

## The void-of-course rule

The Moon is void of course from its last exact major aspect to any of the bodies while in a sign until it enters the next sign. Astrologers disagree on the details, so state which rule the table follows whenever you present or publish it:

| Choice | This skill | Alternative |
|---|---|---|
| Bodies | Sun through Pluto, the usual modern convention | `--traditional`: Sun through Saturn, the visible planets |
| Aspects | Conjunction, sextile, square, trine, opposition | Some add minor aspects; not supported |
| Orbs | None: an aspect counts at the moment it is exact | Some traditional astrologers count an aspect once the Moon is within orb, which moves where the void begins |
| A sign with no aspect | The void runs on from the last aspect in the sign before, through two signs; the table shows two rows that begin at the same aspect | — |

Voids range from a few minutes to nearly two days. A void of 35 hours, such as the Moon through Gemini on 19–21 April 2026, is real, not an error.

---

## Presenting the tables

1. **Say what was computed.** Month, time zone, modern or traditional bodies, exact aspects only, times rounded to the nearest minute.
2. **Show the voids.** Render the void table in conversation (begins, last aspect, ingress, duration). It is short, 12 to 14 rows, and it is usually what the user wants first.
3. **Summarise the aspectarian.** Do not paste 100 rows. Name the lunar phases (Moon conjunct, square, and opposite the Sun), the aspects between the slow planets, and any void longer than a day. Then point to the file.
4. **Deliver both files** with whatever file-sharing mechanism the environment provides.

---

## Publishing and licensing

The output is the user's to license. When they plan to publish it:

- **The data.** Exact times of astronomical events are facts, and in the United States facts are not protected by copyright (*Feist v. Rural Telephone*, 1991). Dedicating the CSVs to the public domain with CC0 1.0 states that plainly and lets anyone reuse them.
- **The designed tables.** A laid-out page or PDF can carry CC BY 4.0, which permits reuse with credit.
- **Avoid NonCommercial (NC) licenses** if the aim is wide access: many open projects and educators cannot reuse NC material.
- **Credit line.** "Computed from NASA JPL's DE440 ephemeris with Skyfield" is accurate and lets readers check the numbers.

Nothing in the pipeline restricts publication: Skyfield and jplephem are MIT-licensed, and NASA distributes DE440 freely. The Swiss Ephemeris is not used anywhere in the skill; its tests use it only as an optional cross-check.

---

## Technical notes

| Setting | Value | Where |
|---|---|---|
| Positions | Apparent geocentric ecliptic longitude of date (tropical zodiac): light time, aberration, precession and nutation applied | `Sky.longitudes()` |
| Ephemeris | JPL DE440 (`de440s.bsp`), 1849–2150; any JPL `.bsp` via `--ephemeris` | `EPHEMERIS` |
| Search | Every body sampled hourly; each sign change of a separation's distance from exact is bisected to 0.1 s | `search()`, `bisect_many()` |
| Rounding | Nearest minute; an event belongs to the date and month of its rounded local time | `round_minute()` |
| Window | The month plus 4 days either side, so voids that cross a month boundary are complete | `PAD_DAYS` |
| Bodies and aspects | `BODIES`, `TRADITIONAL`, `ASPECTS` | top of `scripts/aspectarian.py` |

- **Accuracy.** DE440 is JPL's current planetary and lunar ephemeris. The tests check all 50 lunar phases of 2026 against the times the U.S. Naval Observatory publishes, to the minute. When pyswisseph is installed they also check positions through 2026 against the Swiss Ephemeris, which agrees to within 0.01 arcseconds with its data files, and confirm both find the same events in the same order.
- **Slow pairs.** Two slow bodies can take minutes to close an arcsecond, so the UTC second of a Saturn–Pluto aspect is precise in the ephemeris's own terms but not meaningful to the second. The minute is.
- **Mars, Jupiter and the outer planets** are taken at their system barycenters, which differ from the planet centers by far less than an arcsecond as seen from Earth.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: skyfield` | `pip install skyfield` |
| `ephemeris not found ... run python scripts/fetch_ephemeris.py` | Run it once; it needs network access to `naif.jpl.nasa.gov`. If that host is blocked, download `de440s.bsp` elsewhere and pass `--ephemeris PATH` |
| `... is outside de440s.bsp` | Fetch `de440.bsp` (120 MB, 1550 to 2650) from the same NAIF folder and pass `--ephemeris PATH` |
| `unknown time zone` | Use an IANA name such as `America/Chicago`, not `CST` |
| A void longer than a day | Normal; see the void-of-course rule above |
| Times differ by a minute from another ephemeris | Rounding (some publishers truncate instead of rounding) or a different void rule; compare the UTC column |
| The Moon's last aspect is to Uranus, Neptune or Pluto and the user expected a traditional table | Re-run with `--traditional` |
