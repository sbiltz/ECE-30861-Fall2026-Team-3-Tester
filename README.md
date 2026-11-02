# Team 3 Phase 4 PDF tester

This tester targets the pod's supplied **OpenAPI v0.4.0** contract. The canonical
contract is `shared-openapi.yaml`, copied from the user-supplied `openapi.yaml`.
Runtime schema validation reads that YAML directly and converts OpenAPI nullable
fields to JSON Schema. `shared-openapi.json` is a generated compatibility copy,
not a separate source of truth; a regression test detects copy drift.

## Start locally

```powershell
cd "C:\Users\sophi\Documents\Codex\ECE-30861-Fall2026-Team-3-Tester"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8002 --workers 1
```

Use `/` for the dashboard or `/docs` and `/tester` for the API explorer. Supply
the target service base URL, including its deployment path prefix if present.
The tester does not require editing source to switch targets. Restart after edits.
These local changes do not deploy or restart a hosted tester.

## Course tester interface

- `POST /test/setup`: JSON `target_url`; creates a UUID and forwards
  `{"session_id":"<uuid>","setup":{}}` to the target. Returns 201 only after
  target setup succeeds with the same session ID. Setup failures create no session.
- `POST /test/run`: JSON `session_id`; runs the suite once and stores its report.
  A second/concurrent run returns 409. If the response is lost, retrieve the saved
  report rather than rerunning the same session. Tester aborts save partial results.
- `GET /test/report?session_id=...`: retrieves the stored report unchanged; 409
  while unfinished, 404 for unknown IDs, 400 for malformed input.

The target system and tester have separate setup/report endpoints and must run
on different ports. Sessions/reports are in memory; use one worker and create a
new session after a restart. There is no authentication. Credentials, query strings
and fragments are not accepted in target URLs.

## Phase 4 suite

There are **21 report entries: 20 executable cases and one Phase 5 skip**.
Original T-01 through T-06 retain their identifiers for comparison with older runs.

| ID | Test |
| --- | --- |
| T-01 | Above-20-MB input: 413 FILE_TOO_LARGE |
| T-02 | Accepted accessible fixture: JSON schema, PDF readability and integrity |
| T-03 | Non-PDF: 415 INVALID_FILE_TYPE |
| T-04 | Password protection: 422 PASSWORD_PROTECTED_PDF |
| T-05 | Encryption: 422 ENCRYPTED_PDF |
| T-06 | Issue fixture: valid evaluation response and integrity |
| T-07 | Health status and current shared version |
| T-08 | All eight catalog entries, WCAG mappings and classifications |
| T-09 | Missing upload: 400 MISSING_FILE |
| T-10 | Corrupt PDF: 422 CORRUPTED_PDF or UNREADABLE_PDF |
| T-11 | Exactly 20,971,520 bytes: accepted if otherwise valid |
| T-12 | All eight Phase 4 checks actually listed in checks_performed |
| T-13 | Predetermined title/language findings and classifications |
| T-14 | Predetermined generic Figure alternative remains unresolved human review |
| T-15 | Shared output=zip format and archive/PDF integrity |
| T-16 | Invalid output option: 400 INVALID_REQUEST |
| T-17 | output=zip input validation still returns JSON and correct error status |
| T-18 | Explicit output=json returns the JSON result |
| T-19 | Duplicate target session: 409 |
| T-20 | Unknown target report session: 404 |
| T-21 | Phase 5 repair/revalidation: explicitly skipped |

`detected` is a valid v0.4.0 status for an unrepaired auto_fixable finding. Human
review findings must retain needs_human_review and must not be automatically
repaired. The suite checks agreed WCAG/classification mappings, finding identifiers,
repair/status consistency, review references, summary counts, PDF hashes and original
preservation. It does not enforce another team's issue_type wording, report prose,
generated UUID/PDF bytes, or exact implementation-specific finding counts.

`fixtures/expectations.md` records why known title/language and human-review cases
are expected. These are selected detection examples, not proof of all semantic
checks' accuracy. T-12 checks execution coverage separately from catalog declaration.

## Shared ZIP contract versus old Team 3 ZIP extension

Default contract mode sends JSON requests. ZIP tests use the **multipart field
`output=zip`**, not an Accept header alone. A shared ZIP contains `original.pdf`,
the named output/report PDFs and `result.json`; its PDF metadata deliberately omits
content_base64. Input-validation failures remain JSON 4xx responses, even with
output=zip. The shared YAML's health example still says 0.3.0, but its declared
info.version and change notes are 0.4.0; T-07 uses info.version.

The six original expected ZIPs are preserved only for optional exact regression:

```powershell
$env:TESTER_MODE = 'zip-baseline'
```

That legacy mode requests the old Accept-header ZIP extension and compares those
six preliminary artifacts exactly (except evaluation IDs); the new cases are
skipped. It is **not** the pod's v0.4.0 cross-team conformance mode. Use this default
for shared testing:

```powershell
$env:TESTER_MODE = 'contract'
```

## Coverage and interpretation

- Code coverage comes only from the target's `/test/report`; null means unavailable.
  The tester does not invent a percentage when target instrumentation is absent.
- Component coverage follows x-pod-testing request-exercise rules. This suite can
  exercise 6 of 8 components; repair and revalidation are deferred to Phase 5.
  A failed assertion may still exercise a component; communication failures do not.
- System-model coverage remains null. The shared file lists AC-01 through AC-10
  without definitions, while the separately supplied AC list uses AC-02 through
  AC-13. The pod must agree a versioned mapping before a numeric count is claimed.

Passing this tester does not certify ADA/WCAG conformance. Correctness of every
semantic accessibility check still requires additional agreed fixtures/manual review.
Failures identify an observed mismatch; they are not silently accepted to improve
the pass rate. Communication failures and target 5xx failures are reported separately.

## Run from PowerShell

```powershell
$tester = 'http://127.0.0.1:8002'
$setupBody = @{target_url='http://127.0.0.1:8001'} | ConvertTo-Json
$session = Invoke-RestMethod -Method Post -Uri "$tester/test/setup" -ContentType 'application/json' -Body $setupBody -TimeoutSec 15
$runBody = @{session_id=$session.session_id} | ConvertTo-Json
$report = Invoke-RestMethod -Method Post -Uri "$tester/test/run" -ContentType 'application/json' -Body $runBody -TimeoutSec 1350
$report.results | Format-Table test_id,outcome,source,message -Wrap
$report | ConvertTo-Json -Depth 20 | Set-Content report.json
```

Setup calls use 10 seconds, project calls and coverage retrieval use 60 seconds,
and no calls are retried. The full suite can take about 21 minutes at timeout
boundaries. Configure any tester hosting/proxy timeout accordingly or retrieve
the saved report after a client timeout. An unreachable target should fail setup
without running the suite; a tester failure should not be blamed on the target.

## Verify the tester

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -v
```

Tests include v0.4.0 status/error/bbox regressions, the previous six baseline
comparisons, a compliant simulated target, deliberate target defects, multipart
form encoding, coverage accounting, and session/report preservation. Local tests
use controlled responses and do not contact deployed services. A live cross-team
run is a separate verification step and produces a new report/session.
