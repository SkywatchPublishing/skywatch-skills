# Returns and composites design

Date: 2026-10-11
Status: validated in conversation, ready for implementation planning

## Goal

Add the second batch of chart types on top of the chart-core contract: return
charts (solar, lunar, and planetary for Mars through Uranus plus Chiron) and
relationship charts (midpoint composite and Davison). Both reuse `chart.json`
and the existing consumers unchanged, which is the test of whether the contract
and the separate wheel skill were worth it.

| Skill | Produces | Depends on |
|---|---|---|
| returns | one chart.json per return in a date range, plus a Markdown summary | natal-chart script (sibling), pyswisseph |
| composite | chart.json for a midpoint composite or a Davison chart | natal-chart script (sibling), pyswisseph |

## Architecture

The two skills delegate every real chart cast to the sibling `natal-chart`
script, found the way synastry finds it (sibling folder, then
`~/.claude/skills/`, then `./.claude/skills/`). A return chart and a Davison
chart are therefore genuine natal-chart output. The midpoint composite has no
real sky, so `composite` copies the small helpers it needs (sign formatting,
house placement, the aspect table and `find_aspects`) as synastry already does,
and never imports across folders.

`natal_chart.py` already accepts seconds in `--time`, so return moments pass
through exactly. No other change to natal-chart beyond the contract addition
below.

## Contract addition

`meta` gains two optional keys. `schema_version` stays 1 because they are
additive and every consumer ignores unknown keys.

| key | type | meaning |
|---|---|---|
| `chart_type` | string | `natal`, `solar_return`, `lunar_return`, `mars_return`, `jupiter_return`, `saturn_return`, `uranus_return`, `chiron_return`, `composite`, `davison` |
| `derived_from` | array of string | Names of the source charts; empty for natal |

natal-chart writes `chart_type: "natal"` and `derived_from: []`. The returns
and composite scripts rewrite the two keys after delegation. chart-wheel shows
the chart type in its caption.

## returns

Inputs: a `chart.json`, `--body` (`sun` default; `moon`, `mars`, `jupiter`,
`saturn`, `uranus`, `chiron`), `--start` and `--end` dates, and a return place
given as `--city`, `--geonameid`, or `--lat/--lon [--tz]`. With no place the
natal location is used and the flag `return_place_natal` is set.

Method: read the natal longitude of the body; sample the transiting body daily
across the range; detect each crossing by the sign change of the wrapped
difference; refine by bisection to about a tenth of a second. Every crossing is
a return, so retrograde loops of Mars through Uranus yield up to three returns,
each written. `--precessed` shifts the target longitude by the ayanamsa
accumulated since birth (Lahiri), off by default.

For each return the script converts the UTC moment to the return place's local
time and calls natal-chart with that date and time (to the second), the place,
and the natal chart's house system, zodiac and node. It then sets `chart_type`
and `derived_from` in the result.

Outputs: one `chart.json` per return named `<body>_return_<YYYY-MM-DD>.json`
(local date), each with its aspect grid, plus `returns_summary.md` listing for
each return the exact UTC moment, the local time and place, the four angles,
and a comparison of return Ascendant and Moon with the natal chart.

Mercury and Venus returns are deferred: their retrograde cycles can give zero
or three returns in a year and need different documentation.

## composite

Inputs: two charts as `--a/--b` files or `--a-birth/--b-birth` raw strings
(delegated to natal-chart as in synastry), `--method midpoint` (default) or
`davison`, and an optional reference place for midpoint houses.

Midpoint: for each body in both charts, the composite longitude is the midpoint
on the shorter arc. The composite MC is the midpoint of the two MCs; houses are
derived from that MC at the reference latitude (default: chart A's location)
with pyswisseph's house-from-MC routine in the natal house system. Aspects use
the natal orb table unchanged. Speeds are averaged; `applying` is null
throughout because a composite does not move; `retrograde` is false. If either
chart has an unknown time the composite has no angles or houses, carries
`time_unknown` and `moon_uncertain`, and `moon_range` is null.

Davison: the midpoint in time is the mean of the two UTC instants; the midpoint
in space is the great-circle midpoint of the two birthplaces, with the timezone
looked up from those coordinates. The script delegates the cast to natal-chart.
An unknown time on either side makes the Davison time-unknown, cast at the mean
of the two noons.

Both methods write `chart.json` (default name `composite.json` or
`davison.json`) with the aspect grid beside it and `derived_from` set to the
two source names.

## Testing

- Returns: the body's longitude at each found moment equals the natal longitude
  to 0.001°; consecutive solar returns are 365.24 days apart within hours; a
  one-year lunar range yields 13 or 14 returns about 27.3 days apart; a Mars
  return in a known retrograde year yields three crossings; the precession
  shift grows by about 50 arcseconds per year of age.
- Composite: midpoint of 350° and 10° is 0°; a chart composited with itself is
  itself; Davison of a chart with itself is the same moment and place; the
  great-circle midpoint of New York and Tokyo lies on Alaska's Arctic coast
  (69.7 N, 153.7 W).
- Round trips: return and Davison charts pass through chart-wheel,
  transits-to-natal and synastry unchanged, proven by a fresh-copy smoke test.
- A golden check against a published solar return is wanted but has the same
  reachability problem as the natal golden set; it goes on the open list.

## Packaging

Two folders, `returns` and `composite`, each with SKILL.md, README.md,
scripts/, examples/, tests/, matching the existing skills. The root README
gains two rows. CONTRACT.md documents the two new meta keys.

## Deferred

Mercury and Venus returns, progressions, relocated natal charts as a
standalone skill, transits to a composite, and a published-return golden test.

## Implementation notes

Decisions made while building the skills that differ from or sharpen the plan above:

- An untimed Davison chart (either birth without a time) is cast at local noon at the midpoint place on the local date of the mean instant, not at the mean of the two noons, so it follows natal-chart's own untimed convention and carries `time_unknown`.
- natal-chart gained `--fold` so a return that falls in the repeated hour of a DST fall-back is cast at the right instant; `returns.py` passes `--fold 1` for the second occurrence and checks the cast against the return moment to within 2 seconds.
- Antipodal midpoints use the min+90 tie rule when the body longitudes are 180° apart (the midpoint is the smaller longitude plus 90°); antipodal birthplaces on a Davison chart have no unique great-circle midpoint and are refused with exit 1.
- Extra flags beyond the plan: `return_place_natal`, `natal_time_unknown` and `precession_corrected` on returns, `davison_timezone_utc` on a Davison chart whose midpoint has no timezone, which is then cast in UTC (the UTC fallback). All four are in CONTRACT.md.
- chart.json stores longitudes to 4 decimals, and the return target is read from that rounded value, so return moments are exact for the rounded degree only: about 4 s for the Sun, about 1 s for the Moon. The bisection resolves far below that.
- The published-return golden check (a solar return against another program's value) is tracked in the same open-items list as the natal golden set, in the implementation notes of `2026-10-08-chart-core-design.md`.
