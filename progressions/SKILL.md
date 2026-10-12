---
name: progressions
description: >
  Move a natal chart.json forward in time with secondary progressions (one day after birth
  for each year of life) and solar arc directions (every natal point moved by the arc the
  progressed Sun has travelled), using Swiss Ephemeris. Writes a progressed or directed chart
  for any date as an ordinary chart.json plus a Markdown aspect grid, and a dated CSV timeline
  of progressed and directed aspects to the natal chart, sign and house ingresses and stations,
  each aspect with its 1° window. Use this skill whenever the user asks about progressions, a
  progressed chart, the progressed Moon or progressed Sun, the progressed Sun changing sign,
  secondary progressions, solar arc, solar arc directions, a directed chart, "what's my
  progressed Moon doing", "what's coming up for me this decade", or long-range timing in their
  own chart, even if they never say "progression". It reads the chart.json written by the
  natal-chart skill; cast one first if it does not exist.
---

# Progressions Skill

Secondary progressions and solar arc directions are the two forward-moving techniques astrologers use most, and both rest on the same key: one day after birth stands for one year of life, so the sky on the 37th day after birth describes the 37th year. A secondary progressed chart is that sky, the planets where they really were that day, with the angles moved forward; a solar arc directed chart moves every natal point forward by the same arc the progressed Sun has travelled. This skill writes either chart for any date as an ordinary `chart.json`, and lists the dated events of both techniques over a range of years as a CSV timeline. The input is a natal `chart.json` from the `natal-chart` skill.

---

## What this skill produces

| Mode | Command | Files |
|---|---|---|
| Secondary progressed chart | `--date <D>` | `secondary_progressed_<D>.json` and `secondary_progressed_<D>_aspects.md` |
| Solar arc directed chart | `--date <D> --method solar-arc` | `solar_arc_directed_<D>.json` and `solar_arc_directed_<D>_aspects.md` |
| Event timeline | `--timeline --start <S> --end <E>` | `progressions_timeline.csv` |

**The charts** are complete `chart.json` files (schema in `natal-chart/CONTRACT.md`): bodies, angles, cusps and aspects, in the natal chart's zodiac, house system and node setting. The `_aspects.md` file is the same Markdown aspect grid natal-chart writes beside every chart. The chart's `aspects` and grid are between the progressed (or directed) points themselves; aspects from the progressed or directed points to the natal chart are in the timeline, or come from running `synastry` (see "The outputs are ordinary charts").

- *Secondary progressed:* every body is computed at the progressed instant, so `speed` is its real daily motion then, in degrees per progressed day, which is degrees per year of life, and `retrograde` shows the planets that are retrograde by progression (in the example, Saturn, Uranus, Neptune, Pluto and the Node). The angles move as `--angles` says (below); the cusps are recomputed from them at the birth latitude, and each body's `house` is its house among the progressed cusps.
- *Solar arc directed:* every natal body, angle and cusp is moved forward by the same arc, so the natal aspect pattern is unchanged and each body keeps its natal house. Directed points have no daily motion: `speed` is `null`, `retrograde` is `false`, every aspect has `applying: null` and the grid cells carry no `a`/`s` suffix. The one exception is whole-sign houses, whose cusps stay on sign boundaries, counted from the directed Ascendant's sign, so a body's house can change.

In each chart's `meta`:

| Key | Value |
|---|---|
| `chart_type` | `secondary_progressed` or `solar_arc_directed` |
| `derived_from` | `["<natal name>"]` |
| `progression` | `{target_date, age_years, solar_arc, angles_method}`: the date the chart is read for, the age then in tropical years, the true solar arc in degrees (both to 4 decimals), and `solar-arc` or `naibod` for a progressed chart with a birth time; `null` for a directed chart and for any chart from an untimed natal chart |
| `datetime_local`, `datetime_utc`, `utc_offset`, `timezone`, `julian_day_ut` | The natal birth values, unchanged. They are not the chart's moment; `progression.target_date` is |
| `moon_range` | `null` for a timed chart. For an untimed one, the progressed Moon for a birth at 00:00 and at 23:59 on the birth date (directed: the natal range plus the arc) |
| `flags` | The natal chart's flags, plus `chiron_unavailable` on a progressed chart cast without the ephemeris files (see Step 3). `polar_fallback_whole_sign` is inherited from the natal chart: whether the house system fails depends on the birth latitude only, so the progressed angles cannot newly trigger it |
| `source` | The natal chart's, with `version` (the pyswisseph that computed the positions) and `ephemeris_files` set for this run: `ephemeris_files` is `false` when the Swiss Ephemeris files were missing and the built-in Moshier ephemeris was used |

**The timeline** is a CSV, sorted by `Exact` (then technique, moving point and target), listing every event whose 1° window overlaps the range:

| Column | Description |
|---|---|
| Technique | `secondary` or `solar arc` |
| Event | `aspect`, `ingress` (a progressed body changing sign), `house` (the progressed Moon entering a natal house) or `station` (a progressed body turning retrograde or direct) |
| Moving | The progressed or directed point |
| Aspect | `Conjunction`, `Sextile`, `Square`, `Trine`, `Quincunx` or `Opposition`; blank on other events |
| Target | The natal body, `Ascendant` or `MC` aspected; blank on other events |
| Exact | The date the aspect perfects, or the date of the ingress or station |
| Orb from | The date the moving point comes within 1° of exact; the birth date if it was already within 1° at birth. Blank on other events |
| Orb to | The date it moves beyond 1° again. Blank on other events, and on an aspect whose window has not closed 60 years after `Exact` |
| Detail | `enters Leo`, `enters natal house 12`, `turns direct at 14°58' Scorpio`; blank on aspects |
| Uncertain | `yes` when an untimed birth makes the date unreliable (see "Unknown birth time"); blank otherwise |

Dates are ISO `YYYY-MM-DD`, local calendar dates at the birthplace (the natal `meta.timezone`), with no clock times. The header is the first line and there are no comment lines, so `csv.DictReader` and `pandas.read_csv` read it as is.

What the timeline scans:

| Event | Moving points | Measured against |
|---|---|---|
| Secondary aspects | Progressed Moon, Sun, Mercury, Venus, Mars, and the progressed Ascendant (plus the progressed MC with `--angles naibod`) | Every natal body, the natal Ascendant and MC |
| Solar arc aspects | Every directed body except the Sun, the directed Ascendant and MC | Every natal body, Ascendant and MC, except the point's own natal place |
| Ingresses | Every progressed body | The signs |
| House ingresses | The progressed Moon | The natal cusps (timed charts only) |
| Stations | Progressed Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron | Their direction of motion (retrograde or direct) |

The six aspects are the repository's usual set, each with a flat 1° window. A conjunction to the Descendant or IC shows as an opposition to the Ascendant or MC. Progressed Jupiter through Pluto, Chiron and the Node are not moving points for aspects, since they move little by progression: over a 90-year life (90 progressed days), for births from 1850 to 2010, at most 20.8° for Jupiter, 11.9° for Chiron, 11.1° for Saturn, 8.1° for the Node, 5.3° for Uranus, 3.4° for Pluto and 3.2° for Neptune. Their sign changes and stations are listed.

---

## How to run

### Step 1 — Have a natal chart.json

This skill does not take birth data. If the user has no `chart.json` yet, cast one with the `natal-chart` skill first and note where it was written. An unknown birth time is accepted, with the limits in "Unknown birth time".

Only natal charts are progressed. A return chart, a midpoint composite, a Davison chart, or a chart that is already progressed or directed (any `meta.chart_type` other than `natal`, an empty or null one included, or any chart carrying `meta.progression`) is refused with exit 1: `progressions: this is a <chart_type> chart, not a natal one; progress the natal chart instead`. A chart with no `meta.chart_type` at all, written before the key existed, is read as natal. A natal chart whose `julian_day_ut`, `datetime_utc` or `timezone` is null is refused too: `progressions: this natal chart has no real moment (julian_day_ut, datetime_utc or timezone is null); recast it with natal-chart`.

### Step 2 — Pick the mode

| The user asks | Run |
|---|---|
| "What's my progressed Moon doing", "my progressed chart", "what sign is my progressed Sun in" | A secondary progressed chart for today's date, plus a timeline for the next few years so the reading has dates |
| "My solar arcs", "solar arc directions", "my directed chart for this birthday" | A solar arc directed chart for the date asked (today if none), plus a timeline for the dates |
| "What's coming up this decade", "when does my progressed Moon change sign", "when does my progressed Sun enter Leo", any "when" question | A timeline over the range; it lists both techniques |

The two techniques answer different questions, conventionally:

- **Secondary progressions** describe slow inner development. The progressed Moon spends about two and a half years in each sign, and a similar span in each natal house (longer or shorter with the house's size), setting the mood and focus of that chapter; the progressed Sun changes sign about every thirty years; a planet turning retrograde or direct by progression marks a shift that lasts decades. Use the progressed chart when the user wants their present chapter described.
- **Solar arc directions** move the whole natal chart as one block, about a degree a year, so the natal pattern stays intact and what matters is when a directed point reaches a natal point. They are the usual technique for timing events, and each solar arc window is about two years wide. Use the directed chart when the user asks for solar arcs by name; otherwise the timeline carries them.

When unsure, run the timeline: it carries both techniques with dates, and a chart alone has none. For "what's coming up" this year or this month, run the `transits-to-natal` skill; progressions answer it for the decade.

### Step 3 — Install the dependency

Requires Python 3.11 or newer.

```bash
pip install pyswisseph --quiet
```

Ephemeris files are looked for in this skill's own `ephe/` folder, then in the sibling `natal-chart/ephe/` (run `python natal-chart/scripts/fetch_ephemeris.py` once). Without them pyswisseph falls back to its built-in Moshier ephemeris, as natal-chart does: the planets are still computed, slightly less precisely, but Chiron is not. A progressed chart then leaves Chiron out, adds `chiron_unavailable` to `meta.flags` and prints `Note: chiron_unavailable`; a directed chart keeps Chiron, which is natal Chiron plus the arc; both record `meta.source.ephemeris_files: false`. A timeline leaves out progressed Chiron's sign ingresses and stations, keeps directed Chiron and aspects to natal Chiron (neither needs the file), and prints `Note: chiron_unavailable`. Tell the user progressed Chiron is missing.

### Step 4 — Run the script

Script paths in these steps are relative to the skill folder: either run them from the skill directory, or write the full path as `<skill dir>/scripts/progressions.py`.

```bash
python scripts/progressions.py chart.json --date 2027-06-15
```

| Argument | Default | Notes |
|---|---|---|
| `chart` | required | Path to a natal `chart.json` with `schema_version` 1 |
| `--date` | | ISO date the chart is read for. Give exactly one of `--date` and `--timeline` |
| `--method` | `secondary` | `secondary` or `solar-arc`; charts only |
| `--angles` | `solar-arc` | `solar-arc` or `naibod`: how secondary progressed angles move. For secondary charts and the timeline; refused with `--method solar-arc` |
| `--timeline` | off | Write the event CSV instead of a chart |
| `--start`, `--end` | required with `--timeline` | ISO dates, inclusive, compared as whole local days; at most 120 years apart |
| `--out` | `secondary_progressed_<date>.json`, `solar_arc_directed_<date>.json` or `progressions_timeline.csv` | Output path, in a folder that already exists; must not be the input chart (by any path or hard link) |
| `--grid` | `<out stem>_aspects.md` | Aspect grid path, charts only, in a folder that already exists; must differ from `--out` and from the input chart |

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Success. A chart prints `Wrote <out> and <grid>`, then a `Note: <flag>` line per flag in `meta.flags`. A timeline prints `Wrote N events to <out>`, then `Note: --start <date> is before the birth date; starting at <birth date>` when the start was moved, then `Note: chiron_unavailable` when the ephemeris files are missing (Step 3), then the unknown-birth-time note for an untimed chart. Either mode then prints `Note: --angles ignored because the natal chart has no birth time, so no angles to progress` when `--angles` was given for an untimed chart. |
| `1` | Bad arguments or input, with the reason on stderr and nothing written: both or neither of `--date` and `--timeline`; `--timeline` without `--start` and `--end`; `--method` or `--grid` with `--timeline`; `--start` or `--end` with `--date`; `--angles` with `--method solar-arc`; `--end` before `--start`; an invalid date or choice; `--grid` the same file as `--out`; `--out` or `--grid` naming the input chart, naming a folder, or in a folder that does not exist (all checked before anything is computed); an unreadable or malformed chart file (missing, invalid JSON, wrong `schema_version`, no `meta.name` or `bodies`, or a key the computation needs missing or of the wrong type, reported as `progressions: <path>: malformed chart (<error>)`); a chart that is not natal or has no real moment (Step 1); a `--date` before the birth date; a timeline `--end` before the birth date; a range over 120 years. Usage errors print the usage line first. |

There is no exit code 2: this skill takes no place names.

**Examples:**
```bash
# Secondary progressed chart for a date, solar-arc angles
python scripts/progressions.py chart.json --date 2027-06-15

# The same with Naibod angles
python scripts/progressions.py chart.json --date 2027-06-15 --angles naibod --out progressed_naibod.json

# Solar arc directed chart
python scripts/progressions.py chart.json --date 2027-06-15 --method solar-arc

# Ten years of events, both techniques
python scripts/progressions.py chart.json --timeline --start 2027-01-01 --end 2036-12-31
```

### Step 5 — Present the results

See "Presenting the results" below.

---

## The time key

- One day after birth stands for one tropical year of life, 365.24219 days. The age is (target − birth) / 365.24219 days, and the progressed instant is the birth moment plus that many days: at 37 the progressed sky is the sky about 37 days after birth.
- The target is local noon on `--date` in the natal timezone, whatever timezone the person lives in now. One day of real time is about four minutes of progressed time, so neither the time of day nor the timezone moves the progressed Moon by more than about 0.04°.
- A target before the birth moment is clamped to the birth moment, age 0: on the birth date itself, for a birth after noon, the chart has age 0 and arc 0 and reproduces the natal chart. A `--date` before the birth date exits 1 (`--date <date> is before the birth date <birth date>; progressions run forward from birth`). A timeline `--start` before the birth date is moved to the birth date with a `Note:`, and a timeline `--end` before the birth date exits 1.
- The solar arc is the **true** solar arc: the progressed Sun minus the natal Sun at the target, not a mean rate of 1° a year. The Sun moves about 0°57' a day in early July and 1°01' in early January, so the arc grows at a rate between those, set mainly by the time of year of birth. The example, born in June, has an arc of 35°18' (35.2991°) at age 37.0001.

---

## Angles: solar-arc (default) or Naibod

A secondary progressed chart's angles are not read off the progressed sky: they are moved forward from the natal angles by a rule, and `--angles` picks the rule:

- **`solar-arc` (default):** progressed MC = natal MC + true solar arc. The Ascendant and cusps are then worked out from that MC at the birth latitude in the natal house system. Under this rule the progressed MC is the directed MC by definition, so the timeline lists MC events once, under `solar arc`.
- **`naibod`:** the natal right ascension of the MC advances 0°59'08" (0.9856473°) per year, the Sun's mean motion, and the MC, Ascendant and cusps follow from it. In the example the Naibod MC is 1.66° behind the solar-arc MC at age 37 (14°52' Cancer against 16°31' Cancer), so at that age an aspect to the Naibod MC comes roughly a year and a half later. Use it when the user or their astrologer asks for Naibod. With Naibod the timeline lists the progressed MC under `secondary` as well as the directed MC under `solar arc`.

A solar arc directed chart moves every angle and cusp by the arc; `--angles` does not apply to it and is refused. Even with solar-arc angles, the progressed Ascendant differs from the directed Ascendant, because one is worked out from the progressed MC through the house table and the other is the natal Ascendant plus the arc: in the example 14°12' Libra against 19°11' Libra. Say which one you mean.

For a sidereal chart the arithmetic is done in tropical longitude and shifted back with the Lahiri ayanamsa at the progressed instant, so the angles agree with the progressed bodies. An untimed chart has no angles to move.

---

## Reading the timeline

**Windows.** An aspect row is a window: `Orb from` is when the moving point comes within 1° of exact, `Exact` when it perfects, `Orb to` when it moves beyond 1° again. Read it as an aspect building to `Exact` and fading after it. In the example, typical widths are about two months for the progressed Moon (it moves about a degree a month), two years for the progressed Sun and every solar arc, one to three years for progressed Mercury, Venus and Mars at their normal pace, and about two and a half years for the progressed Ascendant (longer or shorter with the sign and the birth latitude). Ingress, house and station rows have no window: they are point events on `Exact`, with `Orb from` and `Orb to` blank.

**Rows outside the range.** A row is listed when its window overlaps the range, compared as whole local days, so its `Exact` can fall before `--start` or after `--end`: 9 of the 132 rows in the example. Progressed Mercury, Venus and Mars can stall near a station, and then a window can last years or decades (up to about 37 years for Mars); the timeline scans them 40 years either side of the range and still lists any window that overlaps it, however far away its `Exact` is. An `Orb from` on the birth date means the point was within 1° at birth, and a blank `Orb to` on an aspect means it is still within 1° 60 years after `Exact`.

**Retrograde passes.** A progressed planet that turns back across a natal point gives one row per exact pass, each with its own window, and the windows of passes in one loop overlap. Present them as one event with several exact dates.

**Stations that fall short.** A station that comes within 1° of an aspect point without perfecting produces no aspect row, because the point never reaches exact; the station row's `Detail` shows where it stations. The example's progressed Mercury turns retrograde on 2061-05-17 with the Detail `turns retrograde at 23°34' Virgo`: 27' short of a trine to natal Saturn (24°01' Capricorn) and 43' short of a square to the natal Sun (24°17' Gemini), and neither gets an aspect row. When a station's degree sits within a degree of an aspect to a natal point, compare it with the natal positions yourself and mention the near-aspect, which holds for years.

**The Sun is listed once, under secondary.** The true solar arc is the distance the progressed Sun has moved, so the directed Sun is always exactly the progressed Sun, and its aspects are listed once, as `secondary` rows (in the example: Sun sextile Mercury 2034-02-20, Sun opposition Node 2036-05-20, Sun quincunx Uranus 2036-06-02). There are no `solar arc` rows moving the Sun; present these as aspects of the progressed (and directed) Sun. The MC is the mirror case: with the default solar-arc angles it is listed once, under `solar arc`.

**Dates and the noon chart.** `Exact` is the local calendar date at the birthplace on which the aspect perfects, found to within a minute, so it does not shift with the range asked for. The moment of perfection can fall earlier or later in that day than the local noon that a `--date` chart for the same date is cast for, so that chart shows the aspect a few hundredths of a degree from exact, not at 0.000°.

---

## Unknown birth time

If the natal chart has `meta.time_unknown: true`, it was cast for noon, and the birth could have been up to twelve hours either side. Say so plainly before giving any date:

- **Secondary events can be about six months off either way.** A day of birth stands for a year of life, so a 12-hour error in the birth moment is half a progressed day, which is half a year. Every secondary row (aspects, ingresses and stations alike) is marked `Uncertain` `yes`. Tell the user: "Without a birth time, each of these dates could be up to about six months earlier or later."
- **Solar arc events touching the Moon, Sun, Mercury, Venus or Mars are uncertain too.** The arc itself barely changes, because it is a difference of two Sun positions that shift together, but the natal positions it moves and aims at do: a 12-hour error moves the natal Moon by up to about 7° (years of arc) and the Sun, Mercury, Venus and Mars by roughly 0.4° to 1° (months). A solar arc row is marked `yes` when any of those five is the moving point or the target; solar arc rows between Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron and the Node stay blank.
- **No angles and no houses.** The charts have `angles`, `houses` and every body's `house` null, `progression.angles_method` null, and no Ascendant or MC in the grid; `--angles` is ignored, with a `Note:` (see Step 4). The timeline has no Ascendant or MC rows and no natal house ingresses.
- **The progressed Moon is a range.** `bodies.Moon` is the progressed Moon for a noon birth; `meta.moon_range` gives it for a birth at 00:00 and at 23:59, a span of about a year's progressed motion (12° to 15°). Use the range for sign claims, as with natal-chart's `moon_uncertain` flag.

The timeline run prints this note, which says the same:

```
Note: the birth time is unknown, so every secondary event may fall up to about six months either side of its date (a 12-hour error in the birth moment is half a progressed day, which is half a year), and solar arc events involving the Moon, Sun, Mercury, Venus or Mars shift with those natal positions, by months (years for the Moon); those rows are marked Uncertain, and angle and house events are left out
```

---

## The outputs are ordinary charts

Each chart file is a complete `chart.json`, so the chart skills take it, except the two that would misread it:

| Skill | A progressed or directed chart |
|---|---|
| `chart-wheel` | Draws it; the caption reads, for example, "Secondary progressed for Example · 2027-06-15" or "Solar arc directed for Example · 2027-06-15". Offer the wheel when the user wants to see the chart |
| `synastry` | Reads it. Run it with the progressed (or directed) chart as one side and the natal chart as the other to get the progressed-to-natal aspects at that date with their orbs (synastry's own orb table), and the progressed planets in the natal houses: the classic bi-wheel reading. Pass the progressed chart as `--a` and the natal chart as `--b`: both sides carry the same name, so side A (`a` in each inter-aspect, `overlays.a_in_b_houses`) is the progressed chart, and `config.a.source` and `config.b.source` (the file paths) tell them apart. Suggest it when the user wants depth on one date |
| `returns` | Refuses it with exit 1: `returns: this is a progressed or directed chart; cast returns from the natal chart` |
| `composite` | Refuses it with exit 1: `composite: progressed and directed charts can't be composited; use the natal charts` |
| `transits-to-natal` | Runs, since the chart keeps the natal timezone, but transits to a progressed chart are unusual: transits are normally read against the natal chart. Offer it only if asked |

This skill refuses its own output as input, along with every other non-natal chart: progress the natal chart again for another date instead.

---

## Presenting the results

The files are the deliverable; the conversation needs a reading. From the chart and the timeline:

1. **Say what was cast.** The technique, the target date, the age and the solar arc ("secondary progressed chart for 15 June 2027, age 37; solar arc 35°18'"), the angle method if Naibod, and the zodiac if sidereal.
2. **Lead with the progressed Moon.** Its sign and degree (`bodies.Moon.formatted`) and its house. Say which house you give: `bodies.Moon.house` in the progressed chart is its house among the progressed cusps, while the natal house it is passing through comes from placing its longitude among the natal chart's `houses.cusps`, or from the most recent `house` row (`enters natal house N`) of a timeline that starts a few years earlier. The natal house is the common reading. In the example, on 2027-06-15, the progressed Moon is at 6°48' Leo, in the natal 11th house and the progressed 10th. Then when it entered the sign and when it leaves (the Moon's `ingress` rows).
3. **Then the next two or three exact events** after the target date, from the timeline, each with its technique and window: "solar arc Venus conjunct natal Sun, exact 21 June 2027 (in orb June 2026 to July 2028)", "progressed Moon opposite the natal Node, exact 19 July 2027 (in orb 23 June to 14 August)". If the user asked only for a chart, run a timeline from the target date over the next few years to get these; the chart has no dates.
4. **Group a timeline by year.** Within each year go in date order, and say for every event which technique it comes from ("progressed Moon trine natal Mars", "solar arc MC conjunct natal Chiron"). Merge the passes of one retrograde loop. Lead each year with the rarer events: the progressed Sun or an angle changing sign, stations, the progressed Moon changing sign or natal house, and aspects to or from the Ascendant and MC. The progressed Moon makes an aspect about every month or two, so over a long range summarize those rather than reading each.
5. **State the caveats.** If the birth time is unknown, say before any date that secondary dates can be about six months off either way and which solar arc rows are uncertain too, and that there are no angles or houses. Say the timeline uses a 1° window and dates without clock times.
6. **Deliver the files.** Hand over the chart, grid and CSV with whatever file-sharing mechanism the environment provides.

Progressions describe timing and themes, not outcomes. Describe what a period emphasizes and when; do not predict concrete events from an aspect.

---

## Technical notes

| Setting | Value | Where |
|---|---|---|
| Time key | Age = (target − birth) / 365.24219 days; progressed instant = birth + age days; target = local noon of `--date` in `meta.timezone`, never before the birth moment | `YEAR`, `progressed_jd()`, `target_jd()` |
| Solar arc | Progressed Sun minus natal Sun, in the chart's zodiac, in `[0, 360)` | `solar_arc()` |
| Progressed bodies | `swe.calc_ut` at the progressed instant with the chart's zodiac (Lahiri for sidereal) and node; Chiron left out and flagged `chiron_unavailable` when its ephemeris file is missing | `body_positions()`, `progressable()` |
| Progressed angles | Solar-arc: MC = natal MC + arc, ARMC from that MC. Naibod: natal ARMC + 0.9856473° per year. Then `swe.houses_armc` at the birth latitude with the birth obliquity; whole-sign fallback flagged `polar_fallback_whole_sign` at polar latitudes; sidereal charts shifted with the Lahiri ayanamsa (with nutation) at the progressed instant | `house_mover()`, `houses_from_armc()` |
| Directed chart | Every natal longitude, angle and cusp + arc; whole-sign cusps from the directed Ascendant's sign | `directed_chart()` |
| Chart aspects | Natal orb table (8° conjunction, opposition, square, trine; 6° sextile; 3° quincunx; +2° with the Sun or Moon), Ascendant-MC pair excluded | `find_aspects()` |
| Timeline sampling | Every 15 days of real time; crossings of exact and of the ±1° edges bisected to the minute; stations from a sign change in progressed speed | `STEP`, `TOL`, `_zero_crossings()`, `_edge()` |
| Scan margins | 5 years either side of the range; 40 years for progressed Mercury, Venus and Mars; a window's closing edge searched up to 60 years after `Exact` | `MARGIN`, `SLOW_MARGIN`, `EDGE_LIMIT` |
| Range limit | 120 years, after a start before birth is moved to the birth date | `MAX_YEARS` |
| Ephemeris | `ephe/` here, else the sibling `natal-chart/ephe/`, else pyswisseph's built-in Moshier ephemeris (no Chiron) | `EPHE_DIR`, `ephemeris_files_present()` |

- A target on the birth moment reproduces the natal chart under both angle methods with a zero arc, and a directed chart is the natal chart shifted by the arc; the tests check both, along with the example's figures (age 37.0001, arc 35.2991°, progressed Sun 29°35' Cancer, progressed Moon 6°48' Leo), that each secondary `Exact` date puts the moving point within 0.05° of the aspect, that moving the sample grid by a fraction of a step moves no date, that a one-day range on a row's `Exact`, `Orb from` or `Orb to` date lists that row with the same dates, and that the README commands reproduce the committed examples byte for byte.
- A ten-year timeline takes about a second.
- The script imports nothing from the other skill folders; the helpers it needs (sign formatting, house placement, the aspect table, house-from-ARMC, the grid renderer, the argument parser and chart loader) are copied from `natal-chart` and `composite`, so the folder is copyable on its own.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: swisseph` | Run `pip install pyswisseph` (it compiles from source; on Debian upgrade `setuptools` inside a venv first) |
| `Note: chiron_unavailable` | The ephemeris files are missing, so progressed Chiron is left out (Step 3); run `python natal-chart/scripts/fetch_ephemeris.py` (or copy the files into `ephe/` here) and run again, or tell the user Chiron is omitted |
| `progressions: this is a <chart_type> chart, not a natal one; progress the natal chart instead` | The input is a return, composite, Davison, or progressed or directed chart; pass the natal `chart.json` |
| `progressions: this natal chart has no real moment ...` | The chart's `julian_day_ut`, `datetime_utc` or `timezone` is null; recast it with `natal-chart` |
| `give exactly one of --date (a chart) and --timeline (an event list)` | Pass one: `--date` for a chart, `--timeline --start --end` for the event list |
| `--timeline needs --start and --end` | Add both dates |
| `--method and --grid apply to --date charts; the timeline lists both techniques` | Drop them; the timeline already has both techniques and no grid |
| `--start and --end apply to --timeline; a chart takes --date` | Use `--date` alone for a chart, or add `--timeline` |
| `--angles applies to secondary progressed charts; a solar arc directed chart moves every angle by the arc` | Drop `--angles` with `--method solar-arc` |
| `--end <date> is before --start <date>` | Swap the dates |
| `--date <date> is before the birth date <date>; progressions run forward from birth` | Pick a date on or after the birth date |
| `--end <date> is before the birth date <date>; there is nothing to list` | The whole range is before birth; move it later |
| `<start> to <end> is over 120 years; split it into shorter ranges` | Run several shorter timelines |
| `--grid and --out are the same file` | Choose a different `--grid`, or let it default to `<out stem>_aspects.md` |
| `--out <path> is the input chart` (or `--grid`) | Choose a different output name; the natal chart is never overwritten |
| `--grid <path>: the folder <folder> does not exist; create it first` (or `--out`) | `--out` and `--grid` must be in a folder that exists; create it first. Nothing is written until both are valid |
| `--out <path> is a folder; give a file name` (or `--grid`) | Give a file name, not a folder |
| `expected schema_version 1`, `not valid JSON`, `missing meta.name`, `missing bodies` | The file is not a `natal-chart` output or is truncated; re-cast it |
| `progressions: <path>: malformed chart (KeyError('location'))` (or another `KeyError`, `TypeError` or `AttributeError`) | A key the computation needs is missing or holds the wrong type, as in a hand-edited file or one from another tool; re-cast it with `natal-chart` |
| `Note: --angles ignored because the natal chart has no birth time` | Expected for an untimed chart: there are no angles to progress |
| Every secondary row says `Uncertain` `yes` | The natal chart has no birth time; see "Unknown birth time" |
| An event whose `Exact` is outside the range | Expected: its window overlaps the range. Mercury, Venus and Mars windows near a station can last decades |
| No `solar arc` rows moving the Sun | Expected: the directed Sun is the progressed Sun, so its aspects are the `secondary` Sun rows |
| No MC rows under `secondary` | Expected with the default solar-arc angles: the progressed MC is the directed MC, listed under `solar arc`. Use `--angles naibod` for a separate progressed MC |
| A progressed planet stations close to a natal point but has no aspect row | It never perfects within 1°; read the station row's `Detail` degree (see "Reading the timeline") |
| `Note: time_unknown` and `Note: moon_uncertain` | The natal chart has no birth time: no angles or houses, and the progressed Moon is a range. See "Unknown birth time" |
| `Note: polar_fallback_whole_sign` | Inherited from the natal chart: its house system fails at the birth latitude, so the natal and progressed houses are whole-sign. The failure depends on the latitude only, so the progressed angles cannot newly trigger it; say so |
| Progressed angles differ from another program by a degree or more | Check the angle method: here the solar arc is added to the MC in longitude (default) and Naibod advances the right ascension of the MC (`--angles naibod`); other programs may apply the arc in right ascension, use a mean arc, or use the sidereal time of the progressed day |
| `No such file` for the script | Paths are relative to the skill folder; run from there or use the full path |
