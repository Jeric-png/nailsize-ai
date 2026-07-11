import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import type { CaptureType, MeasureOkResponse } from "@nailsize/contracts";
import { measureCapture, MeasureRequestError } from "./api";
import {
  Button,
  Card,
  Eyebrow,
  ProgressStepper,
  StatusMessage,
} from "./components/Primitives";
import { prepareImage } from "./imagePreparation";
import { captureOrder, initialSession, sessionReducer } from "./session";

function FocusOnNavigation() {
  const { pathname } = useLocation();
  const previousPath = useRef(pathname);

  useEffect(() => {
    if (previousPath.current === pathname) return;
    previousPath.current = pathname;
    const heading = document.querySelector<HTMLElement>("main h1");
    if (!heading) return;
    heading.tabIndex = -1;
    heading.focus();
  }, [pathname]);

  return null;
}

const captureCopy: Record<
  CaptureType,
  { title: string; nails: string; instruction: string }
> = {
  left_fingers: {
    title: "Left fingers",
    nails: "Index, middle, ring, pinky",
    instruction: "Lay four fingers flat beside the reference card.",
  },
  left_thumb: {
    title: "Left thumb",
    nails: "Thumb",
    instruction: "Place your thumb flat beside the reference card.",
  },
  right_fingers: {
    title: "Right fingers",
    nails: "Index, middle, ring, pinky",
    instruction: "Lay four fingers flat beside the reference card.",
  },
  right_thumb: {
    title: "Right thumb",
    nails: "Thumb",
    instruction: "Place your thumb flat beside the reference card.",
  },
};

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <header className="site-header">
        <Link to="/" className="brand">
          NAILSIZE / AI
        </Link>
        <span>Calibrated sizing</span>
      </header>
      <main>{children}</main>
      <footer className="site-footer">
        Photos are processed transiently and are not saved.
      </footer>
    </div>
  );
}

function Landing() {
  return (
    <div className="page landing">
      <Eyebrow>Press-on nail measurement</Eyebrow>
      <h1>Size every nail from four guided photos.</h1>
      <p className="lede">
        Use a standard-size reference card to turn image pixels into projected
        nail widths your nail artist can use.
      </p>
      <div className="hero-placeholder" aria-hidden="true">
        <span>HAND + REFERENCE CARD</span>
      </div>
      <Card>
        <h2>What you will need</h2>
        <ul className="check-list">
          <li>Bare, natural nails</li>
          <li>Bright, even lighting</li>
          <li>A blank ISO ID-1 size card</li>
          <li>About four minutes</li>
        </ul>
      </Card>
      <Link className="button" to="/prepare">
        Start sizing
      </Link>
      <p className="fine-print">
        Do not photograph payment cards, driving licences, or government IDs.
      </p>
    </div>
  );
}

function Preparation() {
  const steps = [
    [
      "01",
      "Prepare your nails",
      "Remove polish and press-ons. Keep every nail edge visible.",
    ],
    [
      "02",
      "Set the light",
      "Use bright indirect light. Avoid glare and hard shadows.",
    ],
    [
      "03",
      "Use a safe reference",
      "Use a blank calibration card or other non-sensitive ISO ID-1 card.",
    ],
    [
      "04",
      "Keep everything flat",
      "Place the card and nails on the same flat surface.",
    ],
  ];
  return (
    <div className="page">
      <Eyebrow>Before you begin</Eyebrow>
      <h1>Prepare for an accurate capture.</h1>
      <p className="lede">
        Calibration is required. We will ask you to retake a photo when the
        reference or nails cannot be measured safely.
      </p>
      <div className="instruction-list">
        {steps.map(([n, title, body]) => (
          <Card key={n}>
            <span className="instruction-number">{n}</span>
            <div>
              <h2>{title}</h2>
              <p>{body}</p>
            </div>
          </Card>
        ))}
      </div>
      <StatusMessage>
        <strong>Privacy:</strong> each photo is held only while it is processed.
        It is not added to an account, gallery, or training dataset.
      </StatusMessage>
      <Link className="button" to="/capture/left_fingers">
        I’m ready
      </Link>
    </div>
  );
}

function CapturePage({
  state,
  dispatch,
}: {
  state: ReturnType<typeof useSession>[0];
  dispatch: ReturnType<typeof useSession>[1];
}) {
  const params = useParams();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const preparationId = useRef(0);
  const [preparing, setPreparing] = useState(false);
  const captureType = captureOrder.includes(params.captureType as CaptureType)
    ? (params.captureType as CaptureType)
    : "left_fingers";
  const config = captureCopy[captureType];
  const record = state.captures[captureType];
  const step = captureOrder.indexOf(captureType) + 1;

  function submit() {
    if (!record || preparing || state.status === "submitting") return;
    dispatch({ type: "submitting" });
    navigate(`/quality/${captureType}`);
  }

  async function selectFile(file: File) {
    const requestId = ++preparationId.current;
    setPreparing(true);
    const prepared = await prepareImage(file).catch(() => ({
      file,
      normalizedInBrowser: false,
    }));
    if (requestId !== preparationId.current) return;
    dispatch({
      type: "select",
      captureType,
      record: {
        file: prepared.file,
        previewUrl: URL.createObjectURL(prepared.file),
      },
    });
    setPreparing(false);
  }

  useEffect(
    () => () => {
      preparationId.current += 1;
    },
    [captureType],
  );

  return (
    <div className="page capture-page">
      <ProgressStepper current={step} />
      <Eyebrow>Capture {step} of 4</Eyebrow>
      <h1>{config.title}</h1>
      <p className="lede">{config.instruction}</p>
      <div
        className={
          record ? "capture-frame capture-frame--filled" : "capture-frame"
        }
      >
        {record ? (
          <img
            src={record.previewUrl}
            alt={`Preview of ${config.title.toLowerCase()}`}
          />
        ) : (
          <div>
            <strong>{config.nails}</strong>
            <span>Keep the full card and nail edges inside this frame.</span>
          </div>
        )}
      </div>
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        tabIndex={-1}
        aria-label={`Choose photo for ${config.title.toLowerCase()}`}
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
        capture="environment"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void selectFile(file);
          event.target.value = "";
        }}
      />
      {preparing && (
        <StatusMessage>
          Preparing the photo for a smaller, orientation-safe upload…
        </StatusMessage>
      )}
      {record?.issues?.map((issue) => (
        <StatusMessage key={issue.code} tone="error">
          <strong>{issue.message}</strong>
          <br />
          {issue.correction}
        </StatusMessage>
      ))}
      {state.error && (
        <StatusMessage tone="error">{state.error.message}</StatusMessage>
      )}
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
          onClick={submit}
          disabled={!record || preparing || state.status === "submitting"}
        >
          {state.status === "submitting"
            ? "Checking photo…"
            : "Check this photo"}
        </Button>
      </div>
      <p className="fine-print">
        Accepted: JPEG, PNG, WebP, HEIC, or HEIF up to 12 MB.
      </p>
    </div>
  );
}

export function QualityPage({
  state,
  dispatch,
}: {
  state: ReturnType<typeof useSession>[0];
  dispatch: ReturnType<typeof useSession>[1];
}) {
  const params = useParams();
  const navigate = useNavigate();
  const captureType = captureOrder.includes(params.captureType as CaptureType)
    ? (params.captureType as CaptureType)
    : "left_fingers";
  const record = state.captures[captureType];
  const step = captureOrder.indexOf(captureType) + 1;
  const returnToResults = state.correctionCapture === captureType;

  useEffect(() => {
    if (!record || state.status !== "submitting") return;
    let current = true;
    const controller = new AbortController();
    void measureCapture(captureType, record.file, controller.signal)
      .then((response) => {
        if (!current) return;
        if (response.status === "retake")
          dispatch({
            type: "retake",
            captureType,
            issues: response.quality_issues,
          });
        else dispatch({ type: "accepted", captureType, result: response });
      })
      .catch((error: unknown) => {
        if (!current) return;
        dispatch({
          type: "error",
          code: error instanceof MeasureRequestError ? error.code : "service",
          message:
            error instanceof Error
              ? error.message
              : "The sizing service could not check this photo.",
        });
      });
    return () => {
      current = false;
      controller.abort();
    };
  }, [captureType, dispatch, record, state.status]);

  if (!record) return <Navigate to={`/capture/${captureType}`} replace />;

  const analyzing = state.status === "submitting";
  const accepted = Boolean(record.result);
  const needsReplacement = ["too_large", "unsupported"].includes(
    state.error?.code ?? "",
  );

  return (
    <div className="page quality-page">
      <ProgressStepper current={step} />
      <Eyebrow>Photo quality check</Eyebrow>
      <h1>
        {analyzing
          ? "Analyzing photo…"
          : accepted
            ? "Photo accepted."
            : record.issues
              ? "Retake required."
              : "Photo check interrupted."}
      </h1>
      <p className="lede" aria-live="polite">
        {analyzing
          ? "Detecting the reference plane, hand landmarks, and nail boundaries."
          : accepted
            ? "The reference and required nails passed this capture check."
            : "Your other accepted captures remain in this browser session."}
      </p>
      <div
        className={`quality-preview${analyzing ? " quality-preview--scanning" : ""}`}
      >
        <div className="quality-canvas">
          <img
            src={record.previewUrl}
            alt={`Quality preview for ${captureCopy[captureType].title}`}
          />
          {accepted && (
            <svg
              className="contour-overlay"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              {record.result?.measurements.map((measurement) => (
                <polygon
                  key={measurement.digit}
                  points={measurement.contour
                    .map(([x, y]) => `${x * 100},${y * 100}`)
                    .join(" ")}
                />
              ))}
            </svg>
          )}
          {analyzing && <span className="scan-line" aria-hidden="true" />}
        </div>
      </div>
      {record.issues?.map((issue) => (
        <StatusMessage key={issue.code} tone="error">
          <strong>{issue.message}</strong>
          <br />
          {issue.correction}
        </StatusMessage>
      ))}
      {state.error && (
        <StatusMessage tone="error">
          <strong>{state.error.message}</strong>
          <br />
          {needsReplacement
            ? "Choose a different image for this capture."
            : "Retry when your connection or the sizing service is available."}
        </StatusMessage>
      )}
      {accepted && (
        <StatusMessage tone="success">
          <strong>Capture {step} accepted</strong>
          <br />
          It remains only in browser memory for this sizing session.
        </StatusMessage>
      )}
      <div className="action-stack">
        {accepted && (
          <>
            <Button
              onClick={() => {
                if (returnToResults) dispatch({ type: "finishCorrection" });
                navigate(
                  returnToResults
                    ? "/results"
                    : step === 4
                      ? "/processing"
                      : `/capture/${captureOrder[step]}`,
                );
              }}
            >
              {returnToResults
                ? "Return to results"
                : step === 4
                  ? "Finish measurements"
                  : "Continue"}
            </Button>
            <Button
              className="button--secondary"
              onClick={() => navigate(`/capture/${captureType}`)}
            >
              Retake photo
            </Button>
          </>
        )}
        {(record.issues || needsReplacement) && (
          <Button
            onClick={() => navigate(`/capture/${captureType}`)}
            className="button--secondary"
          >
            Choose another photo
          </Button>
        )}
        {state.error && !needsReplacement && (
          <Button onClick={() => dispatch({ type: "submitting" })}>
            Retry check
          </Button>
        )}
        {!analyzing && !accepted && !record.issues && !state.error && (
          <Button onClick={() => dispatch({ type: "submitting" })}>
            Check photo
          </Button>
        )}
      </div>
    </div>
  );
}

function Processing({ results }: { results: MeasureOkResponse[] }) {
  const navigate = useNavigate();
  const missing = captureOrder.find(
    (type) => !results.some((result) => result.capture_type === type),
  );
  if (results.length === 0) return <Navigate to="/recover/session" replace />;
  if (missing) return <Navigate to={`/capture/${missing}`} replace />;

  const stages = [
    "Photo quality checked",
    "Reference planes calibrated",
    "Nail edges measured",
    "Press-on sizes matched",
  ];

  return (
    <div className="page processing-page">
      <Eyebrow>Processing complete</Eyebrow>
      <h1>Your measurements are ready.</h1>
      <p className="lede">
        All four captures passed calibration and measurement. Review the
        projected widths before sharing them with your nail artist.
      </p>
      <ol className="processing-list" aria-label="Completed measurement stages">
        {stages.map((stage) => (
          <li key={stage}>
            <span aria-hidden="true">✓</span>
            {stage}
          </li>
        ))}
      </ol>
      <StatusMessage tone="success">
        <strong>Photos processed transiently</strong>
        <br />
        The service returned measurements without adding your photos to a
        gallery, account, or training dataset.
      </StatusMessage>
      <Button onClick={() => navigate("/results")}>Review results</Button>
    </div>
  );
}

function SessionRecovery({ reset }: { reset: () => void }) {
  const navigate = useNavigate();
  return (
    <div className="page recovery-page">
      <Eyebrow>Session ended</Eyebrow>
      <h1>Your previous sizing session is no longer available.</h1>
      <p className="lede">
        Photos and measurements live only in browser memory. They are erased
        when the page session ends, so you will need to take the four photos
        again.
      </p>
      <StatusMessage>
        <strong>Nothing was saved</strong>
        <br />
        This recovery behavior is part of the application’s privacy design.
      </StatusMessage>
      <Button
        onClick={() => {
          reset();
          navigate("/");
        }}
      >
        Start a new sizing session
      </Button>
    </div>
  );
}

type ResultMeasurement = MeasureOkResponse["measurements"][number] & {
  side: "Left" | "Right";
  captureType: CaptureType;
};

function NailResult({
  measurement,
  compact = false,
  onRetake,
}: {
  measurement: ResultMeasurement;
  compact?: boolean;
  onRetake: () => void;
}) {
  return (
    <div
      className={`measurement-row${compact ? " measurement-row--compact" : ""}`}
    >
      <div>
        <strong>{measurement.digit}</strong>
        <span>
          {measurement.confidence} confidence · ±
          {measurement.uncertainty_mm.toFixed(1)} mm
        </span>
        <button type="button" className="text-button" onClick={onRetake}>
          Retake
        </button>
      </div>
      <div className="measurement-value">
        <strong>{measurement.projected_width_mm.toFixed(1)} mm</strong>
        <span>
          Size {measurement.recommended_size}
          {measurement.alternate_size ? ` / ${measurement.alternate_size}` : ""}
        </span>
      </div>
    </div>
  );
}

function Results({
  results,
  reset,
  reopen,
}: {
  results: MeasureOkResponse[];
  reset: () => void;
  reopen: (captureType: CaptureType) => void;
}) {
  const navigate = useNavigate();
  const [shareStatus, setShareStatus] = useState("");
  const [activeSide, setActiveSide] = useState<"Left" | "Right">("Left");
  const [erasing, setErasing] = useState(false);
  const measurements: ResultMeasurement[] = results.flatMap((result) =>
    result.measurements.map((item) => ({
      ...item,
      side: result.capture_type.startsWith("left")
        ? ("Left" as const)
        : ("Right" as const),
      captureType: result.capture_type,
    })),
  );
  if (erasing) return <Navigate to="/" replace />;
  if (measurements.length !== 10)
    return (
      <Navigate
        to={
          results.length === 0
            ? "/recover/session"
            : `/capture/${captureOrder.find((type) => !results.some((r) => r.capture_type === type)) ?? "left_fingers"}`
        }
        replace
      />
    );
  const summary = measurements
    .map(
      (m) =>
        `${m.side} ${m.digit}: ${m.projected_width_mm.toFixed(1)} mm — size ${m.recommended_size}`,
    )
    .join("\n");

  async function copy() {
    if (!navigator.clipboard?.writeText) {
      setShareStatus("Copy is not supported in this browser.");
      return;
    }
    try {
      await navigator.clipboard.writeText(`NailSize AI results\n${summary}`);
      setShareStatus("Results copied. No photos were included.");
    } catch {
      setShareStatus("Results could not be copied. Select the text manually.");
    }
  }

  async function share() {
    if (!navigator.share) {
      await copy();
      return;
    }
    try {
      await navigator.share({
        title: "NailSize AI results",
        text: `NailSize AI results\n${summary}`,
      });
      setShareStatus("Text-only results shared.");
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError"))
        setShareStatus(
          "Sharing was not completed. You can copy the results instead.",
        );
    }
  }

  function retake(measurement: ResultMeasurement) {
    reopen(measurement.captureType);
    navigate(`/capture/${measurement.captureType}`);
  }

  return (
    <div className="page results-page">
      <Eyebrow>Measurement complete</Eyebrow>
      <h1>Your projected nail widths.</h1>
      <p className="lede">
        Send this text-only summary to your nail artist. Fit can still vary by
        tip brand and curvature.
      </p>
      <div className="results-layout">
        <div className="result-summary">
          <div
            className="result-tabs"
            role="tablist"
            aria-label="Choose a hand"
          >
            {(["Left", "Right"] as const).map((side) => (
              <button
                key={side}
                type="button"
                role="tab"
                aria-selected={activeSide === side}
                onClick={() => setActiveSide(side)}
              >
                {side} hand
              </button>
            ))}
          </div>
          <Card className="results-mobile-hand">
            <h2>{activeSide} hand</h2>
            {measurements
              .filter((measurement) => measurement.side === activeSide)
              .map((measurement) => (
                <NailResult
                  key={`${measurement.side}-${measurement.digit}`}
                  measurement={measurement}
                  onRetake={() => retake(measurement)}
                />
              ))}
          </Card>
          <div className="results-desktop-hands">
            {(["Left", "Right"] as const).map((side) => (
              <Card className="hand-panel" key={side}>
                <h2>{side} hand</h2>
                <div className="hand-grid">
                  {measurements
                    .filter((measurement) => measurement.side === side)
                    .map((measurement) => (
                      <NailResult
                        compact
                        key={`${measurement.side}-${measurement.digit}`}
                        measurement={measurement}
                        onRetake={() => retake(measurement)}
                      />
                    ))}
                </div>
              </Card>
            ))}
          </div>
        </div>
        <aside>
          <StatusMessage tone="success">
            <strong>Calibrated result</strong>
            <br />
            All measurements used a detected reference plane.
          </StatusMessage>
          <div className="action-stack">
            <Button onClick={() => void copy()}>Copy results</Button>
            <Button className="button--secondary" onClick={() => void share()}>
              Share results
            </Button>
            <Button
              className="button--secondary"
              onClick={() => {
                setErasing(true);
                reset();
              }}
            >
              Start over and erase session
            </Button>
          </div>
          <p className="share-status" aria-live="polite">
            {shareStatus}
          </p>
        </aside>
      </div>
    </div>
  );
}

function useSession() {
  const tuple = useReducer(sessionReducer, initialSession);
  const stateRef = useRef(tuple[0]);
  stateRef.current = tuple[0];
  useEffect(
    () => () =>
      Object.values(stateRef.current.captures).forEach(
        (capture) => capture && URL.revokeObjectURL(capture.previewUrl),
      ),
    [],
  );
  return tuple;
}

export function App() {
  const [state, dispatch] = useSession();
  const results = useMemo(
    () =>
      Object.values(state.captures).flatMap((capture) =>
        capture?.result ? [capture.result] : [],
      ),
    [state.captures],
  );
  return (
    <Shell>
      <FocusOnNavigation />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/prepare" element={<Preparation />} />
        <Route
          path="/capture/:captureType"
          element={<CapturePage state={state} dispatch={dispatch} />}
        />
        <Route
          path="/quality/:captureType"
          element={<QualityPage state={state} dispatch={dispatch} />}
        />
        <Route path="/processing" element={<Processing results={results} />} />
        <Route
          path="/recover/session"
          element={
            <SessionRecovery reset={() => dispatch({ type: "reset" })} />
          }
        />
        <Route
          path="/results"
          element={
            <Results
              results={results}
              reset={() => dispatch({ type: "reset" })}
              reopen={(captureType) =>
                dispatch({ type: "reopen", captureType })
              }
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
