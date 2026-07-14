import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";
import type { Digit } from "../guidedSizing";
import type {
  AutomaticNailMeasurement,
  NailWidthLine,
} from "../vision/automaticSizing";
import type {
  CoinEllipseCalibration,
  ImageSize,
  PixelPoint,
} from "../vision/coinCalibration";
import type { YoloV8SegDetection } from "../vision/yoloV8SegPostprocess";

interface AutomaticReviewSurfaceProps {
  previewUrl: string;
  image: ImageSize;
  calibration: CoinEllipseCalibration;
  detections: readonly YoloV8SegDetection[];
  measurements: readonly AutomaticNailMeasurement[];
  activeDigit: Digit | null;
  onSelectDigit: (digit: Digit) => void;
  onWidthLineChange: (digit: Digit, line: NailWidthLine) => void;
}

export function AutomaticReviewSurface({
  previewUrl,
  image,
  calibration,
  detections,
  measurements,
  activeDigit,
  onSelectDigit,
  onWidthLineChange,
}: AutomaticReviewSurfaceProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const maskCanvasRef = useRef<HTMLCanvasElement>(null);
  const [dragging, setDragging] = useState<0 | 1 | null>(null);
  const active = measurements.find(({ digit }) => digit === activeDigit);

  useEffect(() => {
    const canvas = maskCanvasRef.current;
    if (!canvas) return;
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext("2d");
    if (!context) return;
    const pixels = context.createImageData(image.width, image.height);
    for (const measurement of measurements) {
      const detection = detections[measurement.detectionIndex];
      if (!detection) continue;
      const { mask } = detection;
      for (let localY = 0; localY < mask.height; localY += 1) {
        const sourceY = mask.y + localY;
        if (sourceY < 0 || sourceY >= image.height) continue;
        for (let localX = 0; localX < mask.width; localX += 1) {
          if (mask.binary[localY * mask.width + localX] === 0) continue;
          const sourceX = mask.x + localX;
          if (sourceX < 0 || sourceX >= image.width) continue;
          const offset = (sourceY * image.width + sourceX) * 4;
          pixels.data[offset] = measurement.needsReview ? 160 : 21;
          pixels.data[offset + 1] = measurement.needsReview ? 78 : 111;
          pixels.data[offset + 2] = measurement.needsReview ? 26 : 75;
          pixels.data[offset + 3] = 74;
        }
      }
    }
    context.putImageData(pixels, 0, 0);
  }, [detections, image.height, image.width, measurements]);

  function pointFromPointer(event: PointerEvent): PixelPoint {
    const bounds = overlayRef.current!.getBoundingClientRect();
    return {
      x: clamp(
        ((event.clientX - bounds.left) / bounds.width) * image.width,
        0,
        image.width,
      ),
      y: clamp(
        ((event.clientY - bounds.top) / bounds.height) * image.height,
        0,
        image.height,
      ),
    };
  }

  function updateActive(index: 0 | 1, point: PixelPoint) {
    if (!active) return;
    onWidthLineChange(active.digit, {
      start: index === 0 ? point : active.widthLine.start,
      end: index === 1 ? point : active.widthLine.end,
    });
  }

  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    if (dragging === null) return;
    event.preventDefault();
    updateActive(dragging, pointFromPointer(event));
  }

  function moveWithKeyboard(
    event: KeyboardEvent<HTMLButtonElement>,
    index: 0 | 1,
    point: PixelPoint,
  ) {
    const direction = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    }[event.key];
    if (!direction) return;
    event.preventDefault();
    const renderedPixels = event.shiftKey ? 8 : 1;
    const bounds = overlayRef.current?.getBoundingClientRect();
    const sourcePixelsX =
      bounds && bounds.width > 0
        ? (image.width / bounds.width) * renderedPixels
        : renderedPixels;
    const sourcePixelsY =
      bounds && bounds.height > 0
        ? (image.height / bounds.height) * renderedPixels
        : renderedPixels;
    updateActive(index, {
      x: clamp(point.x + direction[0] * sourcePixelsX, 0, image.width),
      y: clamp(point.y + direction[1] * sourcePixelsY, 0, image.height),
    });
  }

  return (
    <div className="annotation-shell automatic-review-surface">
      <div className="annotation-image">
        <img
          src={previewUrl}
          alt="Nail and coin detection review"
          draggable={false}
        />
        <canvas
          ref={maskCanvasRef}
          className="automatic-mask-overlay"
          aria-hidden="true"
        />
        <div
          ref={overlayRef}
          className="annotation-overlay annotation-overlay--nail"
          onPointerMove={moveDrag}
          onPointerUp={() => setDragging(null)}
          onPointerCancel={() => setDragging(null)}
        >
          <svg
            viewBox={`0 0 ${image.width} ${image.height}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <ellipse
              className="automatic-coin-outline"
              cx={calibration.center.x}
              cy={calibration.center.y}
              rx={calibration.majorRadiusPx}
              ry={calibration.minorRadiusPx}
              transform={`rotate(${(calibration.rotationRadians * 180) / Math.PI} ${calibration.center.x} ${calibration.center.y})`}
            />
            {measurements.map((measurement) => (
              <line
                key={measurement.digit}
                className={`automatic-width-line${measurement.needsReview ? " automatic-width-line--review" : ""}${activeDigit === measurement.digit ? " automatic-width-line--active" : ""}`}
                x1={measurement.widthLine.start.x}
                y1={measurement.widthLine.start.y}
                x2={measurement.widthLine.end.x}
                y2={measurement.widthLine.end.y}
              />
            ))}
          </svg>

          {active &&
            ([active.widthLine.start, active.widthLine.end] as const).map(
              (point, index) => (
                <button
                  key={`${active.digit}-${index}`}
                  type="button"
                  className="marker-handle marker-handle--edge"
                  style={{
                    left: `${(point.x / image.width) * 100}%`,
                    top: `${(point.y / image.height) * 100}%`,
                  }}
                  aria-label={`${index === 0 ? "First" : "Second"} sidewall of ${active.digit}`}
                  onPointerDown={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    event.currentTarget.setPointerCapture(event.pointerId);
                    setDragging(index as 0 | 1);
                  }}
                  onKeyDown={(event) =>
                    moveWithKeyboard(event, index as 0 | 1, point)
                  }
                >
                  <span>{index === 0 ? "A" : "B"}</span>
                </button>
              ),
            )}
        </div>
      </div>
      <div className="automatic-review-list" aria-label="Detected nails">
        {measurements.map((measurement) => (
          <button
            key={measurement.digit}
            type="button"
            aria-pressed={activeDigit === measurement.digit}
            className={measurement.needsReview ? "needs-review" : ""}
            onClick={() => onSelectDigit(measurement.digit)}
          >
            <span>{measurement.digit}</span>
            <strong>{measurement.projectedWidthMm.toFixed(1)} mm</strong>
            <small>
              {measurement.needsReview
                ? "Adjust line"
                : measurement.source === "user-corrected"
                  ? "Adjusted"
                  : "Automatic"}
            </small>
          </button>
        ))}
      </div>
      {active && (
        <p className="fine-print">
          Drag A and B to the visible sidewalls at the widest part of the{" "}
          {active.digit} nail. Arrow keys move a selected handle by one
          displayed pixel; Shift moves eight.
        </p>
      )}
    </div>
  );
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}
