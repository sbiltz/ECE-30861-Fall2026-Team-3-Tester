---
name: cross-team-verification
description: Verify the Team 3 tester against a configurable pod target and collect Section 6.1 evidence for hosted routes, live calls, and saved reports.
---

# Cross-team tester verification

1. Check the target's GET /health against the supplied API version. Read the tester's public OpenAPI and verify the exact methods and paths from the rubric. The local FastAPI routes use /test/setup, /test/run and /test/report. /tester serves Swagger. If /tester/test/* is required publicly, verify the deployed prefix or route mapping explicitly.
2. Send a compatible team's base URL, including any deployment path, as target_url to tester setup. Use the returned session ID for one run, then retrieve the saved report. An unknown report session can itself return 404, so use a known ID to verify a report route.
3. Before a live suite run, check that the intended target is available for testing and that the run fits its quota. For offline verification run the existing simulated target tests.
4. Document the actual hosted tester URL and commands in the README so a grader can swap target_url without editing code. In VERIFICATION.md record the date, revision if known, target version, route statuses and observed case outcomes. Label simulations and historical phase evidence accordingly.
