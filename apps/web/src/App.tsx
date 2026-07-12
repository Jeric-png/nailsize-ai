import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { captureCopy } from "./captureConfig";
import { CaptureRoute, GuideRoute } from "./components/GuidedCapture";
import { Button, Card, Eyebrow, StatusMessage } from "./components/Primitives";
import {
  COIN_DIAMETER_MM,
  captureOrder,
  type CaptureResult,
  type CaptureType,
  type FinalMeasurement,
} from "./guidedSizing";
import {
  initialSession,
  releaseSession,
  sessionReducer,
  type SessionAction,
  type SessionState,
} from "./session";

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

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <header className="site-header">
        <Link to="/" className="brand">
          NAILSIZE / GUIDE
        </Link>
        <span>Dataset-free sizing</span>
      </header>
      <main>{children}</main>
      <footer className="site-footer">
        <span>Photos stay in this browser and are never uploaded.</span>
        <Link to="/privacy">Privacy notice</Link>
      </footer>
    </div>
  );
}

function Landing() {
  return (
    <div className="page landing">
      <Eyebrow>Guided press-on nail measurement</Eyebrow>
      <h1>Measure every nail without an AI training dataset.</h1>
      <p className="lede">
        Use a current Singapore 50-cent coin as the scale, place the measurement
        markers yourself, and verify every width with a second photo.
      </p>
      <div className="hero-placeholder" aria-hidden="true">
        <span>HAND + 50-CENT REFERENCE</span>
      </div>
      <Card>
        <h2>What you will need</h2>
        <ul className="check-list">
          <li>Bare, natural nails</li>
          <li>Bright, even lighting</li>
          <li>One current Third Series Singapore 50-cent coin</li>
          <li>About eight minutes</li>
        </ul>
      </Card>
      <Link className="button" to="/prepare">
        Start guided sizing
      </Link>
      <p className="fine-print">
        This tool measures visible, projected width. It does not measure the
        curved surface of highly arched nails or guarantee fit.
      </p>
    </div>
  );
}

function Preparation({
  state,
  dispatch,
}: {
  state: SessionState;
  dispatch: React.Dispatch<SessionAction>;
}) {
  const navigate = useNavigate();
  const steps = [
    [
      "01",
      "Prepare your nails",
      "Remove polish and press-ons. Keep every sidewall visible.",
    ],
    [
      "02",
      "Confirm the coin",
      "Use only the silver Third Series 50-cent coin showing the Port of Singapore and a large 50 with CENTS.",
    ],
    [
      "03",
      "Place the reference",
      "Lay the coin flat beside the nails on the same surface. Keep the full rim visible and avoid glare.",
    ],
    [
      "04",
      "Photograph from above",
      "Hold the phone directly overhead. A tilted coin looks oval and the app will reject it.",
    ],
  ];
  return (
    <div className="page">
      <Eyebrow>Before you begin</Eyebrow>
      <h1>Confirm your Singapore 50-cent reference.</h1>
      <p className="lede">
        The current Third Series coin is {COIN_DIAMETER_MM.toFixed(1)} mm wide.
        The app uses its marked rim to turn nearby nail widths into millimetres.
      </p>

      <Card className="coin-reference-card">
        <h2>Accepted reference</h2>
        <p>
          Third Series Singapore 50-cent circulation coin: silver-coloured,
          round with a micro-scalloped edge, Port of Singapore, large “50” and
          “CENTS”.
        </p>
        <p className="fine-print">
          Do not use a flower, fish, commemorative, damaged, or foreign coin.
          Older Singapore 50-cent coins are legal tender but have a different
          diameter.
        </p>
        <label className="coin-confirmation">
          <input
            type="checkbox"
            checked={state.coinConfirmed}
            onChange={(event) =>
              dispatch({
                type: "confirmCoin",
                confirmed: event.currentTarget.checked,
              })
            }
          />
          <span>
            I have the Third Series Port of Singapore 50-cent coin described
            above.
          </span>
        </label>
      </Card>

      <div className="instruction-list">
        {steps.map(([number, title, body]) => (
          <Card key={number}>
            <span className="instruction-number">{number}</span>
            <div>
              <h2>{title}</h2>
              <p>{body}</p>
            </div>
          </Card>
        ))}
      </div>
      <StatusMessage>
        <strong>How it works:</strong> you will place eight markers around the
        coin rim, then mark both sides of each nail. A new second photo must
        agree within the repeatability limit.
      </StatusMessage>
      <StatusMessage tone="success">
        <strong>Private by design:</strong> all geometry is calculated in this
        browser. Photos are not sent to OpenAI, Vercel functions, or any
        inference service.
      </StatusMessage>
      <Button
        disabled={!state.coinConfirmed}
        onClick={() => navigate("/capture/left_fingers/1")}
      >
        I’m ready
      </Button>
    </div>
  );
}

function PrivacyNotice() {
  return (
    <div className="page policy-page">
      <Eyebrow>Privacy notice</Eyebrow>
      <h1>Your nail photos never leave this browser.</h1>
      <p className="lede">
        NailSize Guide performs coin calibration, nail-edge measurement, repeat
        comparison, and size-chart mapping on your device.
      </p>
      <Card>
        <h2>No image upload</h2>
        <p>
          The application does not send selected photos to an API, model
          provider, database, object store, analytics service, or training
          workflow.
        </p>
      </Card>
      <Card>
        <h2>Temporary browser memory</h2>
        <p>
          A local preview exists only while you mark a capture. Its object URL
          is released when that capture is accepted, replaced, restarted, or the
          session is erased.
        </p>
      </Card>
      <Card>
        <h2>Results are not saved</h2>
        <p>
          Measurements live only in the current page session. Reloading or
          closing the page clears them. Copying or sharing sends text only when
          you choose that action.
        </p>
      </Card>
      <Card>
        <h2>No training dataset</h2>
        <p>
          This release uses deterministic coin geometry and user-confirmed
          markers. It does not train or run a nail-recognition model.
        </p>
      </Card>
      <Link className="button button--secondary" to="/">
        Return home
      </Link>
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
        when the page session ends, so you will need to repeat the guided
        measurements.
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

type ResultMeasurement = FinalMeasurement & {
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
          Two-photo difference: {measurement.repeatDeltaMm.toFixed(2)} mm
        </span>
        <button type="button" className="text-button" onClick={onRetake}>
          Remeasure
        </button>
      </div>
      <div className="measurement-value">
        <strong>{measurement.projectedWidthMm.toFixed(1)} mm</strong>
        <span>
          {measurement.recommendedSize
            ? `Recommended size ${measurement.recommendedSize}`
            : "Outside default chart"}
        </span>
        {measurement.alternateSize && (
          <span className="measurement-boundary-warning">
            Average-only size {measurement.alternateSize} may be too narrow;
            confirm physically.
          </span>
        )}
      </div>
    </div>
  );
}

function Results({
  results,
  reset,
  reopen,
}: {
  results: CaptureResult[];
  reset: () => void;
  reopen: (captureType: CaptureType) => void;
}) {
  const navigate = useNavigate();
  const [shareStatus, setShareStatus] = useState("");
  const [activeSide, setActiveSide] = useState<"Left" | "Right">("Left");
  const [erasing, setErasing] = useState(false);
  const measurements: ResultMeasurement[] = results.flatMap((result) =>
    result.measurements.map((measurement) => ({
      ...measurement,
      side: captureCopy[result.captureType].side,
      captureType: result.captureType,
    })),
  );

  if (erasing) return <Navigate to="/" replace />;
  if (measurements.length !== 10) {
    const missing = captureOrder.find(
      (captureType) =>
        !results.some((result) => result.captureType === captureType),
    );
    return (
      <Navigate
        to={
          results.length === 0
            ? "/recover/session"
            : `/capture/${missing ?? "left_fingers"}/1`
        }
        replace
      />
    );
  }

  const summary = measurements
    .map((measurement) => {
      const size = measurement.recommendedSize
        ? `recommended size ${measurement.recommendedSize}${measurement.alternateSize ? `; average-only boundary size ${measurement.alternateSize} may be too narrow and needs physical confirmation` : ""}`
        : "manual chart check";
      return `${measurement.side} ${measurement.digit}: ${measurement.projectedWidthMm.toFixed(1)} mm average; ${measurement.sizingWidthMm.toFixed(1)} mm sizing width — ${size}`;
    })
    .join("\n");
  const shareText = [
    "NailSize guided projected-width results",
    "Method: guided-sg50-coin-v1; Third Series Singapore 50-cent reference; provisional tip chart.",
    "Top-down widths do not measure nail curvature or guarantee press-on fit. Confirm with the nail artist or a physical sizing kit.",
    summary,
  ].join("\n");

  async function copy() {
    if (!navigator.clipboard?.writeText) {
      setShareStatus("Copy is not supported in this browser.");
      return;
    }
    try {
      await navigator.clipboard.writeText(shareText);
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
        title: "NailSize guided results",
        text: shareText,
      });
      setShareStatus("Text-only results shared.");
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError"))
        setShareStatus("Sharing was not completed. Copy the results instead.");
    }
  }

  function retake(measurement: ResultMeasurement) {
    reopen(measurement.captureType);
    navigate(`/capture/${measurement.captureType}/1`);
  }

  return (
    <div className="page results-page">
      <Eyebrow>Guided measurement complete</Eyebrow>
      <h1>Your projected nail widths.</h1>
      <p className="lede">
        Send this text-only summary to your nail artist. Each recommendation
        uses the wider of two agreeing readings so the selected tip is not
        narrower than either measurement.
      </p>
      <div className="results-layout">
        <div className="result-summary">
          <div className="result-tabs" role="group" aria-label="Choose a hand">
            {(["Left", "Right"] as const).map((side) => (
              <button
                key={side}
                type="button"
                aria-pressed={activeSide === side}
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
            <strong>Two-photo agreement passed</strong>
            <br />
            These are guided projected-width measurements, not validated fit
            claims.
          </StatusMessage>
          <StatusMessage>
            Strong nail curvature can make the visible top-down width differ
            from the curved tip surface. Ask the artist for a sizing kit when in
            doubt.
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
  useEffect(() => () => releaseSession(stateRef.current), []);
  return tuple;
}

export function App() {
  const [state, dispatch] = useSession();
  const results = useMemo(
    () =>
      captureOrder.flatMap((captureType) => {
        const result = state.captures[captureType]?.result;
        return result ? [result] : [];
      }),
    [state.captures],
  );

  return (
    <Shell>
      <FocusOnNavigation />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/privacy" element={<PrivacyNotice />} />
        <Route
          path="/prepare"
          element={<Preparation state={state} dispatch={dispatch} />}
        />
        <Route
          path="/capture/:captureType/:sample"
          element={<CaptureRoute state={state} dispatch={dispatch} />}
        />
        <Route
          path="/guide/:captureType/:sample"
          element={<GuideRoute state={state} dispatch={dispatch} />}
        />
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
