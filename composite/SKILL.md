---
name: composite
description: >
  Cast the chart of a relationship from two natal charts: a midpoint composite (every planet at
  the midpoint of the two positions, houses derived from the composite MC) or a Davison chart
  (a real chart cast for the moment halfway between the two births at the place halfway between
  the birthplaces), written as an ordinary chart.json plus a Markdown aspect grid. Use this skill
  whenever the user asks for a composite chart, a relationship chart, "our chart as a couple",
  a Davison chart, a midpoint chart, "the chart of the relationship", "what does our
  relationship chart say", or wants the relationship itself read as one chart rather than two
  charts compared (that is synastry). Takes two chart.json files from the natal-chart skill, or
  raw birth data for either person, which it hands to natal-chart.
---

# Composite Skill

Synastry compares two charts; a composite treats the relationship as a third entity with a chart of its own. This skill casts that chart two ways. The input is two `chart.json` files written by `natal-chart` (or raw birth data, which this skill passes to `natal-chart` for you); the output is a `chart.json` for the relationship plus a Markdown aspect grid, so `chart-wheel` draws it and, for a Davison chart, `transits-to-natal` scans it.

---

## What this skill produces

One chart file and its grid, by default `composite.json` and `composite.md` (midpoint) or `davison.json` and `davison.md` (Davison). The chart follows `natal-chart/CONTRACT.md` with `meta.chart_type` set to `composite` or `davison` and `meta.derived_from` holding the two source names; `meta.name` is `"A & B"`.

**Midpoint composite** (`--method midpoint`, the default). Every body both charts share is placed at the midpoint of its two positions on the shorter arc, and the aspects between those midpoints are the relationship's aspects. The composite MC is the midpoint of the two MCs (the Robert Hand convention; some programs derive it from the midpoint of the two ARMCs instead, which differs by up to a degree or so), and the houses are derived from that MC at a reference latitude, by default chart A's birthplace, in the natal house system.

Because there is no real sky behind it: `datetime_local`, `datetime_utc`, `utc_offset` and `timezone` are `null`; `julian_day_ut` is the mean of the two; `speed` is the mean of the two speeds, `retrograde` is always `false`, every aspect has `applying: null` and the grid cells carry no `a`/`s` suffix. Orbs are the natal table unchanged (8° for conjunction, opposition, square and trine; 6° sextile; 3° quincunx; +2° when the Sun or Moon is involved). `meta.location` records the reference place and `meta.source.method` is `"midpoint"`.

**Davison chart** (`--method davison`). A real chart cast for the moment exactly halfway between the two births (the mean of the two UTC instants) at the great-circle midpoint of the two birthplaces. The timezone is looked up at that spot; it is often an `Etc/GMT±N` zone when the midpoint falls over an ocean, and if no zone exists at all the chart is cast in UTC and flagged `davison_timezone_utc`.

The Davison chart is cast by `natal-chart` itself, so it has real timestamps, real speeds and retrogrades, applying and separating aspects, and every consumer (`chart-wheel`, `transits-to-natal`, `synastry`, `returns`) takes it unchanged. `meta.location` is the computed midpoint as coordinates (`geonameid` null) and `meta.source.method` is `"davison"`.

Bodies: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Node, plus Ascendant and MC when both inputs are timed. A midpoint composite includes only the bodies present in both inputs; if either lacks Chiron the composite does too and is flagged `chiron_unavailable`.

---

## How to run

Script paths below are relative to the skill folder: either run from the skill directory, or write the full path as `<skill dir>/scripts/composite.py`. Requires Python 3.11 or newer with `pyswisseph`; the `natal-chart` skill must be installed alongside it (same parent folder, `~/.claude/skills/`, or `./.claude/skills/`) for raw birth data, for `--city`/`--geonameid` reference places, and for every Davison chart. A Davison chart also needs `timezonefinder` (`pip install timezonefinder`).

### Step 1 — Get the two charts

Each person is given one of two ways, exactly as in `synastry`:

| Option | Use when |
|---|---|
| `--a chartA.json` / `--b chartB.json` | A `chart.json` from `natal-chart` already exists for that person. |
| `--a-birth "..."` / `--b-birth "..."` | You only have birth data. The string is the full argument list for `natal_chart.py`, quoted as one shell word, e.g. `--a-birth "--name Ada --date 1990-06-15 --time 14:30 --city 'London, GB'"`. |

Mix them freely. A birth string is handed verbatim to the natal-chart script; its stderr is forwarded, and so are its `Note:` lines, with the flag prefixed `a_` or `b_` for the person it is about (`Note: a_polar_fallback_whole_sign`), as synastry does. The cast natal charts are kept in a temporary directory, so if the user will want them again, run `natal-chart` with `--out` and pass the files.

Both charts must share the same zodiac and the same node setting. If they differ (`charts disagree on zodiac: 'tropical' vs 'sidereal'`), re-cast one of them with matching `--zodiac`/`--node` and run again.

### Step 2 — Choose the method, and for a midpoint composite the reference place

Use the midpoint composite unless the user asks for Davison by name or wants to run transits against the relationship chart (see "What the consumers can do"). When the user says "composite" without qualification they mean the midpoint method.

The midpoint composite's houses depend on a reference latitude. By default the script uses chart A's birthplace. Before running, ask one question: **"Where does the relationship live?"** (where the couple is based, or where they met if they are not together). Pass the answer as `--city "Paris, FR"`, `--geonameid <id>`, or `--lat/--lon`. If the user does not know or does not care, let it default and say in the reading that the houses assume A's birthplace. The reference place is recorded in `meta.location`.

These flags are for the midpoint method only; a Davison chart's place is computed from the two births and the script refuses `--city`, `--geonameid`, `--lat/--lon` and `--tz` with `--method davison`.

### Step 3 — Run the script

```bash
# Midpoint composite of two chart files, houses at A's birthplace
python scripts/composite.py --a ada.json --b bob.json --out ada_bob_composite.json

# Midpoint composite with houses for where the couple lives
python scripts/composite.py --a ada.json --b bob.json --city "Paris, FR"

# Davison chart (place and time are computed; no place flags)
python scripts/composite.py --a ada.json --b bob.json --method davison --out ada_bob_davison.json

# Raw birth data for both, quoting each whole string
python scripts/composite.py \
  --a-birth "--name Ada --date 1990-06-15 --time 14:30 --geonameid 2643743" \
  --b-birth "--name Bob --date 1988-02-02 --geonameid 5128581"
```

| Flag | Default | Meaning |
|---|---|---|
| `--method` | `midpoint` | `midpoint` or `davison` |
| `--city`, `--geonameid`, `--lat --lon` | A's place | Reference place for midpoint houses; at most one of the three. `--tz` is accepted for symmetry with `natal-chart` but a midpoint composite has no clock time |
| `--houses` | chart A's | `placidus`, `koch`, `equal`, `porphyry`, `whole_sign` |
| `--out` | `composite.json` or `davison.json` | Output chart path; needs a file name, not just an extension (`--out .json` is refused) |
| `--grid` | `<out stem>.md` | Markdown grid path; must differ from `--out`. For a Davison chart natal-chart writes the grid straight to this path |

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Success; `Wrote <out> and <grid>` followed by one `Note:` line per flag in `meta.flags`; any `Note: a_...`/`Note: b_...` lines printed before it are about that person's natal cast, not the composite. If `--houses` was given but the composite has no houses (an untimed side) a `Note: --houses ignored ...` line follows. |
| `1` | Bad arguments (both `--a` and `--a-birth`, or neither; place flags with `--method davison`; `--lat` without `--lon`; a mix of place flags; `--out` that is only an extension; `--grid` naming the same file as `--out`), an unreadable or malformed chart file (invalid JSON, wrong `schema_version`, no `meta.name` or `bodies`), the two charts disagreeing on zodiac or node, antipodal birthplaces on a Davison chart (`birthplaces are antipodal; no unique midpoint`), or `natal-chart` not found when it is needed. A progressed or directed chart file (`meta.chart_type` `secondary_progressed` or `solar_arc_directed`, or any chart carrying `meta.progression`) is refused for both methods with `composite: progressed and directed charts can't be composited; use the natal charts`. One line on stderr. |
| `2` | A `--city` (in a birth string or as the reference place) matched several places. The natal-chart candidate table is printed on stdout; nothing is written. |

On exit `2`, show the candidate table to the user and ask which place they mean, exactly as the `natal-chart` skill does. Then re-run with `--geonameid <id>` in place of `--city` (inside the birth string, or as the reference flag). If the user already said which one ("Paris, Texas"), write `--city 'Paris, TX'`.

### Step 4 — Present the result

See "Presenting the result" below.

---

## Unknown birth time

If a birth string has no `--time`, or a chart file carries `meta.time_unknown`, that person has no angles or houses, and the relationship chart cannot have them either.

- **Midpoint composite:** `angles` and `houses` are `null`, every body's `house` is `null`, `meta.house_system` is `null`, `moon_range` is `null`, and `meta.flags` carries `time_unknown` and `moon_uncertain`. The composite Moon is the midpoint of one known Moon and one noon Moon, so it is uncertain by up to about 7°; say so, and do not read Moon aspects under a few degrees of orb as exact. The grid has no Ascendant or MC columns.
- **Davison chart:** the script omits `--time`, so `natal-chart` casts the Davison at local noon on the local date of the mean instant at the midpoint place and flags it `time_unknown` and `moon_uncertain` itself. The Davison Moon is then uncertain by the usual 12° to 15°, and the chart has no angles or houses.

When both times are unknown the same applies; nothing further is lost.

---

## What the consumers can do

The output is a `chart.json`, so the other skills take it with no changes, with one exception:

| Skill | Midpoint composite | Davison |
|---|---|---|
| `chart-wheel` | Draws it; the caption shows the chart type | Draws it |
| `transits-to-natal` | **Refused**: the chart has no timezone, so the script exits 1 with `transits: this chart has no timezone (chart_type composite); transits need a real moment, so cast a Davison chart or use the natal chart instead`. Transits to a midpoint composite are deliberately deferred | Works; this is the main reason to choose Davison |
| `synastry` | Possible with one person's natal chart against the composite ("how does each person relate to the relationship"), but unusual; offer it only if asked | Same |
| `returns` | Not meaningful | Works, but unusual |

If the user wants to know "what is happening to our relationship right now", cast the Davison chart and run `transits-to-natal` on it, or offer that when they ask for transits to a midpoint composite.

---

## Presenting the result

The script writes files; the conversation needs a reading. From the chart and the grid:

1. **Say which method was used and why.** "This is a midpoint composite, houses set for Paris where you live" or "This is a Davison chart, cast for 1989-04-09 at 12:37 UTC in the mid-Atlantic, the point halfway between your two births". If the houses defaulted to A's birthplace, say so and offer to re-run.
2. **Lead with the composite Sun, Moon, Venus, Mars and Ascendant.** Sign and house of each (`bodies.<name>.formatted`, `bodies.<name>.house`), then the MC. These describe the relationship's purpose, emotional tone, affection, drive and how it presents itself.
3. **Call out the tightest aspects.** Sort `aspects` by `orb` and mention the four or five smallest ("Mars square Pluto, 0.1°"), then any contact between the Sun, Moon, Venus, Mars and Ascendant whatever its orb. Deliver the grid as a file or paste it when it fits.
4. **State the uncertainty.** If `time_unknown` is set, say there is no Ascendant and no houses for the relationship and that the Moon is approximate. If `davison_timezone_utc` is set, say the Davison local time is given in UTC because the midpoint has no timezone. If `polar_fallback_whole_sign` is set, say the reference latitude was too far north or south for the chosen house system.
5. **Do not score it.** The output is a chart, not a compatibility rating. Describe what is there and leave the weighing to the user. Do not present the composite as a prediction about whether the relationship works.

A midpoint composite is not a moment in time: do not describe it as "the sky on" any date, and do not read its planets as applying or separating.

---

## Technical notes

| Setting | Value | Where |
|---|---|---|
| Input | Two `chart.json` files with `schema_version: 1`, from `natal-chart`, sharing zodiac and node | `load_chart()`, `midpoint_chart()`, `cast_davison()` |
| Midpoint | Shorter arc; an exactly antipodal pair takes the smaller longitude plus 90°; symmetric in A and B | `midpoint()` |
| Composite MC | Midpoint of the two MCs (Robert Hand convention) | `midpoint_chart()` |
| Composite houses | `swe.houses_armc(armc, lat, eps, code)` with `armc = atan2(sin(MC)·cos(eps), cos(MC))` and the obliquity at the mean Julian day; whole-sign fallback flagged `polar_fallback_whole_sign` at polar latitudes | `armc_from_mc()`, `houses_from_mc()` |
| Composite aspects | Bodies plus Ascendant and MC (the Ascendant-MC pair excluded), natal orb table, `applying` always `null` | `find_aspects()` |
| Davison moment | Mean of the two `datetime_utc` instants, to the second | `davison_inputs()` |
| Davison place | Great-circle midpoint of the two `meta.location` coordinates; exactly antipodal birthplaces have no unique midpoint and exit 1 | `great_circle_midpoint()` |
| Davison timezone | `timezonefinder` at the midpoint; `UTC` with flag `davison_timezone_utc` when none | `cast_davison()` |
| Davison cast | One `natal_chart.py` run with `--date`, `--time` to the second, `--lat/--lon/--tz`, A's house system (or `--houses`), zodiac and node, `--out` and `--grid` as given, so the aspect grid is natal-chart's own; `chart_type`, `derived_from` and `source.method` rewritten afterwards | `cast_davison()` |
| Reference place | `--lat/--lon` used directly; `--city`/`--geonameid` resolved by one untimed probe run of `natal-chart` on a fixed date (2000-01-01), since only the location is read; the probe also surfaces an ambiguous city as exit 2 | `resolve_reference()` |
| Ephemeris | `ephe/` here, else the sibling `natal-chart/ephe/` (only the obliquity is computed here) | top of `scripts/composite.py` |
| Dependencies | `pyswisseph`; `timezonefinder` and `natal-chart` for Davison; `natal-chart` for raw birth data and city references | |

- A chart composited with itself is itself, and the Davison of a chart with itself is the same moment and place; the tests check both. Composites from two chart files and from the same two birth strings produce identical JSON.
- The helpers (sign formatting, house placement, the aspect table, `find_aspects`, the grid renderer) are copied from `natal-chart`, not imported across skill folders, so this folder is copyable on its own. Only the Davison and raw-birth paths reach outside it, to the natal script.
- The great-circle midpoint of two places on opposite sides of the world (New York and Tokyo) is on Alaska's Arctic coast (69.7 N, 153.7 W), far from either; that is correct, and the Davison chart there is what the method defines. The arithmetic mean of the coordinates would be somewhere else entirely.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `composite needs the natal-chart skill installed beside it to cast a Davison chart` | Install `natal-chart` in the same parent folder (or `~/.claude/skills/`, `./.claude/skills/`), or use `--method midpoint`. |
| `composite needs the natal-chart skill installed beside it to accept raw birth data or a --city/--geonameid reference` | Same install, or pass chart files with `--a/--b` and the reference place as `--lat/--lon`. |
| `charts disagree on zodiac` or `charts disagree on node` | Re-cast one chart with `natal-chart` so both use the same `--zodiac` and `--node`. |
| `a Davison chart is cast at the great-circle midpoint of the two birthplaces; the reference place flags apply to --method midpoint only` | Drop `--city`, `--geonameid`, `--lat/--lon` and `--tz` for Davison. |
| Exit code `2` with a table of places | Ambiguous city, in a birth string or as the reference. Show the table, ask, and re-run with `--geonameid`. |
| `give --a or --a-birth, not both` | Each person is given exactly one way. |
| `--lat and --lon must be given together` / `pass exactly one of --city, --geonameid, or --lat/--lon` | One reference place, given one way. |
| `--grid and --out are the same file` | Pick a different `--grid` path or let it default to `<out stem>.md`. |
| `--out needs a file name, not just an extension` | `--out .json` has an empty stem; give a name such as `--out ada_bob.json`. |
| `birthplaces are antipodal; no unique midpoint` | The two birthplaces are exactly opposite each other on the globe, so every great circle between them is equally short and no Davison place exists; use the midpoint method. |
| `Note: --houses ignored because the composite has no houses` | One side is untimed, so there are no houses for `--houses` to shape. Expected. |
| `expected schema_version 1`, `not valid JSON`, `missing meta.name`, `missing bodies` | The file is not a `natal-chart` output or is truncated; re-cast it. |
| `ModuleNotFoundError: swisseph` | `pip install pyswisseph` in the environment the script runs in. |
| `ModuleNotFoundError: timezonefinder` on a Davison run | `pip install timezonefinder`. |
| `Note: davison_timezone_utc` | The midpoint has no timezone (open ocean, Antarctica); the chart is cast in UTC, which changes nothing in the positions. Mention it. |
| `Note: time_unknown` and `Note: moon_uncertain` | One input is untimed; no angles or houses, Moon approximate. See "Unknown birth time". |
| `Note: polar_fallback_whole_sign` | The reference latitude is beyond where Placidus or Koch work; houses are whole-sign. Choose a lower-latitude reference place if that matters. |
| `Note: a_polar_fallback_whole_sign` (or another `a_`/`b_` flag) | A flag from casting that person's natal chart from a birth string, not about the composite; read it as the `natal-chart` skill explains it. |
| `transits-to-natal` exits 1 on the composite | Expected for a midpoint composite; cast a Davison chart for transits. |
| `angles` is `null` though both charts were timed | One chart file has had its `angles` removed; re-cast it. |
| Results disagree with another program | Check each natal chart first (timezone, zodiac, house system). Then check which composite MC convention the other program uses (midpoint of MCs here; some use the midpoint of the ARMCs) and which reference latitude; for Davison, whether it uses the great-circle or arithmetic midpoint of the birthplaces. |
