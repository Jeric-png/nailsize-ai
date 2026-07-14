# Calibration and Measurement Contract

## Active beta method

`auto-assumed23-single-v0.1.0` accepts one photo of one selected nail. The user explicitly instructs the app to treat the complete round reference in the image as exactly `23.00 mm`. This is an input assumption, not denomination recognition or diameter verification.

The browser prepares the image locally, runs the pinned nail-specific YOLOv8-seg artifact described in [`automatic-model-provenance.md`](automatic-model-provenance.md), and proposes nail geometry. Deterministic PCA and transverse-chord geometry derive a visible width line from the strongest usable mask. The proposal remains editable and is never measurement proof by itself.

## Reference fitting and scale

The local edge detector first proposes reference-like ellipses. Accepted geometry requires a complete rim, sufficient pixel diameter, moderate ovality, strong rim coverage, and low residual. If full-frame selection is ambiguous, the user taps the intended reference centre once. A bounded local search then fits the strongest qualifying rim automatically; the beta never asks for eight rim markers.

For a width vector rotated into the fitted ellipse axes:

```text
length_in_reference_radii = hypot(delta_major / major_radius_px,
                                  delta_minor / minor_radius_px)
projected_width_mm = (23.00 / 2) * length_in_reference_radii
```

This directional local scale handles moderate apparent ovality but is not a full homography. A wrong reference diameter, reference/nail distance, perspective, nail height, lens distortion, and curvature can all bias the result.

## Review and recommendation

Low-confidence, fragmented, cropped, or otherwise weak nail proposals require review through two visible sidewall handles. Corrected endpoints replace the proposed width line. Invalid geometry fails closed.

The UI displays projected width and uncertainty rounded to `0.1 mm`. `platform-default@1` is provisional: size 0 is 18 mm, size 1 is 17 mm, through size 9 at 9 mm. The recommendation uses the uncertainty-adjusted width and returns exactly one conservative best-fit size. A boundary warning may accompany that one result; readings outside the chart receive no default size.

## Guided rollback

`guided-sg50-coin-v1` remains the deterministic manual fallback. It uses four capture groups with two photos per group. Users mark eight coin-rim points and two nail sidewalls in each photo; paired readings must agree within `0.6 mm`. That rule demonstrates repeatability only, not accuracy. Evidence for the guided and automatic methods must not be mixed.

## Interpretation and validation boundary

Both methods estimate visible projected planar width, not curved surface length. Neither guarantees fit. The automatic method's model scores, visible overlays, deterministic geometry, software tests, and supplied-photo functional result do not establish millimetre accuracy. Representative technician-defined physical measurements and the actual supplier tip chart are required before accuracy or fit claims.
