# Skywatch Skills

Claude skills for astrology and timing work, built by [Ellen Kimble](https://github.com/mermellla) at [Skywatch Publishing](https://www.skywatchastrology.com).

Skywatch treats the sky as timing information, not prediction. These skills give Claude the structured data and procedures to work that way: real ephemeris math, reproducible output, and clear boundaries on what is being claimed.

Each skill is a self-contained folder you can drop into `.claude/skills/` and use immediately.

## Skills

| Skill | What it produces | Install |
|---|---|---|
| [astrology-ephemeris](astrology-ephemeris/) | A CSV of every major planetary aspect for a given month, with exact Moon times, computed with the Swiss Ephemeris | `cp -r astrology-ephemeris ~/.claude/skills/` |

More skills are added as they are proven in daily use.

## How these are built

Every skill in this collection follows the same shape:

- **`SKILL.md`** carries the description Claude uses to decide when the skill applies, plus the step-by-step procedure.
- **`scripts/`** holds any deterministic code. The skill text tells Claude how to run it rather than asking Claude to recompute the math itself.
- **`examples/`** contains real output, so you can judge the result before installing anything.
- **`README.md`** explains the skill to a human reader: what it does, how to install it, and why it exists.

Skills are tested against the sort of request a working astrologer or publisher actually makes, and the trigger descriptions are tuned so the skill fires on plain language ("what aspects are active next month") rather than requiring the right keyword.

## Install

```bash
git clone https://github.com/mermellla/skywatch-skills
cp -r skywatch-skills/astrology-ephemeris ~/.claude/skills/
```

Use project scope (`.claude/skills/` inside a repo) when you want the skill to travel with a codebase.

## Licensing

The skill text and scripts in this repository are released under the MIT License. See [LICENSE](LICENSE).

The ephemeris skill depends on [pyswisseph](https://github.com/astrorigin/pyswisseph), a binding for the [Swiss Ephemeris](https://www.astro.com/swisseph/), which Astrodienst distributes under AGPL-3.0 or a commercial license. The library is not bundled here. If you redistribute a combined work or use it in a closed-source product, check their terms.

## About

Ellen Kimble designs the connective tissue between AI, support, and software. Skywatch Publishing produces the Skywatch Datebook and the Kairos timing scanner. This repository is where the reusable pieces of that work live.
