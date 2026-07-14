import { describe, expect, it } from "vitest";
import {
  AUTO_SG50_TWO_HAND_METHOD_MANIFEST,
  assertVisionMethodManifestV2,
  isVisionMethodManifestV2,
} from "./manifest";

function cloneManifest(): unknown {
  return structuredClone(AUTO_SG50_TWO_HAND_METHOD_MANIFEST);
}

function mutateManifest(mutator: (manifest: Record<string, unknown>) => void) {
  const manifest = cloneManifest() as Record<string, unknown>;
  mutator(manifest);
  return manifest;
}

describe("automatic sizing method manifest v2", () => {
  it("pins the complete automatic method and exported ONNX contract", () => {
    expect(AUTO_SG50_TWO_HAND_METHOD_MANIFEST).toMatchObject({
      schemaVersion: "nailsize-vision-method-manifest@2",
      methodVersion: "auto-sg50-two-hand-v0.1.0",
      captureProtocolVersion: "two-hand-photo-v1",
      calibration: {
        version: "sg50-ellipse-affine-v1",
      },
      nailSegmentationModel: {
        repositoryId: "mnemic/nails_seg_yolov8",
        source: {
          sha256:
            "99b7d1c6ceb4bde32d80fe7ae8c8eb809c27d99b55cf9db54b6692afe68f4070",
        },
        runtime: {
          sha256:
            "6b0b806819748b0f3800982df8448e322d30b329090aedb3fa181bddbf6f17f5",
          input: { name: "images", shape: [1, 3, 640, 640] },
          outputs: [
            { name: "output0", shape: [1, 37, 8400] },
            { name: "output1", shape: [1, 32, 160, 160] },
          ],
        },
        license: {
          spdxId: "CC-BY-4.0",
          attributionRequired: true,
          exportedGraphMetadataLicense: "AGPL-3.0",
          distributionReviewRequired: true,
        },
      },
      measurementVersion: "transverse-chord-v2",
      qualityProfileVersion: "auto-beta-v1",
      chartVersion: "platform-default@1",
    });
  });

  it("is deeply immutable", () => {
    expect(Object.isFrozen(AUTO_SG50_TWO_HAND_METHOD_MANIFEST)).toBe(true);
    expect(
      Object.isFrozen(
        AUTO_SG50_TWO_HAND_METHOD_MANIFEST.nailSegmentationModel.runtime
          .outputs[0].shape,
      ),
    ).toBe(true);
    expect(() =>
      Object.defineProperty(
        AUTO_SG50_TWO_HAND_METHOD_MANIFEST.nailSegmentationModel.license,
        "exportedGraphMetadataLicense",
        {
          value: "MIT",
        },
      ),
    ).toThrow(TypeError);
  });

  it("accepts an equivalent deserialized manifest", () => {
    const manifest = cloneManifest();

    expect(isVisionMethodManifestV2(manifest)).toBe(true);
    expect(() => assertVisionMethodManifestV2(manifest)).not.toThrow();
  });

  it.each([
    [
      "method version",
      (manifest: Record<string, unknown>) => {
        manifest.methodVersion = "auto-sg50-two-hand-v0.2.0";
      },
    ],
    [
      "capture protocol",
      (manifest: Record<string, unknown>) => {
        manifest.captureProtocolVersion = "single-photo-v1";
      },
    ],
    [
      "calibration",
      (manifest: Record<string, unknown>) => {
        const calibration = manifest.calibration as Record<string, unknown>;
        calibration.version = "sg50-circle-v1";
      },
    ],
    [
      "source model",
      (manifest: Record<string, unknown>) => {
        const model = manifest.nailSegmentationModel as Record<string, unknown>;
        const source = model.source as Record<string, unknown>;
        source.sha256 = "0".repeat(64);
      },
    ],
    [
      "exported ONNX",
      (manifest: Record<string, unknown>) => {
        const model = manifest.nailSegmentationModel as Record<string, unknown>;
        const runtime = model.runtime as Record<string, unknown>;
        runtime.sha256 = "f".repeat(64);
      },
    ],
    [
      "tensor contract",
      (manifest: Record<string, unknown>) => {
        const model = manifest.nailSegmentationModel as Record<string, unknown>;
        const runtime = model.runtime as Record<string, unknown>;
        runtime.outputs = [
          { name: "output0", dataType: "float32", shape: [1, 37, 8400] },
        ];
      },
    ],
    [
      "measurement",
      (manifest: Record<string, unknown>) => {
        manifest.measurementVersion = "transverse-chord-v1";
      },
    ],
    [
      "quality profile",
      (manifest: Record<string, unknown>) => {
        manifest.qualityProfileVersion = "auto-beta-v2";
      },
    ],
    [
      "chart",
      (manifest: Record<string, unknown>) => {
        manifest.chartVersion = "platform-default@2";
      },
    ],
  ])("rejects a manifest mixed with a different %s", (_, mutate) => {
    const manifest = mutateManifest(mutate);

    expect(isVisionMethodManifestV2(manifest)).toBe(false);
    expect(() => assertVisionMethodManifestV2(manifest)).toThrow(
      /mixed or mutated manifests are not supported/i,
    );
  });

  it("rejects additional unversioned fields", () => {
    const manifest = mutateManifest((candidate) => {
      candidate.unversionedThreshold = 0.75;
    });

    expect(isVisionMethodManifestV2(manifest)).toBe(false);
  });
});
