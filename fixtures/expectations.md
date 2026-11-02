# Phase 4 fixture expectations

The original six inputs and their preliminary ZIP baselines are preserved. Those
ZIPs are only exact-regression artifacts in optional zip-baseline mode; they do
not define the current shared response schema or detection expectations.

`accessibilityIssues.pdf` has a blank Info/Title and no Catalog/Lang. T-13 expects
fail findings for CHK-TITLE and CHK-LANG, mapped to their agreed WCAG criteria and
auto_fixable classification; issue_type wording is not prescribed by the contract.

`phase4_human_review.pdf` is a locally generated raster chart with bars and in-image
year/value labels. It has Figure MCID 0, generic /Alt "image1", a valid /P and
ParentTree association, MarkInfo, valid title and en-US. Extracted page text does
not reproduce the chart values; no equivalent alternative table is provided.
T-14 expects a CHK-NONTEXT human-review finding, unresolved and included in
human_review_items. It does not prescribe issue_type wording or a fabricated
passing alternative. No external content or model is used to create this fixture.

T-12 requires all eight check IDs in checks_performed. A catalog entry alone is
not evidence a check ran. Other semantic findings may differ across implementations.
