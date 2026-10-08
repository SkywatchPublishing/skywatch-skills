# synastry

Compares two natal charts: every inter-aspect from one person's planets and angles to the other's, and house overlays (each person's planets placed in the other's houses). Reads two `chart.json` files from the `natal-chart` skill, or raw birth data that it hands to `natal-chart`, and writes `synastry.json` plus a Markdown grid.

**Input:** two `chart.json` files with `schema_version: 1`, or birth data for either person
**Output:** `synastry.json` (inter-aspects, overlays, flags) and `synastry.md` (grid, A down, B across)
**Orbs:** the natal table minus 2° (6/4/6/6/1/6 for conjunction, sextile, square, trine, quincunx, opposition), +2° when a Sun or Moon is involved

## Example output

[`examples/synastry.json`](examples/synastry.json) and [`examples/synastry.md`](examples/synastry.md) compare two charts:

- **A, "Example":** 1990-06-15 at 12:00 in New York City, from [`natal-chart/examples/chart.json`](../natal-chart/examples/chart.json)
- **B, "Partner":** 1988-02-02 at 09:15 in London (GeoNames 2643743), cast with `natal-chart` into [`examples/chart_b.json`](examples/chart_b.json)

The pair has 50 inter-aspects. Each one in `synastry.json` looks like this:

```json
{
  "a": "Sun",
  "b": "Chiron",
  "aspect": "Conjunction",
  "angle": 0,
  "orb": 0.73,
  "max_orb": 8.0,
  "applying": null,
  "uncertain": false
}
```

and the overlays say where each body falls in the other chart's houses, for example Partner's Sun in Example's 5th house and Example's Moon in Partner's 12th. The grid opens:

| A \ B | Sun | Moon | Mercury | Venus | Mars | ... |
|---|---|---|---|---|---|---|
| Sun |  |  | △ 3.8 | □ 2.8 | ☍ 7.8 | |
| Moon |  |  |  | ☌ 3.9 | □ 1.1 | |

There is no applying/separating mark: two natal charts do not move relative to each other.

## Install

```bash
# Claude Code, project scope
cp -r synastry .claude/skills/

# Claude Code, user scope
cp -r synastry ~/.claude/skills/
```

Then ask Claude to "compare our charts" or "how does his Mars sit on my Venus". To accept raw birth data the skill needs `natal-chart` installed alongside it (same parent folder, `~/.claude/skills/`, or `./.claude/skills/`); with two existing `chart.json` files it needs nothing else.

## Run the script directly

```bash
python scripts/synastry.py --a ada.json --b bob.json --out ada_bob.json
python scripts/synastry.py \
  --a-birth "--name Ada --date 1990-06-15 --time 14:30 --geonameid 2643743" \
  --b-birth "--name Bob --date 1988-02-02 --geonameid 5128581"
```

Each birth string is the full argument list for `natal_chart.py`, quoted as one shell word. Options: `--out synastry.json`, `--grid synastry.md`. Exit code `2` means a `--city` in a birth string matched several places; the candidates are printed as a table and the script should be re-run with `--geonameid` in the string. Exit `1` covers bad arguments, unreadable charts, and raw birth data with no `natal-chart` found.

Requires Python 3.11 or newer. The script itself uses the standard library only; `pyswisseph` is needed through `natal-chart` for raw birth data.

## How it works

- Both charts are read as written; nothing is recomputed from the sky, so the synastry always agrees with each natal chart. Synastry from two chart files and from the same two birth strings produce identical JSON, and the tests check that round trip.
- Every body (and the Ascendant and MC of any timed chart) in A is checked against every one in B with the aspect table at the top of `scripts/synastry.py`, reduced by `REDUCTION = 2.0`. The table and helpers are copied from `natal-chart`, not imported, so this folder is copyable on its own.
- Overlays use the host chart's `houses.cusps`. When one person's birth time is unknown, their chart has no houses, so the overlay into their chart is `null`, the other direction is still filled in, their Moon aspects are flagged `uncertain`, and `a_time_unknown` or `b_time_unknown` is set.
- Raw birth data is delegated: the string is split shell-style and run through `natal_chart.py`, found beside this skill or in `.claude/skills/`, into a temporary directory. The natal script's exit `2` and its candidate table are passed through unchanged.

## Why it exists

Synastry is the third thing people ask of a chart program after the chart itself and the transits. Building it on the `chart.json` contract means the timezone, house and orb decisions are made once in `natal-chart` and reused here; the only new rules are the tighter orbs and the two-way overlays. Composite and Davison charts are left for a later skill.
