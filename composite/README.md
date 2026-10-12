# composite

Casts the chart of a relationship from two natal charts, as a midpoint composite (every planet at the midpoint of the two positions on the shorter arc, houses derived from the composite MC at a reference latitude) or a Davison chart (a real chart for the moment halfway between the two births at the great-circle midpoint of the two birthplaces). Reads two `chart.json` files from the `natal-chart` skill, or raw birth data that it hands to `natal-chart`, and writes a `chart.json` for the relationship plus a Markdown aspect grid.

**Input:** two `chart.json` files with `schema_version: 1` sharing zodiac and node, or birth data for either person
**Methods:** `midpoint` (default; `--city`/`--geonameid`/`--lat --lon` set the reference place for houses, A's birthplace by default) or `davison` (place and time computed)
**Output:** `composite.json` + `composite.md`, or `davison.json` + `davison.md`, with `meta.chart_type` and `meta.derived_from` set

## Example output

Both examples combine the two charts the `synastry` examples use:

- **A, "Example":** 1990-06-15 at 12:00 in New York City, from [`natal-chart/examples/chart.json`](../natal-chart/examples/chart.json)
- **B, "Partner":** 1988-02-02 at 09:15 in London, from [`synastry/examples/chart_b.json`](../synastry/examples/chart_b.json)

[`examples/composite.json`](examples/composite.json) and [`examples/composite.md`](examples/composite.md) are the midpoint composite with houses at A's birthplace (New York). The composite Ascendant is 11°51' Cancer and the MC 20°48' Pisces; the Sun sits at 18°31' Aries in the tenth house with Mercury and Venus beside it, the Moon at 27°33' Taurus in the eleventh. The tightest of its 34 aspects is Mars square Pluto at 0.1°, then Saturn conjunct Neptune at 0.2°, both opposite the Ascendant. Every timestamp in `meta` is `null`, `applying` is `null` throughout and `meta.source.method` is `"midpoint"`.

[`examples/davison.json`](examples/davison.json) and [`examples/davison.md`](examples/davison.md) are the Davison chart. The moment is 1989-04-09T12:37:30Z, halfway between the two births, and the place is 52.37 N, 41.29 W in the mid-Atlantic, halfway along the great circle from New York to London, where the timezone is `Etc/GMT+3` (local time 09:37:30). It is a real `natal-chart` cast: Ascendant 16°43' Cancer, MC 14°36' Pisces, Sun 19°38' Aries in the tenth, Moon 6°40' Gemini in the eleventh, with real speeds, retrogrades and applying/separating aspects, `chart_type: davison` and `derived_from: ["Example", "Partner"]`.

Examples are produced by (from the repo root):

```bash
python composite/scripts/composite.py --a natal-chart/examples/chart.json --b synastry/examples/chart_b.json --out composite/examples/composite.json
python composite/scripts/composite.py --a natal-chart/examples/chart.json --b synastry/examples/chart_b.json --method davison --out composite/examples/davison.json
```

## Install

```bash
# Claude Code, project scope
cp -r composite .claude/skills/

# Claude Code, user scope
cp -r composite ~/.claude/skills/
```

Install `natal-chart` alongside it (same parent folder, `~/.claude/skills/`, or `./.claude/skills/`): the Davison chart is cast by that skill's script, and raw birth data and `--city`/`--geonameid` reference places go through it too. A midpoint composite from two existing `chart.json` files with a `--lat/--lon` reference (or none) needs only `pyswisseph`.

Then ask Claude for "our composite chart", "the chart of our relationship" or "cast our Davison chart". For a midpoint composite Claude will ask where the relationship lives, because the houses depend on it.

## Run the script directly

```bash
pip install pyswisseph timezonefinder
python scripts/composite.py --a ada.json --b bob.json --out ada_bob_composite.json
python scripts/composite.py --a ada.json --b bob.json --city "Paris, FR"
python scripts/composite.py --a ada.json --b bob.json --method davison
python scripts/composite.py \
  --a-birth "--name Ada --date 1990-06-15 --time 14:30 --geonameid 2643743" \
  --b-birth "--name Bob --date 1988-02-02 --geonameid 5128581"
```

Each birth string is the full argument list for `natal_chart.py`, quoted as one shell word. Options: `--method midpoint|davison`, one of `--city`, `--geonameid` or `--lat --lon` as the reference place for midpoint houses (refused with `--method davison`; a city is resolved by one untimed probe run of `natal-chart` on 2000-01-01), `--houses` to override chart A's house system (ignored with a `Note:` when an untimed side leaves the composite without houses), `--out` (a real file name; `.json` alone is refused) and `--grid` (must differ; a Davison grid is written there by natal-chart directly). Each flag in `meta.flags` is printed once as a `Note:` line after the `Wrote` line; notes from casting a birth string come before it, prefixed `a_` or `b_` (`Note: a_polar_fallback_whole_sign`) as in synastry. Exit code `2` means a `--city` matched several places; the candidates are printed as a table and the script should be re-run with `--geonameid`. Exit `1` covers bad arguments, unreadable or malformed charts, charts that disagree on zodiac or node, antipodal birthplaces on a Davison chart (`birthplaces are antipodal; no unique midpoint`), and a missing `natal-chart` when it is needed (one-line error on stderr).

Requires Python 3.11 or newer; `timezonefinder` is needed for Davison charts only.

## How it works

- **Midpoint:** each body present in both charts is placed at the midpoint of its two longitudes on the shorter arc. The composite MC is the midpoint of the two MCs (the Robert Hand convention; some programs use the midpoint of the ARMCs), converted to a right ascension and fed to pyswisseph's `houses_armc` at the reference latitude with the obliquity at the mean Julian day, in chart A's house system (whole-sign fallback at polar latitudes). Speeds are averaged, `retrograde` is false, every aspect has `applying: null`, and the natal orb table is used unchanged. If either chart is untimed the composite has no angles or houses and is flagged `time_unknown` and `moon_uncertain`.
- **Davison:** the mean of the two UTC instants and the great-circle midpoint of the two birthplaces, with the timezone looked up there (`UTC`, flagged `davison_timezone_utc`, if there is none), are passed to `natal_chart.py` with chart A's house system, zodiac and node. The result's `meta` is then rewritten with `chart_type`, `derived_from` and `source.method`. If either chart is untimed the Davison is cast at noon on the local date of the mean instant and flagged by natal-chart.
- Both inputs must share zodiac and node; the script refuses otherwise. A chart composited with itself is itself, and the Davison of a chart with itself is the same moment and place; the tests check both, along with the round trip from chart files versus birth strings.
- Because a Davison chart is a real moment, `transits-to-natal` works on it; it refuses a midpoint composite, which has no timezone. `chart-wheel` draws either and shows the chart type in the caption.
- Raw birth data and `--city`/`--geonameid` references are delegated to `natal_chart.py`, found beside this skill or in `.claude/skills/`, into a temporary directory. The natal script's exit `2`, its candidate table and its stderr are passed through unchanged; its `Note:` lines from a birth string are prefixed `a_`/`b_`, and those from the Davison cast are the output chart's own flags, printed once at the end.
- The helpers (sign formatting, house placement, the aspect table, `find_aspects`, the grid renderer) are copied from `natal-chart`, not imported, so this folder is copyable on its own.

## Why it exists

After synastry, the next thing people ask is "what is the chart of us", and the two standard answers disagree with each other: the midpoint composite is a geometric construction with no moment behind it, and the Davison chart is a real sky that happens to belong to nobody. Building both on the `chart.json` contract means the wheel, the aspect grid and, for Davison, the transits all come for free, and the only new decisions are the composite MC convention and the reference latitude for houses, both recorded in the file.
