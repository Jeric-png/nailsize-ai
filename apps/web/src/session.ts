import {
  captureOrder,
  compareSamples,
  isCaptureConsistent,
  type CaptureResult,
  type CaptureType,
  type CoinMarkers,
  type ImageDimensions,
  type SampleMeasurement,
} from "./guidedSizing";

export type SampleNumber = 1 | 2;

export interface SampleRecord {
  previewUrl: string;
  fingerprint: string;
  dimensions: ImageDimensions;
  coinMarkers?: CoinMarkers;
  measurements?: SampleMeasurement[];
}

export interface CaptureRecord {
  samples: Partial<Record<SampleNumber, SampleRecord>>;
  result?: CaptureResult;
}

export interface SessionState {
  coinConfirmed: boolean;
  captures: Partial<Record<CaptureType, CaptureRecord>>;
  activeCapture: CaptureType;
  correctionCapture?: CaptureType;
}

export type SessionAction =
  | { type: "confirmCoin"; confirmed: boolean }
  | {
      type: "selectPhoto";
      captureType: CaptureType;
      sample: SampleNumber;
      previewUrl: string;
      fingerprint: string;
      dimensions: ImageDimensions;
    }
  | {
      type: "saveCalibration";
      captureType: CaptureType;
      sample: SampleNumber;
      coinMarkers: CoinMarkers;
    }
  | {
      type: "completeSample";
      captureType: CaptureType;
      sample: SampleNumber;
      coinMarkers: CoinMarkers;
      measurements: SampleMeasurement[];
    }
  | { type: "accept"; captureType: CaptureType }
  | { type: "clearSample"; captureType: CaptureType; sample: SampleNumber }
  | { type: "reopen"; captureType: CaptureType }
  | { type: "finishCorrection" }
  | { type: "reset" };

export const initialSession: SessionState = {
  coinConfirmed: false,
  captures: {},
  activeCapture: "left_fingers",
};

export function releaseSample(sample: SampleRecord | undefined): void {
  if (sample) URL.revokeObjectURL(sample.previewUrl);
}

export function releaseCapture(record: CaptureRecord | undefined): void {
  if (!record) return;
  releaseSample(record.samples[1]);
  releaseSample(record.samples[2]);
}

export function releaseSession(state: SessionState): void {
  Object.values(state.captures).forEach(releaseCapture);
}

export function sessionReducer(
  state: SessionState,
  action: SessionAction,
): SessionState {
  if (
    !state.coinConfirmed &&
    action.type !== "confirmCoin" &&
    action.type !== "reset"
  ) {
    if (action.type === "selectPhoto") URL.revokeObjectURL(action.previewUrl);
    return state;
  }

  switch (action.type) {
    case "confirmCoin":
      if (action.confirmed === state.coinConfirmed) return state;
      if (!action.confirmed) {
        releaseSession(state);
        return initialSession;
      }
      return { ...state, coinConfirmed: true };

    case "selectPhoto": {
      const current = state.captures[action.captureType];
      const retainedFirst = current?.samples[1];
      if (
        action.sample === 2 &&
        (!retainedFirst || retainedFirst.fingerprint === action.fingerprint)
      ) {
        URL.revokeObjectURL(action.previewUrl);
        return state;
      }
      if (action.sample === 1) releaseCapture(current);
      else releaseSample(current?.samples[2]);
      const retainedSamples =
        action.sample === 2 && retainedFirst ? { 1: retainedFirst } : {};
      return {
        ...state,
        activeCapture: action.captureType,
        captures: {
          ...state.captures,
          [action.captureType]: {
            samples: {
              ...retainedSamples,
              [action.sample]: {
                previewUrl: action.previewUrl,
                fingerprint: action.fingerprint,
                dimensions: action.dimensions,
              },
            },
          },
        },
      };
    }

    case "saveCalibration":
    case "completeSample": {
      const current = state.captures[action.captureType];
      const sample = current?.samples[action.sample];
      if (!current || !sample) return state;
      const updatedSample: SampleRecord = {
        ...sample,
        coinMarkers: action.coinMarkers,
        ...(action.type === "completeSample"
          ? { measurements: action.measurements }
          : {}),
      };
      return {
        ...state,
        captures: {
          ...state.captures,
          [action.captureType]: {
            ...current,
            result: undefined,
            samples: { ...current.samples, [action.sample]: updatedSample },
          },
        },
      };
    }

    case "accept": {
      const current = state.captures[action.captureType];
      const firstRecord = current?.samples[1];
      const verificationRecord = current?.samples[2];
      const first = firstRecord?.measurements;
      const verification = verificationRecord?.measurements;
      if (
        !current ||
        !first ||
        !verification ||
        firstRecord.fingerprint === verificationRecord.fingerprint
      )
        return state;
      let result: CaptureResult;
      try {
        result = compareSamples(action.captureType, first, verification);
      } catch {
        return state;
      }
      if (!isCaptureConsistent(result)) return state;
      const currentIndex = captureOrder.indexOf(action.captureType);
      const nextCapture = captureOrder[currentIndex + 1];
      releaseCapture(current);
      return {
        ...state,
        activeCapture: nextCapture ?? action.captureType,
        captures: {
          ...state.captures,
          [action.captureType]: {
            samples: {},
            result,
          },
        },
      };
    }

    case "clearSample": {
      const current = state.captures[action.captureType];
      if (!current) return state;
      if (action.sample === 1) {
        releaseCapture(current);
        return {
          ...state,
          captures: {
            ...state.captures,
            [action.captureType]: { samples: {} },
          },
        };
      }
      releaseSample(current.samples[2]);
      return {
        ...state,
        captures: {
          ...state.captures,
          [action.captureType]: {
            samples: current.samples[1] ? { 1: current.samples[1] } : {},
          },
        },
      };
    }

    case "reopen":
      releaseCapture(state.captures[action.captureType]);
      return {
        ...state,
        activeCapture: action.captureType,
        correctionCapture: action.captureType,
        captures: {
          ...state.captures,
          [action.captureType]: { samples: {} },
        },
      };

    case "finishCorrection":
      return { ...state, correctionCapture: undefined };

    case "reset":
      releaseSession(state);
      return initialSession;
  }
}
