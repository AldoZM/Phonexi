from pathlib import Path
from unittest.mock import patch

import pytest

from phonexi.screenshot import DEFAULT_REGION, _region_box, parse_region, prune

MONITOR = {"left": 0, "top": 0, "width": 1920, "height": 1080}
SECOND = {"left": 1920, "top": -120, "width": 1600, "height": 900}


def _ratio(box: dict) -> float:
    return box["width"] / box["height"]


# ── geometry ────────────────────────────────────────────────────────────────

def test_region_is_centred_on_the_cursor():
    box = _region_box(MONITOR, (960, 540), (1280, 720))

    assert box == {"left": 320, "top": 180, "width": 1280, "height": 720}


def test_region_shifts_inward_at_the_top_left_corner():
    box = _region_box(MONITOR, (5, 5), (1280, 720))

    assert box["left"] == 0
    assert box["top"] == 0
    assert (box["width"], box["height"]) == (1280, 720)


def test_region_shifts_inward_at_the_bottom_right_corner():
    box = _region_box(MONITOR, (1915, 1075), (1280, 720))

    assert box["left"] == 1920 - 1280
    assert box["top"] == 1080 - 720
    assert (box["width"], box["height"]) == (1280, 720)


def test_region_never_shrinks_so_the_cost_stays_flat():
    """A shrunk box changes the aspect ratio, and cost tracks ratio, not size."""
    corners = [(0, 0), (1919, 0), (0, 1079), (1919, 1079), (960, 540)]

    for cursor in corners:
        box = _region_box(MONITOR, cursor, (1280, 720))
        assert _ratio(box) == pytest.approx(16 / 9)


def test_region_honours_a_monitor_that_is_not_at_the_origin():
    box = _region_box(SECOND, (2720, 330), (1280, 720))

    assert box == {"left": 2080, "top": -30, "width": 1280, "height": 720}


def test_region_clamps_within_a_monitor_that_is_not_at_the_origin():
    box = _region_box(SECOND, (1921, -119), (1280, 720))

    assert box["left"] == 1920
    assert box["top"] == -120


def test_region_falls_back_to_the_whole_monitor_when_it_would_not_fit():
    box = _region_box(MONITOR, (960, 540), (2560, 1440))

    assert box == MONITOR


def test_region_falls_back_when_only_one_side_overflows():
    box = _region_box(SECOND, (2720, 330), (1920, 1080))

    assert box == SECOND


# ── flag parsing ────────────────────────────────────────────────────────────

def test_parse_region_reads_width_by_height():
    assert parse_region("960x540") == (960, 540)


def test_parse_region_accepts_an_uppercase_separator():
    assert parse_region("960X540") == (960, 540)


def test_parse_region_rejects_junk():
    with pytest.raises(ValueError):
        parse_region("big")


def test_parse_region_rejects_zero_and_negative_sides():
    for bad in ("0x540", "960x0", "-960x540"):
        with pytest.raises(ValueError):
            parse_region(bad)


def test_default_region_is_sixteen_by_nine():
    assert DEFAULT_REGION[0] / DEFAULT_REGION[1] == pytest.approx(16 / 9)


# ── pruning ─────────────────────────────────────────────────────────────────

def _shots(dir_: Path, count: int) -> list:
    made = []
    for i in range(count):
        p = dir_ / f"capture_{i:03d}.png"
        p.write_bytes(b"x")
        # mtime decides which survive, so make the order unambiguous
        import os
        os.utime(p, (1_700_000_000 + i, 1_700_000_000 + i))
        made.append(p)
    return made


def test_prune_keeps_only_the_newest(tmp_path):
    made = _shots(tmp_path, 25)

    prune(keep=20, directory=tmp_path)

    survivors = sorted(p.name for p in tmp_path.glob("*.png"))
    assert len(survivors) == 20
    assert survivors == sorted(p.name for p in made[5:])


def test_prune_is_a_noop_below_the_limit(tmp_path):
    _shots(tmp_path, 3)

    prune(keep=20, directory=tmp_path)

    assert len(list(tmp_path.glob("*.png"))) == 3


def test_prune_leaves_other_files_alone(tmp_path):
    _shots(tmp_path, 25)
    keeper = tmp_path / ".gitkeep"
    keeper.write_bytes(b"")

    prune(keep=1, directory=tmp_path)

    assert keeper.exists()
    assert len(list(tmp_path.glob("*.png"))) == 1


def test_prune_survives_a_missing_directory(tmp_path):
    prune(keep=20, directory=tmp_path / "nope")


def test_prune_survives_a_file_it_cannot_delete(tmp_path):
    _shots(tmp_path, 25)

    with patch("phonexi.screenshot.Path.unlink", side_effect=PermissionError):
        prune(keep=1, directory=tmp_path)

    assert len(list(tmp_path.glob("*.png"))) == 25
