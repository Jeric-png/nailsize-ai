# Calibration and Measurement Contract

## Active beta method

`auto-assumed23-single-v0.2.0` accepts one photo of one nail beside a Singapore 50-cent coin. The app automatically treats the detected round reference as exactly `23.00 mm`. This is a product assumption, not denomination recognition or diameter verification.

The browser prepares the image locally, runs the pinned nail-specific YOLOv8-seg artifact described in [`automatic-model-provenance.md`](automatic-model-provenance.md), and proposes nail geometry. Deterministic PCA and transverse-chord geometry derive a visible width line from the strongest usable mask. The result screen shows this detection as a read-only overlay.

## Reference fitting and scale

The local edge detector proposes reference-like ellipses and the single-nail route uses its strongest confident proposal as a best-effort scale. It does not stop for ovality, rim-quality, or minimum-size questions. If no confident round reference is found, the app asks for another photo instead of opening a calibration screen.

For a width vector rotated into the fitted ellipse axes:

```text
length_in_reference_radii = hypot(delta_major / major_radius_px,
                                  delta_minor / minor_radius_px)
projected_width_mm = (23.00 / 2) * length_in_reference_radii
```

This directional local scale handles moderate apparent ovality but is not a full homography. A wrong reference diameter, reference/nail distance, perspective, nail height, lens distortion, and curvature can all bias the result.

## Review and recommendation

Unusable nail proposals are rejected. Any usable proposal produces the result without a confirmation or adjustment step. Detection confidence and calibration details are not exposed as customer decisions.

`platform-default@1` is provisional: size 0 is 18 mm, size 1 is 17 mm, through size 9 at 9 mm. The recommendation uses the uncertainty-adjusted width and always returns exactly one best-fit size. Estimates wider than the chart use size 0; narrower estimates use size 9.

## Guided rollback

`guided-sg50-coin-v1` remains the deterministic manual fallback. It uses four capture groups with two photos per group. Users mark eight coin-rim points and two nail sidewalls in each photo; paired readings must agree within `0.6 mm`. That rule demonstrates repeatability only, not accuracy. Evidence for the guided and automatic methods must not be mixed.

## Interpretation and validation boundary

Both methods estimate visible projected planar width, not curved surface length. Neither guarantees fit. The automatic method's model scores, visible overlays, deterministic geometry, software tests, and supplied-photo functional result do not establish millimetre accuracy. Representative technician-defined physical measurements and the actual supplier tip chart are required before accuracy or fit claims.
