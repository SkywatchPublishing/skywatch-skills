---
name: synastry
description: >
  Compare two natal charts: every inter-aspect from one person's planets and angles to the
  other's, with orbs, plus house overlays (each person's planets placed in the other's houses),
  written as synastry.json and a Markdown grid. Use this skill whenever the user asks for
  synastry, compatibility, a relationship chart or couple's chart, says "compare our charts",
  "how do our charts interact", "his Mars on my Venus", "where does her Sun fall in my chart",
  or gives two people's birth data and asks how they get along. Takes two chart.json files from
  the natal-chart skill, or raw birth data for either person, which it hands to natal-chart.
---

# Synastry Skill

Lay two cast charts over each other. The input is two `chart.json` files written by `natal-chart` (or raw birth data, which this skill passes to `natal-chart` for you); the output is `synastry.json` plus a Markdown inter-aspect grid.

---

## What this skill produces

Two files, by default `synastry.json` and `synastry.md` next to it:

| File | Contents |
|---|---|
| `synastry.json` | `a` and `b` (the two names), `flags`, `inter_aspects`, and `overlays`. Each inter-aspect carries `a` (the body or angle in A's chart), `b` (the body or angle in B's chart), `aspect`, `angle`, `orb`, `max_orb`, `applying` (always `null`, see below) and `uncertain`. `overlays.a_in_b_houses` maps each of A's bodies to the house it falls in by B's cusps; `overlays.b_in_a_houses` is the reverse. Either overlay is `null` when the host chart has no houses. |
| `synastry.md` | A Markdown grid with A's bodies and angles down the left and B's across the top, each cell holding the aspect symbol and orb, e.g. `△ 3.8`. Symbols: ☌ conjunction, ⚹ sextile, □ square, △ trine, ⚻ quincunx, ☍ opposition. |

Bodies: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Node, plus the Ascendant and MC of any chart that has a birth time.

Orbs are the natal table minus 2°:

| Aspect | Angle | Synastry orb |
|---|---|---|
| Conjunction | 0° | 6° |
| Sextile | 60° | 4° |
| Square | 90° | 6° |
| Trine | 120° | 6° |
| Quincunx | 150° | 1° |
| Opposition | 180° | 6° |

Any inter-aspect involving either person's Sun or Moon gets 2° more (the same luminary bonus as `natal-chart`), so a Sun-Venus conjunction is allowed up to 8°.

**Applying and separating are not computed.** Two natal charts are fixed snapshots; they do not move relative to each other, so every `applying` field is `null` and the grid cells have no `a`/`s` suffix.

---

## How to run

Script paths below are relative to the skill folder: either run from the skill directory, or write the full path as `<skill dir>/scripts/synastry.py`. The script itself needs only Python 3.11 or newer; the `natal-chart` skill (with `pyswisseph`) is needed alongside it only when you hand it raw birth data.

### Step 1 — Get the two charts

Each person is given one of two ways:

| Option | Use when |
|---|---|
| `--a chartA.json` / `--b chartB.json` | A `chart.json` from `natal-chart` already exists for that person. |
| `--a-birth "..."` / `--b-birth "..."` | You only have birth data. The string is the full argument list for `natal_chart.py`, quoted as one shell word, e.g. `--a-birth "--name Ada --date 1990-06-15 --time 14:30 --city 'London, GB'"`. |

Mix them freely (`--a` with `--b-birth`). A birth string is handed verbatim to the natal-chart script, which the skill looks for in this order: beside this skill in the same parent folder, then `~/.claude/skills/natal-chart/scripts/natal_chart.py`, then `./.claude/skills/natal-chart/scripts/natal_chart.py` under the current directory. The cast chart is kept in a temporary directory; if the user will want it again (for a wheel, or transits), run `natal-chart` yourself with `--out` and pass the file instead.

### Step 2 — Run the script

```bash
# Two chart files
python scripts/synastry.py --a ada.json --b bob.json --out ada_bob.json

# Raw birth data for both, quoting each whole string
python scripts/synastry.py \
  --a-birth "--name Ada --date 1990-06-15 --time 14:30 --geonameid 2643743" \
  --b-birth "--name Bob --date 1988-02-02 --geonameid 5128581"

# One existing chart, one from birth data
python scripts/synastry.py --a ada.json --b-birth "--name Bob --date 1988-02-02 --time 09:15 --city 'Paris, FR'"
```

| Flag | Default | Meaning |
|---|---|---|
| `--out` | `synastry.json` | Output JSON path |
| `--grid` | `<out stem>.md` | Markdown grid path |

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Success; both paths are printed. |
| `1` | Bad arguments (both `--a` and `--a-birth`, or neither), an unreadable chart file, a chart with the wrong `schema_version`, or raw birth data given when no `natal-chart` script can be found (`synastry needs the natal-chart skill installed beside it to accept raw birth data; pass chart files instead`). |
| `2` | A `--city` in a birth string matched several places. The natal-chart candidate table is printed on stdout; nothing is written. |

On exit `2`, show the candidate table to the user and ask which place they mean, exactly as the `natal-chart` skill does. Then re-run with `--geonameid <id>` inside the same birth string in place of `--city`. If the user already said which one ("Paris, Texas"), write `--city 'Paris, TX'` in the string.

### Step 3 — Present the result

See "Presenting the result" below.

---

## Handling one unknown birth time

If a birth string has no `--time`, or a chart file carries `meta.time_unknown`, that chart has no houses and no angles. The comparison still runs:

- **Inter-aspects** are computed for every body. That person's Moon can be anywhere within roughly 12° to 15° (it was cast at local noon), so every inter-aspect to that Moon has `uncertain: true`. All other inter-aspects are `uncertain: false`. Their Ascendant and MC are absent from both the aspect list and the grid.
- **Overlays** are produced only in the direction that has houses. If B's time is unknown, `a_in_b_houses` is `null` (A cannot be placed in houses B does not have) while `b_in_a_houses` is still filled in: B's planets do fall somewhere in A's chart.
- **Flags** `a_time_unknown` and/or `b_time_unknown` are set so the reading can say so.

When both times are unknown, both overlays are `null`, both Moons are uncertain, and the grid is bodies only.

---

## Presenting the result

The script writes files; the conversation needs a reading. From `synastry.json` and the grid:

1. **Show the grid.** Deliver `synastry.md` as a file, or paste it when it fits. Name both people and say which is A (down the side) and which is B (across the top).
2. **Call out the tightest inter-aspects.** Sort `inter_aspects` by `orb` and mention the four or five smallest, always naming whose planet is which ("Ada's Saturn sextile Bob's Node, 0.4°"). Then pick out the contacts that matter most for a relationship whatever their orb: anything between the two Suns, Moons, Venuses, Marses and Ascendants (Sun-Moon, Venus-Mars, Moon-Moon, Sun-Ascendant, and so on). Skip the quincunxes unless they are under a degree.
3. **Summarise the overlays in words.** From `a_in_b_houses` and `b_in_a_houses`, say where each person's Sun, Moon, Venus and Mars land in the other's chart ("Bob's Sun falls in Ada's 5th house; Ada's Moon falls in Bob's 12th"). Mention groups: three or more of one person's planets in the same house of the other's chart is worth a sentence.
4. **State the uncertainty.** If either flag is set, say that there is no rising sign and no houses for that person, that overlays are one-directional, and that their Moon contacts are approximate. Never report an overlay or an Ascendant contact for an untimed chart.
5. **Do not score it.** The output is a list of contacts, not a compatibility percentage. Describe what is there and leave the weighing to the user.

---

## Technical notes

| Setting | Value |
|---|---|
| Input | Two `chart.json` files with `schema_version: 1`, from `natal-chart` |
| Points compared | Every body in `bodies`, plus `angles.ascendant` and `angles.mc` when the chart has them |
| Aspects | Conjunction, opposition, square, trine 6°; sextile 4°; quincunx 1°; +2° when the Sun or Moon of either chart is involved |
| Orb source | The natal table copied into `scripts/synastry.py` with `REDUCTION = 2.0`; change the reduction there, not the table |
| Applying | Always `null`; no suffix in the grid |
| Overlays | `house_of` against the host's `houses.cusps`; `null` when the host has none |
| Dependencies | Standard library only. `pyswisseph` is needed indirectly, through `natal-chart`, for raw birth data |

- Nothing is recomputed from the sky: both charts are read as written, so the synastry always agrees with each person's natal positions. Synastry from two chart files and synastry from the same two birth strings produce identical JSON; the test suite checks this round trip.
- The ordering of rows and columns in the grid follows the body order in each `chart.json` (Sun first, Node last, then Ascendant and MC).
- The aspect config and helpers are copied from `natal-chart`, not imported across skill folders, so this folder is copyable on its own. Only the raw-birth path reaches outside it, to the natal script.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `synastry needs the natal-chart skill installed beside it ...` | Raw birth data was given but no `natal_chart.py` was found in the sibling folder, `~/.claude/skills/`, or `./.claude/skills/`. Install `natal-chart` next to this skill, or cast the charts yourself and pass the files with `--a/--b`. |
| Exit code `2` with a table of places | Ambiguous city in a birth string. Show the table, ask, and re-run with `--geonameid` inside the string. |
| `give --a or --a-birth, not both` | Each person is given exactly one way. |
| `expected schema_version 1, got None` | The file is not a `natal-chart` output. Re-cast it; do not edit the version by hand. |
| `ModuleNotFoundError: swisseph` on stderr | The delegated natal script could not import `pyswisseph`. Run `pip install pyswisseph` in the environment the script runs in; see the `natal-chart` troubleshooting table. |
| An overlay is `null` | The host chart has no houses (`time_unknown`). Expected; report the other direction only. |
| No Ascendant or MC column for one person | That chart is untimed. Expected. |
| Far fewer aspects than the natal grids show | Synastry orbs are 2° tighter than natal orbs by design. |
| Results disagree with another program | Check each natal chart first (timezone, zodiac, house system); then compare orb settings, since most programs use their own synastry table. |
