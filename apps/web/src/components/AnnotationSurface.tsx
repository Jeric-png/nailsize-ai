import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";
import {
  COIN_MARKER_LABELS,
  type CoinMarkers,
  type ImageDimensions,
  type Point,
} from "../guidedSizing";

type DragTarget = { kind: "coin" | "edge"; index: number } | null;

interface AnnotationSurfaceProps {
  previewUrl: string;
  imageDimensions: ImageDimensions;
  mode: "calibration" | "nail";
  coinMarkers: CoinMarkers;
  onCoinMarkersChange: (markers: CoinMarkers) => void;
  onCoinInteraction?: (index: number) => void;
  activeCoinMarkerIndex?: number;
  edgePoints?: Point[];
  onEdgePointsChange?: (points: Point[]) => void;
  digitLabel?: string;
}

export const AnnotationSurface = forwardRef<
  HTMLDivElement,
  AnnotationSurfaceProps
>(function AnnotationSurface(
  {
    previewUrl,
    imageDimensions,
    mode,
    coinMarkers,
    onCoinMarkersChange,
    onCoinInteraction,
    activeCoinMarkerIndex,
    edgePoints = [],
    onEdgePointsChange,
    digitLabel = "nail",
  },
  forwardedRef,
) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<DragTarget>(null);
  useImperativeHandle(
    forwardedRef,
    () => overlayRef.current as HTMLDivElement,
    [],
  );

  function pointFromPointer(event: PointerEvent): Point {
    const bounds = overlayRef.current!.getBoundingClientRect();
    return {
      x: clamp((event.clientX - bounds.left) / bounds.width),
      y: clamp((event.clientY - bounds.top) / bounds.height),
    };
  }

  function updatePoint(target: Exclude<DragTarget, null>, point: Point) {
    if (target.kind === "coin") {
      const current = coinMarkers[target.index];
      if (current.x === point.x && current.y === point.y) return;
      const updated = [...coinMarkers] as CoinMarkers;
      updated[target.index] = point;
      onCoinMarkersChange(updated);
      onCoinInteraction?.(target.index);
      return;
    }
    const updated = [...edgePoints];
    updated[target.index] = point;
    onEdgePointsChange?.(updated);
  }

  function startDrag(
    event: PointerEvent<HTMLButtonElement>,
    target: Exclude<DragTarget, null>,
  ) {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(target);
  }

  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    if (!dragging) return;
    event.preventDefault();
    updatePoint(dragging, pointFromPointer(event));
  }

  function moveWithKeyboard(
    event: KeyboardEvent<HTMLButtonElement>,
    target: Exclude<DragTarget, null>,
    point: Point,
  ) {
    const direction = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    }[event.key];
    if (!direction) return;
    event.preventDefault();
    const pixels = event.shiftKey ? 8 : 1;
    const renderedBounds = overlayRef.current?.getBoundingClientRect();
    const renderedWidth =
      renderedBounds && renderedBounds.width > 0
        ? renderedBounds.width
        : imageDimensions.width;
    const renderedHeight =
      renderedBounds && renderedBounds.height > 0
        ? renderedBounds.height
        : imageDimensions.height;
    updatePoint(target, {
      x: clamp(point.x + (direction[0] * pixels) / renderedWidth),
      y: clamp(point.y + (direction[1] * pixels) / renderedHeight),
    });
  }

  function placePoint(event: PointerEvent<HTMLDivElement>) {
    if (dragging || event.target !== event.currentTarget) return;
    if (mode === "calibration") {
      if (activeCoinMarkerIndex === undefined) return;
      updatePoint(
        { kind: "coin", index: activeCoinMarkerIndex },
        pointFromPointer(event),
      );
      return;
    }
    if (edgePoints.length >= 2) return;
    onEdgePointsChange?.([...edgePoints, pointFromPointer(event)]);
  }

  return (
    <div className="annotation-shell">
      <div className="annotation-image">
        <img
          src={previewUrl}
          alt="Photo being calibrated and measured"
          draggable={false}
        />
        <div
          ref={overlayRef}
          className={`annotation-overlay annotation-overlay--${mode}`}
          onPointerDown={placePoint}
          onPointerMove={moveDrag}
          onPointerUp={() => setDragging(null)}
          onPointerCancel={() => setDragging(null)}
        >
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <polygon
              className="coin-outline"
              points={coinMarkers
                .map((point) => `${point.x * 100},${point.y * 100}`)
                .join(" ")}
            />
            {edgePoints.length === 2 && (
              <line
                className="nail-width-line"
                x1={edgePoints[0].x * 100}
                y1={edgePoints[0].y * 100}
                x2={edgePoints[1].x * 100}
                y2={edgePoints[1].y * 100}
              />
            )}
          </svg>

          {coinMarkers.map((point, index) => (
            <button
              key={COIN_MARKER_LABELS[index]}
              type="button"
              className={`marker-handle marker-handle--coin${mode === "nail" ? " marker-handle--locked" : ""}`}
              style={{ left: `${point.x * 100}%`, top: `${point.y * 100}%` }}
              aria-label={`${COIN_MARKER_LABELS[index]} coin rim marker, ${Math.round(point.x * 100)} percent across and ${Math.round(point.y * 100)} percent down`}
              disabled={mode !== "calibration"}
              onPointerDown={(event) =>
                startDrag(event, { kind: "coin", index })
              }
              onKeyDown={(event) =>
                moveWithKeyboard(event, { kind: "coin", index }, point)
              }
            >
              <span>{index + 1}</span>
            </button>
          ))}

          {edgePoints.map((point, index) => (
            <button
              key={`${digitLabel}-${index}`}
              type="button"
              className={`marker-handle marker-handle--edge${edgePoints.length === 1 ? " marker-handle--pending" : ""}`}
              style={{ left: `${point.x * 100}%`, top: `${point.y * 100}%` }}
              aria-label={`${index === 0 ? "Left" : "Right"} edge of ${digitLabel}, ${Math.round(point.x * 100)} percent across and ${Math.round(point.y * 100)} percent down`}
              onPointerDown={(event) =>
                startDrag(event, { kind: "edge", index })
              }
              onKeyDown={(event) =>
                moveWithKeyboard(event, { kind: "edge", index }, point)
              }
            >
              <span>{index === 0 ? "L" : "R"}</span>
            </button>
          ))}
        </div>
      </div>

      {mode === "nail" && edgePoints.length < 2 && (
        <div className="marker-fallback" aria-label="Keyboard marker controls">
          <span>
            Tap the photo, or add a marker and move it with the arrow keys.
          </span>
          {edgePoints.length === 0 && (
            <button
              type="button"
              className="text-button"
              onClick={() => onEdgePointsChange?.([{ x: 0.46, y: 0.5 }])}
            >
              Add left marker at centre
            </button>
          )}
          {edgePoints.length === 1 && (
            <button
              type="button"
              className="text-button"
              onClick={() =>
                onEdgePointsChange?.([...edgePoints, { x: 0.54, y: 0.5 }])
              }
            >
              Add right marker at centre
            </button>
          )}
        </div>
      )}
    </div>
  );
});

function clamp(value: number): number {
  return Math.min(1, Math.max(0, value));
}
