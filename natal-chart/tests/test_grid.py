import grid


def test_grid_cells_and_symbols():
    chart = {
        "bodies": {"Sun": {}, "Moon": {}, "Mars": {}},
        "angles": None,
        "aspects": [{"body1": "Sun", "body2": "Mars", "aspect": "Trine", "orb": 2.31, "applying": True}],
    }
    md = grid.render(chart)
    lines = md.splitlines()
    assert lines[0].startswith("| | Sun | Moon | Mars |")
    assert "| Sun |  |  | △ 2.3a |" in md
    assert "| Mars | △ 2.3a |  |  |" in md


def test_grid_includes_angles_when_known():
    chart = {"bodies": {"Sun": {}}, "angles": {"ascendant": 1, "mc": 2},
             "aspects": [{"body1": "Sun", "body2": "MC", "aspect": "Square", "orb": 0.5, "applying": None}]}
    md = grid.render(chart)
    assert "| MC |" in md.splitlines()[0]
    assert "□ 0.5" in md
