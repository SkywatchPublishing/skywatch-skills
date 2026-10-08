# Skywatch Skills

Claude skills for astrology and timing work, built by [Ellen Kimble](https://github.com/mermellla) at [Skywatch Publishing](https://www.skywatchastrology.com).

Skywatch treats the sky as timing information, not prediction. These skills give Claude the structured data and procedures to work that way: real ephemeris math, reproducible output, and clear boundaries on what is being claimed.

Each skill is a self-contained folder you can drop into `.claude/skills/` and use immediately.

## Skills

| Skill | What it produces | Install |
|---|---|---|
| [astrology-ephemeris](astrology-ephemeris/) | A CSV of every major planetary aspect for a given month, with exact Moon times, computed with the Swiss Ephemeris | `cp -r astrology-ephemeris ~/.claude/skills/` |
| [natal-chart](natal-chart/) | A birth chart cast from date, time and place: `chart.json` with every body, the angles, house cusps and aspects, plus a Markdown aspect grid | `cp -r natal-chart ~/.claude/skills/` |
| [chart-wheel](chart-wheel/) | A self-contained SVG chart wheel drawn from `chart.json`: sign ring, houses, planet glyphs with degrees, aspect lines | `cp -r chart-wheel ~/.claude/skills/` |
| [transits-to-natal](transits-to-natal/) | A daily CSV of transiting aspects to a natal chart over any date range, in the same shape as the ephemeris CSV | `cp -r transits-to-natal ~/.claude/skills/` |
| [synastry](synastry/) | Two charts compared: every inter-aspect with orbs, house overlays in both directions, as `synastry.json` and a Markdown grid | `cp -r synastry ~/.claude/skills/` |

More skills are added as they are proven in daily use.

## How these are built

Every skill in this collection follows the same shape:

- **`SKILL.md`** carries the description Claude uses to decide when the skill applies, plus the step-by-step procedure.
- **`scripts/`** holds any deterministic code. The skill text tells Claude how to run it rather than asking Claude to recompute the math itself.
- **`examples/`** contains real output, so you can judge the result before installing anything.
- **`README.md`** explains the skill to a human reader: what it does, how to install it, and why it exists.

The chart skills share one file format. `natal-chart` writes `chart.json`, and [`natal-chart/CONTRACT.md`](natal-chart/CONTRACT.md) documents it field by field; `chart-wheel`, `transits-to-natal` and `synastry` read that file rather than recomputing anything, so the folders stay copyable on their own and always agree with each other.

Skills are tested against the sort of request a working astrologer or publisher actually makes, and the trigger descriptions are tuned so the skill fires on plain language ("what aspects are active next month") rather than requiring the right keyword.

## Install

```bash
git clone https://github.com/mermellla/skywatch-skills
cp -r skywatch-skills/astrology-ephemeris ~/.claude/skills/
cp -r skywatch-skills/natal-chart skywatch-skills/chart-wheel skywatch-skills/transits-to-natal skywatch-skills/synastry ~/.claude/skills/
```

The chart skills need the Swiss Ephemeris data files once; run `python natal-chart/scripts/fetch_ephemeris.py` after copying. `chart-wheel` and `synastry` read the `chart.json` that `natal-chart` writes, so install `natal-chart` alongside them.

Use project scope (`.claude/skills/` inside a repo) when you want the skill to travel with a codebase.

## Licensing

The skill text and scripts in this repository are released under the MIT License. See [LICENSE](LICENSE).

The ephemeris and chart skills depend on [pyswisseph](https://github.com/astrorigin/pyswisseph), a binding for the [Swiss Ephemeris](https://www.astro.com/swisseph/), which Astrodienst distributes under AGPL-3.0 or a commercial license. The library is not bundled here. If you redistribute a combined work or use it in a closed-source product, check their terms.

The city table in `natal-chart/data/cities.csv` is derived from [GeoNames](https://www.geonames.org), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Keep that attribution if you copy the table.

## About

Ellen Kimble designs the connective tissue between AI, support, and software. Skywatch Publishing produces the Skywatch Datebook and the Kairos timing scanner. This repository is where the reusable pieces of that work live.
