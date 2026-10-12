# astrology-ephemeris

Generates a complete daily planetary aspect list for any month and year, exported as CSV, using the Swiss Ephemeris.

**Bodies:** Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto
**Aspects:** conjunction, sextile, square, trine, opposition, within a 1° orb
**Extra:** every aspect the Moon perfects each day, with the time it perfects, in Pacific time

## Example output

| Date | Planet 1 | Aspect | Planet 2 | Orb (°) | Exact Time |
|---|---|---|---|---|---|
| 2026-04-16 | Moon | Square | Jupiter | 0.0 | 11:54 AM PDT |
| 2026-04-16 | Mars | Sextile | Pluto | 0.002 | |

A full month is in [`examples/aspects_april_2026.csv`](examples/aspects_april_2026.csv).

## Install

```bash
# Claude Code, project scope
cp -r astrology-ephemeris .claude/skills/

# Claude Code, user scope
cp -r astrology-ephemeris ~/.claude/skills/
```

Then ask Claude for "the aspects for May 2026" or "a monthly ephemeris".

## Run the script directly

```bash
pip install pyswisseph
python scripts/compute_aspects.py 5 2026
python scripts/compute_aspects.py 4 2026 april.csv
```

Requires Python 3.9 or newer.

## How it works

- Slow bodies are sampled at noon Pacific each day. An aspect is listed when its orb is within 1° at that moment.
- The Moon is sampled every hour across the day and each aspect it perfects is bisected to the second, so every Moon aspect gets a row with its time to the minute, not only the ones near noon. Moon rows show an orb of `0.0` because they are listed at the moment of perfection.
- Timezone, orb, sampling step, bodies, and aspects are constants at the top of `scripts/compute_aspects.py`, so the skill adapts without code surgery.

## Tests

```bash
pip install pyswisseph pytest
python -m pytest astrology-ephemeris/tests -q
```

The lunar phases of April 2026 are checked against the times the U.S. Naval Observatory publishes, and the slow-planet rows against the committed example.

## Why it exists

Daily aspect data is the raw material for the Skywatch Datebook and for Kairos timing scans. Writing it by hand from a printed ephemeris is slow and error-prone. This skill makes it a one-line request.
