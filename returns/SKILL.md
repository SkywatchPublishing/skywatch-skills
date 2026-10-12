---
name: returns
description: >
  Cast return charts from a natal chart.json using Swiss Ephemeris: solar returns, lunar
  returns, and Mars, Jupiter, Saturn, Uranus and Chiron returns, each written as an ordinary
  chart.json plus a Markdown aspect grid, with a summary comparing the return angles and Moon
  to the natal chart. Finds every exact return moment in a date range to the second and casts
  it for the place the user will be, so the houses are right. Use this skill whenever the user
  asks for a solar return, a lunar return, a birthday chart, "my return chart this year", their
  Saturn return, Jupiter return, Chiron return, Mars return or Uranus return, when their next
  return happens, "where should I be for my birthday", or solar return relocation — even if
  they never say "return". It reads the chart.json written by the natal-chart skill; cast one
  first if it does not exist.
---

# Returns Skill

A return is the moment a transiting body comes back to the exact longitude it held at birth, and a return chart is the sky cast for that moment at the place the person is then. The solar return is the birthday chart; the lunar return repeats about every 27.3 days; Saturn, Jupiter, Chiron, Mars and Uranus returns mark the longer cycles. This skill finds the exact moments inside a date range and casts each one through the `natal-chart` skill, so every output is a normal `chart.json`.

---

## What this skill produces

For each return found in the range:

| File | Contents |
|---|---|
| `<body>_return_<YYYY-MM-DD>.json` | A full `chart.json` for the return moment (schema in `natal-chart/CONTRACT.md`): bodies, angles, cusps, aspects, cast with the natal chart's house system, zodiac and node setting. The date is the local date at the return place. The script never overwrites: if `<body>_return_<date>.json` already exists (an earlier run into the same folder, or a second crossing on the same local date in a tight retrograde loop) the new chart takes the next free name `_2`, `_3`, ... and a `Note:` line says so. |
| `<body>_return_<YYYY-MM-DD>_aspects.md` | The Markdown aspect grid natal-chart writes beside every chart, for the return chart's own aspects. |

Plus one `returns_summary.md` for the run: the natal body's longitude, the natal Ascendant and Moon, a table with one row per return (name, exact UTC moment, local time and timezone, place, ASC, MC, DSC, IC, return Moon sign), a line per return comparing the return Ascendant sign and Moon sign to the natal ones, and the flags that apply. The summary is numbered the same way as the charts: if `returns_summary.md` already exists the run writes `returns_summary_2.md`, `_3`, ... and a `Note:` line says so; the `Wrote` line names the file actually written.

In each return's `meta`:

| Key | Value |
|---|---|
| `chart_type` | `solar_return`, `lunar_return`, `mars_return`, `jupiter_return`, `saturn_return`, `uranus_return` or `chiron_return` |
| `derived_from` | `["<natal name>"]` |
| `return_utc` | The exact return moment as `YYYY-MM-DDTHH:MM:SSZ`; `datetime_local` and `timezone` give the same moment at the return place |
| `flags` | natal-chart's own flags plus any of `return_place_natal`, `natal_time_unknown`, `precession_corrected` (below) |

Bodies: `sun` (default), `moon`, `mars`, `jupiter`, `saturn`, `uranus`, `chiron`. Mercury and Venus are not offered (see "Technical notes").

---

## How to run

### Step 1 — Have a chart.json

This skill does not take birth data. If the user has no `chart.json` yet, cast one with the `natal-chart` skill first and note where it was written. The natal chart supplies the target longitude, the name, and the house system, zodiac and node that every return is cast with.

### Step 2 — Ask where they will be

The return's planets are the same anywhere on Earth, but the Ascendant, MC and houses depend on the place the chart is cast for, and a return chart is conventionally cast for where the person is at the moment of the return, not where they were born. So before running:

- If the user has said where they will be (or were) for the return, pass it as `--city`, `--geonameid` or `--lat/--lon`.
- If they have not said, ask: "Where will you be on (around) that date? The houses of the return depend on it." Keep it to one question.
- If they do not know, or want the birthplace version, run without a place. The script then uses the natal location and sets the flag `return_place_natal`; say in the summary that the houses assume they are at the birthplace and would change elsewhere.

For "where should I be for my birthday" questions, run the same solar return once per candidate city (separate `--out-dir` for each) and compare the angles and the house of the return Sun.

### Step 3 — Install the dependencies

Requires Python 3.11 or newer, and `natal-chart` installed beside this skill (same parent folder, `~/.claude/skills/`, or `./.claude/skills/`).

```bash
pip install pyswisseph timezonefinder --quiet
```

`timezonefinder` is only needed for `--lat/--lon` input without `--tz`. Ephemeris files are borrowed from `natal-chart/ephe/` (run `python natal-chart/scripts/fetch_ephemeris.py` once); Chiron returns need them.

### Step 4 — Run the script

Script paths in these steps are relative to the skill folder: either run them from the skill directory, or write the full path as `<skill dir>/scripts/returns.py`.

```bash
python scripts/returns.py chart.json --start 2027-01-01 --end 2027-12-31 --city "Austin, TX"
```

| Argument | Default | Notes |
|---|---|---|
| `chart` | required | Path to a `chart.json` with `schema_version` 1 |
| `--body` | `sun` | `sun`, `moon`, `mars`, `jupiter`, `saturn`, `uranus`, `chiron` |
| `--start`, `--end` | required | ISO dates, inclusive on both ends (00:00 UT on the start day to 24:00 UT on the end day) |
| `--city "Austin, TX"` | | Return place by name; add a region or country code after the comma to disambiguate |
| `--geonameid 4671654` | | Return place by GeoNames id, typically from the ambiguity table |
| `--lat`, `--lon` | | Return place as coordinates; timezone looked up from them |
| `--tz` | | IANA timezone override, only with `--lat/--lon` |
| `--precessed` | off | Shift the target by the precession accumulated since birth (Lahiri ayanamsa), the "precession-corrected" return some astrologers use |
| `--out-dir` | `.` | Folder for the chart files and `returns_summary.md`; created if missing |

Pass at most one of `--city`, `--geonameid`, `--lat/--lon`; none means the natal place.

Exit codes: `0` success (`Wrote N return chart(s), each with a _aspects.md aspect-grid sidecar, and <dir>/returns_summary.md`, then a `Note:` line per flag), `1` bad input (end before start, `--city` together with `--geonameid` or either with `--lat/--lon`, a half-given place, `--tz` without coordinates, a chart that is not `schema_version` 1, a midpoint composite (`this chart has no real moment`: it has no `datetime_local` or `timezone` to search from; a Davison chart is fine), a progressed or directed chart (`meta.chart_type` `secondary_progressed` or `solar_arc_directed`, or any chart carrying `meta.progression`: `this is a progressed or directed chart; cast returns from the natal chart`), a body missing from the chart, `--precessed` on a sidereal chart, natal-chart not installed, unknown city), `2` ambiguous city. On `2` nothing is written and natal-chart's candidate table is printed on stdout: show it, ask the user which place they mean, and re-run with `--geonameid <id>`. Do not guess.

**Examples:**
```bash
# This year's solar return where the user will be
python scripts/returns.py chart.json --start 2027-01-01 --end 2027-12-31 --city "Austin, TX"

# Three months of lunar returns at home, by GeoNames id
python scripts/returns.py chart.json --body moon --start 2027-01-01 --end 2027-03-31 --geonameid 5128581

# The Saturn return, however many passes it makes
python scripts/returns.py chart.json --body saturn --start 2019-01-01 --end 2020-12-31 --lat 30.2672 --lon -97.7431

# Birthplace solar return, flagged return_place_natal
python scripts/returns.py chart.json --start 2027-01-01 --end 2027-12-31 --out-dir returns-2027
```

### Step 5 — Present the return

See "Presenting the return" below.

---

## Flags

| Flag | Meaning | What to say |
|---|---|---|
| `return_place_natal` | No place was given, so the return was cast at the natal location | The houses assume the person is at the birthplace; offer to re-run for where they will actually be |
| `natal_time_unknown` | The natal chart has no birth time, so the target longitude is the noon position | For the Sun and slow bodies the return moment is off by at most hours, which barely moves the return angles; for a lunar return the natal Moon is uncertain by up to 7°, so the return moment is uncertain by half a day and the chart is not reliable. The summary omits the natal Ascendant comparison. |
| `precession_corrected` | `--precessed` was used | Name it; the return moment is roughly 20 minutes per year of age later than the tropical return, so the angles differ. Only tropical charts take `--precessed`: on a sidereal chart the script exits 1 with `--precessed applies to tropical charts only; a sidereal chart's returns are already precession-free` |

natal-chart's own flags (`chiron_unavailable`, `polar_fallback_whole_sign`) pass through and mean the same as there.

---

## The outputs are ordinary charts

Each return file is a complete `chart.json`, so the other skills take it unchanged:

- `chart-wheel` draws it; the caption shows the chart type. Offer the wheel when the user wants to see the return.
- `synastry` run with the natal chart as one side and the return as the other lays the return planets on the natal houses, which is the classic way to read a return chart. Suggest it when the user wants depth.
- `transits-to-natal` scans the sky against the return chart for the year it governs, if asked.

---

## Presenting the return

The files are the deliverable; the conversation needs a reading of the chart. From `returns_summary.md` and the return `chart.json`:

1. **The moment and place.** Give the exact local time and UTC of the return and the place it was cast for. If `return_place_natal` is set, say so.
2. **Lead with the angles and the Moon against natal.** The return Ascendant sign compared to the natal Ascendant, and the return Moon sign compared to the natal Moon; these are what change from year to year. The summary file already has both. Then the MC.
3. **The house of the return body.** For a solar return, the house the return Sun falls in is the theme of the year; read `bodies.Sun.house`. For other bodies, the house of that body. Also note which return planets sit within a few degrees of the return angles.
4. **The tightest aspects.** The two or three smallest `orb` entries in `aspects`, and deliver the `_aspects.md` grid as a file.
5. **Multiple returns.** Saturn through Uranus and Chiron can cross the natal degree three times in a retrograde loop; the script writes one chart per crossing. Present them as one return with three passes, dated, and read the first fully. Lunar returns come every 27.3 days: list them in a table from the summary rather than reading each.
6. **Caveats.** State every flag that applies (above), and that the return is cast with the natal chart's house system and zodiac.

Do not read the return chart as a natal chart; it describes the period until the next return of that body.

---

## Technical notes

| Setting | Value | Where |
|---|---|---|
| Search | Daily samples of the wrapped (body minus natal) difference, sign change detection, 60 bisection steps (about 1e-10 day) | `find_returns()` in `scripts/returns.py` |
| Retrograde loops | Every crossing is a return, so a loop gives one chart per pass | `find_returns()` |
| Target | The natal body's `longitude` from the chart; a sidereal chart is searched in sidereal longitude (Lahiri), which is a precession-corrected return by construction, so `--precessed` is for tropical charts | `longitude()`, `main()` |
| Precession | `--precessed` adds the Lahiri ayanamsa accumulated between birth and the sample to the target. The ayanamsa's zero point cancels in the difference, so any ayanamsa gives the same drift | `precession_shift()` |
| Casting | One `natal_chart.py` run per return, with `--date`, `--time` to the second, the place, and the natal `--houses`, `--zodiac`, `--node`; `chart_type`, `derived_from`, `return_utc` and the flags are rewritten afterwards. A return that falls in the repeated hour of a DST fall-back is passed with natal-chart's `--fold 1`, and the cast is checked against the return moment to within 2 seconds | `cast_return()` |
| Timezone | `--tz` as given; `timezonefinder` for coordinates; for a city, one probe run of natal-chart on the natal date, which also surfaces ambiguity before any search | `resolve_timezone()`, `probe_place()` |
| Ephemeris | `ephe/` here, else the sibling `natal-chart/ephe/`; the Moshier fallback has no Chiron | top of `scripts/returns.py` |

- `chart.json` stores longitudes to 4 decimals (0.0001°). The target is read from that rounded value, so the return moment is exact for the rounded degree, not for the unrounded natal position: the Sun moves 0.0001° in about 4 seconds and the Moon in about 1 second, which bounds the precision of the moments the search reports. The bisection itself resolves far below that.
- Mercury and Venus returns are deferred. Their retrograde loops can put zero or three returns in a year depending on where the loop falls against the natal degree, so "your Venus return this year" needs different wording and documentation than the other bodies; the script refuses them at the argument level.
- Lunar returns recur about every 27.3 days (the sidereal month), so a year gives 13 or 14 charts; narrow the range to the months the user cares about.
- The script imports nothing from the other skill folders; it copies the helpers it needs from `synastry` so the folder is self-contained, and finds `natal_chart.py` beside itself, in `~/.claude/skills/`, or in `./.claude/skills/`.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `returns needs the natal-chart skill installed beside it` | Install `natal-chart` in the same parent folder (or `~/.claude/skills/`, `./.claude/skills/`) |
| `ModuleNotFoundError: swisseph` | Run `pip install pyswisseph` (it compiles from source; on Debian upgrade `setuptools` inside a venv first) |
| `ModuleNotFoundError: timezonefinder` | Run `pip install timezonefinder`, or pass `--tz` with `--lat/--lon` |
| `Wrote 0 return chart(s)` | No return falls in the range: a solar return needs the range to include the birthday, a Saturn return happens near ages 29, 58, 88, a Uranus return near 84, Chiron near 50, Jupiter every 12 years, Mars every 2. Widen the range |
| `no Chiron in bodies (flagged chiron_unavailable)` | The natal chart was cast without ephemeris files; run `python natal-chart/scripts/fetch_ephemeris.py` and re-cast the natal chart |
| Exit code 2 | Ambiguous city: show the table, ask, re-run with `--geonameid` |
| `No city over 15,000 people matches ...` | Use a larger nearby town, or `--lat/--lon` |
| `No timezone found for those coordinates` | Open ocean or Antarctica: pass `--tz` explicitly |
| `expected schema_version 1` | The file is not a `chart.json` from the natal-chart skill; cast one with that skill |
| Return moment differs from another program by minutes | Check whether the other program precession-corrects (`--precessed`), and whether the natal chart is sidereal: a sidereal chart's return is searched in sidereal longitude, which is the precession-corrected moment, later than the tropical return by about 20 minutes per year of age |
| Return Ascendant disagrees with another program by a sign | Different return place or timezone; `meta.location` and `meta.timezone` in the return file show what was used |
| `Note: <name>.json already exists; writing <name>_2.json instead` (likewise `returns_summary.md` -> `returns_summary_2.md`) | The output folder already holds a chart or summary of that name from an earlier run; nothing was overwritten. Use a fresh `--out-dir` per run if that is confusing |
| `--precessed applies to tropical charts only` | The chart is sidereal; drop `--precessed`, its returns are already searched in sidereal longitude |
| `No such file` for the script | Paths are relative to the skill folder; run from there or use the full path |
