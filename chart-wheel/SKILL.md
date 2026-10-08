---
name: chart-wheel
description: >
  Draw an astrological chart wheel as an SVG image from a chart.json produced by the natal-chart
  skill: zodiac ring, house cusps, planet glyphs with degree labels, and aspect lines coloured by
  family. Use this skill whenever the user asks for a chart wheel, says "draw my chart", wants a
  birth chart image or a picture of the chart, asks to "show the chart", asks for an SVG of the
  chart, or wants to see what their chart looks like rather than read it as a table. It reads any
  schema-version-1 chart.json, so it will later draw return and composite charts unchanged. If no
  chart.json exists yet, run natal-chart first.
---

# Chart Wheel Skill

Render a cast chart as a wheel. The input is a `chart.json` written by `natal-chart` (or any later skill that follows the same contract); the output is a single self-contained SVG file.

---

## What this skill produces

One file, by default `wheel.svg`: an 800×800 SVG with a white background, drawn with the standard library only.

Reading from the outside in:

| Ring | Contents |
|---|---|
| Sign ring | Twelve 30° sectors in alternating cream and sand, each with its sign glyph (♈ … ♓). |
| House ring | Twelve cusp lines with the house number at the middle of each house. The Ascendant and MC are drawn as heavy black lines that extend past the outer ring, labelled `ASC` and `MC`; the Descendant and IC are lighter, labelled `DSC` and `IC`. |
| Planet ring | A tick at each body's true longitude on the inner edge of the house ring, the body's glyph (☉ ☽ ☿ ♀ ♂ ♃ ♄ ♅ ♆ ♇ ⚷ ☊) inside it, and a degree label such as `24°17'` below the glyph, with ` ℞` appended for a retrograde body. |
| Aspect lines | Chords across the inner circle joining aspected bodies and angles. Red for the hard aspects (opposition, square), blue for the soft ones (trine, sextile), grey for the quincunx. Conjunctions are not drawn; the glyphs sitting together say it already. |

Line style carries one more fact: a **solid** aspect line is applying, a **dashed** line is separating. Aspects to the Ascendant and MC have no applying/separating value (`applying: null`) and are drawn solid.

When bodies crowd together (a stellium, or a tight conjunction) the glyphs are nudged apart so they do not overlap, and each nudged glyph gets a thin grey **lead line** from its true-position tick in to the glyph. The ticks and the aspect lines always use the true longitude; only the glyph and its label move. Degree labels of close neighbours are staggered through three radii so they do not touch.

Two captions sit outside the wheel: the name, local date-time and timezone at the top; the place, house system, zodiac (when sidereal) and any chart flags at the bottom.

**Unknown birth time.** When `meta.time_unknown` is true the chart has no angles or houses, so the wheel rotates to put 0° Aries at 9 o'clock, draws no house ring, no angle lines and no aspects to the angles, and the bottom caption reads "Birth time unknown: houses not shown, Moon approximate". Everything else is drawn as usual.

---

## How to run

Script paths below are relative to the skill folder: either run from the skill directory, or write the full path as `<skill dir>/scripts/chart_wheel.py`.

### Step 1 — Have a chart.json

The wheel is drawn from a `chart.json` with `schema_version: 1`, the file `natal-chart` writes. If there is none for this person yet, run the `natal-chart` skill first and come back with the path it wrote. Do not build a chart.json by hand.

### Step 2 — Run the script

No dependencies beyond Python 3.11 or newer; nothing to `pip install` and no ephemeris files are read.

```bash
python scripts/chart_wheel.py chart.json --out wheel.svg
```

| Argument | Meaning |
|---|---|
| `chart.json` | Path to the chart file. |
| `--out` | Output SVG path. Default `wheel.svg` in the current directory. |

The script prints the output path on success and exits `0`. On a missing file, unreadable JSON, an unsupported schema version or a malformed chart (no `meta` or `bodies` object, missing longitudes) it prints `chart_wheel: <reason>` on stderr and exits `1` without writing anything. A chart whose `meta.location` is absent still renders; the place is simply left out of the bottom caption.

**Examples:**
```bash
# Natal wheel next to the chart file
python scripts/chart_wheel.py ada.json --out ada_wheel.svg

# From anywhere, with full paths
python ~/.claude/skills/chart-wheel/scripts/chart_wheel.py ./chart.json --out ./wheel.svg
```

### Step 3 — Present the wheel

See "Presenting the wheel" below.

---

## Presenting the wheel

1. **Deliver the SVG file** with whatever file-sharing mechanism the environment provides. It is self-contained (no external fonts, images or scripts) and opens in any browser or vector editor.
2. **Offer a PNG when the environment can rasterise.** If a converter is available (`rsvg-convert`, `cairosvg`, Inkscape, ImageMagick with an SVG delegate) offer a PNG for chat clients and documents that do not render SVG, e.g. `rsvg-convert -w 1600 wheel.svg -o wheel.png`. Do not install a rasteriser just for this; the SVG is the deliverable.
3. **Say what the picture shows** in two or three lines: the rising sign and MC when known, where the bodies cluster, and the one or two tightest aspect lines. The positions table and the aspect grid belong to `natal-chart`; do not re-derive them here.
4. **Mention the glyph fonts once if it matters.** The SVG names a font stack (DejaVu Sans, Segoe UI Symbol, Noto Sans Symbols2, Apple Symbols) but embeds nothing. The sign and classical planet glyphs are in nearly every system font; **Chiron ⚷, the Node ☊ and the retrograde mark ℞** depend on the viewer's font and may show as boxes on a bare system. The lines and positions are unaffected.

---

## Technical notes

| Setting | Value |
|---|---|
| Canvas | 800×800 user units, `viewBox="0 0 800 800"`, white background; scales to any size |
| Orientation | Ascendant at 9 o'clock; zodiac and houses run counter-clockwise, so the MC is near the top and house 1 lies just below the left horizon |
| Untimed charts | 0° Aries at 9 o'clock, no house ring, no angles |
| Ring radii | Sign ring 340–380, house ring 300–340, glyphs at 270, labels at 240 (224 and 208 when staggered: `LABEL_STAGGER = 16`, `LABEL_LEVELS = 3`), aspect circle 210; the whole wheel is scaled by 0.85 about the centre so the captions clear it |
| Aspect families | Opposition and square `#c0392b` (red); trine and sextile `#2e86c1` (blue); quincunx `#7f8c8d` (grey); conjunction not drawn |
| Line style | Dashed `6 4` only when `applying` is `false`; `true` and `null` (aspects to angles) are solid |
| Degree labels | `DEGREE_FONT = 12` user units, about 10px after the wheel scale; neighbours closer than `LABEL_PAD = 6` units step inward |
| Glyph spacing | Minimum 6° between displayed glyphs (`MIN_GAP`); nudged glyphs get a lead line from the true tick |
| Fonts | Named, not embedded: DejaVu Sans, Segoe UI Symbol, Noto Sans Symbols2, Apple Symbols, then sans-serif. Every sign and planet glyph carries the text-presentation selector U+FE0E so viewers do not swap in colour emoji |

- Everything the wheel shows is read from `chart.json`: bodies and their longitudes, `angles`, `houses.cusps`, the `aspects` list with its `applying` flag, and `meta` for the captions. Nothing is recomputed, so the wheel always agrees with the aspect grid.
- The geometry (angle-to-point mapping and the glyph spreading) lives in `scripts/wheel_geometry.py`, imported by sibling path; keep the two files together when copying the skill.
- Colours, radii, glyphs and the font stack are constants at the top of `scripts/chart_wheel.py`.
- Because the script only depends on the contract, charts written by future skills (solar returns, composites) draw without changes.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `chart_wheel: [Errno 2] No such file or directory` | The path to `chart.json` is wrong, or no chart has been cast yet. Run `natal-chart` first and pass the path it printed. |
| `chart_wheel: unsupported chart schema_version None` or a number other than `1` | The file is not a `natal-chart` output (or is from a newer contract). Re-cast with the current `natal-chart`; do not edit the version field by hand. |
| `chart_wheel: Expecting value ...`, `chart_wheel: 'bodies'` or another one-line `chart_wheel:` error | The JSON is truncated or hand-edited (exit `1`). Re-run `natal-chart` to regenerate it. |
| Glyphs show as boxes (`▯`) or question marks | The viewer's font lacks the symbol. Chiron, the Node and ℞ are the usual casualties. Open the SVG in a browser, or rasterise on a machine with DejaVu Sans or Noto Sans Symbols2 installed. |
| Labels touch or overlap in a tight stellium | Five or more bodies within a few degrees exhaust the three label radii. Raise `MIN_GAP`, `LABEL_STAGGER` or `LABEL_LEVELS` at the top of `scripts/chart_wheel.py`, or tell the user the exact degrees from `chart.json` and let the lead lines show which glyph is which. |
| Glyphs render as colour emoji | Should not happen: each glyph is followed by U+FE0E (text presentation). If a viewer still shows emoji, rasterise the SVG instead. |
| No houses or angles drawn | `meta.time_unknown` is true: expected. The caption says so; there is no rising sign without a birth time. |
| Wheel looks rotated compared with another program | Most software also puts the Ascendant at 9 o'clock; a program that fixes 0° Aries on the left is showing the same chart with a different convention. Check the `ASC` label. |
