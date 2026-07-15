import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type PointerEvent,
} from "react";
import type { Digit } from "../guidedSizing";
import { IMAGE_FILE_ACCEPT, prepareImage } from "../imagePreparation";
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
import {
  recalculateAutomaticMeasurement,
  type HandSide,
} from "../vision/automaticSizing";
import type { CoinEllipseProposal } from "../vision/coinCalibration";
import { Button, Card, Eyebrow, StatusMessage } from "./Primitives";
import { AutomaticReviewSurface } from "./AutomaticReviewSurface";

const SIDE_LABEL: Record<HandSide, string> = {
  left: "Left hand",
  right: "Right hand",
};
const STAGE_LABEL: Record<AutomaticAnalysisStage, string> = {
  preparing: "Preparing the photo",
  "loading-model": "Loading the private on-device model",
  "finding-nails": "Finding five nail outlines",
  "finding-coin": "Finding the 50-cent coin",
  calculating: "Calculating projected widths",
};
const SIDES: readonly HandSide[] = ["left", "right"];

interface CapturedPhoto {
  file: File;
  previewUrl: string;
}

interface InstantSizingProps {
  analyzePhoto?: AutomaticPhotoAnalyzer;
  completeCoin?: AutomaticCoinCompleter;
}

export function InstantSizing({
  analyzePhoto = analyzeAutomaticPhoto,
  completeCoin = completeAutomaticPhotoWithCoin,
}: InstantSizingProps) {
  const [phase, setPhase] = useState<
    "capture" | "analyzing" | "coin-review" | "review" | "results"
  >("capture");
  const [captures, setCaptures] = useState<
    Partial<Record<HandSide, CapturedPhoto>>
  >({});
  const [coinConfirmed, setCoinConfirmed] = useState(false);
  const [preparingSide, setPreparingSide] = useState<HandSide | null>(null);
  const [stage, setStage] = useState<AutomaticAnalysisStage>("preparing");
  const [stageSide, setStageSide] = useState<HandSide>("left");
  const [analyses, setAnalyses] = useState<AutomaticHandAnalysis[]>([]);
  const [coinReview, setCoinReview] = useState<CoinReviewContext | null>(null);
  const [coinProposal, setCoinProposal] = useState<CoinEllipseProposal | null>(
    null,
  );
  const [continuation, setContinuation] = useState<{
    nextIndex: number;
    completed: AutomaticHandAnalysis[];
  } | null>(null);
  const [retry, setRetry] = useState<{
    startIndex: number;
    completed: AutomaticHandAnalysis[];
  } | null>(null);
  const [reviewIndex, setReviewIndex] = useState(0);
  const [activeDigit, setActiveDigit] = useState<Digit | null>(null);
  const [error, setError] = useState("");
  const [shareStatus, setShareStatus] = useState("");
  const captureRef = useRef(captures);
  const analysesRef = useRef(analyses);
  const coinReviewRef = useRef(coinReview);
  const continuationRef = useRef(continuation);
  const retryRef = useRef(retry);
  const preparationId = useRef(0);
  const analysisId = useRef(0);
  captureRef.current = captures;
  analysesRef.current = analyses;
  coinReviewRef.current = coinReview;
  continuationRef.current = continuation;
  retryRef.current = retry;

  useEffect(
    () => () => {
      preparationId.current += 1;
      analysisId.current += 1;
      for (const capture of Object.values(captureRef.current))
        URL.revokeObjectURL(capture.previewUrl);
      releaseRetainedAnalysisData(
        analysesRef.current,
        coinReviewRef.current,
        continuationRef.current,
        retryRef.current,
      );
    },
    [],
  );

  async function selectPhoto(side: HandSide, file: File) {
    const requestId = ++preparationId.current;
    setPreparingSide(side);
    setError("");
    try {
      const prepared = await prepareImage(file);
      if (requestId !== preparationId.current) return;
      const pendingRetry = retryRef.current;
      if (pendingRetry && SIDES.indexOf(side) < pendingRetry.startIndex) {
        for (const analysis of pendingRetry.completed)
          releaseAutomaticAnalysis(analysis);
        setRetry(null);
      }
      const previewUrl = URL.createObjectURL(prepared.file);
      setCaptures((current) => {
        const previous = current[side];
        if (previous) URL.revokeObjectURL(previous.previewUrl);
        return {
          ...current,
          [side]: { file: prepared.file, previewUrl },
        };
      });
    } catch (cause) {
      if (requestId === preparationId.current)
        setError(
          cause instanceof Error
            ? cause.message
            : "This photo could not be prepared locally.",
        );
    } finally {
      if (requestId === preparationId.current) setPreparingSide(null);
    }
  }

  async function runFrom(
    startIndex: number,
    completed: AutomaticHandAnalysis[],
  ) {
    const requestId = ++analysisId.current;
    setRetry(null);
    setPhase("analyzing");
    setError("");
    const next = [...completed];
    try {
      for (let index = startIndex; index < SIDES.length; index += 1) {
        const side = SIDES[index];
        const capture = captures[side];
        if (!capture) throw new Error(`${SIDE_LABEL[side]} photo is missing.`);
        setStageSide(side);
        const outcome = await analyzePhoto(side, capture.file, (nextStage) => {
          if (requestId === analysisId.current) setStage(nextStage);
        });
        if (requestId !== analysisId.current) {
          releaseAutomaticOutcome(outcome);
          for (const analysis of next) releaseAutomaticAnalysis(analysis);
          return;
        }
        if (outcome.status === "rejected") {
          if (next.length > 0) {
            setRetry({ startIndex: index, completed: next });
          } else {
            for (const analysis of next) releaseAutomaticAnalysis(analysis);
          }
          setError(
            `${SIDE_LABEL[side]}: ${outcome.message}${
              next.length > 0
                ? ` Your ${SIDE_LABEL[SIDES[index - 1]].toLowerCase()} result is kept; replace only this photo.`
                : ""
            }`,
          );
          setPhase("capture");
          return;
        }
        if (outcome.status === "coin-review") {
          setCoinReview(outcome.context);
          setCoinProposal(
            outcome.context.suggestedEllipse ??
              defaultCoinProposal(outcome.context),
          );
          setContinuation({ nextIndex: index + 1, completed: next });
          setPhase("coin-review");
          return;
        }
        next.push(outcome.analysis);
      }
      beginReview(next);
    } catch (cause) {
      for (const analysis of next) releaseAutomaticAnalysis(analysis);
      if (requestId !== analysisId.current) return;
      setError(
        cause instanceof Error
          ? cause.message
          : "Automatic sizing stopped before a result was produced.",
      );
      setPhase("capture");
    }
  }

  function beginReview(completed: AutomaticHandAnalysis[]) {
    for (const analysis of analysesRef.current) {
      if (!completed.includes(analysis)) releaseAutomaticAnalysis(analysis);
    }
    setRetry(null);
    setAnalyses(completed);
    setReviewIndex(0);
    setActiveDigit(
      completed[0]?.measurements.find(({ needsReview }) => needsReview)
        ?.digit ?? null,
    );
    setPhase("review");
  }

  function confirmCoin() {
    if (!coinReview || !coinProposal || !continuation) return;
    const outcome = completeCoin(coinReview, coinProposal);
    if (outcome.status === "coin-review") {
      setCoinReview(outcome.context);
      setError(outcome.context.message);
      return;
    }
    if (outcome.status === "rejected") {
      analysisId.current += 1;
      releaseRetainedAnalysisData(analyses, coinReview, continuation, retry);
      setAnalyses([]);
      setCoinReview(null);
      setContinuation(null);
      setRetry(null);
      setPhase("capture");
      setError(
        `${SIDE_LABEL[coinReview.side]}: ${outcome.message} Choose a clearer photo and try again.`,
      );
      return;
    }
    const completed = [...continuation.completed, outcome.analysis];
    setCoinReview(null);
    setCoinProposal(null);
    setContinuation(null);
    void runFrom(continuation.nextIndex, completed);
  }

  function updateWidthLine(
    digit: Digit,
    line: { start: { x: number; y: number }; end: { x: number; y: number } },
  ) {
    setError("");
    setAnalyses((current) =>
      current.map((analysis, index) => {
        if (index !== reviewIndex) return analysis;
        try {
          return {
            ...analysis,
            measurements: analysis.measurements.map((measurement) =>
              measurement.digit === digit
                ? recalculateAutomaticMeasurement(
                    measurement,
                    line,
                    analysis.calibration,
                  )
                : measurement,
            ),
          };
        } catch (cause) {
          setError(
            cause instanceof Error
              ? cause.message
              : "That line cannot produce a supported nail width.",
          );
          return analysis;
        }
      }),
    );
  }

  function approveCurrentHand() {
    releaseAutomaticAnalysis(analyses[reviewIndex]);
    const nextIndex = reviewIndex + 1;
    if (nextIndex >= analyses.length) {
      setActiveDigit(null);
      setPhase("results");
      return;
    }
    setReviewIndex(nextIndex);
    setActiveDigit(
      analyses[nextIndex].measurements.find(({ needsReview }) => needsReview)
        ?.digit ?? null,
    );
    setError("");
  }

  function reset() {
    preparationId.current += 1;
    analysisId.current += 1;
    for (const capture of Object.values(captures))
      URL.revokeObjectURL(capture.previewUrl);
    releaseRetainedAnalysisData(analyses, coinReview, continuation, retry);
    setCaptures({});
    setCoinConfirmed(false);
    setAnalyses([]);
    setCoinReview(null);
    setContinuation(null);
    setRetry(null);
    setError("");
    setShareStatus("");
    setPhase("capture");
  }

  if (phase === "capture")
    return (
      <CaptureTwoHands
        captures={captures}
        coinConfirmed={coinConfirmed}
        preparingSide={preparingSide}
        error={error}
        onCoinConfirmationChange={setCoinConfirmed}
        onSelect={(side, event) => {
          const file = event.target.files?.[0];
          if (file) void selectPhoto(side, file);
          event.target.value = "";
        }}
        retrySide={retry ? SIDES[retry.startIndex] : null}
        onAnalyze={() =>
          void runFrom(retry?.startIndex ?? 0, retry?.completed ?? [])
        }
      />
    );

  if (phase === "analyzing")
    return (
      <div className="page processing-page">
        <Eyebrow>Private on-device analysis</Eyebrow>
        <h1>Finding your nail sizes.</h1>
        <p className="lede">
          {SIDE_LABEL[stageSide]} · {STAGE_LABEL[stage]}. The first run
          downloads the model from this website; your photos are never uploaded.
        </p>
        <ol className="processing-list">
          {Object.values(STAGE_LABEL).map((label, index) => (
            <li key={label}>
              <span>{index + 1}</span>
              {label}
            </li>
          ))}
        </ol>
      </div>
    );

  if (phase === "coin-review" && coinReview && coinProposal) {
    const capture = captures[coinReview.side]!;
    return (
      <CoinReview
        context={coinReview}
        previewUrl={capture.previewUrl}
        proposal={coinProposal}
        error={error}
        onProposalChange={(proposal) => {
          setCoinProposal(proposal);
          setError("");
        }}
        onConfirm={confirmCoin}
        onRetake={() => {
          analysisId.current += 1;
          releaseRetainedAnalysisData(
            analyses,
            coinReview,
            continuation,
            retry,
          );
          setAnalyses([]);
          setCoinReview(null);
          setContinuation(null);
          setRetry(null);
          setPhase("capture");
          setError(`${SIDE_LABEL[coinReview.side]}: choose a clearer photo.`);
        }}
      />
    );
  }

  if (phase === "review") {
    const analysis = analyses[reviewIndex];
    const capture = captures[analysis.side]!;
    const unresolved = analysis.measurements.filter(
      ({ needsReview }) => needsReview,
    );
    return (
      <div className="page automatic-review-page">
        <Eyebrow>
          Review {reviewIndex + 1} of 2 · {SIDE_LABEL[analysis.side]}
        </Eyebrow>
        <h1>Check the coin and five width lines.</h1>
        <p className="lede">
          If a line reaches the visible sidewalls at the nail’s widest point,
          leave it alone. Adjust only the nails marked for review.
        </p>
        {unresolved.length > 0 && (
          <StatusMessage tone="error">
            <strong>
              {unresolved.length} nail
              {unresolved.length === 1 ? " needs" : "s need"} a quick check
            </strong>
            <br />
            Select each highlighted nail and drag A/B to its visible sidewalls.
          </StatusMessage>
        )}
        {error && <StatusMessage tone="error">{error}</StatusMessage>}
        <AutomaticReviewSurface
          previewUrl={capture.previewUrl}
          image={analysis.image}
          calibration={analysis.calibration}
          detections={analysis.detections}
          measurements={analysis.measurements}
          activeDigit={activeDigit}
          onSelectDigit={setActiveDigit}
          onWidthLineChange={updateWidthLine}
        />
        <div className="action-stack">
          <Button disabled={unresolved.length > 0} onClick={approveCurrentHand}>
            {reviewIndex === 0
              ? "Approve and review right hand"
              : "Approve and show best fits"}
          </Button>
          <Button
            className="button--secondary"
            onClick={() => {
              analysisId.current += 1;
              releaseRetainedAnalysisData(
                analyses,
                coinReview,
                continuation,
                retry,
              );
              setAnalyses([]);
              setCoinReview(null);
              setContinuation(null);
              setRetry(null);
              setPhase("capture");
              setError(
                `${SIDE_LABEL[analysis.side]}: choose a replacement photo.`,
              );
            }}
          >
            Retake this hand
          </Button>
        </div>
      </div>
    );
  }

  return (
    <AutomaticResults
      analyses={analyses}
      shareStatus={shareStatus}
      setShareStatus={setShareStatus}
      onReset={reset}
    />
  );
}

function CaptureTwoHands({
  captures,
  coinConfirmed,
  preparingSide,
  error,
  retrySide,
  onCoinConfirmationChange,
  onSelect,
  onAnalyze,
}: {
  captures: Partial<Record<HandSide, CapturedPhoto>>;
  coinConfirmed: boolean;
  preparingSide: HandSide | null;
  error: string;
  retrySide: HandSide | null;
  onCoinConfirmationChange: (confirmed: boolean) => void;
  onSelect: (side: HandSide, event: ChangeEvent<HTMLInputElement>) => void;
  onAnalyze: () => void;
}) {
  return (
    <div className="page instant-capture-page">
      <Eyebrow>Automatic sizing beta</Eyebrow>
      <h1>Upload two hand photos. Get one best-fit size per nail.</h1>
      <p className="lede">
        One photo per hand, with all five bare nails and a current Singapore
        50-cent coin. The beta is designed for a short upload-and-review flow;
        timing still needs real-phone testing.
      </p>
      <Card className="instant-instructions">
        <h2>For both photos</h2>
        <ul className="check-list">
          <li>Lay the hand and coin flat on the same surface</li>
          <li>Point fingertips away from you and spread all five digits</li>
          <li>Hold the phone directly overhead in bright, even light</li>
          <li>Keep every nail and the complete coin rim visible</li>
        </ul>
        <label className="coin-confirmation">
          <input
            type="checkbox"
            checked={coinConfirmed}
            onChange={(event) =>
              onCoinConfirmationChange(event.currentTarget.checked)
            }
          />
          <span>
            I am using the current Third Series Singapore 50-cent coin showing
            the Port of Singapore and large 50/CENTS design.
          </span>
        </label>
      </Card>
      {error && <StatusMessage tone="error">{error}</StatusMessage>}
      <div className="two-photo-grid">
        {SIDES.map((side) => (
          <label className="photo-upload-card" key={side}>
            <span className="eyebrow">{SIDE_LABEL[side]}</span>
            {captures[side] ? (
              <img
                src={captures[side].previewUrl}
                alt={`${SIDE_LABEL[side]} selected preview`}
              />
            ) : (
              <span className="photo-upload-placeholder">+</span>
            )}
            <strong>
              {preparingSide === side
                ? "Preparing locally…"
                : captures[side]
                  ? "Replace photo"
                  : "Take or choose photo"}
            </strong>
            <input
              className="visually-hidden"
              type="file"
              accept={IMAGE_FILE_ACCEPT}
              capture="environment"
              disabled={preparingSide !== null}
              onChange={(event) => onSelect(side, event)}
            />
          </label>
        ))}
      </div>
      <Button
        disabled={
          !captures.left ||
          !captures.right ||
          !coinConfirmed ||
          preparingSide !== null
        }
        onClick={onAnalyze}
      >
        {retrySide
          ? `Retry ${SIDE_LABEL[retrySide].toLowerCase()}`
          : "Find my best-fit sizes"}
      </Button>
      <p className="fine-print">
        Beta: review the detected lines before using a result. Projected width
        does not measure strong nail curvature or guarantee fit.
      </p>
    </div>
  );
}

function CoinReview({
  context,
  previewUrl,
  proposal,
  error,
  onProposalChange,
  onConfirm,
  onRetake,
}: {
  context: CoinReviewContext;
  previewUrl: string;
  proposal: CoinEllipseProposal;
  error: string;
  onProposalChange: (proposal: CoinEllipseProposal) => void;
  onConfirm: () => void;
  onRetake: () => void;
}) {
  function placeCenter(event: PointerEvent<HTMLDivElement>) {
    if (event.target !== event.currentTarget) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    onProposalChange({
      ...proposal,
      center: {
        x: ((event.clientX - bounds.left) / bounds.width) * context.image.width,
        y:
          ((event.clientY - bounds.top) / bounds.height) * context.image.height,
      },
    });
  }
  function moveCenterWithKeyboard(event: KeyboardEvent<HTMLDivElement>) {
    const direction = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    }[event.key];
    if (!direction) return;
    event.preventDefault();
    const bounds = event.currentTarget.getBoundingClientRect();
    const renderedPixels = event.shiftKey ? 8 : 1;
    const sourceX =
      bounds.width > 0
        ? (context.image.width / bounds.width) * renderedPixels
        : renderedPixels;
    const sourceY =
      bounds.height > 0
        ? (context.image.height / bounds.height) * renderedPixels
        : renderedPixels;
    onProposalChange({
      ...proposal,
      center: {
        x: clamp(
          proposal.center.x + direction[0] * sourceX,
          0,
          context.image.width,
        ),
        y: clamp(
          proposal.center.y + direction[1] * sourceY,
          0,
          context.image.height,
        ),
      },
    });
  }
  const minRadius = 60;
  const maxRadius = Math.max(
    minRadius,
    Math.min(context.image.width, context.image.height) * 0.3,
  );
  return (
    <div className="page coin-review-page">
      <Eyebrow>One quick correction · {SIDE_LABEL[context.side]}</Eyebrow>
      <h1>Tap the coin once.</h1>
      <p className="lede">
        The coin was not clear enough to select automatically. Tap its centre,
        then adjust the single outline to the rim—no eight-point marking.
      </p>
      <StatusMessage>{context.message}</StatusMessage>
      {error && <StatusMessage tone="error">{error}</StatusMessage>}
      <div className="coin-tap-surface">
        <img src={previewUrl} alt="Select the 50-cent coin" draggable={false} />
        <div
          className="coin-tap-overlay"
          role="group"
          tabIndex={0}
          aria-label="Position the coin outline; use arrow keys for precise movement"
          onPointerDown={placeCenter}
          onKeyDown={moveCenterWithKeyboard}
        >
          <svg
            viewBox={`0 0 ${context.image.width} ${context.image.height}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <ellipse
              cx={proposal.center.x}
              cy={proposal.center.y}
              rx={proposal.majorRadiusPx}
              ry={proposal.minorRadiusPx}
              className="automatic-coin-outline"
            />
          </svg>
        </div>
      </div>
      <label className="coin-size-control">
        <span>Match the outline to the coin rim</span>
        <input
          type="range"
          min={minRadius}
          max={maxRadius}
          step="1"
          value={proposal.majorRadiusPx}
          onChange={(event) => {
            const radius = Number(event.currentTarget.value);
            onProposalChange({
              ...proposal,
              majorRadiusPx: radius,
              minorRadiusPx: radius,
            });
          }}
        />
      </label>
      <div className="action-stack">
        <Button onClick={onConfirm}>Use this coin outline</Button>
        <Button className="button--secondary" onClick={onRetake}>
          Retake this hand instead
        </Button>
      </div>
    </div>
  );
}

function AutomaticResults({
  analyses,
  shareStatus,
  setShareStatus,
  onReset,
}: {
  analyses: readonly AutomaticHandAnalysis[];
  shareStatus: string;
  setShareStatus: (status: string) => void;
  onReset: () => void;
}) {
  const lines = analyses.flatMap((analysis) =>
    analysis.measurements.map(
      (measurement) =>
        `${SIDE_LABEL[analysis.side]} ${measurement.digit}: ${measurement.projectedWidthMm.toFixed(1)} ± ${measurement.uncertaintyMm.toFixed(1)} mm — ${measurement.recommendedSize ? `best-fit size ${measurement.recommendedSize}` : "outside provisional chart"}${measurement.requiresPhysicalConfirmation ? "; borderline measurement—confirm physically" : ""} (${measurement.source})`,
    ),
  );
  const shareText = [
    "NailSize automatic best-fit suggestions",
    "Method: auto-sg50-two-hand-v0.1.0; chart: platform-default@1 (provisional).",
    ...lines,
    "Review only. Top-down projected width does not measure strong curvature or guarantee fit.",
  ].join("\n");

  async function copy() {
    try {
      await navigator.clipboard.writeText(shareText);
      setShareStatus("Results copied. Photos and outlines were not included.");
    } catch {
      setShareStatus("Copy is unavailable in this browser.");
    }
  }

  return (
    <div className="page automatic-results-page">
      <Eyebrow>Two-photo sizing complete</Eyebrow>
      <h1>Your suggested best-fit nail set.</h1>
      <p className="lede">
        One conservative size is selected for each nail. Share the projected
        widths and best-fit suggestions with your nail artist.
      </p>
      <div className="results-desktop-hands automatic-result-hands">
        {analyses.map((analysis) => (
          <Card className="hand-panel" key={analysis.side}>
            <h2>{SIDE_LABEL[analysis.side]}</h2>
            {analysis.measurements.map((measurement) => (
              <div className="measurement-row" key={measurement.digit}>
                <div>
                  <strong>{measurement.digit}</strong>
                  <span>
                    {measurement.projectedWidthMm.toFixed(1)} ±{" "}
                    {measurement.uncertaintyMm.toFixed(1)} mm ·{" "}
                    {measurement.source === "automatic"
                      ? "automatic"
                      : "adjusted"}
                  </span>
                </div>
                <div className="measurement-value">
                  <strong>
                    {measurement.recommendedSize
                      ? `Best-fit size ${measurement.recommendedSize}`
                      : "Check chart"}
                  </strong>
                  {measurement.requiresPhysicalConfirmation && (
                    <span className="measurement-boundary-warning">
                      Borderline measurement—confirm this nail physically.
                    </span>
                  )}
                </div>
              </div>
            ))}
          </Card>
        ))}
      </div>
      <StatusMessage>
        This beta has not passed a representative physical-width validation
        study. Confirm borderline or highly curved nails with the artist or a
        sizing kit.
      </StatusMessage>
      <div className="action-stack">
        <Button onClick={() => void copy()}>Copy text-only results</Button>
        <Button className="button--secondary" onClick={onReset}>
          Start over and erase photos
        </Button>
      </div>
      <p className="share-status" aria-live="polite">
        {shareStatus}
      </p>
    </div>
  );
}

function defaultCoinProposal(context: CoinReviewContext): CoinEllipseProposal {
  const radius = Math.max(
    60,
    Math.min(context.image.width, context.image.height) * 0.12,
  );
  return {
    center: {
      x: context.image.width * 0.2,
      y: context.image.height * 0.75,
    },
    majorRadiusPx: radius,
    minorRadiusPx: radius,
    rotationRadians: 0,
    rimCoverage: 0,
    normalizedResidual: 1,
  };
}

function releaseRetainedAnalysisData(
  analyses: readonly AutomaticHandAnalysis[],
  coinReview: CoinReviewContext | null,
  continuation: {
    nextIndex: number;
    completed: AutomaticHandAnalysis[];
  } | null,
  retry: {
    startIndex: number;
    completed: AutomaticHandAnalysis[];
  } | null,
) {
  for (const analysis of analyses) releaseAutomaticAnalysis(analysis);
  for (const analysis of continuation?.completed ?? [])
    releaseAutomaticAnalysis(analysis);
  for (const analysis of retry?.completed ?? [])
    releaseAutomaticAnalysis(analysis);
  if (coinReview) releaseCoinReviewContext(coinReview);
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}
