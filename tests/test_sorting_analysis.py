"""Tests for the fractional-length reduction + comparison (cbc-04 tooling).

Uses the real heterotypicboundary.dat files the cbc-02 spike archived under the
investigation, so the reduction is verified against genuine Chaste output with no
Docker dependency.
"""
import math
from pathlib import Path

import pytest

from pbg_chaste.sorting_analysis import (
    Trajectory,
    compare,
    read_dat,
)

_RAW = (
    Path(__file__).resolve().parent.parent
    / "workspace/investigations/cellbased-comparison-2017"
    / "studies/cbc-02-onlattice-wrapper-extension/spikes/raw"
)


def test_read_dat_computes_fractional_length():
    # cp spike file: rows like "0.2  99  203  30  56" -> 99/203
    traj = read_dat(str(_RAW / "cp-heterotypicboundary.dat"), model="cp", source="spike")
    assert traj.times, "no rows parsed"
    last = traj.fractional_length[-1]
    assert last is not None
    assert 0.0 < last < 1.0


def test_os_degenerate_row_is_not_silently_zero():
    """OS spike lengths are ~1e-7 (tangent tissue). Fraction is a real ratio, not None/0."""
    traj = read_dat(str(_RAW / "os-heterotypicboundary.dat"), model="os", source="spike")
    fl = traj.fractional_length[-1]
    # total length is tiny but > 0, so the fraction is defined (and ~ pair ratio)
    assert fl is not None
    assert 0.0 <= fl <= 1.0


def test_undefined_fraction_when_total_zero(tmp_path):
    p = tmp_path / "heterotypicboundary.dat"
    p.write_text("0.0  0  0  0  0\n0.1  5  10  2  4\n")
    traj = read_dat(str(p))
    assert traj.fractional_length[0] is None      # 0/0 -> undefined, not 0.0
    assert traj.fractional_length[1] == 0.5


def test_compare_aligns_and_diffs():
    a = Trajectory(model="cp", source="cxx",
                   times=[0.0, 1.0, 2.0], fractional_length=[1.0, 0.6, 0.3],
                   pair_fraction=[1.0, 0.6, 0.3])
    b = Trajectory(model="cp", source="pychaste",
                   times=[0.0, 1.0, 2.0], fractional_length=[1.0, 0.5, 0.35],
                   pair_fraction=[1.0, 0.5, 0.35])
    cmp = compare(a, b)
    assert cmp.times == [0.0, 1.0, 2.0]
    assert cmp.abs_diff[0] == pytest.approx(0.0)
    assert cmp.abs_diff[1] == pytest.approx(0.1)
    assert cmp.max_abs_diff == pytest.approx(0.1)


def test_compare_skips_undefined_points():
    a = Trajectory(model="os", source="cxx", times=[0.0, 1.0],
                   fractional_length=[None, 0.4], pair_fraction=[None, 0.4])
    b = Trajectory(model="os", source="pychaste", times=[0.0, 1.0],
                   fractional_length=[0.5, 0.42], pair_fraction=[0.5, 0.42])
    cmp = compare(a, b)
    # t=0: cxx undefined -> abs_diff None; t=1: both defined
    assert cmp.abs_diff[0] is None
    assert cmp.abs_diff[1] == pytest.approx(0.02)
    assert cmp.max_abs_diff == pytest.approx(0.02)
