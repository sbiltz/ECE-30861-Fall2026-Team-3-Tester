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

## Supplied 15-file fixture set

T-06 requires findings from the five checks in the shared catalog that apply to
the original issue fixture. Low contrast (WCAG 1.4.3) is outside that catalog.
T-22 through T-29 require the assigned check to be the only check producing
findings. T-30 checks that the target processes the valid raster PDF. OCR
transcription quality remains a separate manual check because the API does not
return transcribed text.

The current test set includes:

Should be rejected:
- NonPDF.docx (File type is not PDF)
- BiggerThan20MB.pdf (File exceeds 20 MB)
- passwordprotected.pdf (Password: test1234)
- encrypted.pdf (It opens without a password, but printing, copying and editing are locked)

Should be accepted:
- goodAccessible.pdf (No accessibility issues)
- accessibilityIssues.pdf (Accessibility issues listed below)
- wcag-1.1.1-missing-alt.pdf (Accessibility issue listed below)
- wcag-1.3.1-heading-tagged-as-paragraph.pdf (Accessibility issue listed below)
- wcag-1.3.3-location-only-instruction.pdf (Accessibility issue listed below)
- wcag-1.4.1-color-only-status.pdf (Accessibility issue listed below)
- wcag-2.4.2-missing-title.pdf (Accessibility issue listed below)
- wcag-2.4.4-ambiguous-link-purpose.pdf (Accessibility issue listed below)
- wcag-2.4.6-vague-heading.pdf (Accessibility issue listed below)
- wcag-3.1.1-missing-language.pdf (Accessibility issue listed below)

Should return no usable OCR text:
- ocr-unreadable-scan.pdf (Simulated scan of a faded 1912 letter with heavily degraded text and no embedded text layer)

accessibilityIssues.pdf has the following issues:
- No tags or structure tree. Headings, the table and the list are visual only (WCAG 1.3.1). (human-review)
- No document language (3.1.1). (auto-fixable)
- Empty document title (2.4.2). (auto-fixable)
- Image with no alt text (1.1.1). (human-review)
- Low-contrast text. The "Important: …" line is light gray on white, about 1.6:1 (1.4.3). (human-review)
- Table drawn as plain lines and text with no header cells (1.3.1). (human-review)
- "Click here" link with non-descriptive text (2.4.4). (human-review)

wcag-1.1.1-missing-alt.pdf has the following issues:
- The labeled route map carries the directions from the trailhead to the ranger station. The surrounding text refers readers to the map without spelling out the route. Inspect the Figure tag for a missing /Alt entry. There is no equivalent description in the text. (WCAG 1.1.1, human-review)

wcag-1.3.1-heading-tagged-as-paragraph.pdf has the following issues:
- "Weekday hours" and "Weekend hours" have the same visible heading style. Inspect the tag tree or a screen reader's headings list. "Weekday hours" is tagged H2, while "Weekend hours" is tagged P and is skipped during heading navigation. (WCAG 1.3.1)

wcag-1.3.3-location-only-instruction.pdf has the following issues:
- To book after 6 p.m., readers are told to choose from the list on the right. Both wings have names and comparable room options, but the instructions never name the eligible wing. Read the page in tag order without the layout and check whether the instructions still identify which wing to choose. (WCAG 1.3.3, human-review)

wcag-1.4.1-color-only-status.pdf has the following issues:
- The Friday register shows four bookings. Its key maps navy to confirmed and maroon to pending, but no booking row states its status in text or uses a secondary marker. In grayscale or extracted text, try identifying which of the two 1 p.m. bookings is confirmed. (WCAG 1.4.1, human-review)

wcag-2.4.2-missing-title.pdf has the following issues:
- The page contains East Branch library information with no visible title. In Document Properties, verify that Title is blank. There is no PDF metadata title or XMP metadata title, and the filename is only the fixture ID. (WCAG 2.4.2, auto-fixable)

wcag-2.4.4-ambiguous-link-purpose.pdf has the following issues:
- The tagged "Click here" link follows generic text in the "Online services" section. The section mentions two different services, but the link text and its context describe neither the actual destination nor what following the link does. Inspect the link text and enclosing section before activating it. (WCAG 2.4.4, human-review)

wcag-2.4.6-vague-heading.pdf has the following issues:
- "Miscellaneous" is a genuine H2, like "After-hours entry." Read the two headings on their own. "Miscellaneous" gives no indication that its section explains how to report and replace a lost badge. (WCAG 2.4.6, human-review)

wcag-3.1.1-missing-language.pdf has the following issues:
- The garage guide is written in English. Inspect the PDF catalog and tag tree for the language setting. The catalog has no /Lang entry and the structure supplies no language override. (WCAG 3.1.1, auto-fixable)

Run the OCR scan separately from the WCAG cases. The scan has no embedded text layer, and the expected OCR result is no usable transcription. OCR may return fragments or noise. The PDF structure and rendered pages were inspected independently of your checker. Exact flags and OCR output still need to be confirmed in your checker.

WCAG 2.1 reference: https://www.w3.org/TR/WCAG21/
