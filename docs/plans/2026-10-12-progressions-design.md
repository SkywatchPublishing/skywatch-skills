# Progressions design

Date: 2026-10-12
Status: validated in conversation, ready for implementation planning

## Goal

Add the two forward-moving techniques astrologers use most, secondary
progressions and solar arc directions, as one skill on the existing
`chart.json` contract. A progressed or directed chart for any date is an
ordinary chart file, so chart-wheel and synastry read it unchanged. A dated
event timeline answers the question astrologers actually ask: what is
coming up, and when.

| Skill | Produces | Depends on |
|---|---|---|
| progressions | a progressed or directed chart.json for a date, and an event timeline CSV | natal chart.json, pyswisseph |

## Time key

One day after birth stands for one tropical year of life (365.24219 days).
For a target date, age in years is (target JD - birth JD) / 365.24219, and
the progressed instant is birth JD + age days. A target before the birth
moment (the birth date's noon, for an afternoon birth) is the birth moment,
age 0.

## Charts

Inputs: a natal `chart.json`, `--date`, `--method secondary` (default) or
`solar-arc`, and for secondary charts `--angles solar-arc` (default) or
`naibod`.

Secondary progressed chart: bodies are computed with pyswisseph at the
progressed instant, in the natal chart's zodiac and node settings. Angles:

- solar-arc (default): progressed MC = natal MC + true solar arc.
- naibod: natal ARMC advances 0°59'08" (0.9856473°) per year; MC from ARMC.

The Ascendant and cusps come from that MC at the birth latitude in the natal
house system, using the house-from-ARMC routine the composite skill uses,
with the same whole-sign fallback at polar latitudes. Body houses and
internal aspects are recomputed. That routine is tropical, so a sidereal
chart's natal MC is shifted to tropical with the birth ayanamsa and the
resulting angles and cusps are shifted back with the ayanamsa at the
progressed instant, the moment the progressed bodies use (Lahiri with
nutation, as natal-chart's sidereal output); whole-sign cusps are then the
sidereal sign boundaries from the progressed Ascendant's sign.

Solar arc directed chart: every natal body, angle and house cusp moves
forward by the same true solar arc, the progressed Sun minus the natal Sun.
Body house placements therefore match the natal chart, and the directed
Ascendant is natal Ascendant plus arc, consistent with the timeline. The one
exception is whole-sign houses: their cusps stay on sign boundaries, starting
from the directed Ascendant's sign. Directed bodies have no daily motion, so
their `speed` is null. With solar-arc angles the progressed MC equals the
directed MC by definition, so the timeline lists its events once, under
solar arc.

Planets are computed in the script rather than by calling natal-chart: the
progressed instant needs no place lookup and the angles are replaced anyway.
The small helpers needed (sign formatting, house placement, aspect table,
house-from-ARMC) are copied, never imported across folders.

Both charts are schema-1 `chart.json` with `chart_type`
`secondary_progressed` or `solar_arc_directed`, `derived_from` the natal
name, and a new `meta.progression` object:

| key | meaning |
|---|---|
| `target_date` | the date the chart is read for |
| `age_years` | age at that date in tropical years |
| `solar_arc` | true solar arc in degrees |
| `angles_method` | `solar-arc` or `naibod`; null for a directed chart |

`datetime_local`, `datetime_utc` and `timezone` keep the birth values, and
other natal meta keys (such as `house_system_requested`) are carried
through. For an untimed natal chart, `moon_range` is the progressed Moon for
a birth at 00:00 and at 23:59 on the birth date (directed: the natal range
plus the arc). Only natal charts are accepted as input. The chart-wheel
caption shows the target date when `progression` is present.

## Timeline

`--timeline --start --end` writes `progressions_timeline.csv`, sorted by
exact date, listing every event whose 1° window overlaps the range.

Events:

- Secondary aspects: progressed Moon, Sun, Mercury, Venus, Mars, and the
  progressed Ascendant and MC when the birth time is known, to every natal
  body and angle, using the repository's six aspects.
- Solar arc aspects: every directed body and angle to every natal body and
  angle, excluding a point to itself.
- Ingresses: any progressed body changing sign; the progressed Moon entering
  a natal house.
- Stations: any progressed body from Mercury outward turning retrograde or
  direct.

Columns: `Technique, Event, Moving, Aspect, Target, Exact, Orb from, Orb to,
Detail`. Dates are local dates in the natal timezone, with no clock times. A
progressed planet that turns back across a natal point gives one row per
exact pass, each with its own window.

Method: sample target dates every 15 days, detect crossings of the exact
angle and of the ±1° window edges, and bisect each to the day.
Progressed Mercury, Venus and Mars can stall near a station, so their
windows can last decades (up to about 37 years for Mars); they are scanned
40 years either side of the range rather than 5. A station that comes
within 1° of an aspect point without perfecting produces no aspect row; the
station row's Detail shows where it stations, e.g. `turns retrograde at
23°34' Virgo`. Windows open no earlier than the birth date, and the range is
compared as whole local days.

## Unknown birth time

A 12-hour error in the birth moment shifts every secondary progression by
about six months, because a day stands for a year. For an untimed chart,
secondary events carry an `uncertain` marker and the SKILL.md explains the
±6-month spread; angles and house events are omitted. The arc itself is
barely affected, because it is a difference of two Sun positions that shift
together, but the natal positions it moves and aims at are not: a ±12-hour
error moves the natal Moon by up to about 7° and the Sun, Mercury, Venus and
Mars by roughly 0.4° to 1°, months of arc. A solar arc event is therefore
marked uncertain when any of the Moon, Sun, Mercury, Venus or Mars is the
moving point or the target.

## Testing

- Example chart on 2027-06-15: age 37.0001 years, solar arc 35.2991°;
  progressed Sun matches pyswisseph at the progressed instant; solar-arc MC
  equals natal MC plus the arc; the Naibod MC differs by 1.66°.
- A target date equal to the birth date reproduces the natal chart under
  both angle methods with a zero arc; a directed chart equals the natal chart
  shifted by the arc.
- Timeline exact dates put the moving point within 0.05° of the aspect
  angle; progressed Moon sign ingresses fall about 2.5 years apart; station
  rows match a sign change in progressed speed; untimed charts have no angle
  or house events and mark secondary rows uncertain.
- A committed round-trip test sends a progressed chart through chart-wheel,
  transits-to-natal and synastry.
- A golden check against a published progressed chart joins the open list.

## Packaging

One `progressions/` folder with SKILL.md, README.md, scripts/, examples/,
tests/. The root README gains a row; CONTRACT.md documents the new chart
types and `meta.progression`.

## Deferred

Tertiary and minor progressions, converse progressions and directions, the
progressed lunation cycle, progressed composites, and primary directions.
