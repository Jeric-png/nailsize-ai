import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { recommendClosestSize } from "../guidedSizing";
import { IMAGE_FILE_ACCEPT, prepareImage } from "../imagePreparation";
import { analyzeAutomaticPhoto } from "../vision/automaticAnalysis";
import type {
  AutomaticAnalysisStage,
  AutomaticHandAnalysis,
  AutomaticPhotoAnalyzer,
} from "../vision/automaticAnalysisTypes";
import {
  releaseAutomaticAnalysis,
  releaseAutomaticOutcome,
  releaseCoinReviewContext,
} from "../vision/automaticMemory";
import { AutomaticReviewSurface } from "./AutomaticReviewSurface";
import { Button, Eyebrow, StatusMessage } from "./Primitives";

const STAGE_LABEL: Record<AutomaticAnalysisStage, string> = {
  preparing: "Preparing your photo",
  "loading-model": "Starting nail detection",
  "finding-nails": "Finding your nail",
  "finding-coin": "Finding the 50-cent coin",
  calculating: "Choosing your best-fit size",
};

interface CapturedPhoto {
  file: File;
  previewUrl: string;
}

export function SingleNailSizing({
  analyzePhoto = analyzeAutomaticPhoto,
}: {
  analyzePhoto?: AutomaticPhotoAnalyzer;
}) {
  const [capture, setCapture] = useState<CapturedPhoto | null>(null);
  const [phase, setPhase] = useState<"capture" | "analyzing" | "result">(
    "capture",
  );
  const [stage, setStage] = useState<AutomaticAnalysisStage>("preparing");
  const [analysis, setAnalysis] = useState<AutomaticHandAnalysis | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const captureRef = useRef(capture);
  const analysisRef = useRef(analysis);
  const requestId = useRef(0);
  captureRef.current = capture;
  analysisRef.current = analysis;

  useEffect(
    () => () => {
      requestId.current += 1;
      if (captureRef.current)
        URL.revokeObjectURL(captureRef.current.previewUrl);
      if (analysisRef.current) releaseAutomaticAnalysis(analysisRef.current);
    },
    [],
  );

  async function selectPhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const currentRequest = ++requestId.current;
    if (analysis) releaseAutomaticAnalysis(analysis);
    setAnalysis(null);
    setCapture((current) => {
      if (current) URL.revokeObjectURL(current.previewUrl);
      return null;
    });
    setPreparing(true);
    setError("");
    setCopyStatus("");

    try {
      const prepared = await prepareImage(file);
      if (currentRequest !== requestId.current) return;

      const previewUrl = URL.createObjectURL(prepared.file);
      setCapture((current) => {
        if (current) URL.revokeObjectURL(current.previewUrl);
        return { file: prepared.file, previewUrl };
      });
    } catch {
      if (currentRequest === requestId.current) {
        setError(
          "We could not read that photo. Try another common phone image.",
        );
        setPhase("capture");
      }
    } finally {
      if (currentRequest === requestId.current) setPreparing(false);
    }
  }

  async function analyze() {
    if (!capture) return;
    const currentRequest = ++requestId.current;
    setError("");
    setStage("preparing");
    setPhase("analyzing");

    try {
      const outcome = await analyzePhoto(
        "right",
        capture.file,
        (nextStage) => {
          if (currentRequest === requestId.current) setStage(nextStage);
        },
        "index",
      );
      if (currentRequest !== requestId.current) {
        releaseAutomaticOutcome(outcome);
        return;
      }

      if (outcome.status === "accepted") {
        setAnalysis(outcome.analysis);
        setPhase("result");
        return;
      }

      if (outcome.status === "coin-review")
        releaseCoinReviewContext(outcome.context);
      setError(
        "We could not clearly find both the nail and 50-cent coin. Try another photo with both fully visible.",
      );
      setPhase("capture");
    } catch {
      if (currentRequest === requestId.current) {
        setError(
          "We could not read that photo. Try another common phone image.",
        );
        setPhase("capture");
      }
    }
  }

  function reset() {
    requestId.current += 1;
    if (capture) URL.revokeObjectURL(capture.previewUrl);
    if (analysis) releaseAutomaticAnalysis(analysis);
    setCapture(null);
    setAnalysis(null);
    setPhase("capture");
    setError("");
    setCopyStatus("");
  }

  if (phase === "capture")
    return (
      <div className="page instant-capture-page">
        <Eyebrow>Instant nail sizing</Eyebrow>
        <h1>Upload one photo. Get your nail size.</h1>
        <p className="lede">
          Place one bare nail beside a Singapore 50-cent coin and take the photo
          from directly above.
        </p>
        {error && <StatusMessage tone="error">{error}</StatusMessage>}
        <label className="photo-upload-card single-photo-upload">
          {capture ? (
            <img src={capture.previewUrl} alt="Selected nail preview" />
          ) : (
            <span className="photo-upload-placeholder">+</span>
          )}
          <strong>
            {preparing
              ? "Preparing photo…"
              : capture
                ? "Try another photo"
                : "Take or choose photo"}
          </strong>
          <span>JPG, PNG, HEIC and other common phone images</span>
          <input
            className="visually-hidden"
            type="file"
            accept={IMAGE_FILE_ACCEPT}
            capture="environment"
            disabled={preparing}
            onChange={(event) => void selectPhoto(event)}
          />
        </label>
        <Button disabled={!capture || preparing} onClick={() => void analyze()}>
          Get my nail size
        </Button>
        <p className="fine-print">
          Your photo stays in this browser and is erased when you start over.
        </p>
      </div>
    );

  if (phase === "analyzing")
    return (
      <div className="page processing-page">
        <Eyebrow>Automatic sizing</Eyebrow>
        <h1>Getting your nail size…</h1>
        <p className="lede">{STAGE_LABEL[stage]}.</p>
      </div>
    );

  if (!analysis || !capture) return null;
  const measurement = analysis.measurements[0];
  const recommendedSize =
    measurement.recommendedSize ??
    recommendClosestSize(measurement.projectedWidthMm) ??
    "9";

  async function copy() {
    try {
      await navigator.clipboard.writeText(
        `Recommended press-on nail size: ${recommendedSize}`,
      );
      setCopyStatus("Size copied.");
    } catch {
      setCopyStatus("Copy is unavailable in this browser.");
    }
  }

  return (
    <div className="page automatic-review-page">
      <Eyebrow>Your result</Eyebrow>
      <h1>Recommended press-on size: {recommendedSize}</h1>
      <p className="lede">
        We matched the nail width to the 50-cent coin in your photo.
      </p>
      <AutomaticReviewSurface
        previewUrl={capture.previewUrl}
        image={analysis.image}
        calibration={analysis.calibration}
        detections={analysis.detections}
        measurements={analysis.measurements}
        activeDigit={null}
        editable={false}
        showDetails={false}
        onSelectDigit={() => undefined}
        onWidthLineChange={() => undefined}
      />
      <p className="fine-print">
        Best-fit photo estimate. Sizing can vary slightly between nail brands.
      </p>
      <div className="action-stack">
        <Button onClick={() => void copy()}>Copy size</Button>
        <Button className="button--secondary" onClick={reset}>
          Size another nail
        </Button>
      </div>
      <p className="share-status" aria-live="polite">
        {copyStatus}
      </p>
    </div>
  );
}
