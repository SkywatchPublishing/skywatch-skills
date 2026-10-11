# Chart core design

Date: 2026-10-08
Status: validated in conversation, ready for implementation planning

## Goal

Extend the collection beyond the monthly ephemeris with the calculations a
working astrologer reaches for first in desktop software such as Sirius or
Solar Fire: a cast natal chart, transits to that chart, and synastry between
two charts. Four skills ship as the first batch:

| Skill | Produces | Depends on |
|---|---|---|
| natal-chart | chart.json plus an aspect grid | GeoNames city table, pyswisseph |
| chart-wheel | SVG wheel from any chart.json | chart.json contract |
| transits-to-natal | daily CSV of transiting aspects to a chart | chart.json contract |
| synastry | inter-aspect list and house overlays for two charts | natal-chart script |

The primary audience is working astrologers generally, not only Datebook
production or Kairos users.

## Shared contract: chart.json

Skills share a documented file format rather than a Python package, so each
folder stays self-contained and copyable into `.claude/skills/`.

`chart.json` holds:

- input echo: name label, local date and time, place string
- resolution: latitude, longitude, IANA timezone, UTC offset at birth,
  Julian day, `time_unknown` boolean, house system actually used
- bodies: for each of Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn,
  Uranus, Neptune, Pluto, Chiron, True Node: longitude, sign, degree within
  sign, house, daily speed, retrograde flag
- houses: twelve cusps and the four angles, omitted when `time_unknown`
- aspects: pairs with aspect name, orb, applying or separating

Times are stored in both birth-place local time and UTC. No skill assumes
Pacific time; the ephemeris skill keeps its Pacific default for Datebook
compatibility.

## natal-chart

Inputs: date, local time, place as a city name or explicit coordinates.

Location resolution uses a committed GeoNames table trimmed to cities with
population over 15,000 (CC BY 4.0, attributed in the README). When a name
matches more than one place the script lists candidates with region and
country and exits; Claude asks the user to choose before casting. Raw
coordinates bypass the table.

Timezone comes from coordinates via timezonefinder and historical rules
from zoneinfo, so old births get the correct offset.

Defaults, each overridable by flag:

| Setting | Default | Alternatives |
|---|---|---|
| Zodiac | Tropical | Sidereal, Lahiri ayanamsa |
| Houses | Placidus | Whole Sign, Koch, Equal, Porphyry |
| Node | True | Mean |
| Bodies | Sun through Pluto, Chiron, True Node | Lilith and major asteroids by flag |
| Aspects | Conjunction, opposition, square, trine 8°; sextile 6°; quincunx 3° | Edit the config block |
| Luminary bonus | Sun and Moon orbs +2° | |

Applying or separating is computed from daily speeds.

Edge cases:

- Unknown birth time: cast at 12:00 local, omit houses and angles, set
  `time_unknown: true`, report the Moon's possible range for the day.
- Latitude above roughly 66°: Placidus cannot compute; fall back to Whole
  Sign and record the fallback in chart.json.
- Ambiguous city: ask, never guess.

Human output is an aspect grid in Markdown. A positions table is left to
Claude to render from the JSON in conversation.

## chart-wheel

Reads any chart.json and writes an SVG wheel: twelve signs, house cusps
when present, body glyphs at their longitudes, aspect lines colored by
aspect family. Separate from natal-chart so composite, return, and later
chart types reuse it unchanged. Design of the wheel itself is its own task.

## transits-to-natal

Inputs: a chart.json, a start date, an end date.

Output is a daily snapshot CSV in the same shape as the ephemeris skill:
one row per day per active transit, with transiting body, aspect, natal
target, orb, and retrograde flag. Orb is 1°. Default transiting bodies are
Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, and the True Node; Sun
through Mars and the Moon are opt-in flags because they flood long ranges.

Natal targets are the twelve bodies plus the four angles. Angles are skipped
automatically when chart.json carries `time_unknown`.

Timestamps use the natal location's timezone, with the offset named in the
header.

## synastry

Inputs: two charts, each given either as a chart.json path or as raw
birth data. Raw data is passed through to the natal-chart script rather
than re-implemented, so the input rules stay in one place.

Output:

- inter-aspect list: every aspect from A's bodies to B's bodies, with orb,
  and which chart owns each body
- house overlays: each of A's bodies placed in B's houses, and the reverse

Orbs are the natal table minus 2°, derived from the same config block.

When one partner's time is unknown, inter-aspects are still computed with
that partner's Moon aspects flagged uncertain, and overlays are skipped in
the direction that needs the missing houses.

Composite and Davison charts are deferred to a later batch.

## Testing

- Golden charts: a small set of public birth data with published positions,
  checked to 0.1° for bodies and 0.5° for cusps. These catch timezone and
  house-system bugs.
- Round-trip checks: synastry computed from two chart.json files must
  match synastry computed from the same raw data.

## Deferred

Composite and Davison charts, progressions, solar and lunar returns, the
sky-calendar set (lunar phases, void-of-course Moon, ingresses, stations,
eclipses), Sabian and fixed-star lookups, and interpretation scaffolds.
