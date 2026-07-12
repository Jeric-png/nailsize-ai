import type { CaptureType } from "./guidedSizing";

export const captureCopy: Record<
  CaptureType,
  {
    title: string;
    nails: string;
    instruction: string;
    side: "Left" | "Right";
  }
> = {
  left_fingers: {
    title: "Left fingers",
    nails: "Index, middle, ring, pinky",
    instruction:
      "Lay four fingers flat with every sidewall visible, and place the confirmed 50-cent coin beside them on the same surface.",
    side: "Left",
  },
  left_thumb: {
    title: "Left thumb",
    nails: "Thumb",
    instruction:
      "Place your thumb flat with both sidewalls visible, and place the confirmed 50-cent coin beside it on the same surface.",
    side: "Left",
  },
  right_fingers: {
    title: "Right fingers",
    nails: "Index, middle, ring, pinky",
    instruction:
      "Lay four fingers flat with every sidewall visible, and place the confirmed 50-cent coin beside them on the same surface.",
    side: "Right",
  },
  right_thumb: {
    title: "Right thumb",
    nails: "Thumb",
    instruction:
      "Place your thumb flat with both sidewalls visible, and place the confirmed 50-cent coin beside it on the same surface.",
    side: "Right",
  },
};
