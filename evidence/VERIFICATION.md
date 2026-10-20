# Publication verification

Verified October 20, 2026. This document reports software/publication checks, not new model performance.

- A fresh Python 3.12 environment installed the standalone viewer and contract dependencies under the recorded constraints. **70 tests passed**, with two native checks deselected and one upstream deprecation warning.
- The two separately marked native mechanics checks passed against the pinned installed AppWorld runtime and official data, with their own isolated output root. They exercised no acting model. Existing native dependencies emitted deprecation warnings. A complete fresh native bootstrap was not executed during publication; its optional instructions and patch are provided separately.
- The original 38-file source inventory and all 1,742 source event rows matched their pre-publication hashes. The original workspace and its Git history were not imported or changed.
- The public projection retains all 1,742 event IDs in order. Comparison reconciliation confirmed four version cells, six native attempts, four conclusive outcomes, two excluded inconclusive attempts and no missing version outcome. Check counts remain 1/4, 3/4, 1/4 and 4/4.
- The sanitized encrypted bundle was successfully unpacked and its local HTML inspected. Known authentication values were removed across code and observations. Private grader details and post-task reviewer payloads were withheld.
- Browser checks passed at 390, 736, 1024 and 1440 pixels, with zero JavaScript errors. All eight public tabs, session switching, receipt/event inspection and offline read-only viewing were exercised. The published screenshot contains only the metadata projection.
- Gitleaks 8.30.1 was downloaded from its official release and its archive checksum verified. The file scan and initial-commit history scan both passed with zero findings. The repository-specific check additionally validates excluded file types, local links, metric counts and the encrypted bundle checksum.

Full detailed benchmark-derived content stays encrypted because AppWorld requires encrypted redistribution. The encryption wrapper prevents accidental plaintext indexing and is not a private-access mechanism. Redaction and source-lineage details are in sanitization-report.json. The publication includes no new AppWorld or model experiment result.
