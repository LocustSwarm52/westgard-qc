"""Each rule gets a case that should trigger it and a near miss that should not."""
import pytest

from app.westgard import (
    Status, check_across_runs, check_within_run, overall_status, z_score,
)


def test_z_score():
    assert z_score(110, 100, 5) == 2
    with pytest.raises(ValueError):
        z_score(1, 1, 0)


def test_in_control_result_breaks_nothing():
    assert check_across_runs([0.3, -0.5, 1.1, 0.2]) == []


@pytest.mark.parametrize("z, expected", [
    (2.1, ["1-2s"]), (-2.1, ["1-2s"]), (1.99, []),
    (3.2, ["1-3s"]), (-3.01, ["1-3s"]), (2.99, ["1-2s"]),
])
def test_single_result_rules(z, expected):
    assert check_across_runs([0.0, z]) == expected


def test_2_2s_fires_on_two_in_a_row_same_side():
    assert "2-2s" in check_across_runs([0.1, 2.2, 2.4])
    assert "2-2s" in check_across_runs([-2.5, -2.1])


def test_2_2s_near_misses():
    assert "2-2s" not in check_across_runs([2.2, 1.9])     # second inside 2 SD
    assert "2-2s" not in check_across_runs([2.2, -2.3])    # opposite sides
    assert "2-2s" not in check_across_runs([2.2, 0.0, 2.3])  # not consecutive


def test_4_1s():
    assert "4-1s" in check_across_runs([1.2, 1.5, 1.1, 1.3])
    assert "4-1s" in check_across_runs([-1.1, -1.4, -1.9, -1.2])
    assert "4-1s" not in check_across_runs([1.2, 1.5, 0.9, 1.3])
    assert "4-1s" not in check_across_runs([1.2, 1.5, 1.1])  # only three


def test_10x():
    above = [0.2, 0.5, 0.1, 0.9, 0.3, 0.4, 0.7, 0.2, 0.6, 0.1]
    assert "10x" in check_across_runs(above)
    assert "10x" in check_across_runs([-v for v in above])
    assert "10x" not in check_across_runs(above[:-1] + [-0.1])
    assert "10x" not in check_across_runs(above[:9])


def test_old_violations_are_not_reported_again():
    # 2-2s happened earlier; the newest result is back in control.
    assert check_across_runs([2.3, 2.4, 0.1]) == []


def test_within_run_r4s():
    assert "R-4s" in check_within_run([2.3, -2.1])
    assert "R-4s" not in check_within_run([2.3, -1.9])
    assert "R-4s" not in check_within_run([2.3])


def test_within_run_2_2s_across_levels():
    assert "2-2s" in check_within_run([2.2, 2.6])
    assert "2-2s" in check_within_run([-2.2, 0.1, -2.6])
    assert "2-2s" not in check_within_run([2.2, 1.6])


@pytest.mark.parametrize("rules, status", [
    ([], Status.ACCEPT),
    (["1-2s"], Status.WARNING),
    (["1-2s", "2-2s"], Status.REJECT),
    (["1-3s"], Status.REJECT),
    (["10x"], Status.REJECT),
])
def test_overall_status(rules, status):
    assert overall_status(rules) == status
