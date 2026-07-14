import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type PointerEvent,
} from "react";
import type { Digit } from "../guidedSizing";
import { prepareImage } from "../imagePreparation";
import {
  analyzeAutomaticPhoto,
  completeAutomaticPhotoWithCoin,
} from "../vision/automaticAnalysis";
import type {
  AutomaticAnalysisStage,
  AutomaticCoinCompleter,
  AutomaticHandAnalysis,
  AutomaticPhotoAnalyzer,
  CoinReviewContext,
} from "../vision/automaticAnalysisTypes";
import {
  releaseAutomaticAnalysis,
  releaseAutomaticOutcome,
  releaseCoinReviewContext,
} from "../vision/automaticMemory";
import { recalculateAutomaticMeasurement } from "../vision/automaticSizing";
import { proposeCoinEllipseAtCenter } from "../vision/coinDetector";
import { AutomaticReviewSurface } from "./AutomaticReviewSurface";
import { Button, Card, Eyebrow, StatusMessage } from "./Primitives";

const DIGITS: readonly Digit[] = ["thumb", "index", "middle", "ring", "pinky"];
const SINGLE_NAIL_METHOD_VERSION = "auto-assumed23-single-v0.1.0";
const STAGE_LABEL: Record<AutomaticAnalysisStage, string> = {
  preparing: "Preparing the photo",
  "loading-model": "Loading private on-device detection",
  "finding-nails": "Finding the nail outline",
  "finding-coin": "Finding the round reference",
  calculating: "Calculating projected width",
};

interface CapturedPhoto {
  file: File;
  previewUrl: string;
}

export function SingleNailSizing({
  analyzePhoto = analyzeAutomaticPhoto,
  completeCoin = completeAutomaticPhotoWithCoin,
}: {
  analyzePhoto?: AutomaticPhotoAnalyzer;
  completeCoin?: AutomaticCoinCompleter;
}) {
  const [capture, setCapture] = useState<CapturedPhoto | null>(null);
  const [digit, setDigit] = useState<Digit>("thumb");
  const [referenceConfirmed, setReferenceConfirmed] = useState(false);
  const [phase, setPhase] = useState<
    "capture" | "analyzing" | "reference-review" | "review" | "result"
  >("capture");
  const [stage, setStage] = useState<AutomaticAnalysisStage>("preparing");
  const [analysis, setAnalysis] = useState<AutomaticHandAnalysis | null>(null);
  const [coinReview, setCoinReview] = useState<CoinReviewContext | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const captureRef = useRef(capture);
  const analysisRef = useRef(analysis);
  const coinReviewRef = useRef(coinReview);
  const requestId = useRef(0);
  captureRef.current = capture;
  analysisRef.current = analysis;
  coinReviewRef.current = coinReview;

  useEffect(
    () => () => {
      requestId.current += 1;
      if (captureRef.current) URL.revokeObjectURL(captureRef.current.previewUrl);
      if (analysisRef.current) releaseAutomaticAnalysis(analysisRef.current);
      if (coinReviewRef.current)
        releaseCoinReviewContext(coinReviewRef.current);
    },
    [],
  );

  async function selectPhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const currentRequest = ++requestId.current;
    setPreparing(true);
    setError("");
    try {
      const prepared = await prepareImage(file);
      if (currentRequest !== requestId.current) return;
      const previewUrl = URL.createObjectURL(prepared.file);
      setCapture((current) => {
        if (current) URL.revokeObjectURL(current.previewUrl);
        return { file: prepared.file, previewUrl };
      });
    } catch (cause) {
      if (currentRequest === requestId.current)
        setError(
          cause instanceof Error
            ? cause.message
            : "This photo could not be prepared locally.",
        );
    } finally {
      if (currentRequest === requestId.current) setPreparing(false);
    }
  }

  async function analyze() {
    if (!capture) return;
    const currentRequest = ++requestId.current;
    if (analysis) releaseAutomaticAnalysis(analysis);
    if (coinReview) releaseCoinReviewContext(coinReview);
    setAnalysis(null);
    setCoinReview(null);
    setPhase("analyzing");
    setError("");
    const outcome = await analyzePhoto(
      "right",
      capture.file,
      (nextStage) => {
        if (currentRequest === requestId.current) setStage(nextStage);
      },
      digit,
    );
    if (currentRequest !== requestId.current) {
      releaseAutomaticOutcome(outcome);
      return;
    }
    if (outcome.status === "coin-review") {
      setCoinReview(outcome.context);
      setError("");
      setPhase("reference-review");
      return;
    }
    if (outcome.status === "rejected") {
      setError(outcome.message);
      setPhase("capture");
      return;
    }
    setAnalysis(outcome.analysis);
    setPhase("review");
  }

  function reset() {
    requestId.current += 1;
    if (capture) URL.revokeObjectURL(capture.previewUrl);
    if (analysis) releaseAutomaticAnalysis(analysis);
    if (coinReview) releaseCoinReviewContext(coinReview);
    setCapture(null);
    setAnalysis(null);
    setCoinReview(null);
    setReferenceConfirmed(false);
    setPhase("capture");
    setError("");
    setCopyStatus("");
  }

  if (phase === "capture")
    return (
      <div className="page instant-capture-page">
        <Eyebrow>One-photo automatic beta</Eyebrow>
        <h1>Upload one nail photo. Get one best-fit suggestion.</h1>
        <p className="lede">
          Include one complete bare nail and one round reference in the same
          top-down photo. The beta treats the reference as exactly 23.00 mm.
        </p>
        <Card className="instant-instructions">
          <h2>Before you upload</h2>
          <ul className="check-list">
            <li>Keep the nail and complete round rim visible</li>
            <li>Place both flat on the same surface</li>
            <li>Hold the phone directly overhead in bright, even light</li>
          </ul>
          <label className="coin-confirmation">
            <input
              type="checkbox"
              checked={referenceConfirmed}
              onChange={(event) =>
                setReferenceConfirmed(event.currentTarget.checked)
              }
            />
            <span>
              For this beta, assume the round reference is exactly 23.00 mm
              across.
            </span>
          </label>
        </Card>
        {error && <StatusMessage tone="error">{error}</StatusMessage>}
        <label className="field-label" htmlFor="single-nail-digit">
          Which nail is shown?
        </label>
        <select
          id="single-nail-digit"
          value={digit}
          onChange={(event) => setDigit(event.currentTarget.value as Digit)}
        >
          {DIGITS.map((value) => (
            <option value={value} key={value}>
              {value[0].toUpperCase() + value.slice(1)}
            </option>
          ))}
        </select>
        <label className="photo-upload-card single-photo-upload">
          {capture ? (
            <img src={capture.previewUrl} alt="Selected nail preview" />
          ) : (
            <span className="photo-upload-placeholder">+</span>
          )}
          <strong>
            {preparing
              ? "Preparing locally…"
              : capture
                ? "Replace photo"
                : "Take or choose photo"}
          </strong>
          <input
            className="visually-hidden"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            disabled={preparing}
            onChange={(event) => void selectPhoto(event)}
          />
        </label>
        <Button
          disabled={!capture || !referenceConfirmed || preparing}
          onClick={() => void analyze()}
        >
          Find my nail size
        </Button>
        <p className="fine-print">
          Experimental result only. The assumed reference and projected width
          are not a guarantee of physical fit.
        </p>
      </div>
    );

  if (phase === "analyzing")
    return (
      <div className="page processing-page">
        <Eyebrow>Private on-device analysis</Eyebrow>
        <h1>Finding your nail size.</h1>
        <p className="lede">{STAGE_LABEL[stage]}. Your photo is not uploaded.</p>
      </div>
    );

  if (phase === "reference-review" && coinReview && capture) {
    const reviewContext = coinReview;
    function selectReference(event: PointerEvent<HTMLButtonElement>) {
      const bounds = event.currentTarget.getBoundingClientRect();
      const center = {
        x:
          ((event.clientX - bounds.left) / bounds.width) *
          reviewContext.image.width,
        y:
          ((event.clientY - bounds.top) / bounds.height) *
          reviewContext.image.height,
      };
      const proposal = proposeCoinEllipseAtCenter(reviewContext.image, center);
      if (!proposal) {
        setError(
          "No complete round rim was found at that point. Tap the centre of the reference or retake the photo.",
        );
        return;
      }
      const outcome = completeCoin(reviewContext, proposal);
      if (outcome.status === "accepted") {
        setCoinReview(null);
        setAnalysis(outcome.analysis);
        setError("");
        setPhase("review");
        return;
      }
      if (outcome.status === "coin-review") {
        setCoinReview(outcome.context);
        setError(outcome.context.message);
        return;
      }
      setError(outcome.message);
    }

    return (
      <div className="page coin-review-page">
        <Eyebrow>One quick correction</Eyebrow>
        <h1>Tap the round reference once.</h1>
        <p className="lede">
          Another circular object distracted the automatic detector. Tap the
          centre of the intended 23.00 mm reference; the app will fit its rim.
        </p>
        <StatusMessage>{coinReview.message}</StatusMessage>
        {error && <StatusMessage tone="error">{error}</StatusMessage>}
        <button
          type="button"
          className="single-reference-tap"
          aria-label="Tap the centre of the round reference"
          onPointerDown={selectReference}
        >
          <img src={capture.previewUrl} alt="Select the round reference" />
        </button>
        <div className="action-stack">
          <Button className="button--secondary" onClick={reset}>
            Choose another photo
          </Button>
        </div>
      </div>
    );
  }

  if (!analysis || !capture) return null;
  const measurement = analysis.measurements[0];
  const unresolved = measurement.needsReview;
  const resultLabel = measurement.recommendedSize
    ? `Best-fit size ${measurement.recommendedSize}`
    : "Outside the provisional chart";

  async function copy() {
    try {
      await navigator.clipboard.writeText(
        `${digit}: ${measurement.projectedWidthMm.toFixed(1)} ± ${measurement.uncertaintyMm.toFixed(1)} mm — ${resultLabel}. Assumed 23.00 mm reference; method ${SINGLE_NAIL_METHOD_VERSION}; experimental projected-width beta.`,
      );
      setCopyStatus("Result copied without the photo.");
    } catch {
      setCopyStatus("Copy is unavailable in this browser.");
    }
  }

  return (
    <div className="page automatic-review-page">
      <Eyebrow>{phase === "result" ? "Sizing result" : "Quick review"}</Eyebrow>
      <h1>{resultLabel}</h1>
      <p className="lede">
        {measurement.projectedWidthMm.toFixed(1)} ±{" "}
        {measurement.uncertaintyMm.toFixed(1)} mm projected width. Check that
        the line reaches the visible sidewalls at the nail’s widest point.
      </p>
      {measurement.requiresPhysicalConfirmation && (
        <StatusMessage>
          This measurement is near a chart boundary. Confirm it physically
          before making the set.
        </StatusMessage>
      )}
      {unresolved && (
        <StatusMessage tone="error">
          The proposed outline needs review. Drag A/B to the visible nail
          sidewalls before accepting the result.
        </StatusMessage>
      )}
      <AutomaticReviewSurface
        previewUrl={capture.previewUrl}
        image={analysis.image}
        calibration={analysis.calibration}
        detections={analysis.detections}
        measurements={analysis.measurements}
        activeDigit={digit}
        onSelectDigit={() => undefined}
        onWidthLineChange={(_, widthLine) => {
          setAnalysis((current) =>
            current
              ? {
                  ...current,
                  measurements: [
                    recalculateAutomaticMeasurement(
                      current.measurements[0],
                      widthLine,
                      current.calibration,
                    ),
                  ],
                }
              : current,
          );
        }}
      />
      <StatusMessage>
        Assumed reference: 23.00 mm. This beta has not passed representative
        physical-fit validation and does not measure strong nail curvature.
        Method: {SINGLE_NAIL_METHOD_VERSION}.
      </StatusMessage>
      <div className="action-stack">
        {phase === "review" ? (
          <Button disabled={unresolved} onClick={() => setPhase("result")}>
            Accept this result
          </Button>
        ) : (
          <Button onClick={() => void copy()}>Copy text-only result</Button>
        )}
        <Button className="button--secondary" onClick={reset}>
          Start over and erase photo
        </Button>
      </div>
      <p className="share-status" aria-live="polite">
        {copyStatus}
      </p>
    </div>
  );
}
