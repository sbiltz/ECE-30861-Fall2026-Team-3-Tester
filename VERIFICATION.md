# Tester v0.4.0 verification — November 1, 2026 (America/Indianapolis)

## Cause and scope

The tester was pinned to shared v0.3.0. The supplied current shared YAML is v0.4.0
and allows unrepaired auto_fixable findings to use `detected`, adds INVALID_REQUEST,
optional bounding boxes and multipart output=json/zip. Rejecting Team 1's detected
statuses was a tester-version defect, not evidence that those statuses were invalid.

Only the tester repository was changed. Neither service was modified, committed,
pushed or deployed by this repair. The previous six input and expected-ZIP artifacts
remain unchanged. The shared YAML is byte-for-byte identical to the supplied file
(SHA-256 d3b4217129181a94f5e657dc0ebdc1632719a31bcdc8bb971f3df17f70b6eda7).

## Local verification

- Baseline: `python -B -m unittest discover -v`: 6 tests passed.
- Before the implementation change: all 4 new regressions failed as expected
  (version, detected enum, INVALID_REQUEST enum, malformed optional bbox).
- Final: `python -B -m unittest discover -v`: 31 tests passed.
- A compliant simulated target passes all 20 executable suite cases; T-21 is a
  deliberate Phase 5 skip. Deliberately malformed responses are rejected.
- The real human-review fixture is tested for its image, MCID, /P and ParentTree
  associations, and does not supply equivalent extracted text for chart values.
- `git diff --check` passes. The shared YAML may produce Git's line-ending notice;
  this does not indicate a content mismatch.

## Live cross-team verification

The final updated suite was executed against both deployed URLs after fixture
validation. Each run used a fresh session; project calls were not automatically
retried. The first diagnostic fixture was improved to a properly associated raster
chart before these final results; final and diagnostic reports remain separate.

| Target | Passed | Failed | Communication/system errors | Phase 5 skipped |
| --- | --- | --- | --- | --- |
| Team 1: http://3.15.117.84/system | 19 | 1 | 0 | 1 |
| Team 3: https://team3-system-756038174349.us-central1.run.app | 13 | 7 | 0 | 1 |

Team 1's prior finding-status schema rejection is gone. Its remaining failure is
T-14: no CHK-NONTEXT human-review finding was returned for the new generic-alt-text
chart fixture. This is a selected detection case, not a universal accuracy measure.

Team 3 failures:

- T-06/T-13: auto_fixable findings still use needs_human_review instead of the
  current detected/fixed/repair_failed status semantics.
- T-07: health advertises 0.3.0 rather than the current 0.4.0.
- T-12: CHK-HEADINGS, CHK-LINK, CHK-SENSORY and CHK-STRUCTURE were not performed.
- T-15: ZIP lacks shared `result.json` / `original.pdf` member names.
- T-16: invalid output option returns 200 instead of 400 INVALID_REQUEST.
- T-17: ZIP validation failure returns 200 instead of JSON HTTP 415.

These are reported service mismatches; the tester does not hide them or loosen
the current shared contract to obtain passing scores.

Both runs exercised 6/8 components. Team 1 reported 592/1555 code lines; Team 3
reported code instrumentation unavailable. System-model coverage remains null
because a consistent versioned AC definition/mapping has not been supplied.
The final reports are named team1_final_v04_report.json and
team3_final_v04_report.json and were saved with this chat's verification outputs.

Restart/redeploy the tester to make these local changes available to podmates.
