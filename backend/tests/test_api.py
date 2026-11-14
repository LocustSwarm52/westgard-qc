"""API tests: logins, roles, results, rule checks, violations, CSV import."""
from datetime import datetime, timedelta, timezone

T0 = datetime(2026, 1, 1, 7, tzinfo=timezone.utc)


def make_control(client, sup, **kw):
    body = {"instrument": "Analyzer", "analyte": "Glucose", "level": "Level 1", "lot": "L1",
            "target_mean": 100, "target_sd": 5, "units": "mg/dL", **kw}
    r = client.post("/api/controls", json=body, headers=sup)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def add(client, headers, cid, value, day, run=None):
    return client.post(f"/api/controls/{cid}/results", headers=headers, json={
        "value": value, "run_id": run or f"R{day}", "measured_at": (T0 + timedelta(days=day)).isoformat()})


def test_login_and_me(client, tech):
    assert client.get("/api/me", headers=tech).json()["role"] == "tech"


def test_wrong_password_rejected(client):
    r = client.post("/api/auth/login", data={"username": "tech@test.lab", "password": "nope"})
    assert r.status_code == 401


def test_routes_need_login(client):
    assert client.get("/api/controls").status_code == 401


def test_only_supervisor_creates_controls(client, tech, sup):
    body = {"instrument": "A", "analyte": "B", "level": "1", "lot": "x", "target_mean": 1, "target_sd": 0.1}
    assert client.post("/api/controls", json=body, headers=tech).status_code == 403
    assert client.post("/api/controls", json=body, headers=sup).status_code == 201


def test_sd_must_be_positive(client, sup):
    body = {"instrument": "A", "analyte": "B", "level": "1", "lot": "x", "target_mean": 1, "target_sd": 0}
    assert client.post("/api/controls", json=body, headers=sup).status_code == 422


def test_in_control_result_is_accepted(client, sup, tech):
    cid = make_control(client, sup)
    r = add(client, tech, cid, 101, 0).json()
    assert r["status"] == "accept" and r["violations"] == [] and r["z"] == 0.2


def test_1_3s_rejects(client, sup, tech):
    cid = make_control(client, sup)
    r = add(client, tech, cid, 116, 0).json()   # z = 3.2
    assert r["status"] == "reject"
    assert [v["rule"] for v in r["violations"]] == ["1-3s"]


def test_2_2s_across_runs(client, sup, tech):
    cid = make_control(client, sup)
    assert add(client, tech, cid, 111, 0).json()["status"] == "warning"   # 1-2s
    r = add(client, tech, cid, 112, 1).json()
    assert r["status"] == "reject"
    assert {"1-2s", "2-2s"} == {v["rule"] for v in r["violations"]}


def test_4_1s_and_10x(client, sup, tech):
    cid = make_control(client, sup)
    statuses = [add(client, tech, cid, 106, d).json() for d in range(10)]  # z = 1.2 every day
    assert statuses[2]["status"] == "accept"
    assert "4-1s" in [v["rule"] for v in statuses[3]["violations"]]
    assert "10x" in [v["rule"] for v in statuses[9]["violations"]]


def test_r4s_within_run(client, sup, tech):
    l1 = make_control(client, sup, level="Level 1")
    l2 = make_control(client, sup, level="Level 2", target_mean=300, target_sd=10)
    r = client.post("/api/runs", headers=tech, json={
        "run_id": "RUN-1", "measured_at": T0.isoformat(), "values": {str(l1): 111.5, str(l2): 277}})
    assert r.status_code == 201
    rules = {v["rule"] for res in r.json() for v in res["violations"]}
    assert "R-4s" in rules
    assert all(res["status"] == "reject" for res in r.json())


def test_rules_use_measured_time_not_entry_order(client, sup, tech):
    cid = make_control(client, sup)
    add(client, tech, cid, 111, 5)            # day 5
    r = add(client, tech, cid, 100, 4).json()  # entered later, measured earlier
    assert r["status"] == "accept"


def test_violation_review_flow(client, sup, tech):
    cid = make_control(client, sup)
    add(client, tech, cid, 117, 0)  # reject
    [v] = client.get("/api/violations", headers=tech).json()
    body = {"corrective_action": "Recalibrated, reran controls, both in range."}
    assert client.patch(f"/api/violations/{v['id']}", json=body, headers=tech).status_code == 403
    assert client.patch(f"/api/violations/{v['id']}", json=body, headers=sup).status_code == 200
    assert client.get("/api/violations", headers=tech).json() == []
    assert len(client.get("/api/violations?open_only=false", headers=tech).json()) == 1
    log = client.get("/api/audit", headers=sup).json()
    assert any(e["action"] == "violation.review" for e in log)


def test_stats(client, sup, tech):
    cid = make_control(client, sup)
    for d, v in enumerate([98, 100, 102, 104]):
        add(client, tech, cid, v, d)
    s = client.get(f"/api/controls/{cid}/stats", headers=tech).json()
    assert s["n"] == 4 and s["mean"] == 101 and s["bias_percent"] == 1.0
    assert abs(s["sd"] - 2.582) < 0.001


def test_csv_import(client, sup, tech):
    cid = make_control(client, sup)
    rows = ["control_id,value,run_id,measured_at"]
    rows += [f"{cid},106,R{d},2026-01-{d + 1:02d}T07:00:00" for d in range(4)]
    rows += [f"{cid},abc,R9,2026-01-09T07:00:00", "999,100,R10,2026-01-10T07:00:00"]
    r = client.post("/api/import", headers=tech,
                    files={"file": ("qc.csv", "\n".join(rows), "text/csv")})
    s = r.json()
    assert s["imported"] == 4 and s["rejects"] == 1 and len(s["errors"]) == 2


def test_csv_missing_columns(client, tech):
    r = client.post("/api/import", headers=tech, files={"file": ("qc.csv", "value\n1", "text/csv")})
    assert r.status_code == 400
