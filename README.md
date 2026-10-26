# Team 3 PDF tester

This tester runs the six provided input files against a system's `/process`
endpoint using the shared v0.3.0 JSON contract. Supplied ZIPs provide the input
fixtures and expected acceptance/rejection outcomes.
It exposes `POST /test/setup`, `POST /test/run`, and `GET /test/report`,
plus a browser homepage at `/`.

## Host locally on Windows

Install Python 3.10 or newer. Open PowerShell and run:

```powershell
cd "C:\Users\sophi\Documents\Codex\ECE-30861-Fall2026-Team-3-Tester"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8002 --workers 1
```

Keep that window open. The tester base URL is `http://127.0.0.1:8002`.
Stop it with Ctrl+C. To restart later, run just the last command from the repo.
No virtual-environment activation is needed. Open http://127.0.0.1:8002 in your
browser to use the homepage. Enter the system URL, click Create new session,
then Run six tests. The page displays results, coverage, and the full JSON
report. Retrieve report recovers an existing session report without running
tests; Download report saves it as JSON. Restart the tester after code changes.

Start your target system in a separate PowerShell window. For the current Team 3
system, using its existing Python environment:

```powershell
cd "C:\Users\sophi\Documents\Codex\ECE-30861-Fall-2026-Team-3-Project"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001 --workers 1
```

The system base URL is `http://127.0.0.1:8001`. The tester and system must use
different ports. Use the actual target team's system URL to test another team.

## Run all six cases

Open a third PowerShell window:

```powershell
$tester = 'http://127.0.0.1:8002'
$setupBody = @{target_url='http://127.0.0.1:8001'} | ConvertTo-Json
$session = Invoke-RestMethod -Method Post -Uri "$tester/test/setup" -ContentType 'application/json' -Body $setupBody -TimeoutSec 15
$runBody = @{session_id=$session.session_id} | ConvertTo-Json
$report = Invoke-RestMethod -Method Post -Uri "$tester/test/run" -ContentType 'application/json' -Body $runBody -TimeoutSec 450
$report.results | Format-Table test_id,outcome,source,message -Wrap
$report | ConvertTo-Json -Depth 20 | Set-Content report.json
```

Retrieve the saved report without rerunning:

```powershell
Invoke-RestMethod -Uri "$tester/test/report?session_id=$($session.session_id)" | ConvertTo-Json -Depth 20
```

Create a new setup session whenever you want to repeat the suite. A second run
in the same session returns 409. If a run response is lost or times out, retrieve
the report instead; 409 means it has not ended yet, so try report retrieval later.

## Test cases and expected behavior

| ID | Input | Expected report.json result |
| --- | --- | --- |
| T-01 | BiggerThan20MB.pdf | error / FILE_TOO_LARGE |
| T-02 | goodAccessible.pdf | completed / completed_no_repairs |
| T-03 | NonPDF.docx | error / INVALID_FILE_TYPE |
| T-04 | passwordprotected.pdf | error / PASSWORD_PROTECTED_PDF |
| T-05 | encrypted.pdf | error / ENCRYPTED_PDF |
| T-06 | accessibilityIssues.pdf | completed / completed_no_repairs |

Inputs are in `fixtures/inputs`; reference ZIPs are in `fixtures/expected`.
They are bundled in this repo, so running the tester does not depend on Downloads.
Default mode is `contract`. All six `/process` requests include the prepared
session ID and `Accept: application/json`. Oversized files must return 413,
non-PDF files 415, and password-protected/encrypted files 422; accepted PDFs
return 200. Error codes must match, while explanatory wording may differ.

Accepted responses are validated against EvaluationResult in the shared schema,
including UUIDs, required fields, enum values and nested findings/repairs. Input
filename, size and SHA-256 must match the uploaded bytes. Embedded output/report
PDFs must contain PDF data and match their SHA-256. An output marked unmodified
must equal the input. Deferred checks must be named in limitations. Another
team may return different valid findings, repairs, generated PDFs and report
wording; this preliminary suite does not assert accessibility correctness.

The exact shared contract is saved as `shared-openapi.yaml`; the nullable-aware
validation copy is `shared-openapi.json`. Source:
https://github.com/arwaMoustafa04/AccessibilityProblemsChecker/blob/v0.3.0-phase3/openapi.yaml
The source version was downloaded and checked when implementing compatibility.

Optional Team 3 ZIP regression mode uses the six exact supplied outputs:

```powershell
$env:TESTER_MODE = 'zip-baseline'
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8002 --workers 1
```

In this mode the tester requests application/zip and expects HTTP 200 delivery
for all six cases. It compares ZIP members, PDF bytes, and report.json exactly,
except generated evaluation IDs; ZIP timestamps/compression/order are ignored.
ZIP transport is a Team 3 extension and is not required by the shared contract.
Return to the cross-team default before starting the server with:

```powershell
$env:TESTER_MODE = 'contract'
```

These examples do not establish accessibility correctness. In particular,
accessibilityIssues.pdf must be accepted, but contract mode permits repairs
and findings from implementations that have progressed beyond input validation.
Only optional ZIP regression mode requires its unchanged preliminary output. Component coverage measures only
input validation and report output (up to 2 of the pod's 8 components). System
acceptance-criterion coverage is null because their detailed definitions have
not been supplied. Code coverage is forwarded from the target, or null with an
explanation when unavailable. Coverage is not a pass rate.

## Endpoint behavior and limits

- `POST /test/setup`: JSON `target_url`; creates a UUID and forwards
  `{"session_id":"<uuid>","setup":{}}` to target setup. Returns 201 only after
  the system returns 201 with the same ID. Valid target setup errors preserve
  their status, message and source. Failed setup creates no runnable session.
- `POST /test/run`: JSON `session_id`; executes six sequential requests, stores
  and returns the complete report, including failed tests and target errors.
  A tester abort returns 500 and saves available outcomes plus error/skip entries.
- `GET /test/report?session_id=...`: unchanged saved report, or 409 before run
  ends. Never starts tests. Invalid input: 400; unknown sessions: 404;
  concurrent/repeated runs: 409. Error bodies contain message and source.

System setup timeout: 10 seconds. Each project call and coverage retrieval:
60 seconds, with no retries. Allow 15 seconds for tester setup and 450 seconds
for tester run (six calls plus coverage retrieval and local comparisons).
Sessions/reports live in memory until shutdown; always use one worker/instance.
No authentication. Do not put credentials, query strings, fragments or `/test`
suffixes in target_url. Deployment path prefixes are supported.

To make the tester reachable from another computer on your local network, start
it with `--host 0.0.0.0` instead of `--host 127.0.0.1`, allow port 8002 through
Windows Firewall if prompted, and use `http://<your-PC-LAN-IP>:8002` from that
computer. Keep the target URL reachable from the tester computer. Local hosting
does not by itself provide a public Internet URL for the course registry.

## Verify the tester's comparison logic

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -v
```
