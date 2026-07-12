# Client Certification

Client certification is a manual release gate performed against the deployed release candidate. Playwright CI is early compatibility evidence; it does not replace branded browsers, physical mobile devices, or assistive-technology review.

Run:

```bash
python services/inference/scripts/client_certification.py \
  /approved-evidence/client-certification-study.json \
  --output /approved-evidence/client-certification-report.json
```

The input must use `nailsize-client-certification-study@1` with these exact top-level fields: `schema_version`, `release_version`, `tested_commit_sha`, `browser_matrix`, `accessibility`, `browser_version_review_ref`, and `client_certification_review_ref`. The version review records the authoritative source used to identify the current branded-browser majors; the final review confirms that the complete evidence belongs to the declared release. Do not include tester names, email addresses, screenshots containing customer data, or free-form notes.

## Browser matrix

Provide exactly one result for `current`, `previous_1`, and `previous_2` for each platform:

- iOS Safari and Android Chrome on physical devices;
- desktop Chrome, Edge, Firefox, and Safari on physical devices or a hosted service running the real branded browser.

Every record contains only `platform`, `version_slot`, `browser_major`, `execution_environment`, `run_ref`, and `passed`. Major versions must be consecutive. Each referenced run must execute the complete NailSize E2E flow, including camera or upload, four accepted captures, targeted retake, error recovery, and ten-nail results against the same deployed commit.

## Accessibility evidence

The `accessibility` object contains pass booleans and named references for mobile and desktop automated scans, manual keyboard review, VoiceOver on iOS Safari, TalkBack on Android Chrome, the blocking-issue count, and accountable accessibility review. Certification requires WCAG 2.2 AA with zero critical/serious automated findings and zero blocking keyboard or assistive-technology issues.

The report returns `insufficient_evidence` when required runs or review references are missing, `client_validation_failed` when complete evidence contains a failure, and `client_validation_passed` only when every check passes. Only the last decision permits continued launch validation. The aggregate report may be retained; raw device recordings and diagnostic material stay in the approved evidence system.
