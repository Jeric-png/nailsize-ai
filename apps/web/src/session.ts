import type {
  CaptureType,
  MeasureOkResponse,
  QualityIssue,
} from "@nailsize/contracts";

export const captureOrder: CaptureType[] = [
  "left_fingers",
  "left_thumb",
  "right_fingers",
  "right_thumb",
];

export interface CaptureRecord {
  file: File;
  previewUrl: string;
  result?: MeasureOkResponse;
  issues?: QualityIssue[];
}

export interface SessionState {
  captures: Partial<Record<CaptureType, CaptureRecord>>;
  activeCapture: CaptureType;
  status: "idle" | "submitting" | "retake" | "complete" | "error";
  error?: string;
}

export type SessionAction =
  | { type: "select"; captureType: CaptureType; record: CaptureRecord }
  | { type: "submitting" }
  | { type: "accepted"; captureType: CaptureType; result: MeasureOkResponse }
  | { type: "retake"; captureType: CaptureType; issues: QualityIssue[] }
  | { type: "error"; message: string }
  | { type: "reset" };

export const initialSession: SessionState = {
  captures: {},
  activeCapture: "left_fingers",
  status: "idle",
};

export function releaseCapture(record: CaptureRecord | undefined): void {
  if (record) URL.revokeObjectURL(record.previewUrl);
}

export function sessionReducer(
  state: SessionState,
  action: SessionAction,
): SessionState {
  switch (action.type) {
    case "select": {
      releaseCapture(state.captures[action.captureType]);
      return {
        ...state,
        status: "idle",
        error: undefined,
        captures: { ...state.captures, [action.captureType]: action.record },
      };
    }
    case "submitting":
      return { ...state, status: "submitting", error: undefined };
    case "accepted": {
      const currentIndex = captureOrder.indexOf(action.captureType);
      const isComplete = currentIndex === captureOrder.length - 1;
      return {
        ...state,
        status: isComplete ? "complete" : "idle",
        activeCapture: isComplete
          ? action.captureType
          : captureOrder[currentIndex + 1],
        captures: {
          ...state.captures,
          [action.captureType]: {
            ...state.captures[action.captureType]!,
            result: action.result,
            issues: undefined,
          },
        },
      };
    }
    case "retake":
      return {
        ...state,
        status: "retake",
        activeCapture: action.captureType,
        captures: {
          ...state.captures,
          [action.captureType]: {
            ...state.captures[action.captureType]!,
            issues: action.issues,
            result: undefined,
          },
        },
      };
    case "error":
      return { ...state, status: "error", error: action.message };
    case "reset":
      Object.values(state.captures).forEach(releaseCapture);
      return initialSession;
  }
}
