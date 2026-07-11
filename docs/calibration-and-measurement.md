# Calibration and Measurement Contract

## Reference plane

V1 requires a fully visible ISO ID-1 reference card (`85.60 × 53.98 mm`) in the same plane as the nails. The detector:

1. Finds convex four-corner candidates covering 3–75% of the image.
2. Orders the corners and checks the physical aspect ratio.
3. Rejects candidates touching the image boundary, with excessive perspective compression, invalid aspect, unstable homography, or excessive edge-fit error.
4. Maps the card to a rectified plane at approximately 10 pixels per millimetre.
5. Applies the same homography to the complete hand/card plane so nail content outside the card is retained.

The system distinguishes missing, invalid/cropped/uncertain, and excessively steep references so the UI can give a specific correction.

## Projected width

The segmentation mask is measured only after it has been transformed into the calibrated reference plane. PCA supplies the nail’s longitudinal axis. The algorithm examines transverse contour chords through the central 80% of the nail axis and returns the widest valid chord.

This is a projected planar width, not a curved surface measurement.

## Uncertainty

For chord width `w_px`, scale `s_px_per_mm`, segmentation boundary error `e_px`, and relative calibration scale uncertainty `r`, the reported uncertainty is:

```text
width_mm = w_px / s_px_per_mm
uncertainty_mm = sqrt((e_px / s_px_per_mm)^2 + (width_mm × r)^2)
```

Calibration uncertainty includes contour-to-quadrilateral fit error with a conservative minimum floor. Model evaluation must supply the segmentation boundary error; IoU alone is insufficient.

Initial confidence buckets are deterministic:

- High: uncertainty ≤ 0.4 mm and segmentation confidence ≥ 0.90.
- Medium: uncertainty ≤ 0.7 mm and segmentation confidence ≥ 0.75.
- Low: everything else; the public API must return a retake rather than a measurement.

These thresholds are provisional until the participant-disjoint feasibility study is complete. They must be recalibrated from physical measurement and best-fit data without weakening the release gates.
