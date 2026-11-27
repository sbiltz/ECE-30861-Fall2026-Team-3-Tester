# Team 3 Tester

This repository tests any compatible pod system. The sibling Project repository implements Team 3's target. [shared-openapi.yaml](contract/shared-openapi.yaml) is the supplied API contract v0.5.0. Regenerate the JSON cache with `python sync_contract.py` when the supplied YAML changes.

- The tester's setup accepts `target_url` at runtime and forwards a generated session ID to the target's setup. Run the suite once per session and serve its stored report on retrieval. Keep tester routes and target routes distinct, and retain target base paths.
- Validate the contract, fixtures and observable behavior. Rule-only targets are valid. Check optional AI fields and provenance when present. Accept semantically valid alternatives to fixture assumptions where the shared contract permits them.
- Keep case IDs stable, preserve binary fixture bytes, and distinguish failure, skip, transport error and unavailable coverage. Verify with `python -B -m unittest discover -v` and `ruff check . --select E9,F`.
- Use the [cross-team verification skill](.agents/skills/cross-team-verification/SKILL.md) for Section 6.1, hosted route checks and submission evidence. Separate simulated and live results. A live run may use the target team's quota.
