import { describe, expect, it, vi } from "vitest";
import { AUTO_SG50_TWO_HAND_METHOD_MANIFEST } from "./manifest";
import {
  createOnnxNailSegmenter,
  NAIL_SEGMENTATION_MODEL_URL,
  type ModelFetch,
  type OnnxRuntimeAdapter,
  type OnnxSessionAdapter,
  type OnnxValueMetadataAdapter,
  type Sha256Digester,
} from "./onnxNailSegmenter";

const CONTRACT =
  AUTO_SG50_TWO_HAND_METHOD_MANIFEST.nailSegmentationModel.runtime;
const EXPECTED_DIGEST = hexToBytes(CONTRACT.sha256);

function validMetadata(): {
  inputs: OnnxValueMetadataAdapter[];
  outputs: OnnxValueMetadataAdapter[];
} {
  return {
    inputs: [
      {
        name: CONTRACT.input.name,
        isTensor: true,
        type: CONTRACT.input.dataType,
        shape: [...CONTRACT.input.shape],
      },
    ],
    outputs: CONTRACT.outputs.map((output) => ({
      name: output.name,
      isTensor: true,
      type: output.dataType,
      shape: [...output.shape],
    })),
  };
}

function validOutputs(): Readonly<Record<string, unknown>> {
  return Object.fromEntries(
    CONTRACT.outputs.map((output) => [
      output.name,
      {
        type: output.dataType,
        dims: [...output.shape],
        data: new Float32Array(
          output.shape.reduce<number>(
            (product, dimension) => product * dimension,
            1,
          ),
        ),
      },
    ]),
  );
}

function createHarness(
  options: {
    digest?: Uint8Array;
    outputs?: Readonly<Record<string, unknown>>;
    outputMetadata?: OnnxSessionAdapter["outputMetadata"];
    fetchStatus?: number;
  } = {},
) {
  const modelBytes = new Uint8Array([7, 11, 13, 17]);
  const fetchModel = vi.fn<ModelFetch>(async () => ({
    ok:
      (options.fetchStatus ?? 200) >= 200 && (options.fetchStatus ?? 200) < 300,
    status: options.fetchStatus ?? 200,
    arrayBuffer: async () => modelBytes.buffer,
  }));
  const digest = vi.fn<Sha256Digester["digest"]>(
    async () => (options.digest ?? EXPECTED_DIGEST).slice().buffer,
  );
  const metadata = validMetadata();
  const run = vi.fn<OnnxSessionAdapter["run"]>(
    async () => options.outputs ?? validOutputs(),
  );
  const release = vi.fn(async () => undefined);
  const session: OnnxSessionAdapter = {
    inputNames: [CONTRACT.input.name],
    outputNames: CONTRACT.outputs.map(({ name }) => name),
    inputMetadata: metadata.inputs,
    outputMetadata: options.outputMetadata ?? metadata.outputs,
    run,
    release,
  };
  const configure = vi.fn();
  const createSession = vi.fn<OnnxRuntimeAdapter["createSession"]>(
    async () => session,
  );
  const createFloat32Tensor = vi.fn<OnnxRuntimeAdapter["createFloat32Tensor"]>(
    (data, dimensions) => ({
      type: "float32",
      dims: [...dimensions],
      firstRedValue: data[0],
    }),
  );
  const runtime: OnnxRuntimeAdapter = {
    configure,
    createSession,
    createFloat32Tensor,
  };
  const sha256: Sha256Digester = { digest };

  return {
    modelBytes,
    fetchModel,
    digest,
    run,
    release,
    configure,
    createSession,
    createFloat32Tensor,
    runtime,
    sha256,
  };
}

describe("OnnxNailSegmenter", () => {
  it("lazy-loads one same-origin session and verifies the hash first", async () => {
    const harness = createHarness();
    const segmenter = createOnnxNailSegmenter(harness);

    expect(harness.fetchModel).not.toHaveBeenCalled();
    await Promise.all([segmenter.warmup(), segmenter.warmup()]);

    expect(harness.fetchModel).toHaveBeenCalledTimes(1);
    expect(harness.fetchModel).toHaveBeenCalledWith(
      NAIL_SEGMENTATION_MODEL_URL,
      {
        cache: "force-cache",
        credentials: "same-origin",
        mode: "same-origin",
      },
    );
    expect(harness.digest).toHaveBeenCalledTimes(1);
    expect(harness.configure).toHaveBeenCalledTimes(1);
    expect(harness.createSession).toHaveBeenCalledTimes(1);
    expect(harness.digest.mock.invocationCallOrder[0]).toBeLessThan(
      harness.createSession.mock.invocationCallOrder[0]!,
    );
    expect(harness.createSession).toHaveBeenCalledWith(harness.modelBytes);
  });

  it("runs the pinned tensor contract locally and returns decoded detections", async () => {
    const harness = createHarness();
    const segmenter = createOnnxNailSegmenter(harness);

    const detections = await segmenter.segment({
      width: 1,
      height: 1,
      data: new Uint8ClampedArray([255, 0, 0, 255]),
    });

    expect(detections).toEqual([]);
    expect(harness.createFloat32Tensor).toHaveBeenCalledTimes(1);
    expect(harness.createFloat32Tensor.mock.calls[0]?.[1]).toEqual(
      CONTRACT.input.shape,
    );
    expect(harness.run).toHaveBeenCalledWith(
      {
        images: expect.objectContaining({
          type: "float32",
          dims: CONTRACT.input.shape,
          firstRedValue: 1,
        }),
      },
      ["output0", "output1"],
    );
    expect(harness.fetchModel).toHaveBeenCalledTimes(1);
  });

  it("never creates a runtime session for a model with the wrong hash", async () => {
    const harness = createHarness({ digest: new Uint8Array(32) });
    const segmenter = createOnnxNailSegmenter(harness);

    await expect(segmenter.warmup()).rejects.toMatchObject({
      name: "NailSegmentationRuntimeError",
      code: "model-integrity-failed",
      recovery: expect.stringMatching(/never run an unverified model/i),
    });
    expect(harness.configure).not.toHaveBeenCalled();
    expect(harness.createSession).not.toHaveBeenCalled();
    expect(harness.modelBytes).toEqual(new Uint8Array(4));
  });

  it("releases and rejects a session whose tensor metadata is not exact", async () => {
    const metadata = validMetadata().outputs;
    metadata[0] = { ...metadata[0]!, shape: [1, 38, 8400] };
    const harness = createHarness({ outputMetadata: metadata });
    const segmenter = createOnnxNailSegmenter(harness);

    await expect(segmenter.warmup()).rejects.toMatchObject({
      code: "model-contract-mismatch",
    });
    expect(harness.release).toHaveBeenCalledTimes(1);
  });

  it("rejects inference output that differs from the manifest", async () => {
    const outputs = validOutputs();
    const output0 = outputs.output0 as {
      type: string;
      dims: number[];
      data: Float32Array;
    };
    output0.dims = [1, 36, 8400];
    const harness = createHarness({ outputs });
    const segmenter = createOnnxNailSegmenter(harness);

    await expect(
      segmenter.segment({
        width: 1,
        height: 1,
        data: new Uint8Array([0, 0, 0, 255]),
      }),
    ).rejects.toMatchObject({
      code: "model-contract-mismatch",
      recovery: expect.stringMatching(/stop sizing/i),
    });
  });

  it("turns a same-origin model response failure into an actionable error", async () => {
    const harness = createHarness({ fetchStatus: 404 });
    const segmenter = createOnnxNailSegmenter(harness);

    await expect(segmenter.warmup()).rejects.toMatchObject({
      code: "model-fetch-failed",
      message: expect.stringMatching(/HTTP 404/i),
      recovery: expect.stringMatching(/deployment needs repair/i),
    });
    expect(harness.digest).not.toHaveBeenCalled();
    expect(harness.createSession).not.toHaveBeenCalled();
  });
});

function hexToBytes(hex: string) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes;
}
