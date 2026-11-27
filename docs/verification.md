# Phase 5 tester verification — November 15, 2026

## Scope and source

Only the tester repository was updated. No service code was edited, no hosted
service was contacted, and no LLM API calls or quota were used. No commits,
pushes or deployments were performed.

Canonical [shared-openapi.yaml](../contract/shared-openapi.yaml) is byte-for-byte identical to the user-supplied
phase5_withLLM_openapi.yaml (OpenAPI 3.0.3, API version 0.5.0).
[shared-openapi.json](../contract/shared-openapi.json) was regenerated using [sync_contract.py](../sync_contract.py) and has a drift test.

## Baseline and reproduced failures

The existing baseline ran 32 tests with one failure: the archived original in
accessibilityIssues_review.zip differed from the checked-out input PDF. The
content matched after CRLF normalization. Ten uncompressed PDF fixtures had
checkout newline conversion, which also produced invalid cross-reference offset
warnings. Their original Git source bytes were restored and .gitattributes now
marks PDFs, ZIPs and DOCX files binary. Existing ZIP baselines were not rewritten.
After this repair all original archive comparisons pass.

The tester otherwise targeted v0.4.0, skipped T-21 repair/revalidation, accepted
the image-only scan, and rejected every human-review repair record. New
regressions failed against those behaviors before the fixes. Separate tests
reproduced that the old transport accepted responses exceeding the complete
request time budget.

## Final behavior

- 35 executable default-contract cases; no deferred Phase 5 skip.
- T-21 inspects title/language repair records, final status, passed validation
  and actual output PDF metadata. The known English fixture must declare English.
- T-30/T-32 reject scanned/image-only and entirely blank PDFs with NO_TEXT_LAYER.
- T-31 tests mixed text/scanned/blank pages; scanned page 2 must be disclosed and
  cannot carry the specified text-based findings.
- T-33 accepts invisible OCR text as a text layer.
- T-34/T-35 verify unknown/omitted optional processing-session IDs.
- LLM fields remain optional. A rule-only simulated target passes the full suite.
- Allowed AI alt/link draft writes remain unresolved human-review items and do
  not increase fixed_count. Color/sensory PDF repairs and LLM use on prohibited
  checks are rejected. Successful LLM writes record applied text.
- Generated model wording is never compared with expected strings. The mandated
  AI label and external-provider disclosure are checked only when LLM use is reported.
- Setup, saved-report behavior, 10/60-second budgets, no retries, nullable coverage,
  JSON/ZIP schemas, PDF bytes/hashes and original preservation remain covered.

## Verification commands and results

The tester has no local .venv in this checkout. Verification reused the installed
service environment as an interpreter only:

~~~powershell
& 'C:/Users/sophi/Documents/Codex/ECE-30861-Fall-2026-Team-3-Project/.venv/Scripts/python.exe' -B -m unittest discover -q
~~~

Final result: **50 tests passed**. The final automated run also blocked any
unexpected live transport calls while allowing individual tests to supply their
mock responses. All tests use local fixtures and controlled target responses.
A separate simulated app.run / saved-report check passed 35/35 cases, exercised
8/8 pod components, and validated the resulting SuiteReport model. Its output is
explicitly named phase5_tester_simulated_report.json in this chat’s outputs.

The supplied YAML identity and generated JSON cache were checked. git diff --check
passed; ordinary Windows line-ending notices do not indicate a failed check.

## Limits and follow-up

No live cross-team run was made. A simulated target passing does not establish
that Team 1 or Team 3 currently passes, nor that a provider is available. Actual
runs may consume the target’s configured model quota or incur charges.

The service’s previously deferred title/language remediation is expected to be
flagged by T-21 until implemented; the tester does not skip it to raise scores.
Existing Rhea model behavior was not changed in the service. The tester validates
observable responses under the supplied Phase 5 contract, which restricts LLM use.
Coverage describes exercised components, not WCAG accuracy or certification.
System-model coverage remains unavailable pending agreed acceptance-criterion
meanings/mappings; target code-coverage availability remains the target’s report.

Historical November 1 Phase 4 deployment scores described in the former version
of this file are not Phase 5 verification and have not been rerun here.
