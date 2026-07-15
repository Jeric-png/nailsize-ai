import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { captureCopy } from "../captureConfig";
import {
  COIN_MARKER_LABELS,
  REPEAT_TOLERANCE_MM,
  captureDigits,
  captureOrder,
  compareSamples,
  createInitialCoinMarkers,
  formatRepeatDeltaMm,
  isCaptureConsistent,
  measureSample,
  validateCoinCalibration,
  validateRenderedCoinSize,
  type CaptureType,
  type CoinMarkers,
  type Digit,
  type EdgePair,
  type Point,
  type SampleMeasurement,
} from "../guidedSizing";
import {
  COMMON_IMAGE_FORMATS,
  fingerprintImage,
  IMAGE_FILE_ACCEPT,
  prepareImage,
} from "../imagePreparation";
import type { SampleNumber, SessionAction, SessionState } from "../session";
import { AnnotationSurface } from "./AnnotationSurface";
import {
  Button,
  Card,
  Eyebrow,
  ProgressStepper,
  StatusMessage,
} from "./Primitives";

interface SessionProps {
  state: SessionState;
  dispatch: React.Dispatch<SessionAction>;
}

const MAX_LOCAL_BYTES = 12 * 1024 * 1024;

export function CaptureRoute(props: SessionProps) {
  const params = useParams();
  const captureType = resolveCaptureType(params.captureType);
  const sample = resolveSample(params.sample);
  return (
    <CapturePage
      key={`${captureType}-${sample}`}
      {...props}
      captureType={captureType}
      sample={sample}
    />
  );
}

function CapturePage({
  state,
  dispatch,
  captureType,
  sample,
}: SessionProps & { captureType: CaptureType; sample: SampleNumber }) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const preparationId = useRef(0);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState("");
  const capture = state.captures[captureType];
  const record = capture?.samples[sample];
  const first = capture?.samples[1];
  const config = captureCopy[captureType];
  const captureStep = captureOrder.indexOf(captureType) + 1;

  useEffect(
    () => () => {
      preparationId.current += 1;
    },
    [],
  );

  if (!state.coinConfirmed) return <Navigate to="/prepare" replace />;

  if (sample === 2 && !first?.measurements) {
    return (
      <Navigate
        to={first ? `/guide/${captureType}/1` : `/capture/${captureType}/1`}
        replace
      />
    );
  }

  async function selectFile(file: File) {
    if (file.size > MAX_LOCAL_BYTES) {
      setError("Choose a photo smaller than 12 MB.");
      return;
    }
    const requestId = ++preparationId.current;
    setPreparing(true);
    setError("");
    try {
      const prepared = await prepareImage(file);
      if (requestId !== preparationId.current) return;
      const fingerprint = await fingerprintImage(prepared.file);
      if (requestId !== preparationId.current) return;
      if (sample === 2 && fingerprint === first?.fingerprint) {
        setError(
          "This is the same image used for measurement 1. Move your hand and phone, then take or choose a new photo.",
        );
        return;
      }
      dispatch({
        type: "selectPhoto",
        captureType,
        sample,
        previewUrl: URL.createObjectURL(prepared.file),
        fingerprint,
        dimensions: { width: prepared.width, height: prepared.height },
      });
    } catch (preparationError) {
      if (requestId === preparationId.current)
        setError(
          preparationError instanceof Error
            ? preparationError.message
            : "This photo could not be prepared locally. Choose another image.",
        );
    } finally {
      if (requestId === preparationId.current) setPreparing(false);
    }
  }

  return (
    <div className="page capture-page">
      <ProgressStepper current={captureStep} />
      <Eyebrow>
        Capture {captureStep} of 4 · measurement {sample} of 2
      </Eyebrow>
      <h1>{config.title}</h1>
      <p className="lede">
        {sample === 1
          ? config.instruction
          : "Reposition your hand and phone, then take a new photo. The second measurement checks repeatability."}
      </p>

      {sample === 2 && first?.measurements && (
        <StatusMessage tone="success">
          <strong>First measurement complete</strong>
          <br />
          The verification photo must be independently positioned.
        </StatusMessage>
      )}

      <div
        className={
          record ? "capture-frame capture-frame--filled" : "capture-frame"
        }
      >
        {record ? (
          <img
            src={record.previewUrl}
            alt={`Preview of ${config.title.toLowerCase()}, measurement ${sample}`}
            onError={() =>
              setError(
                `This browser could not display the selected photo. Choose ${COMMON_IMAGE_FORMATS}.`,
              )
            }
          />
        ) : (
          <div>
            <strong>{config.nails}</strong>
            <span>
              Keep the complete 50-cent coin and every target nail inside the
              photo.
            </span>
          </div>
        )}
      </div>

      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        tabIndex={-1}
        aria-label={`Choose measurement ${sample} photo for ${config.title.toLowerCase()}`}
        accept={IMAGE_FILE_ACCEPT}
        capture="environment"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void selectFile(file);
          event.target.value = "";
        }}
      />

      {preparing && (
        <StatusMessage>
          Preparing the photo locally in your browser…
        </StatusMessage>
      )}
      {error && <StatusMessage tone="error">{error}</StatusMessage>}

      <Card className="capture-requirements">
        <h2>Before taking this photo</h2>
        <ul className="check-list">
          <li>Use only the confirmed Third Series 50-cent coin</li>
          <li>Place the coin flat beside the nails on the same surface</li>
          <li>Hold the phone directly overhead so the coin appears round</li>
          <li>
            Move close enough for the coin to fill about one-third of the
            photo&rsquo;s shorter side, while keeping every target nail visible
          </li>
          <li>Keep the full coin rim visible and sharply focused</li>
          <li>Use a new hand and phone position for measurement 2</li>
        </ul>
      </Card>

      <div className="action-stack">
        <Button
          onClick={() => inputRef.current?.click()}
          className={record ? "button--secondary" : ""}
          disabled={preparing}
        >
          {preparing
            ? "Preparing photo…"
            : record
              ? "Choose another photo"
              : "Take or choose photo"}
        </Button>
        <Button
          onClick={() => navigate(`/guide/${captureType}/${sample}`)}
          disabled={!record || preparing || Boolean(error)}
        >
          Mark coin rim
        </Button>
      </div>
      <p className="fine-print">
        The photo stays on this device. Nothing is uploaded to a sizing service.
      </p>
    </div>
  );
}

export function GuideRoute(props: SessionProps) {
  const params = useParams();
  const captureType = resolveCaptureType(params.captureType);
  const sample = resolveSample(params.sample);
  return (
    <GuidePage
      key={`${captureType}-${sample}`}
      {...props}
      captureType={captureType}
      sample={sample}
    />
  );
}

type GuidePhase = "calibration" | "marking" | "first-review" | "repeat-review";

function GuidePage({
  state,
  dispatch,
  captureType,
  sample,
}: SessionProps & { captureType: CaptureType; sample: SampleNumber }) {
  const navigate = useNavigate();
  const capture = state.captures[captureType];
  const record = capture?.samples[sample];
  const digits = captureDigits[captureType];
  const existingMarks = useMemo(
    () =>
      Object.fromEntries(
        (record?.measurements ?? []).map((measurement) => [
          measurement.digit,
          [...measurement.edges],
        ]),
      ) as Partial<Record<Digit, Point[]>>,
    [record?.measurements],
  );
  const fallbackDimensions = record?.dimensions ?? { width: 600, height: 800 };
  const [coinMarkers, setCoinMarkers] = useState<CoinMarkers>(
    cloneCoinMarkers(
      record?.coinMarkers ?? createInitialCoinMarkers(fallbackDimensions),
    ),
  );
  const [placedCoinMarkers, setPlacedCoinMarkers] = useState<Set<number>>(
    () =>
      new Set(
        record?.coinMarkers
          ? Array.from(
              { length: COIN_MARKER_LABELS.length },
              (_, index) => index,
            )
          : [],
      ),
  );
  const [edgeMarks, setEdgeMarks] = useState(existingMarks);
  const [digitIndex, setDigitIndex] = useState(0);
  const [measurements, setMeasurements] = useState<
    SampleMeasurement[] | undefined
  >(record?.measurements);
  const [phase, setPhase] = useState<GuidePhase>(
    record?.measurements
      ? sample === 1
        ? "first-review"
        : "repeat-review"
      : record?.coinMarkers
        ? "marking"
        : "calibration",
  );
  const [error, setError] = useState("");
  const annotationRef = useRef<HTMLDivElement>(null);
  const nextCoinMarkerIndex = COIN_MARKER_LABELS.findIndex(
    (_, index) => !placedCoinMarkers.has(index),
  );
  const guideHeadingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    guideHeadingRef.current?.focus();
  }, [phase, digitIndex]);

  if (!state.coinConfirmed) return <Navigate to="/prepare" replace />;

  if (!record) {
    if (capture?.result) {
      const next = captureOrder[captureOrder.indexOf(captureType) + 1];
      return <Navigate to={next ? `/capture/${next}/1` : "/results"} replace />;
    }
    return <Navigate to={`/capture/${captureType}/${sample}`} replace />;
  }
  const imageDimensions = record.dimensions;
  if (sample === 2 && !capture?.samples[1]?.measurements)
    return <Navigate to={`/capture/${captureType}/1`} replace />;

  const currentDigit = digits[digitIndex];
  const currentPoints = edgeMarks[currentDigit] ?? [];
  const firstMeasurements = capture?.samples[1]?.measurements;
  const repeatResult =
    phase === "repeat-review" && firstMeasurements && measurements
      ? compareSamples(captureType, firstMeasurements, measurements)
      : undefined;

  function confirmCalibration() {
    if (placedCoinMarkers.size !== COIN_MARKER_LABELS.length) {
      const missing = COIN_MARKER_LABELS.filter(
        (_, index) => !placedCoinMarkers.has(index),
      ).join(", ");
      setError(
        `Place every coin-rim marker before continuing. Missing: ${missing}.`,
      );
      return;
    }
    const issue = validateCoinCalibration(coinMarkers, imageDimensions);
    if (issue) {
      setError(issue);
      return;
    }
    const bounds = annotationRef.current?.getBoundingClientRect();
    const renderedIssue = validateRenderedCoinSize(
      coinMarkers,
      bounds
        ? { width: bounds.width, height: bounds.height }
        : { width: 0, height: 0 },
    );
    if (renderedIssue) {
      setError(renderedIssue);
      return;
    }
    setError("");
    dispatch({
      type: "saveCalibration",
      captureType,
      sample,
      coinMarkers,
    });
    setPhase("marking");
  }

  function saveCurrentNail() {
    if (currentPoints.length !== 2) {
      setError(`Mark the left and right sidewall of the ${currentDigit} nail.`);
      return;
    }
    const completedMarks = { ...edgeMarks, [currentDigit]: currentPoints };
    setEdgeMarks(completedMarks);
    if (digitIndex < digits.length - 1) {
      setDigitIndex(digitIndex + 1);
      setError("");
      return;
    }

    try {
      const pairs = Object.fromEntries(
        digits.map((digit) => {
          const points = completedMarks[digit];
          if (!points || points.length !== 2)
            throw new RangeError(`Mark both edges of the ${digit} nail.`);
          return [digit, points as EdgePair];
        }),
      ) as Partial<Record<Digit, EdgePair>>;
      const measured = measureSample(
        imageDimensions,
        coinMarkers,
        pairs,
        digits,
      );
      dispatch({
        type: "completeSample",
        captureType,
        sample,
        coinMarkers,
        measurements: measured,
      });
      setMeasurements(measured);
      setError("");
      setPhase(sample === 1 ? "first-review" : "repeat-review");
    } catch (measurementError) {
      setError(
        measurementError instanceof Error
          ? measurementError.message
          : "These markers could not be measured.",
      );
    }
  }

  function acceptResult() {
    if (!repeatResult || !isCaptureConsistent(repeatResult)) return;
    const returningToResults = state.correctionCapture === captureType;
    dispatch({ type: "accept", captureType });
    if (returningToResults) {
      dispatch({ type: "finishCorrection" });
      navigate("/results");
      return;
    }
    const next = captureOrder[captureOrder.indexOf(captureType) + 1];
    navigate(next ? `/capture/${next}/1` : "/results");
  }

  if (phase === "first-review" && measurements) {
    return (
      <MeasurementReview
        eyebrow="First measurement complete"
        title="Now verify it with a new photo."
        measurements={measurements}
        description="Move both your hand and phone before taking measurement 2. Repeating the same marker placement on the same photo would not test capture consistency."
        actionLabel="Take verification photo"
        onAction={() => navigate(`/capture/${captureType}/2`)}
        onRestart={() => {
          dispatch({ type: "clearSample", captureType, sample: 1 });
          navigate(`/capture/${captureType}/1`);
        }}
      />
    );
  }

  if (phase === "repeat-review" && repeatResult) {
    const consistent = isCaptureConsistent(repeatResult);
    return (
      <div className="page repeat-review-page">
        <Eyebrow>Two-photo agreement</Eyebrow>
        <h1 ref={guideHeadingRef} tabIndex={-1}>
          {consistent
            ? "The measurements agree."
            : "One or more nails need another check."}
        </h1>
        <p className="lede">
          Each nail must differ by no more than {REPEAT_TOLERANCE_MM.toFixed(1)}{" "}
          mm between independently positioned photos.
        </p>
        <div
          className="repeat-table"
          role="table"
          aria-label="Repeat measurement comparison"
        >
          <div className="repeat-table__header" role="row">
            <span role="columnheader">Nail</span>
            <span role="columnheader">First</span>
            <span role="columnheader">Verify</span>
            <span role="columnheader">Difference</span>
          </div>
          {repeatResult.measurements.map((measurement) => (
            <div
              className={
                measurement.consistent
                  ? "repeat-table__row"
                  : "repeat-table__row repeat-table__row--error"
              }
              role="row"
              key={measurement.digit}
            >
              <span className="repeat-table__cell" role="cell">
                <span className="repeat-table__mobile-label" aria-hidden="true">
                  Nail
                </span>
                <strong>{measurement.digit}</strong>
              </span>
              <span className="repeat-table__cell" role="cell">
                <span className="repeat-table__mobile-label" aria-hidden="true">
                  First measurement
                </span>
                {measurement.firstWidthMm.toFixed(1)} mm
              </span>
              <span className="repeat-table__cell" role="cell">
                <span className="repeat-table__mobile-label" aria-hidden="true">
                  Verification
                </span>
                {measurement.verificationWidthMm.toFixed(1)} mm
              </span>
              <span className="repeat-table__cell" role="cell">
                <span className="repeat-table__mobile-label" aria-hidden="true">
                  Difference
                </span>
                {formatRepeatDeltaMm(
                  measurement.repeatDeltaMm,
                  measurement.consistent,
                )}{" "}
                mm · {measurement.consistent ? "agrees" : "retry"}
              </span>
            </div>
          ))}
        </div>

        <StatusMessage tone={consistent ? "success" : "error"}>
          <strong>
            {consistent
              ? "Consistency check passed"
              : "Consistency check failed"}
          </strong>
          <br />
          {consistent
            ? "The wider of the two readings will be used for the press-on size recommendation."
            : "Retake the verification photo and mark the named nail edges again."}
        </StatusMessage>

        <div className="action-stack">
          {consistent && (
            <Button onClick={acceptResult}>Accept and continue</Button>
          )}
          <Button
            className={consistent ? "button--secondary" : ""}
            onClick={() => {
              dispatch({ type: "clearSample", captureType, sample: 2 });
              navigate(`/capture/${captureType}/2`);
            }}
          >
            Retake verification photo
          </Button>
          {!consistent && (
            <Button
              className="button--secondary"
              onClick={() => {
                dispatch({ type: "clearSample", captureType, sample: 1 });
                navigate(`/capture/${captureType}/1`);
              }}
            >
              Restart both measurements
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="page guide-page">
      <Eyebrow>
        {captureCopy[captureType].title} · measurement {sample} of 2
      </Eyebrow>
      <h1 ref={guideHeadingRef} tabIndex={-1}>
        {phase === "calibration"
          ? "Trace the 50-cent coin rim."
          : `Mark the ${currentDigit} nail.`}
      </h1>
      <p className="lede" aria-live="polite">
        {phase === "calibration"
          ? "Tap the coin rim at points 1–8 in order, then drag any marker that needs adjustment. The app rejects a small or oval-looking calibration."
          : `Tap the left and right sidewall at the widest visible point. Nail ${digitIndex + 1} of ${digits.length}.`}
      </p>

      {phase === "calibration" && (
        <ol className="marker-order" aria-label="Required coin rim order">
          {COIN_MARKER_LABELS.map((label, index) => (
            <li key={label}>
              <span>{index + 1}</span> {label}
            </li>
          ))}
        </ol>
      )}

      <AnnotationSurface
        ref={annotationRef}
        previewUrl={record.previewUrl}
        imageDimensions={imageDimensions}
        mode={phase === "calibration" ? "calibration" : "nail"}
        coinMarkers={coinMarkers}
        onCoinMarkersChange={setCoinMarkers}
        onCoinInteraction={(index) =>
          setPlacedCoinMarkers((current) => new Set(current).add(index))
        }
        activeCoinMarkerIndex={
          phase === "calibration" && nextCoinMarkerIndex >= 0
            ? nextCoinMarkerIndex
            : undefined
        }
        edgePoints={phase === "marking" ? currentPoints : []}
        onEdgePointsChange={(points) =>
          setEdgeMarks({ ...edgeMarks, [currentDigit]: points })
        }
        digitLabel={currentDigit}
      />

      {error && <StatusMessage tone="error">{error}</StatusMessage>}

      {phase === "calibration" && (
        <p className="fine-print" role="status">
          Coin-rim placement: {placedCoinMarkers.size} of{" "}
          {COIN_MARKER_LABELS.length}
          {placedCoinMarkers.size === COIN_MARKER_LABELS.length
            ? " complete."
            : " — move each numbered marker onto the visible rim."}
        </p>
      )}

      <div className="action-stack">
        {phase === "calibration" ? (
          <>
            <Button onClick={confirmCalibration}>Confirm coin rim</Button>
            <Button
              className="button--secondary"
              onClick={() => {
                setCoinMarkers(
                  cloneCoinMarkers(createInitialCoinMarkers(imageDimensions)),
                );
                setPlacedCoinMarkers(new Set());
                setError("");
              }}
            >
              Reset coin markers
            </Button>
          </>
        ) : (
          <>
            <Button
              onClick={saveCurrentNail}
              disabled={currentPoints.length !== 2}
            >
              {digitIndex === digits.length - 1
                ? "Calculate this measurement"
                : `Save ${currentDigit} and continue`}
            </Button>
            {currentPoints.length > 0 && (
              <Button
                className="button--secondary"
                onClick={() =>
                  setEdgeMarks({ ...edgeMarks, [currentDigit]: [] })
                }
              >
                Clear {currentDigit} markers
              </Button>
            )}
            {digitIndex > 0 && (
              <Button
                className="button--secondary"
                onClick={() => {
                  setDigitIndex(digitIndex - 1);
                  setError("");
                }}
              >
                Previous nail
              </Button>
            )}
            <Button
              className="button--secondary"
              onClick={() => {
                setPhase("calibration");
                setError("");
              }}
            >
              Adjust coin rim
            </Button>
          </>
        )}
      </div>
      <p className="fine-print">
        Arrow keys move a focused marker precisely; hold Shift for a larger
        step.
      </p>
    </div>
  );
}

function MeasurementReview({
  eyebrow,
  title,
  measurements,
  description,
  actionLabel,
  onAction,
  onRestart,
}: {
  eyebrow: string;
  title: string;
  measurements: SampleMeasurement[];
  description: string;
  actionLabel: string;
  onAction: () => void;
  onRestart: () => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <div className="page measurement-review-page">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h1 ref={headingRef} tabIndex={-1}>
        {title}
      </h1>
      <p className="lede">{description}</p>
      <Card>
        <h2>First-photo readings</h2>
        <dl className="measurement-list">
          {measurements.map((measurement) => (
            <div key={measurement.digit}>
              <dt>{measurement.digit}</dt>
              <dd>{measurement.widthMm.toFixed(1)} mm</dd>
            </div>
          ))}
        </dl>
      </Card>
      <StatusMessage>
        These readings are provisional until the independent verification photo
        agrees.
      </StatusMessage>
      <div className="action-stack">
        <Button onClick={onAction}>{actionLabel}</Button>
        <Button className="button--secondary" onClick={onRestart}>
          Retake first photo
        </Button>
      </div>
    </div>
  );
}

function resolveCaptureType(value: string | undefined): CaptureType {
  return captureOrder.includes(value as CaptureType)
    ? (value as CaptureType)
    : "left_fingers";
}

function resolveSample(value: string | undefined): SampleNumber {
  return value === "2" ? 2 : 1;
}

function cloneCoinMarkers(markers: CoinMarkers): CoinMarkers {
  return markers.map((point) => ({ ...point })) as CoinMarkers;
}
