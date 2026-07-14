import * as ort from "onnxruntime-web/wasm";
import { AUTO_SG50_TWO_HAND_METHOD_MANIFEST } from "./manifest";
import {
  postprocessYoloV8Seg,
  type YoloV8SegDetection,
  type YoloV8SegPostprocessOptions,
} from "./yoloV8SegPostprocess";
import { preprocessYoloRgba, type RgbaImageData } from "./yoloPreprocess";

export const NAIL_SEGMENTATION_MODEL_URL =
  "/models/nails_seg_s_yolov8_v1.onnx" as const;
export const ONNX_WASM_PATHS = Object.freeze({
  mjs: "/ort/ort-wasm-simd-threaded.mjs",
  wasm: "/ort/ort-wasm-simd-threaded.wasm",
});

const RUNTIME_CONTRACT =
  AUTO_SG50_TWO_HAND_METHOD_MANIFEST.nailSegmentationModel.runtime;

export type NailSegmentationRuntimeErrorCode =
  | "model-fetch-failed"
  | "model-integrity-unavailable"
  | "model-integrity-failed"
  | "runtime-unavailable"
  | "model-contract-mismatch"
  | "inference-failed";

export class NailSegmentationRuntimeError extends Error {
  readonly name = "NailSegmentationRuntimeError";

  constructor(
    readonly code: NailSegmentationRuntimeErrorCode,
    message: string,
    readonly recovery: string,
    options?: ErrorOptions,
  ) {
    super(message, options);
  }
}

interface ModelResponse {
  readonly ok: boolean;
  readonly status: number;
  arrayBuffer(): Promise<ArrayBuffer>;
}

export type ModelFetch = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<ModelResponse>;

export interface Sha256Digester {
  digest(data: Uint8Array): Promise<ArrayBuffer>;
}

export interface OnnxValueMetadataAdapter {
  readonly name: string;
  readonly isTensor: boolean;
  readonly type?: string;
  readonly shape?: readonly (number | string)[];
}

export interface OnnxSessionAdapter {
  readonly inputNames: readonly string[];
  readonly outputNames: readonly string[];
  readonly inputMetadata: readonly OnnxValueMetadataAdapter[];
  readonly outputMetadata: readonly OnnxValueMetadataAdapter[];
  run(
    feeds: Readonly<Record<string, unknown>>,
    outputNames: readonly string[],
  ): Promise<Readonly<Record<string, unknown>>>;
  release?(): Promise<void>;
}

export interface OnnxRuntimeAdapter {
  configure(): void;
  createSession(modelBytes: Uint8Array): Promise<OnnxSessionAdapter>;
  createFloat32Tensor(
    data: Float32Array,
    dimensions: readonly number[],
  ): unknown;
}

export interface OnnxNailSegmenterDependencies {
  readonly fetchModel?: ModelFetch;
  readonly sha256?: Sha256Digester;
  readonly runtime?: OnnxRuntimeAdapter;
}

export class OnnxNailSegmenter {
  private sessionPromise: Promise<OnnxSessionAdapter> | undefined;
  private readonly fetchModel: ModelFetch;
  private readonly sha256: Sha256Digester;
  private readonly runtime: OnnxRuntimeAdapter;

  constructor(dependencies: OnnxNailSegmenterDependencies = {}) {
    this.fetchModel = dependencies.fetchModel ?? defaultModelFetch;
    this.sha256 = dependencies.sha256 ?? defaultSha256Digester;
    this.runtime = dependencies.runtime ?? browserOnnxRuntime;
  }

  /** Loads and verifies the model without retaining or processing a photo. */
  async warmup(): Promise<void> {
    await this.getSession();
  }

  /**
   * Runs fully in the browser. Only the immutable same-origin model asset is
   * fetched; photo pixels are never passed to fetch or another service.
   */
  async segment(
    image: RgbaImageData,
    postprocessOptions: YoloV8SegPostprocessOptions = {},
  ): Promise<YoloV8SegDetection[]> {
    const preprocessed = preprocessYoloRgba(image);

    try {
      const session = await this.getSession();
      let inputTensor: unknown;
      try {
        inputTensor = this.runtime.createFloat32Tensor(
          preprocessed.data,
          RUNTIME_CONTRACT.input.shape,
        );
      } catch (cause) {
        throw new NailSegmentationRuntimeError(
          "inference-failed",
          "Automatic nail detection could not prepare this photo.",
          "Try the photo again. If it still fails, reload the app.",
          { cause },
        );
      }
      let outputs: Readonly<Record<string, unknown>>;

      try {
        outputs = await session.run(
          { [RUNTIME_CONTRACT.input.name]: inputTensor },
          RUNTIME_CONTRACT.outputs.map(({ name }) => name),
        );
      } catch (cause) {
        throw new NailSegmentationRuntimeError(
          "inference-failed",
          "Automatic nail detection could not process this photo.",
          "Try the photo again. If it still fails, retake it in even lighting.",
          { cause },
        );
      }

      const [detectionsOutput, prototypesOutput] =
        validateInferenceOutputs(outputs);

      try {
        return postprocessYoloV8Seg(
          {
            output0: detectionsOutput,
            output1: prototypesOutput,
            letterbox: preprocessed.letterbox,
          },
          postprocessOptions,
        );
      } catch (cause) {
        throw new NailSegmentationRuntimeError(
          "model-contract-mismatch",
          "The nail model output could not be decoded safely.",
          "Stop sizing and reload the latest version of the app.",
          { cause },
        );
      }
    } finally {
      preprocessed.data.fill(0);
    }
  }

  private getSession(): Promise<OnnxSessionAdapter> {
    if (this.sessionPromise) return this.sessionPromise;

    const pendingSession = this.loadSession();
    this.sessionPromise = pendingSession;
    void pendingSession.catch(() => {
      if (this.sessionPromise === pendingSession)
        this.sessionPromise = undefined;
    });
    return pendingSession;
  }

  private async loadSession(): Promise<OnnxSessionAdapter> {
    const modelBytes = await this.fetchAndVerifyModel();

    try {
      this.runtime.configure();
    } catch (cause) {
      throw new NailSegmentationRuntimeError(
        "runtime-unavailable",
        "This browser could not initialize private on-device nail detection.",
        "Update the browser or try another current browser.",
        { cause },
      );
    }

    let session: OnnxSessionAdapter;
    try {
      session = await this.runtime.createSession(modelBytes);
    } catch (cause) {
      throw new NailSegmentationRuntimeError(
        "runtime-unavailable",
        "This browser could not start the verified nail model.",
        "Reload the app. If it still fails, try another current browser.",
        { cause },
      );
    }

    try {
      validateSessionContract(session);
    } catch (cause) {
      await session.release?.().catch(() => undefined);
      if (cause instanceof NailSegmentationRuntimeError) throw cause;
      throw new NailSegmentationRuntimeError(
        "model-contract-mismatch",
        "The installed nail model does not match this app version.",
        "Stop sizing and reload the latest version of the app.",
        { cause },
      );
    }

    return session;
  }

  private async fetchAndVerifyModel(): Promise<Uint8Array> {
    let response: ModelResponse;
    try {
      response = await this.fetchModel(NAIL_SEGMENTATION_MODEL_URL, {
        cache: "force-cache",
        credentials: "same-origin",
        mode: "same-origin",
      });
    } catch (cause) {
      throw new NailSegmentationRuntimeError(
        "model-fetch-failed",
        "The on-device nail model could not be loaded from this app.",
        "Check the connection, then refresh and try again.",
        { cause },
      );
    }

    if (!response.ok) {
      throw new NailSegmentationRuntimeError(
        "model-fetch-failed",
        `The on-device nail model returned HTTP ${response.status}.`,
        "Refresh and try again. If it continues, the app deployment needs repair.",
      );
    }

    let modelBytes: Uint8Array;
    try {
      modelBytes = new Uint8Array(await response.arrayBuffer());
    } catch (cause) {
      throw new NailSegmentationRuntimeError(
        "model-fetch-failed",
        "The on-device nail model download was incomplete.",
        "Check the connection, then refresh and try again.",
        { cause },
      );
    }

    let actualHash: string;
    try {
      actualHash = bytesToHex(await this.sha256.digest(modelBytes));
    } catch (cause) {
      throw new NailSegmentationRuntimeError(
        "model-integrity-unavailable",
        "This browser could not verify the nail model before running it.",
        "Stop sizing and use a current browser with secure-context support.",
        { cause },
      );
    }

    if (actualHash !== RUNTIME_CONTRACT.sha256) {
      modelBytes.fill(0);
      throw new NailSegmentationRuntimeError(
        "model-integrity-failed",
        "The downloaded nail model failed its integrity check.",
        "Stop sizing and reload. The app must never run an unverified model.",
      );
    }

    return modelBytes;
  }
}

export function createOnnxNailSegmenter(
  dependencies: OnnxNailSegmenterDependencies = {},
): OnnxNailSegmenter {
  return new OnnxNailSegmenter(dependencies);
}

let singletonSegmenter: OnnxNailSegmenter | undefined;

export function getOnnxNailSegmenter(): OnnxNailSegmenter {
  singletonSegmenter ??= createOnnxNailSegmenter();
  return singletonSegmenter;
}

const defaultModelFetch: ModelFetch = (input, init) => fetch(input, init);

const defaultSha256Digester: Sha256Digester = {
  async digest(data) {
    if (!globalThis.crypto?.subtle) {
      throw new Error("Web Crypto is unavailable");
    }
    const buffer =
      data.buffer instanceof ArrayBuffer &&
      data.byteOffset === 0 &&
      data.byteLength === data.buffer.byteLength
        ? data.buffer
        : Uint8Array.from(data).buffer;
    return globalThis.crypto.subtle.digest("SHA-256", buffer);
  },
};

const browserOnnxRuntime: OnnxRuntimeAdapter = {
  configure() {
    ort.env.wasm.wasmPaths = ONNX_WASM_PATHS;
    const hardwareConcurrency = globalThis.navigator?.hardwareConcurrency ?? 2;
    ort.env.wasm.numThreads = globalThis.crossOriginIsolated
      ? Math.min(Math.max(hardwareConcurrency, 1), 4)
      : 1;
  },
  async createSession(modelBytes) {
    const session = await ort.InferenceSession.create(modelBytes, {
      executionProviders: ["wasm"],
      executionMode: "sequential",
      graphOptimizationLevel: "all",
    });
    return {
      inputNames: session.inputNames,
      outputNames: session.outputNames,
      inputMetadata: session.inputMetadata,
      outputMetadata: session.outputMetadata,
      run: (feeds, outputNames) =>
        session.run(feeds as ort.InferenceSession.FeedsType, outputNames),
      release: () => session.release(),
    };
  },
  createFloat32Tensor(data, dimensions) {
    return new ort.Tensor("float32", data, dimensions);
  },
};

function validateSessionContract(session: OnnxSessionAdapter) {
  const expectedInputs = [RUNTIME_CONTRACT.input];
  const expectedOutputs = [...RUNTIME_CONTRACT.outputs];

  assertExactNames(
    session.inputNames,
    expectedInputs.map(({ name }) => name),
    "input",
  );
  assertExactNames(
    session.outputNames,
    expectedOutputs.map(({ name }) => name),
    "output",
  );
  assertExactMetadata(session.inputMetadata, expectedInputs, "input");
  assertExactMetadata(session.outputMetadata, expectedOutputs, "output");
}

function assertExactNames(
  actual: readonly string[],
  expected: readonly string[],
  kind: "input" | "output",
) {
  if (!arraysEqual(actual, expected)) {
    throw new NailSegmentationRuntimeError(
      "model-contract-mismatch",
      `The nail model ${kind} names do not match the pinned manifest.`,
      "Stop sizing and reload the latest version of the app.",
    );
  }
}

function assertExactMetadata(
  actual: readonly OnnxValueMetadataAdapter[],
  expected: readonly {
    readonly name: string;
    readonly dataType: "float32";
    readonly shape: readonly number[];
  }[],
  kind: "input" | "output",
) {
  if (actual.length !== expected.length) {
    throw new NailSegmentationRuntimeError(
      "model-contract-mismatch",
      `The nail model ${kind} metadata count does not match the pinned manifest.`,
      "Stop sizing and reload the latest version of the app.",
    );
  }

  expected.forEach((contract, index) => {
    const metadata = actual[index];
    if (
      !metadata ||
      metadata.name !== contract.name ||
      !metadata.isTensor ||
      metadata.type !== contract.dataType ||
      !metadata.shape ||
      !arraysEqual(metadata.shape, contract.shape)
    ) {
      throw new NailSegmentationRuntimeError(
        "model-contract-mismatch",
        `The nail model ${kind} tensor ${contract.name} does not match the pinned type and shape.`,
        "Stop sizing and reload the latest version of the app.",
      );
    }
  });
}

function validateInferenceOutputs(
  outputs: Readonly<Record<string, unknown>>,
): readonly [Float32Array, Float32Array] {
  const expectedNames = RUNTIME_CONTRACT.outputs.map(({ name }) => name);
  const actualNames = Object.keys(outputs);
  if (
    actualNames.length !== expectedNames.length ||
    expectedNames.some((name) => !actualNames.includes(name))
  ) {
    throw new NailSegmentationRuntimeError(
      "model-contract-mismatch",
      "The nail model inference output names do not match the pinned manifest.",
      "Stop sizing and reload the latest version of the app.",
    );
  }

  const validated = RUNTIME_CONTRACT.outputs.map((contract) => {
    const value = outputs[contract.name];
    if (!isRecord(value)) {
      throw outputMismatch(contract.name);
    }

    const data = value.data;
    const dimensions = value.dims;
    const expectedLength = contract.shape.reduce<number>(
      (product, dimension) => product * dimension,
      1,
    );
    if (
      value.type !== contract.dataType ||
      !Array.isArray(dimensions) ||
      !arraysEqual(dimensions, contract.shape) ||
      !(data instanceof Float32Array) ||
      data.length !== expectedLength
    ) {
      throw outputMismatch(contract.name);
    }
    return data;
  });

  return [validated[0]!, validated[1]!];
}

function outputMismatch(name: string) {
  return new NailSegmentationRuntimeError(
    "model-contract-mismatch",
    `The nail model output tensor ${name} does not match the pinned type and shape.`,
    "Stop sizing and reload the latest version of the app.",
  );
}

function bytesToHex(buffer: ArrayBuffer) {
  return Array.from(new Uint8Array(buffer), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function arraysEqual(actual: readonly unknown[], expected: readonly unknown[]) {
  return (
    actual.length === expected.length &&
    actual.every((value, index) => value === expected[index])
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
