# Aspectarian and void-of-course design

Date: 2026-10-12
Status: validated in conversation, implemented on this branch

## Goal

Give the datebook its two monthly timing tables, an aspectarian and a void-of-course
Moon table, computed without the Swiss Ephemeris, so the tables can be released under an
open license with no AGPL question attached. While checking the new tables against
`astrology-ephemeris`, that skill turned out to list only a sixth of the Moon's aspects;
fix that in the same change.

## Engine

Skyfield (MIT) reading NASA JPL's DE440s (`de440s.bsp`, 32 MB, 1849–2150), fetched once by
`aspectarian/scripts/fetch_ephemeris.py` into the skill's own `ephe/`, the way natal-chart
fetches its Swiss files. Positions are apparent geocentric ecliptic longitudes of date,
which is what the Swiss Ephemeris returns by default and what printed ephemerides list.
Swiss Ephemeris is itself a compression of JPL ephemerides, so the two should agree to
hundredths of an arcsecond; the tests hold them to that when pyswisseph is installed.

## Search

Sample every body hourly over the month padded by four days on each side. For each pair
and each exact separation (0°, ±60°, ±90°, ±120°, 180°), a sign change of the wrapped
distance from exact brackets a root, provided the step is under 90° (otherwise it is the
±180° wraparound). Bisect all brackets together, one vectorised ephemeris call per body
per iteration, to 0.1 s. Moon ingresses are sign changes of the Moon's distance from the
next multiple of 30°.

Hourly sampling cannot miss a Moon aspect: the Moon outruns every other body, so each
Moon–body separation grows monotonically. For two slow bodies a miss would need the
pair to touch and leave an exact aspect within one hour around a station; that is not
guarded against.

## Void of course

From the Moon's last exact aspect before an ingress to the ingress. Modern bodies (Sun
through Pluto) by default, `--traditional` for Sun through Saturn. Major aspects only, no
orbs. A sign with no Moon aspect yields two rows that begin at the same aspect. The rule
is printed in SKILL.md because published tables differ on each of these choices.

## Output

Two CSVs per month and zone, rows assigned to the month of their local time rounded to the
minute (the printed time), with the exact UTC second alongside. Durations are differences
of UTC instants, so a void across a daylight-saving change is the right length. Time
format matches astrology-ephemeris (`07:12 PM PDT`).

## astrology-ephemeris fix

Moon pairs were gated on the 1° orb at the noon snapshot, so only aspects within about two
hours of noon were listed (13 of 77 in April 2026, none of the four lunar phases). Moon
pairs now get every perfection in the Pacific day, found the same way as above but with
pyswisseph, bisected to the second and rounded to the minute; their orb column is 0.0.
Slow pairs are untouched, which a test pins against the committed example.

## Tests

- USNO's published phase times (all 50 of 2026 for aspectarian; April for
  astrology-ephemeris): an independent source for Sun–Moon conjunction, square and
  opposition, to the minute.
- Golden: the April 2026 run against the committed examples.
- Optional Swiss cross-check: positions through 2026 and the April event list, with
  tolerances for the Moshier fallback when the Swiss data files are absent.
- The two skills agree on all 77 April 2026 Moon aspects to the minute (checked by hand;
  the folders stay independent, so no test imports across them).
