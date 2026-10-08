import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "chart_wheel.py"
EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"


def test_renders_well_formed_svg(tmp_path):
    out = tmp_path / "wheel.svg"
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), str(EXAMPLE), "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    root = ET.parse(out).getroot()
    assert root.tag.endswith("svg")
    text = out.read_text(encoding="utf-8")
    assert "☉" in text and "♈" in text
    assert text.count("<line") >= 12            # at least the cusps


def test_unknown_time_has_no_house_numbers(tmp_path):
    chart = json.loads(EXAMPLE.read_text())
    chart["angles"] = chart["houses"] = None
    chart["meta"]["time_unknown"] = True
    chart["meta"]["flags"] = ["time_unknown", "moon_uncertain"]
    for b in chart["bodies"].values():
        b["house"] = None
    src = tmp_path / "c.json"
    src.write_text(json.dumps(chart))
    out = tmp_path / "wheel.svg"
    subprocess.run([sys.executable, "-I", str(SCRIPT), str(src), "--out", str(out)], check=True)
    text = out.read_text(encoding="utf-8")
    assert "Birth time unknown" in text
    assert 'class="house-number"' not in text
