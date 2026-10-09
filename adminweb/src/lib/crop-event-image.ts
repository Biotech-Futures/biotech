export interface EventCropRect {
  /** Values are normalized against the maximum 4:1 workspace. */
  x: number;
  y: number;
  width: number;
  height: number;
}

interface PixelRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

const OUTPUT_WIDTH = 1280;
const OUTPUT_HEIGHT = 320;

function loadImage(source: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Unable to load the selected image."));
    image.src = source;
  });
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob);
        else reject(new Error("Unable to create the cropped image."));
      },
      "image/webp",
      0.9,
    );
  });
}

/** Smallest 4:1 rectangle, in source-image pixels, containing the whole image. */
export function getMaximumEventCropBounds(
  imageWidth: number,
  imageHeight: number,
): PixelRect {
  const imageRatio = imageWidth / imageHeight;

  if (imageRatio >= 4) {
    const height = imageWidth / 4;
    return {
      x: 0,
      y: (imageHeight - height) / 2,
      width: imageWidth,
      height,
    };
  }

  const width = imageHeight * 4;
  return {
    x: (imageWidth - width) / 2,
    y: 0,
    width,
    height: imageHeight,
  };
}

export async function cropEventImage(
  sourceUrl: string,
  crop: EventCropRect,
): Promise<File> {
  const image = await loadImage(sourceUrl);
  const maximum = getMaximumEventCropBounds(
    image.naturalWidth,
    image.naturalHeight,
  );

  const sourceCrop: PixelRect = {
    x: maximum.x + crop.x * maximum.width,
    y: maximum.y + crop.y * maximum.height,
    width: crop.width * maximum.width,
    height: crop.height * maximum.height,
  };

  // Only draw the overlap with the source image. Anything outside remains white.
  const overlapLeft = Math.max(0, sourceCrop.x);
  const overlapTop = Math.max(0, sourceCrop.y);
  const overlapRight = Math.min(image.naturalWidth, sourceCrop.x + sourceCrop.width);
  const overlapBottom = Math.min(image.naturalHeight, sourceCrop.y + sourceCrop.height);

  const canvas = document.createElement("canvas");
  canvas.width = OUTPUT_WIDTH;
  canvas.height = OUTPUT_HEIGHT;

  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Canvas is not supported by this browser.");
  }

  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, OUTPUT_WIDTH, OUTPUT_HEIGHT);
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";

  if (overlapRight > overlapLeft && overlapBottom > overlapTop) {
    const scaleX = OUTPUT_WIDTH / sourceCrop.width;
    const scaleY = OUTPUT_HEIGHT / sourceCrop.height;

    context.drawImage(
      image,
      overlapLeft,
      overlapTop,
      overlapRight - overlapLeft,
      overlapBottom - overlapTop,
      (overlapLeft - sourceCrop.x) * scaleX,
      (overlapTop - sourceCrop.y) * scaleY,
      (overlapRight - overlapLeft) * scaleX,
      (overlapBottom - overlapTop) * scaleY,
    );
  }

  const blob = await canvasToBlob(canvas);
  return new File([blob], `event-banner-${Date.now()}.webp`, {
    type: "image/webp",
    lastModified: Date.now(),
  });
}
