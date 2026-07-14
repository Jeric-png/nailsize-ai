# Client Certification

Client certification is a manual release gate performed against the deployed release candidate. Playwright CI is early compatibility evidence; it does not replace branded browsers, physical mobile devices, or assistive-technology review.

Record the immutable deployment URL, tested commit SHA, browser and operating-system versions, execution environment, pass/fail status, and an approved review reference. Do not include tester names, email addresses, customer photos, marker coordinates, measurements, screenshots containing customer data, or free-form notes.

## Browser matrix

Provide exactly one result for `current`, `previous_1`, and `previous_2` for each platform:

- iOS Safari and Android Chrome on physical devices;
- desktop Chrome, Edge, Firefox, and Safari on physical devices or a hosted service running the real branded browser.

Every referenced run must execute the complete guided flow against the same deployed commit: mandatory confirmation of the current Third Series Port of Singapore/large `50` and `CENTS` coin, eight local photos across four groups, independent eight-rim-marker calibration for every photo, all nail-edge markers, an inconsistent-repeat retake, one clear sizing result for each of ten nails without a competing boundary size, text-only copy/share, reset, and reload recovery. Include rejection checks for a coin under `120 px` in prepared-image/source-coordinate space, a coin under `120 CSS/screen px` in the rendered annotation view, oval/centre-spread failures, a nail beyond `4.5` coin diameters, and source images over 20 MP or with either side over 8192 px. Confirm that arrow keys move a focused marker by one rendered CSS pixel and Shift plus an arrow moves it by eight, including on a high-resolution image. Confirm the browser makes no non-GET or cross-origin sizing request. The rendered-size check is an ergonomics requirement, not physical accuracy evidence.

## Accessibility evidence

The `accessibility` object contains pass booleans and named references for mobile and desktop automated scans, manual keyboard review, VoiceOver on iOS Safari, TalkBack on Android Chrome, the blocking-issue count, and accountable accessibility review. Certification requires WCAG 2.2 AA with zero critical/serious automated findings and zero blocking keyboard or assistive-technology issues.

Certification is incomplete when required runs or review references are missing, fails when any required behavior fails, and passes only when every check passes. Only a pass permits continued launch validation. Retain the aggregate decision; raw device recordings and diagnostic material stay in the approved evidence system and must not contain customer data.
