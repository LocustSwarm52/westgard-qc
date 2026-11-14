"""Recording QC results and judging them with the Westgard rules."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import westgard
from .models import AuditEntry, Control, Result, User, Violation

HISTORY_NEEDED = 10  # the longest rule (10x) looks back 10 results


def z_of(result: Result) -> float:
    c = result.control
    return westgard.z_score(result.value, c.target_mean, c.target_sd)


def record_run(db: Session, run_id: str, values: dict[int, float],
               user: User | None, measured_at: datetime | None = None) -> list[Result]:
    """Save one run (one or more control levels) and judge every new result.

    1. Save each value.
    2. Across runs: compare each new result with that control's earlier results.
    3. Within the run: compare the levels of the same analyte on the same
       instrument measured in this run, including any entered earlier.
    4. Set each result's status from the rules it broke.
    """
    measured_at = measured_at or datetime.now(timezone.utc)
    if measured_at.tzinfo is None:
        measured_at = measured_at.replace(tzinfo=timezone.utc)

    new: list[Result] = []
    for control_id, value in values.items():
        control = db.get(Control, control_id)
        if control is None or not control.active:
            raise ValueError(f"Control {control_id} not found or inactive")
        r = Result(control=control, value=value, run_id=run_id, measured_at=measured_at,
                   entered_by_id=user.id if user else None)
        db.add(r)
        new.append(r)
    db.flush()  # assigns ids

    rules_by_result: dict[int, list[tuple[str, str]]] = {r.id: [] for r in new}

    # 2. Across runs, per control.
    for r in new:
        earlier = db.scalars(
            select(Result)
            .where(Result.control_id == r.control_id, Result.id != r.id,
                   Result.measured_at <= r.measured_at)
            .order_by(Result.measured_at.desc(), Result.id.desc())
            .limit(HISTORY_NEEDED - 1)
        ).all()
        history = [z_of(x) for x in reversed(earlier)] + [z_of(r)]
        for code in westgard.check_across_runs(history):
            rules_by_result[r.id].append((code, "across-runs"))

    # 3. Within the run, grouped by instrument and analyte.
    groups: dict[tuple[str, str], list[Result]] = {}
    for r in new:
        groups.setdefault((r.control.instrument, r.control.analyte), []).append(r)
    for (instrument, analyte), members in groups.items():
        run_results = db.scalars(
            select(Result).join(Control)
            .where(Result.run_id == run_id, Control.instrument == instrument, Control.analyte == analyte)
        ).all()
        zs = [z_of(x) for x in run_results]
        for code in westgard.check_within_run(zs):
            # Attach the violation to each new result that took part (beyond 2 SD).
            for r in members:
                if abs(z_of(r)) > 2 and (code, "across-runs") not in rules_by_result[r.id]:
                    rules_by_result[r.id].append((code, "within-run"))

    # 4. Save violations and statuses.
    for r in new:
        codes = rules_by_result[r.id]
        for code, scope in codes:
            r.violations.append(Violation(rule=code, scope=scope))
        r.status = westgard.overall_status([c for c, _ in codes]).value
        audit(db, user, "result.add",
              f"control {r.control_id} value {r.value} run {run_id} -> {r.status}"
              + (f" ({', '.join(c for c, _ in codes)})" if codes else ""))
    db.commit()
    return new


def audit(db: Session, user: User | None, action: str, detail: str) -> None:
    db.add(AuditEntry(user_id=user.id if user else None, action=action, detail=detail))
