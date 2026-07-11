import { useEffect, useMemo, useReducer, useRef } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useParams,
} from "react-router-dom";
import type { CaptureType, MeasureOkResponse } from "@nailsize/contracts";
import { measureCapture } from "./api";
import {
  Button,
  Card,
  Eyebrow,
  ProgressStepper,
  StatusMessage,
} from "./components/Primitives";
import { captureOrder, initialSession, sessionReducer } from "./session";

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
  const captureType = captureOrder.includes(params.captureType as CaptureType)
    ? (params.captureType as CaptureType)
    : "left_fingers";
  const config = captureCopy[captureType];
  const record = state.captures[captureType];
  const step = captureOrder.indexOf(captureType) + 1;

  async function submit() {
    if (!record || state.status === "submitting") return;
    dispatch({ type: "submitting" });
    try {
      const response = await measureCapture(captureType, record.file);
      if (response.status === "retake")
        dispatch({
          type: "retake",
          captureType,
          issues: response.quality_issues,
        });
      else {
        dispatch({ type: "accepted", captureType, result: response });
        navigate(step === 4 ? "/results" : `/capture/${captureOrder[step]}`);
      }
    } catch (error) {
      dispatch({
        type: "error",
        message: error instanceof Error ? error.message : "Upload failed.",
      });
    }
  }

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
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
        capture="environment"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file)
            dispatch({
              type: "select",
              captureType,
              record: { file, previewUrl: URL.createObjectURL(file) },
            });
        }}
      />
      {record?.issues?.map((issue) => (
        <StatusMessage key={issue.code} tone="error">
          <strong>{issue.message}</strong>
          <br />
          {issue.correction}
        </StatusMessage>
      ))}
      {state.error && <StatusMessage tone="error">{state.error}</StatusMessage>}
      <div className="action-stack">
        <Button
          onClick={() => inputRef.current?.click()}
          className={record ? "button--secondary" : ""}
        >
          {record ? "Choose another photo" : "Take or choose photo"}
        </Button>
        <Button
          onClick={submit}
          disabled={!record || state.status === "submitting"}
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

function Results({
  results,
  reset,
}: {
  results: MeasureOkResponse[];
  reset: () => void;
}) {
  const navigate = useNavigate();
  const measurements = results.flatMap((result) =>
    result.measurements.map((item) => ({
      ...item,
      side: result.capture_type.startsWith("left") ? "Left" : "Right",
    })),
  );
  if (measurements.length !== 10)
    return (
      <Navigate
        to={`/capture/${captureOrder.find((type) => !results.some((r) => r.capture_type === type)) ?? "left_fingers"}`}
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
    await navigator.clipboard.writeText(`NailSize AI results\n${summary}`);
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
        <Card className="result-summary">
          <h2>All ten nails</h2>
          {measurements.map((m) => (
            <div className="measurement-row" key={`${m.side}-${m.digit}`}>
              <div>
                <strong>
                  {m.side} {m.digit}
                </strong>
                <span>
                  {m.confidence} confidence · ±{m.uncertainty_mm.toFixed(1)} mm
                </span>
              </div>
              <div className="measurement-value">
                <strong>{m.projected_width_mm.toFixed(1)} mm</strong>
                <span>
                  Size {m.recommended_size}
                  {m.alternate_size ? ` / ${m.alternate_size}` : ""}
                </span>
              </div>
            </div>
          ))}
        </Card>
        <aside>
          <StatusMessage tone="success">
            <strong>Calibrated result</strong>
            <br />
            All measurements used a detected reference plane.
          </StatusMessage>
          <div className="action-stack">
            <Button onClick={copy}>Copy results</Button>
            <Button
              className="button--secondary"
              onClick={() => {
                reset();
                navigate("/");
              }}
            >
              Start over and erase session
            </Button>
          </div>
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
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/prepare" element={<Preparation />} />
        <Route
          path="/capture/:captureType"
          element={<CapturePage state={state} dispatch={dispatch} />}
        />
        <Route
          path="/results"
          element={
            <Results
              results={results}
              reset={() => dispatch({ type: "reset" })}
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
