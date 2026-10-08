---
name: natal-chart
description: >
  Cast a natal (birth) chart from a date, time, and place using Swiss Ephemeris, exported as
  chart.json plus a Markdown aspect grid. Covers Sun through Pluto, Chiron, and the lunar Node,
  the Ascendant, MC, and twelve house cusps (Placidus by default; Whole Sign, Koch, Equal,
  Porphyry by flag), tropical or sidereal zodiac, and every natal aspect with orb and
  applying/separating. Use this skill whenever the user asks for a natal chart or birth chart,
  wants to cast a chart, asks where their Moon (or any planet) was, asks about their rising
  sign or ascendant, their houses, or the aspects in their chart, or gives birth data such as
  "born on June 15, 1990 at 2:30pm in Paris" — even if they never say "chart". Also use it as
  the first step whenever another chart skill (chart-wheel, transits-to-natal, synastry) needs
  a chart.json that does not exist yet.
---

# Natal Chart Skill

Cast a birth chart from date, local time, and place, and write it as `chart.json` plus a Markdown aspect grid. The JSON is the shared contract the other chart skills read; the grid is for the user.

---

## What this skill produces

Two files, by default `chart.json` and `chart_aspects.md` next to it:

| File | Contents |
|---|---|
| `chart.json` | Birth data as resolved (coordinates, IANA timezone, UTC offset, Julian day), every body's longitude, sign, degree, house, speed and retrograde flag, the four angles, twelve cusps, and the aspect list. Full schema in [`CONTRACT.md`](CONTRACT.md). |
| `chart_aspects.md` | A Markdown grid, bodies down and across, each cell holding the aspect symbol and orb, e.g. `△ 2.3a` (`a` applying, `s` separating, no suffix for aspects to the angles). Symbols: ☌ conjunction, ⚹ sextile, □ square, △ trine, ⚻ quincunx, ☍ opposition. |

Bodies: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Node (true by default).

Aspects and orbs:

| Aspect | Angle | Orb |
|---|---|---|
| Conjunction | 0° | 8° |
| Sextile | 60° | 6° |
| Square | 90° | 8° |
| Trine | 120° | 8° |
| Quincunx | 150° | 3° |
| Opposition | 180° | 8° |

Any aspect involving the Sun or Moon gets 2° more. Aspects to the Ascendant and MC are included when the birth time is known.

---

## How to run

### Step 1 — Install dependencies

Requires Python 3.11 or newer.

```bash
pip install pyswisseph timezonefinder --quiet
```

`timezonefinder` is only needed for `--lat/--lon` input without `--tz`.

### Step 2 — Fetch the ephemeris files (once)

Script paths in these steps are relative to the skill folder: either run them from the skill directory, or write the full path as `<skill dir>/scripts/natal_chart.py`.

```bash
python scripts/fetch_ephemeris.py
```

This downloads three Swiss Ephemeris data files (about 2 MB) into `ephe/` beside `scripts/`. Run it once per install; it skips files already present. Without the files the script still works: the planets fall back to the built-in Moshier ephemeris (slightly lower precision, `meta.source.ephemeris_files` is `false`) and Chiron is omitted with the `chiron_unavailable` flag. If the download fails (no network), say so and continue without it.

### Step 3 — Run the script

```bash
python scripts/natal_chart.py --name "Ada" --date 1990-06-15 --time 14:30 --city "London, GB"
```

Location is given one of three ways; pass exactly one of `--city`, `--geonameid`, or `--lat/--lon`:

| Option | Use when |
|---|---|
| `--city "Paris, FR"` | The user names a city. Add a country or region code after a comma to disambiguate (`"Paris, TX"`). Matches cities with population over 15,000. |
| `--geonameid 2988507` | You already have the GeoNames id, typically from the ambiguity table below. |
| `--lat 48.85 --lon 2.35 [--tz Europe/Paris]` | The user gives coordinates or the place is not in the table. Timezone is looked up from the coordinates unless `--tz` overrides it. |

Other options, all with sensible defaults:

| Flag | Default | Alternatives |
|---|---|---|
| `--time HH:MM` | omitted = unknown | Local wall-clock time at the birthplace, 24-hour and zero-padded (`09:05`, not `9:05`) |
| `--houses` | `placidus` | `koch`, `equal`, `porphyry`, `whole_sign` |
| `--zodiac` | `tropical` | `sidereal` (Lahiri ayanamsa) |
| `--node` | `true` | `mean` |
| `--out` | `chart.json` | Any path |
| `--grid` | `<out stem>_aspects.md` | Any path |

Exit codes: `0` success, `1` bad arguments or unknown location (message on stderr), `2` ambiguous city (see below).

**Examples:**
```bash
# Known time, city by name
python scripts/natal_chart.py --name "Ada" --date 1990-06-15 --time 14:30 --city "London, GB"

# Unknown time, city by GeoNames id, Whole Sign houses
python scripts/natal_chart.py --name "Ada" --date 1990-06-15 --geonameid 2643743 --houses whole_sign

# Raw coordinates, sidereal zodiac, custom output path
python scripts/natal_chart.py --name "Ada" --date 1990-06-15 --time 06:00 --lat 51.5 --lon -0.13 --zodiac sidereal --out ada.json
```

### Step 4 — Present the chart

See "Presenting the chart" below.

---

## Handling an ambiguous city

When `--city` matches more than one place the script writes nothing and exits with code `2`, printing a table on stdout like this:

```
2 places match 'Paris'. Re-run with --geonameid:

| geonameid | place | population | timezone |
|---|---|---|---|
| 2988507 | Paris, 11, FR | 2138551 | Europe/Paris |
| 4717560 | Paris, TX, US | 24782 | America/Chicago |
```

Show that table to the user and ask which one they mean. Do not guess, even when one candidate is far larger. Then re-run with `--geonameid <id>`. The middle part of each label is the raw GeoNames admin1 code: a US state or Canadian province abbreviation, but a number for many countries (`11` is Île-de-France). If the user already answered the question in their request ("Paris, Texas"), pass the region code directly: `--city "Paris, TX"`.

If no city matches at all (exit `1`, "No city over 15,000 people matches ..."), ask the user for the nearest larger town, or for coordinates to pass with `--lat/--lon`.

---

## Unknown birth time

Omit `--time` when the user does not know it. The script then:

- casts the chart at 12:00 local time, so every planet except the Moon is within about a degree of its true position (the Sun moves about 1° a day, and Mercury and Venus can move more), so quote their degrees with that uncertainty;
- omits houses and angles entirely (`angles` and `houses` are `null`, every `house` is `null`, and there are no aspects to the Ascendant or MC);
- sets `meta.time_unknown: true` with the flags `time_unknown` and `moon_uncertain`;
- records `meta.moon_range`, the Moon's longitude at 00:00 and 23:59 local, since it moves 12° to 15° in a day.

When presenting such a chart, say plainly that there is no rising sign and no houses without a birth time. Report the Moon as a range (if `moon_range` crosses a sign boundary, name both signs), and treat any Moon aspect with an orb wider than a couple of degrees as uncertain. Never state a rising sign for an untimed chart.

---

## Presenting the chart

The script writes files; the conversation needs a readable summary. From `chart.json`:

1. **Positions table.** Render it yourself in Markdown from `bodies`, in the order the file gives (Sun first, Node last), one row per body: body, sign, `formatted` degree, house, and an `R` for `retrograde: true`. Add the Ascendant and MC from `angles` when present. Example row: `| Sun | Gemini | 24°17' Gemini | 10 | |`.
2. **Aspect grid.** Deliver `chart_aspects.md` as a file with whatever file-sharing mechanism the environment provides, and mention the two or three tightest aspects (smallest `orb`) in conversation.
3. **Caveats.** Read `meta.flags` and state each one that applies: unknown time (above), `polar_fallback_whole_sign` (the requested house system cannot be computed at that latitude, Whole Sign was used), `chiron_unavailable` (Chiron missing because the ephemeris files are absent).
4. **Wheel.** If the user wants to see the chart, point them to the `chart-wheel` skill, which draws an SVG from this `chart.json`. Do not draw the wheel by hand.

Keep `chart.json` where other skills can find it: `transits-to-natal` and `synastry` both take its path.

---

## Technical notes

| Setting | Default | Alternatives |
|---|---|---|
| Ephemeris | Swiss Ephemeris via `pyswisseph`, data files in `ephe/` | Moshier fallback when files are absent (planets only, no Chiron) |
| Zodiac | Tropical | Sidereal, Lahiri ayanamsa (`--zodiac sidereal`); houses and angles are shifted too |
| Houses | Placidus | Whole Sign, Koch, Equal, Porphyry (`--houses`) |
| Node | True | Mean (`--node mean`) |
| Bodies | Sun through Pluto, Chiron, Node | Fixed in this version |
| Aspects | Conjunction, opposition, square, trine 8°; sextile 6°; quincunx 3° | Edit the config block at the top of `scripts/aspects.py` |
| Luminary bonus | Sun and Moon orbs +2° | `LUMINARY_BONUS` in `scripts/aspects.py` |
| Location | GeoNames cities15000 table in `data/cities.csv` | `--lat/--lon` bypasses it |
| Timezone | From the city table, or `timezonefinder` for coordinates; historical offsets and DST from `zoneinfo` | `--tz` override |

- Applying or separating is decided from the two daily speeds: a pair is applying when the separation is closing on the exact angle.
- Above roughly 66° latitude Placidus and Koch cannot compute; the script falls back to Whole Sign and sets `polar_fallback_whole_sign`.
- Times in `chart.json` are stored both as birthplace local time and UTC. Nothing here assumes Pacific time.
- Scripts in `scripts/` import each other by sibling path; keep the folder together when copying it.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: swisseph` | Run `pip install pyswisseph` (it compiles from source; on Debian upgrade `setuptools` inside a venv first) |
| `ModuleNotFoundError: timezonefinder` | Run `pip install timezonefinder`, or pass `--tz` with `--lat/--lon` |
| `chiron_unavailable` in the flags | Run `python scripts/fetch_ephemeris.py`; if the network is blocked, tell the user Chiron is omitted |
| Exit code 2 | Ambiguous city: show the table, ask, re-run with `--geonameid` |
| `No city over 15,000 people matches ...` | Use a larger nearby town, or `--lat/--lon` |
| `No timezone found for those coordinates` | Open ocean or Antarctica: pass `--tz` explicitly |
| Positions differ from another program by a degree or more | Check the timezone and DST for the birth date first (`meta.utc_offset`), then the zodiac setting; the engine's golden test (`tests/test_golden.py`) checks the Sun, Moon, Ascendant, MC and one intermediate cusp of one chart against Astrodienst's published values and they agree to 0.001° |
| Rising sign disagrees by a sign | Birth time near a cusp or a wrong offset; `meta.datetime_utc` shows what was actually used |
