# Study guide: know this project cold

Read the files in this order. After each one, close it and explain out loud what it does. If you can't, read it again. The questions at the end are the kind interviewers ask.

## 1. `backend/app/westgard.py` (start here, about 120 lines)

- Every result becomes a **z-score**: how many SDs it sits from the target mean.
- `check_across_runs(history)` looks at **one control over time**. The list is oldest-first, and the last item is the result being judged. Every rule checks a window that *ends* at the newest result, which is why an old violation isn't reported again.
- `check_within_run(run)` looks at **several control levels from one run**, for R-4s and 2-2s across levels.
- `overall_status()` turns the list of broken rules into accept, warning, or reject. 1-2s alone is only a warning, and every other rule rejects.

## 2. `backend/tests/test_westgard.py`

Notice the pattern: each rule has a case that **should** trigger it and a **near miss** that shouldn't, for example 2-2s with the second value at 1.9 SD. Testing the edge is what catches off-by-one mistakes like `>` versus `>=`.

## 3. `backend/app/models.py`

Five tables: users, controls, results, violations, audit_log. A control is one control material at one level on one instrument. Results store the **raw value**, never the z-score, so correcting a control's target mean can't leave stale numbers behind.

## 4. `backend/app/qc.py` (the core logic)

`record_run()` does four steps; read the docstring. Key ideas:
- `db.flush()` sends the new rows to the database so they get ids, without committing yet.
- History is ordered by `measured_at`, the time the sample was run, not the time someone typed it. There's a test for this.
- Everything commits in one transaction at the end, so a failure leaves no half-saved run.

## 5. `backend/app/auth.py`

- Passwords are never stored. Each gets a random **salt**, then is run through PBKDF2 200,000 times. Salting means two people with the same password get different hashes, and the iterations make guessing slow.
- `hmac.compare_digest` compares in constant time, so an attacker can't learn anything from how long a comparison takes.
- After login the server hands out a **JWT**: a signed token with the user id, role, and expiry. The browser sends it with every request in the `Authorization` header.
- `Depends(current_user)` and `Depends(require_supervisor)` are FastAPI **dependencies**: any route that lists one runs the check first.

## 6. `backend/app/main.py`

Skim the routes. Each one takes validated input (the classes in `schemas.py`) and returns a typed response. FastAPI uses those types to reject bad input with a 422 and to generate the docs page at `/docs`.

## 7. `backend/tests/conftest.py` and `test_api.py`

Each test gets a fresh **in-memory** database through `app.dependency_overrides`, so tests never touch real data and can't affect each other.

## 8. Frontend: `api.js`, then `main.jsx`, `pages.jsx`, `LeveyJennings.jsx`

- `api.js` attaches the token to every request and signs you out on a 401.
- `useLoad` in `pages.jsx` is a small custom hook: it calls the API, tracks loading and error state, and offers `reload()`.
- `LeveyJennings.jsx` plots z-scores, so every control shares the same -4 to +4 axis. The SD lines are extra flat datasets.

## 9. `Dockerfile` and `.github/workflows/ci.yml`

- The Dockerfile has **two stages**: Node builds the React app, then a slim Python image copies in just the built files. The final image has no Node in it, which keeps it small.
- CI runs two jobs on every push: the backend tests and the frontend build.

## Interview questions to practise

1. Walk me through what happens when a tech enters a result.
2. Why convert values to z-scores?
3. How do you avoid reporting the same 4-1s violation four times?
4. Why order history by measurement time instead of insertion order?
5. How are passwords stored? Why salt them?
6. What's in a JWT, and why can't a user just edit their role in it?
7. Why is the rule engine separate from the web code?
8. How do the tests get a clean database each time?
9. What would you change to support thousands of labs? (Index the time columns, which they are; paginate the violations list; cache control lookups; move CSV imports to a background job.)
10. What would you add next? (Cumulative mean recalculation for new lots, a 2-of-3-2s rule for three-level controls, email alerts on rejects.)
