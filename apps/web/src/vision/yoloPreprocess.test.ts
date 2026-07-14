import { describe, expect, it } from "vitest";
import {
  preprocessYoloRgba,
  YOLO_INPUT_SHAPE,
  YOLO_LETTERBOX_FILL,
  YoloPreprocessError,
} from "./yoloPreprocess";

const INPUT_SIZE = 640;
const PLANE_SIZE = INPUT_SIZE * INPUT_SIZE;

describe("preprocessYoloRgba", () => {
  it("normalizes RGBA pixels into RGB CHW planes", () => {
    const result = preprocessYoloRgba({
      width: 1,
      height: 1,
      data: new Uint8ClampedArray([255, 128, 0, 255]),
    });

    expect(result.shape).toBe(YOLO_INPUT_SHAPE);
    expect(result.data).toHaveLength(3 * PLANE_SIZE);
    expect(result.data[0]).toBe(1);
    expect(result.data[PLANE_SIZE - 1]).toBe(1);
    expect(result.data[PLANE_SIZE]).toBeCloseTo(128 / 255, 7);
    expect(result.data[2 * PLANE_SIZE]).toBe(0);
    expect(result.letterbox).toEqual({
      originalWidth: 1,
      originalHeight: 1,
      inputSize: 640,
      scale: 640,
      padX: 0,
      padY: 0,
    });
  });

  it("centers the image and preserves the 114 letterbox fill", () => {
    const result = preprocessYoloRgba({
      width: 2,
      height: 1,
      data: new Uint8Array([255, 0, 0, 255, 0, 0, 255, 255]),
    });
    const paddingIndex = 159 * INPUT_SIZE + 320;
    const firstContentIndex = 160 * INPUT_SIZE;
    const lastContentIndex = 479 * INPUT_SIZE + 639;
    const afterContentIndex = 480 * INPUT_SIZE + 320;

    expect(result.letterbox).toMatchObject({
      scale: 320,
      padX: 0,
      padY: 160,
    });
    expect(result.data[paddingIndex]).toBeCloseTo(YOLO_LETTERBOX_FILL / 255, 7);
    expect(result.data[firstContentIndex]).toBe(1);
    expect(result.data[2 * PLANE_SIZE + lastContentIndex]).toBe(1);
    expect(result.data[afterContentIndex]).toBeCloseTo(
      YOLO_LETTERBOX_FILL / 255,
      7,
    );
  });

  it("composites transparency over the model fill instead of black", () => {
    const result = preprocessYoloRgba({
      width: 1,
      height: 1,
      data: new Uint8Array([255, 0, 0, 0]),
    });

    expect(result.data[0]).toBeCloseTo(YOLO_LETTERBOX_FILL / 255, 7);
    expect(result.data[PLANE_SIZE]).toBeCloseTo(YOLO_LETTERBOX_FILL / 255, 7);
    expect(result.data[2 * PLANE_SIZE]).toBeCloseTo(
      YOLO_LETTERBOX_FILL / 255,
      7,
    );
  });

  it("fails closed for invalid dimensions and incomplete pixels", () => {
    expect(() =>
      preprocessYoloRgba({
        width: 0,
        height: 1,
        data: new Uint8Array(),
      }),
    ).toThrowError(
      expect.objectContaining<Partial<YoloPreprocessError>>({
        code: "invalid-image-dimensions",
      }),
    );

    expect(() =>
      preprocessYoloRgba({
        width: 1,
        height: 1,
        data: new Uint8Array([255, 255, 255]),
      }),
    ).toThrowError(
      expect.objectContaining<Partial<YoloPreprocessError>>({
        code: "invalid-image-data",
      }),
    );
  });
});
