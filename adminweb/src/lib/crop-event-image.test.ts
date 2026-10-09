import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { cropEventImage, getMaximumEventCropBounds } from "./crop-event-image";

describe("getMaximumEventCropBounds", () => {
  it("keeps an existing 4:1 image as the full crop", () => {
    expect(getMaximumEventCropBounds(1280, 320)).toEqual({
      x: 0,
      y: 0,
      width: 1280,
      height: 320,
    });
  });

  it("adds equal white space on both sides of a portrait image", () => {
    expect(getMaximumEventCropBounds(400, 800)).toEqual({
      x: -1400,
      y: 0,
      width: 3200,
      height: 800,
    });
  });

  it("adds equal white space above and below an extra-wide image", () => {
    expect(getMaximumEventCropBounds(2000, 200)).toEqual({
      x: 0,
      y: -150,
      width: 2000,
      height: 500,
    });
  });

  it("creates the smallest 4:1 workspace for ordinary landscape images", () => {
    expect(getMaximumEventCropBounds(1600, 900)).toEqual({
      x: -1000,
      y: 0,
      width: 3600,
      height: 900,
    });
  });
});

describe("cropEventImage", () => {
  let imageWidth = 1280;
  let imageHeight = 320;
  let canvasWidth = 0;
  let canvasHeight = 0;
  const fillRect = vi.fn();
  const drawImage = vi.fn();
  const context = {
    fillStyle: "",
    fillRect,
    drawImage,
    imageSmoothingEnabled: false,
    imageSmoothingQuality: "low",
  };

  class FakeImage {
    naturalWidth = imageWidth;
    naturalHeight = imageHeight;
    onload: null | (() => void) = null;
    onerror: null | (() => void) = null;

    set src(_value: string) {
      this.onload?.();
    }
  }

  class FakeFile extends Blob {
    name: string;
    lastModified: number;

    constructor(parts: BlobPart[], name: string, options: FilePropertyBag = {}) {
      super(parts, options);
      this.name = name;
      this.lastModified = options.lastModified ?? Date.now();
    }
  }

  beforeEach(() => {
    imageWidth = 1280;
    imageHeight = 320;
    canvasWidth = 0;
    canvasHeight = 0;
    fillRect.mockClear();
    drawImage.mockClear();

    vi.stubGlobal("Image", FakeImage);
    vi.stubGlobal("File", FakeFile);
    vi.stubGlobal("document", {
      createElement: vi.fn(() => ({
        get width() {
          return canvasWidth;
        },
        set width(value: number) {
          canvasWidth = value;
        },
        get height() {
          return canvasHeight;
        },
        set height(value: number) {
          canvasHeight = value;
        },
        getContext: vi.fn(() => context),
        toBlob: (callback: BlobCallback, type?: string) =>
          callback(new Blob(["cropped"], { type })),
      })),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("always exports a 1280 by 320 WEBP file", async () => {
    const result = await cropEventImage("blob:test", {
      x: 0,
      y: 0,
      width: 1,
      height: 1,
    });

    expect(canvasWidth).toBe(1280);
    expect(canvasHeight).toBe(320);
    expect(result.type).toBe("image/webp");
    expect(result.name).toMatch(/^event-banner-\d+\.webp$/);
  });

  it("fills the complete output with white before drawing the image", async () => {
    await cropEventImage("blob:test", {
      x: 0,
      y: 0,
      width: 1,
      height: 1,
    });

    expect(context.fillStyle).toBe("#ffffff");
    expect(fillRect).toHaveBeenCalledWith(0, 0, 1280, 320);
    expect(fillRect.mock.invocationCallOrder[0]).toBeLessThan(
      drawImage.mock.invocationCallOrder[0],
    );
  });

  it("centres a portrait image and leaves white space on both sides", async () => {
    imageWidth = 400;
    imageHeight = 800;

    await cropEventImage("blob:portrait", {
      x: 0,
      y: 0,
      width: 1,
      height: 1,
    });

    expect(drawImage).toHaveBeenCalledWith(
      expect.any(FakeImage),
      0,
      0,
      400,
      800,
      560,
      0,
      160,
      320,
    );
  });

  it("draws the whole source when it already has the required ratio", async () => {
    await cropEventImage("blob:banner", {
      x: 0,
      y: 0,
      width: 1,
      height: 1,
    });

    expect(drawImage).toHaveBeenCalledWith(
      expect.any(FakeImage),
      0,
      0,
      1280,
      320,
      0,
      0,
      1280,
      320,
    );
  });
});
