"""Westgard multirule engine.

Pure Python with no web or database code, so every rule can be tested
on its own. Results are compared as z-scores:

    z = (value - target mean) / target SD

Two kinds of checks:
  * across runs: the newest result of one control, compared with that
    control's earlier results (1-2s, 1-3s, 2-2s, 4-1s, 10x)
  * within a run: results from different control levels measured in
    the same run (2-2s and R-4s across levels)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    ACCEPT = "accept"
    WARNING = "warning"
    REJECT = "reject"


@dataclass(frozen=True)
class Rule:
    code: str
    name: str
    status: Status
    error_type: str  # "random", "systematic", or "none"
    description: str


RULES = {
    "1-2s": Rule("1-2s", "1-2s", Status.WARNING, "none",
                 "One result beyond 2 SD. A warning to inspect the other rules."),
    "1-3s": Rule("1-3s", "1-3s", Status.REJECT, "random",
                 "One result beyond 3 SD."),
    "2-2s": Rule("2-2s", "2-2s", Status.REJECT, "systematic",
                 "Two consecutive results beyond 2 SD on the same side."),
    "R-4s": Rule("R-4s", "R-4s", Status.REJECT, "random",
                 "In one run, one result beyond +2 SD and another beyond -2 SD."),
    "4-1s": Rule("4-1s", "4-1s", Status.REJECT, "systematic",
                 "Four consecutive results beyond 1 SD on the same side."),
    "10x": Rule("10x", "10x", Status.REJECT, "systematic",
                "Ten consecutive results on the same side of the mean."),
}


def z_score(value: float, mean: float, sd: float) -> float:
    if sd <= 0:
        raise ValueError("SD must be positive")
    return (value - mean) / sd


def _same_side_beyond(zs: list[float], limit: float) -> bool:
    """True if every z is beyond +limit, or every z is beyond -limit."""
    return all(z > limit for z in zs) or all(z < -limit for z in zs)


def check_across_runs(history: list[float]) -> list[str]:
    """Rules broken by the newest result of one control.

    `history` holds that control's z-scores in time order, oldest first;
    the last element is the result being judged. A rule only fires if the
    newest result is part of the pattern, so an old violation is never
    reported again.
    """
    if not history:
        return []
    broken: list[str] = []
    z = history[-1]

    if abs(z) > 3:
        broken.append("1-3s")
    elif abs(z) > 2:
        broken.append("1-2s")

    if len(history) >= 2 and _same_side_beyond(history[-2:], 2):
        broken.append("2-2s")
    if len(history) >= 4 and _same_side_beyond(history[-4:], 1):
        broken.append("4-1s")
    if len(history) >= 10 and _same_side_beyond(history[-10:], 0):
        broken.append("10x")
    return broken


def check_within_run(run: list[float]) -> list[str]:
    """Rules broken across the control levels measured in one run."""
    broken: list[str] = []
    if len(run) < 2:
        return broken
    if max(run) > 2 and min(run) < -2:
        broken.append("R-4s")
    # 2-2s across levels: two or more levels beyond 2 SD on the same side.
    if sum(z > 2 for z in run) >= 2 or sum(z < -2 for z in run) >= 2:
        broken.append("2-2s")
    return broken


def overall_status(rule_codes: list[str]) -> Status:
    """Reject if any rejection rule fired; warning if only 1-2s fired."""
    statuses = {RULES[c].status for c in rule_codes}
    if Status.REJECT in statuses:
        return Status.REJECT
    if Status.WARNING in statuses:
        return Status.WARNING
    return Status.ACCEPT
