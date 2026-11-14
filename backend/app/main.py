"""HTTP API. All routes live under /api; the built React app is served from /."""
import csv
import io
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas, stats
from .auth import create_token, current_user, require_supervisor, verify_password
from .db import Base, engine, get_db
from .models import AuditEntry, Control, Result, User, Violation
from .qc import audit, record_run, z_of

Base.metadata.create_all(engine)

app = FastAPI(title="Westgard QC Tracker", version="1.0.0",
              description="Log quality-control results and check them against the Westgard rules.")


# ---------------------------------------------------------------- auth
@app.post("/api/auth/login", response_model=schemas.Token, tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"access_token": create_token(user)}


@app.get("/api/me", response_model=schemas.UserOut, tags=["auth"])
def me(user: User = Depends(current_user)):
    return user


# ---------------------------------------------------------------- controls
def _control_out(db: Session, c: Control) -> schemas.ControlOut:
    latest = db.scalar(select(Result.status).where(Result.control_id == c.id)
                       .order_by(Result.measured_at.desc(), Result.id.desc()).limit(1))
    open_count = db.scalar(select(func.count(Violation.id)).join(Result)
                           .where(Result.control_id == c.id, Violation.reviewed_at.is_(None)))
    out = schemas.ControlOut.model_validate(c)
    out.latest_status = latest
    out.open_violations = open_count or 0
    return out


@app.get("/api/controls", response_model=list[schemas.ControlOut], tags=["controls"])
def list_controls(db: Session = Depends(get_db), user: User = Depends(current_user)):
    controls = db.scalars(select(Control).where(Control.active)
                          .order_by(Control.instrument, Control.analyte, Control.level)).all()
    return [_control_out(db, c) for c in controls]


@app.post("/api/controls", response_model=schemas.ControlOut, status_code=201, tags=["controls"])
def create_control(body: schemas.ControlIn, db: Session = Depends(get_db),
                   user: User = Depends(require_supervisor)):
    c = Control(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, user, "control.create", f"{c.instrument} {c.analyte} {c.level} lot {c.lot}")
    db.commit()
    return _control_out(db, c)


@app.get("/api/controls/{control_id}", response_model=schemas.ControlOut, tags=["controls"])
def get_control(control_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = db.get(Control, control_id)
    if not c:
        raise HTTPException(404, "Control not found")
    return _control_out(db, c)


@app.get("/api/controls/{control_id}/stats", tags=["controls"])
def control_stats(control_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = db.get(Control, control_id)
    if not c:
        raise HTTPException(404, "Control not found")
    values = db.scalars(select(Result.value).where(Result.control_id == control_id)).all()
    return stats.summarize(list(values), c.target_mean, c.target_sd)


# ---------------------------------------------------------------- results
def _result_out(r: Result) -> schemas.ResultOut:
    return schemas.ResultOut(
        id=r.id, control_id=r.control_id, value=r.value, z=round(z_of(r), 3), run_id=r.run_id,
        measured_at=r.measured_at, status=r.status,
        violations=[schemas.ViolationOut.model_validate(v) for v in r.violations])


@app.get("/api/controls/{control_id}/results", response_model=list[schemas.ResultOut], tags=["results"])
def list_results(control_id: int, limit: int = 60, db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    rows = db.scalars(select(Result).where(Result.control_id == control_id)
                      .order_by(Result.measured_at.desc(), Result.id.desc()).limit(min(limit, 500))).all()
    return [_result_out(r) for r in reversed(rows)]


@app.post("/api/controls/{control_id}/results", response_model=schemas.ResultOut, status_code=201,
          tags=["results"])
def add_result(control_id: int, body: schemas.ResultIn, db: Session = Depends(get_db),
               user: User = Depends(current_user)):
    try:
        [r] = record_run(db, body.run_id, {control_id: body.value}, user, body.measured_at)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _result_out(r)


@app.post("/api/runs", response_model=list[schemas.ResultOut], status_code=201, tags=["results"])
def add_run(body: schemas.RunIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Enter several control levels from the same run, so within-run rules apply."""
    try:
        results = record_run(db, body.run_id, body.values, user, body.measured_at)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return [_result_out(r) for r in results]


@app.post("/api/import", response_model=schemas.ImportSummary, tags=["results"])
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db),
                     user: User = Depends(current_user)):
    """CSV columns: control_id, value, run_id, measured_at (ISO 8601, optional).

    Rows are grouped by run and processed in time order, so the rules see
    the history in the right sequence.
    """
    text = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    missing = {"control_id", "value", "run_id"} - set(reader.fieldnames or [])
    if missing:
        raise HTTPException(400, f"CSV is missing columns: {', '.join(sorted(missing))}")
    runs: dict[tuple[datetime, str], dict[int, float]] = {}
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        try:
            cid = int(row["control_id"])
            value = float(row["value"])
            when = datetime.fromisoformat(row["measured_at"]) if row.get("measured_at") else datetime.now(timezone.utc)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if not db.get(Control, cid):
                raise ValueError(f"no control {cid}")
            runs.setdefault((when, row["run_id"]), {})[cid] = value
        except (ValueError, KeyError) as e:
            errors.append(f"Row {i}: {e}")
    imported = warnings = rejects = 0
    for (when, run_id), values in sorted(runs.items()):
        for r in record_run(db, run_id, values, user, when):
            imported += 1
            warnings += r.status == "warning"
            rejects += r.status == "reject"
    return {"imported": imported, "warnings": warnings, "rejects": rejects, "errors": errors}


# ---------------------------------------------------------------- violations
@app.get("/api/violations", response_model=list[schemas.ViolationDetail], tags=["violations"])
def list_violations(open_only: bool = True, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Violation).join(Result).order_by(Result.measured_at.desc(), Violation.id.desc()).limit(200)
    if open_only:
        q = q.where(Violation.reviewed_at.is_(None))
    out = []
    for v in db.scalars(q).all():
        r, c = v.result, v.result.control
        reviewer = db.get(User, v.reviewed_by_id) if v.reviewed_by_id else None
        out.append(schemas.ViolationDetail(
            id=v.id, rule=v.rule, scope=v.scope, corrective_action=v.corrective_action,
            reviewed_at=v.reviewed_at, result_id=r.id, control_id=c.id,
            control_label=f"{c.instrument} · {c.analyte} · {c.level}", value=r.value,
            measured_at=r.measured_at, reviewed_by=reviewer.name if reviewer else None))
    return out


@app.patch("/api/violations/{violation_id}", response_model=schemas.ViolationOut, tags=["violations"])
def resolve_violation(violation_id: int, body: schemas.CorrectiveActionIn, db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    """Record the corrective action. Only a supervisor can sign off a reject."""
    v = db.get(Violation, violation_id)
    if not v:
        raise HTTPException(404, "Violation not found")
    if v.result.status == "reject" and user.role != "supervisor":
        raise HTTPException(403, "A supervisor must review rejected runs")
    v.corrective_action = body.corrective_action
    v.reviewed_by_id = user.id
    v.reviewed_at = datetime.now(timezone.utc)
    audit(db, user, "violation.review", f"violation {v.id} ({v.rule}): {body.corrective_action}")
    db.commit()
    return v


@app.get("/api/audit", tags=["audit"])
def audit_log(db: Session = Depends(get_db), user: User = Depends(require_supervisor)):
    rows = db.scalars(select(AuditEntry).order_by(AuditEntry.at.desc()).limit(200)).all()
    names = {u.id: u.name for u in db.scalars(select(User)).all()}
    return [{"at": a.at, "user": names.get(a.user_id, "system"), "action": a.action, "detail": a.detail}
            for a in rows]


@app.get("/api/health", tags=["meta"])
def health():
    return {"ok": True}


# ---------------------------------------------------------------- frontend
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = DIST / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(DIST / "index.html")
