import csv
import build_cities as bc

ROW = "\t".join([
    "5128581", "New York City", "New York City", "NYC,Nueva York", "40.71427", "-74.00597",
    "P", "PPL", "US", "", "NY", "", "", "", "8804190", "", "10", "America/New_York", "2022-03-09",
])


def test_reduce_row():
    assert bc.reduce_row(ROW.split("\t")) == [
        "5128581", "New York City", "New York City", "US", "NY",
        "40.71427", "-74.00597", "America/New_York", "8804190",
    ]


def test_build_writes_sorted_csv(tmp_path):
    src = tmp_path / "cities15000.txt"
    src.write_text(ROW + "\n" + ROW.replace("5128581", "1").replace("8804190", "20000") + "\n", encoding="utf-8")
    out = tmp_path / "cities.csv"
    bc.build(src, out)
    rows = list(csv.reader(out.open(encoding="utf-8")))
    assert rows[0] == bc.HEADER
    assert rows[1][0] == "5128581"   # larger population first
    assert len(rows) == 3
