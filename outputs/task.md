# NailSize Single-Nail Tasks

## Product and implementation

- [x] Replace the two-hand automatic route with one digit and one photo.
- [x] Require an explicit `23.00 mm` reference assumption.
- [x] Automatically propose reference and nail geometry locally.
- [x] Replace eight-point reference marking with one centre tap when correction is needed.
- [x] Show two sidewall handles only when the nail line needs review.
- [x] Return one conservative size suggestion or an out-of-chart result.
- [x] Keep the guided workflow as rollback.
- [x] Keep selected images out of requests and persistence.

## Verification and release

- [x] Add single-photo component, sizing, and one-tap detector tests.
- [x] Exercise the supplied one-nail photo after local JPEG conversion under the explicit 23 mm assumption.
- [x] Pass lint, typecheck, unit, build, bundle, E2E, compatibility, and dependency checks.
- [ ] Pass GitHub CI and security checks.
- [ ] Deploy and verify staging.
- [ ] Promote and verify the identical production artifact.

## Independent validation still required

- [ ] Validate projected widths against technician-defined physical ground truth.
- [ ] Approve or replace `platform-default@1` with the actual supplier chart.
- [ ] Test model generalization, mobile performance, and assistive-technology behavior on representative devices and users.
- [ ] Confirm the long-term interpretation of upstream model licensing metadata.
