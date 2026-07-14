# Calibration and Measurement Contract

## Active method

`guided-sg50-coin-v1` is a deterministic, browser-local measurement method. It does not detect nails, call an API, or run an AI model. The user supplies the geometry by marking the supported coin rim and the nail sidewalls.

The only supported reference is the current Third Series Singapore 50-cent circulation coin. Its official diameter is `23.00 mm` with a `±0.10 mm` tolerance. Before capture, the user must confirm that the coin shows the Port of Singapore and a large `50` with `CENTS`. Older Singapore 50-cent coins, commemoratives, damaged coins, and foreign coins must be rejected because their dimensions are not the active reference.

The coin specification and identifying design are documented by the [Singapore Currency Act legal specification](https://sso.agc.gov.sg/SL/CA1967-S347-2013?ProvIds=Sc-&ValidDate=20130611) and the [Monetary Authority of Singapore Third Series coin release](https://www.nas.gov.sg/archivesonline/data/pdfdoc/20130228006/press_release.pdf).

## Coin calibration

Every photo must show the complete coin beside the target nails on the same flat surface. The phone should be directly overhead so the coin appears round. The user places eight markers clockwise around the rim, starting at the top and continuing through the upper-right, right, lower-right, bottom, lower-left, left, and upper-left positions.

The UI retains normalized marker positions for responsive display, then converts them using the prepared image's real dimensions:

```text
x_px = x_normalized * prepared_image_width_px
y_px = y_normalized * prepared_image_height_px
```

The four opposite marker pairs produce four pixel diameters. Calibration uses their median diameter and the average of their pair centres. It fails closed when:

- any marker or part of the rim is outside the prepared image;
- the markers are not clockwise, convex, and reasonably evenly distributed;
- the median coin diameter is less than `120 px` in the prepared image's source-coordinate space;
- `(maximum_diameter - minimum_diameter) / median_diameter > 0.08`; or
- the greatest opposite-pair centre deviation exceeds `0.06 * median_diameter`.

The scale is:

```text
millimetres_per_pixel = 23.00 / median_coin_diameter_px
```

The `±0.10 mm` legal coin tolerance is a physical source of scale uncertainty. The method does not estimate an individual coin's actual diameter.

Before coin confirmation, the UI independently measures the marked coin in the rendered annotation view. Its median diameter must be at least `120 CSS/screen px`. This display-space guard keeps eight rim controls large enough to place and adjust; it does not change the millimetre scale and is not physical accuracy validation.

Arrow keys move a focused marker by one rendered CSS pixel, and Shift plus an arrow key moves it by eight rendered CSS pixels. Keyboard movement is defined in the displayed annotation's coordinate space rather than the prepared image's source pixels, so a high-resolution photo does not make keyboard adjustment impractically fine.

## Nail width

The user marks the left and right sidewalls at the widest visible point of each nail. Their prepared-image pixel distance is multiplied by `millimetres_per_pixel`. The nail midpoint must remain within `4.5` median coin diameters of the calibrated coin centre, and a single-photo reading outside `5–25 mm` is rejected as a marker or setup error.

The four capture groups are left fingers, left thumb, right fingers, and right thumb. Each group requires two separately positioned photos, for eight photos and ten final nail measurements. After local normalization, the client hashes each image with SHA-256 and rejects an exact duplicate as the second observation. This detects same-image reuse only; it cannot establish that the hand and phone were physically repositioned.

## Repeatability and result mapping

For each nail:

```text
repeat_delta_mm = abs(first_width_mm - verification_width_mm)
displayed_projected_width_mm = (first_width_mm + verification_width_mm) / 2
sizing_width_mm = max(first_width_mm, verification_width_mm)
```

The group passes only when every nail has `repeat_delta_mm <= 0.6`. The **0.6 mm value is a repeatability threshold, not an accuracy bound, confidence interval, or fit guarantee**. It is provisional until physical validation establishes an appropriate operating limit.

The UI displays the two-photo average, rounded to 0.1 mm. Size selection uses the wider repeat so the suggested tip is not narrower than either agreeing observation. `platform-default@1` is currently a provisional 10-tip chart: size 0 is 18 mm, size 1 is 17 mm, through size 9 at 9 mm. The mapping chooses the narrowest listed tip that is not narrower than `sizing_width_mm`. Readings outside 9–18 mm receive no default size. If average-based and conservative mappings cross a chart boundary, the UI keeps the conservative size as the single best-fit result and shows a generic physical-confirmation warning instead of a competing size.

## Interpretation and validation status

This is a nearby scale estimate, not a full planar homography. The oval and centre-spread checks reject obvious tilt but do not correct arbitrary perspective. Coin tolerance, lens distortion, camera angle, distance between coin and nail, nail height, and human marker placement remain error sources.

The result is a **projected planar width**. A top-down photo cannot measure the curved surface length of a strongly arched nail, and the provisional chart has not been certified against a physical tip set. The application therefore must not promise measurement accuracy or press-on fit. Users should confirm borderline results with their nail artist or a physical sizing kit.

Geometry unit tests and browser tests validate the implementation contract. They do not establish real-world projected-width accuracy or tip fit. Those claims require a separate physical validation study; no training dataset is required for that study.
