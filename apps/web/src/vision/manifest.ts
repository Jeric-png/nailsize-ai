export const VISION_METHOD_MANIFEST_SCHEMA_VERSION =
  "nailsize-vision-method-manifest@2" as const;
export const AUTO_SG50_TWO_HAND_METHOD_VERSION =
  "auto-sg50-two-hand-v0.1.0" as const;
export const NAIL_SEGMENTATION_SOURCE_SHA256 =
  "99b7d1c6ceb4bde32d80fe7ae8c8eb809c27d99b55cf9db54b6692afe68f4070" as const;
export const NAIL_SEGMENTATION_ONNX_SHA256 =
  "6b0b806819748b0f3800982df8448e322d30b329090aedb3fa181bddbf6f17f5" as const;

export type VisionMethodVersion = typeof AUTO_SG50_TWO_HAND_METHOD_VERSION;
export type VisionCaptureProtocolVersion = "two-hand-photo-v1";
export type VisionCalibrationVersion = "sg50-ellipse-affine-v1";
export type VisionMeasurementVersion = "transverse-chord-v2";
export type VisionQualityProfileVersion = "auto-beta-v1";
export type VisionChartVersion = "platform-default@1";

export interface VisionTensorContract<
  TName extends string,
  TShape extends readonly number[],
> {
  readonly name: TName;
  readonly dataType: "float32";
  readonly shape: TShape;
}

export interface VisionModelLicense {
  readonly spdxId: "CC-BY-4.0";
  readonly name: "Creative Commons Attribution 4.0 International";
  readonly url: "https://creativecommons.org/licenses/by/4.0/";
  readonly attributionRequired: true;
  readonly attribution: string;
  readonly exportedGraphMetadataLicense: "AGPL-3.0";
  readonly distributionReviewRequired: true;
}

export interface VisionMethodManifestV2 {
  readonly schemaVersion: typeof VISION_METHOD_MANIFEST_SCHEMA_VERSION;
  readonly methodVersion: VisionMethodVersion;
  readonly captureProtocolVersion: VisionCaptureProtocolVersion;
  readonly calibration: {
    readonly version: VisionCalibrationVersion;
    readonly referenceId: "sg-50-cent-third-series-23mm";
    readonly nominalDiameterMm: 23;
  };
  readonly nailSegmentationModel: {
    readonly family: "YOLOv8-seg";
    readonly repositoryId: "mnemic/nails_seg_yolov8";
    readonly modelCardUrl: "https://huggingface.co/mnemic/nails_seg_yolov8";
    readonly variant: "nails_seg_s_yolov8_v1";
    readonly source: {
      readonly format: "pytorch";
      readonly fileName: "nails_seg_s_yolov8_v1.pt";
      readonly sha256: typeof NAIL_SEGMENTATION_SOURCE_SHA256;
    };
    readonly runtime: {
      readonly format: "onnx";
      readonly fileName: "nails_seg_s_yolov8_v1.onnx";
      readonly sha256: typeof NAIL_SEGMENTATION_ONNX_SHA256;
      readonly opset: 17;
      readonly dynamicShapes: false;
      readonly input: VisionTensorContract<"images", readonly [1, 3, 640, 640]>;
      readonly outputs: readonly [
        VisionTensorContract<"output0", readonly [1, 37, 8400]>,
        VisionTensorContract<"output1", readonly [1, 32, 160, 160]>,
      ];
    };
    readonly license: VisionModelLicense;
  };
  readonly measurementVersion: VisionMeasurementVersion;
  readonly qualityProfileVersion: VisionQualityProfileVersion;
  readonly chartVersion: VisionChartVersion;
}

export const AUTO_SG50_TWO_HAND_METHOD_MANIFEST: VisionMethodManifestV2 =
  deepFreeze({
    schemaVersion: VISION_METHOD_MANIFEST_SCHEMA_VERSION,
    methodVersion: AUTO_SG50_TWO_HAND_METHOD_VERSION,
    captureProtocolVersion: "two-hand-photo-v1",
    calibration: {
      version: "sg50-ellipse-affine-v1",
      referenceId: "sg-50-cent-third-series-23mm",
      nominalDiameterMm: 23,
    },
    nailSegmentationModel: {
      family: "YOLOv8-seg",
      repositoryId: "mnemic/nails_seg_yolov8",
      modelCardUrl: "https://huggingface.co/mnemic/nails_seg_yolov8",
      variant: "nails_seg_s_yolov8_v1",
      source: {
        format: "pytorch",
        fileName: "nails_seg_s_yolov8_v1.pt",
        sha256: NAIL_SEGMENTATION_SOURCE_SHA256,
      },
      runtime: {
        format: "onnx",
        fileName: "nails_seg_s_yolov8_v1.onnx",
        sha256: NAIL_SEGMENTATION_ONNX_SHA256,
        opset: 17,
        dynamicShapes: false,
        input: {
          name: "images",
          dataType: "float32",
          shape: [1, 3, 640, 640],
        },
        outputs: [
          {
            name: "output0",
            dataType: "float32",
            shape: [1, 37, 8400],
          },
          {
            name: "output1",
            dataType: "float32",
            shape: [1, 32, 160, 160],
          },
        ],
      },
      license: {
        spdxId: "CC-BY-4.0",
        name: "Creative Commons Attribution 4.0 International",
        url: "https://creativecommons.org/licenses/by/4.0/",
        attributionRequired: true,
        attribution:
          "mnemic/nails_seg_yolov8 by mnemic, licensed under CC BY 4.0.",
        exportedGraphMetadataLicense: "AGPL-3.0",
        distributionReviewRequired: true,
      },
    },
    measurementVersion: "transverse-chord-v2",
    qualityProfileVersion: "auto-beta-v1",
    chartVersion: "platform-default@1",
  });

export function isVisionMethodManifestV2(
  value: unknown,
): value is VisionMethodManifestV2 {
  return exactlyMatches(value, AUTO_SG50_TWO_HAND_METHOD_MANIFEST);
}

export function assertVisionMethodManifestV2(
  value: unknown,
): asserts value is VisionMethodManifestV2 {
  if (!isVisionMethodManifestV2(value)) {
    throw new TypeError(
      `Vision method manifest must exactly match ${AUTO_SG50_TWO_HAND_METHOD_VERSION}; mixed or mutated manifests are not supported.`,
    );
  }
}

function deepFreeze<T>(value: T): T {
  if (typeof value !== "object" || value === null || Object.isFrozen(value)) {
    return value;
  }

  const record = value as Record<PropertyKey, unknown>;
  for (const key of Reflect.ownKeys(record)) deepFreeze(record[key]);
  return Object.freeze(value);
}

function exactlyMatches(value: unknown, expected: unknown): boolean {
  if (Object.is(value, expected)) return true;
  if (
    typeof value !== "object" ||
    value === null ||
    typeof expected !== "object" ||
    expected === null ||
    Array.isArray(value) !== Array.isArray(expected)
  ) {
    return false;
  }

  const actual = value as Record<PropertyKey, unknown>;
  const canonical = expected as Record<PropertyKey, unknown>;
  const actualKeys = Reflect.ownKeys(actual);
  const canonicalKeys = Reflect.ownKeys(canonical);
  if (
    actualKeys.length !== canonicalKeys.length ||
    canonicalKeys.some((key) => !actualKeys.includes(key))
  ) {
    return false;
  }

  return canonicalKeys.every((key) =>
    exactlyMatches(actual[key], canonical[key]),
  );
}
