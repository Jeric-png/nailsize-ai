import { describe, expect, it } from "vitest";
import {
  createLetterboxTransform,
  postprocessYoloV8Seg,
  YOLOV8_SEG_CONTRACT,
} from "./yoloV8SegPostprocess";

const OUTPUT0_LENGTH =
  YOLOV8_SEG_CONTRACT.detectionChannels *
  YOLOV8_SEG_CONTRACT.detectionCount;
const PROTOTYPE_PIXEL_COUNT =
  YOLOV8_SEG_CONTRACT.prototypeWidth *
  YOLOV8_SEG_CONTRACT.prototypeHeight;
const OUTPUT1_LENGTH =
  YOLOV8_SEG_CONTRACT.maskCoefficientCount * PROTOTYPE_PIXEL_COUNT;

interface DetectionFixture {
  centerX: number;
  centerY: number;
  width: number;
  height: number;
  confidence: number;
  coefficients?: readonly number[];
}

function createOutputs(prototypeFill = 0) {
  const output1 = new Float32Array(OUTPUT1_LENGTH);
  if (prototypeFill !== 0) output1.fill(prototypeFill);
  return {
    output0: new Float32Array(OUTPUT0_LENGTH),
    output1,
  };
}

function setDetection(
  output0: Float32Array,
  index: number,
  fixture: DetectionFixture,
) {
  const values = [
    fixture.centerX,
    fixture.centerY,
    fixture.width,
    fixture.height,
    fixture.confidence,
  ];
  values.forEach((value, channel) => {
    output0[channel * YOLOV8_SEG_CONTRACT.detectionCount + index] = value;
  });
  fixture.coefficients?.forEach((value, coefficient) => {
    output0[
      (5 + coefficient) * YOLOV8_SEG_CONTRACT.detectionCount + index
    ] = value;
  });
}

function setPrototype(
  output1: Float32Array,
  channel: number,
  x: number,
  y: number,
  value: number,
) {
  output1[
    channel * PROTOTYPE_PIXEL_COUNT +
      y * YOLOV8_SEG_CONTRACT.prototypeWidth +
      x
  ] = value;
}

describe("createLetterboxTransform", () => {
  it("describes the centered 640 input mapping", () => {
    expect(createLetterboxTransform(1280, 720)).toEqual({
      originalWidth: 1280,
      originalHeight: 720,
      inputSize: 640,
      scale: 0.5,
      padX: 0,
      padY: 140,
    });
  });

  it("rejects dimensions that cannot describe an image", () => {
    expect(() => createLetterboxTransform(0, 720)).toThrow(RangeError);
    expect(() => createLetterboxTransform(640.5, 480)).toThrow(RangeError);
  });
});

describe("postprocessYoloV8Seg", () => {
  it("filters confidence, applies deterministic class-agnostic NMS, and undoes letterboxing", () => {
    const outputs = createOutputs();
    const letterbox = createLetterboxTransform(1280, 720);
    setDetection(outputs.output0, 0, {
      centerX: 100,
      centerY: 190,
      width: 100,
      height: 50,
      confidence: 0.9,
    });
    setDetection(outputs.output0, 1, {
      centerX: 105,
      centerY: 192.5,
      width: 100,
      height: 50,
      confidence: 0.8,
    });
    setDetection(outputs.output0, 2, {
      centerX: 350,
      centerY: 215,
      width: 100,
      height: 50,
      confidence: 0.7,
    });
    setDetection(outputs.output0, 3, {
      centerX: 500,
      centerY: 250,
      width: 40,
      height: 40,
      confidence: 0.2,
    });

    const detections = postprocessYoloV8Seg(
      { ...outputs, letterbox },
      { confidenceThreshold: 0.25, iouThreshold: 0.5, maskThreshold: 0.51 },
    );

    expect(detections.map(({ candidateIndex }) => candidateIndex)).toEqual([
      0, 2,
    ]);
    expect(detections[0].box).toEqual({
      x: 100,
      y: 50,
      width: 200,
      height: 100,
    });
    expect(detections[1].box).toEqual({
      x: 600,
      y: 100,
      width: 200,
      height: 100,
    });
    expect(detections[0].quality.components.count).toBe(0);
  });

  it("combines prototypes, applies sigmoid, and crops the mask to the detection box", () => {
    const outputs = createOutputs();
    const letterbox = createLetterboxTransform(640, 640);
    setDetection(outputs.output0, 7, {
      centerX: 8,
      centerY: 8,
      width: 6.5,
      height: 6.5,
      confidence: 0.95,
      coefficients: [1],
    });
    for (let pixel = 0; pixel < PROTOTYPE_PIXEL_COUNT; pixel += 1)
      outputs.output1[pixel] = 2;

    const [detection] = postprocessYoloV8Seg({ ...outputs, letterbox });

    expect(detection.mask).toMatchObject({ x: 4, y: 4, width: 8, height: 8 });
    expect(detection.mask.probabilities[0]).toBe(0);
    expect(detection.mask.binary[0]).toBe(0);
    expect(detection.mask.probabilities[9]).toBeCloseTo(0.880797, 5);
    expect(detection.mask.binary[9]).toBe(1);
    expect(detection.quality.foregroundPixelCount).toBe(36);
    expect(detection.quality.foregroundRatio).toBe(36 / 64);
    expect(detection.quality.components).toEqual({
      count: 1,
      largestPixelCount: 36,
      largestForegroundRatio: 1,
      largestBounds: { x: 5, y: 5, width: 6, height: 6 },
      touchesCropEdge: false,
      largestTouchesCropEdge: false,
    });
  });

  it("reports disconnected mask components in absolute image coordinates", () => {
    const outputs = createOutputs(-10);
    const letterbox = createLetterboxTransform(160, 160);
    setDetection(outputs.output0, 4, {
      centerX: 20,
      centerY: 20,
      width: 24,
      height: 24,
      confidence: 0.9,
      coefficients: [1],
    });
    setPrototype(outputs.output1, 0, 3, 3, 10);
    setPrototype(outputs.output1, 0, 4, 3, 10);
    setPrototype(outputs.output1, 0, 3, 4, 10);
    setPrototype(outputs.output1, 0, 4, 4, 10);
    setPrototype(outputs.output1, 0, 6, 6, 10);

    const [detection] = postprocessYoloV8Seg({ ...outputs, letterbox });

    expect(detection.mask).toMatchObject({ x: 2, y: 2, width: 6, height: 6 });
    expect(detection.quality.foregroundPixelCount).toBe(5);
    expect(detection.quality.meanForegroundProbability).toBeGreaterThan(0.999);
    expect(detection.quality.components).toEqual({
      count: 2,
      largestPixelCount: 4,
      largestForegroundRatio: 0.8,
      largestBounds: { x: 3, y: 3, width: 2, height: 2 },
      touchesCropEdge: false,
      largestTouchesCropEdge: false,
    });
  });

  it("breaks equal-confidence NMS ties by the original candidate index", () => {
    const outputs = createOutputs();
    const letterbox = createLetterboxTransform(640, 640);
    setDetection(outputs.output0, 20, {
      centerX: 100,
      centerY: 100,
      width: 20,
      height: 20,
      confidence: 0.8,
    });
    setDetection(outputs.output0, 10, {
      centerX: 100,
      centerY: 100,
      width: 20,
      height: 20,
      confidence: 0.8,
    });

    const detections = postprocessYoloV8Seg(
      { ...outputs, letterbox },
      { maskThreshold: 0.51 },
    );

    expect(detections).toHaveLength(1);
    expect(detections[0].candidateIndex).toBe(10);
  });

  it("fails closed on incompatible tensors and unsafe thresholds", () => {
    const outputs = createOutputs();
    const letterbox = createLetterboxTransform(640, 640);

    expect(() =>
      postprocessYoloV8Seg({
        output0: new Float32Array(10),
        output1: outputs.output1,
        letterbox,
      }),
    ).toThrow(/\[1, 37, 8400\]/);
    expect(() =>
      postprocessYoloV8Seg(
        { ...outputs, letterbox },
        { confidenceThreshold: 1.01 },
      ),
    ).toThrow(RangeError);
  });
});
