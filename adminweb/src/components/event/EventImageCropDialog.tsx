import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  cropEventImage,
  type EventCropRect,
} from "@/lib/crop-event-image";

interface EventImageCropDialogProps {
  file: File | null;
  open: boolean;
  onCancel: () => void;
  onConfirm: (file: File) => void;
}

type ResizeCorner = "nw" | "ne" | "sw" | "se";

type Interaction =
  | {
      kind: "move";
      pointerId: number;
      startX: number;
      startY: number;
      initial: EventCropRect;
    }
  | {
      kind: "resize";
      pointerId: number;
      startX: number;
      startY: number;
      corner: ResizeCorner;
      initial: EventCropRect;
    };

const FULL_CROP: EventCropRect = { x: 0, y: 0, width: 1, height: 1 };
const MIN_CROP_SIZE = 0.2;

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

export function EventImageCropDialog({
  file,
  open,
  onCancel,
  onConfirm,
}: EventImageCropDialogProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const interactionRef = useRef<Interaction | null>(null);
  const zoomFocusRef = useRef<{
    x: number;
    y: number;
    screenX: number | null;
    screenY: number | null;
  }>({ x: 0.5, y: 0.5, screenX: null, screenY: null });
  const [sourceUrl, setSourceUrl] = useState("");
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [crop, setCrop] = useState<EventCropRect>(FULL_CROP);
  const [constrainToImage, setConstrainToImage] = useState(true);
  const [viewZoom, setViewZoom] = useState(1);
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    if (!file) {
      setSourceUrl("");
      setImageSize({ width: 0, height: 0 });
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    setSourceUrl(objectUrl);
    setCrop(FULL_CROP);
    setConstrainToImage(true);
    setViewZoom(1);
    setImageSize({ width: 0, height: 0 });

    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const focus = zoomFocusRef.current;
    viewport.scrollLeft =
      focus.x * viewport.scrollWidth - (focus.screenX ?? viewport.clientWidth / 2);
    viewport.scrollTop =
      focus.y * viewport.scrollHeight - (focus.screenY ?? viewport.clientHeight / 2);
  }, [viewZoom]);

  // The workspace is the smallest 4:1 area that contains the entire image.
  // These percentages place the fixed image inside that white workspace.
  const imagePlacement = useMemo(() => {
    if (!imageSize.width || !imageSize.height) return null;
    const ratio = imageSize.width / imageSize.height;

    if (ratio >= 4) {
      const height = (4 / ratio) * 100;
      return { left: 0, top: (100 - height) / 2, width: 100, height };
    }

    const width = (ratio / 4) * 100;
    return { left: (100 - width) / 2, top: 0, width, height: 100 };
  }, [imageSize]);

  const imageBounds = useMemo(() => {
    if (!imagePlacement) return FULL_CROP;
    return {
      x: imagePlacement.left / 100,
      y: imagePlacement.top / 100,
      width: imagePlacement.width / 100,
      height: imagePlacement.height / 100,
    };
  }, [imagePlacement]);

  useEffect(() => {
    if (!imagePlacement || !constrainToImage) return;

    const size = Math.min(imageBounds.width, imageBounds.height);
    setCrop({
      x: imageBounds.x + (imageBounds.width - size) / 2,
      y: imageBounds.y + (imageBounds.height - size) / 2,
      width: size,
      height: size,
    });
  }, [imageBounds, imagePlacement, constrainToImage]);

  const selectionBounds = constrainToImage ? imageBounds : FULL_CROP;
  const maximumSelectionSize = Math.min(selectionBounds.width, selectionBounds.height);
  const minimumSelectionSize = Math.min(MIN_CROP_SIZE, maximumSelectionSize);

  const placeCropAtCenter = (size: number, centerX: number, centerY: number) => ({
    x: clamp(
      centerX - size / 2,
      selectionBounds.x,
      selectionBounds.x + selectionBounds.width - size,
    ),
    y: clamp(
      centerY - size / 2,
      selectionBounds.y,
      selectionBounds.y + selectionBounds.height - size,
    ),
    width: size,
    height: size,
  });

  const updateViewZoom = (requestedZoom: number) => {
    const nextZoom = clamp(requestedZoom, 1, 5);
    const centerX = crop.x + crop.width / 2;
    const centerY = crop.y + crop.height / 2;
    const viewport = viewportRef.current;
    // Inverse scaling keeps the frame approximately the same size on screen,
    // while its represented source area shrinks/grows like a phone cropper.
    const nextSize = clamp(
      (crop.width * viewZoom) / nextZoom,
      minimumSelectionSize,
      maximumSelectionSize,
    );
    setCrop(placeCropAtCenter(nextSize, centerX, centerY));
    zoomFocusRef.current = {
      x: centerX,
      y: centerY,
      screenX: viewport
        ? centerX * viewport.scrollWidth - viewport.scrollLeft
        : null,
      screenY: viewport
        ? centerY * viewport.scrollHeight - viewport.scrollTop
        : null,
    };
    setViewZoom(nextZoom);
  };

  const toggleImageOnly = () => {
    if (constrainToImage) {
      setConstrainToImage(false);
      return;
    }

    const size = Math.min(imageBounds.width, imageBounds.height);
    setConstrainToImage(true);
    setCrop({
      x: imageBounds.x + (imageBounds.width - size) / 2,
      y: imageBounds.y + (imageBounds.height - size) / 2,
      width: size,
      height: size,
    });
    zoomFocusRef.current = {
      x: imageBounds.x + imageBounds.width / 2,
      y: imageBounds.y + imageBounds.height / 2,
      screenX: null,
      screenY: null,
    };
  };

  const normalizedPointer = (event: React.PointerEvent) => {
    const bounds = workspaceRef.current?.getBoundingClientRect();
    if (!bounds) return null;
    return {
      x: (event.clientX - bounds.left) / bounds.width,
      y: (event.clientY - bounds.top) / bounds.height,
    };
  };

  const beginMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const point = normalizedPointer(event);
    if (!point || processing) return;
    event.preventDefault();
    workspaceRef.current?.setPointerCapture(event.pointerId);
    interactionRef.current = {
      kind: "move",
      pointerId: event.pointerId,
      startX: point.x,
      startY: point.y,
      initial: crop,
    };
  };

  const beginResize = (
    event: React.PointerEvent<HTMLButtonElement>,
    corner: ResizeCorner,
  ) => {
    const point = normalizedPointer(event);
    if (!point || processing) return;
    event.preventDefault();
    event.stopPropagation();
    workspaceRef.current?.setPointerCapture(event.pointerId);
    interactionRef.current = {
      kind: "resize",
      pointerId: event.pointerId,
      startX: point.x,
      startY: point.y,
      corner,
      initial: crop,
    };
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const interaction = interactionRef.current;
    const point = normalizedPointer(event);
    if (!interaction || !point || interaction.pointerId !== event.pointerId) return;
    event.preventDefault();

    const dx = point.x - interaction.startX;
    const dy = point.y - interaction.startY;
    const initial = interaction.initial;

    if (interaction.kind === "move") {
      setCrop({
        ...initial,
        x: clamp(
          initial.x + dx,
          selectionBounds.x,
          selectionBounds.x + selectionBounds.width - initial.width,
        ),
        y: clamp(
          initial.y + dy,
          selectionBounds.y,
          selectionBounds.y + selectionBounds.height - initial.height,
        ),
      });
      return;
    }

    const signs: Record<ResizeCorner, { x: number; y: number }> = {
      nw: { x: -1, y: -1 },
      ne: { x: 1, y: -1 },
      sw: { x: -1, y: 1 },
      se: { x: 1, y: 1 },
    };
    const sign = signs[interaction.corner];
    // Project pointer movement onto the corner diagonal. In normalized space,
    // equal width/height means the crop remains physically 4:1.
    const projectedDelta = (dx * sign.x + dy * sign.y) / 2;

    const anchorRight = initial.x + initial.width;
    const anchorBottom = initial.y + initial.height;
    const maxSizeByCorner: Record<ResizeCorner, number> = {
      nw: Math.min(anchorRight - selectionBounds.x, anchorBottom - selectionBounds.y),
      ne: Math.min(
        selectionBounds.x + selectionBounds.width - initial.x,
        anchorBottom - selectionBounds.y,
      ),
      sw: Math.min(
        anchorRight - selectionBounds.x,
        selectionBounds.y + selectionBounds.height - initial.y,
      ),
      se: Math.min(
        selectionBounds.x + selectionBounds.width - initial.x,
        selectionBounds.y + selectionBounds.height - initial.y,
      ),
    };
    const size = clamp(
      initial.width + projectedDelta,
      minimumSelectionSize,
      maxSizeByCorner[interaction.corner],
    );

    const next: EventCropRect = { x: initial.x, y: initial.y, width: size, height: size };
    if (interaction.corner === "nw" || interaction.corner === "sw") {
      next.x = anchorRight - size;
    }
    if (interaction.corner === "nw" || interaction.corner === "ne") {
      next.y = anchorBottom - size;
    }
    setCrop(next);
  };

  const finishInteraction = (event: React.PointerEvent<HTMLDivElement>) => {
    if (interactionRef.current?.pointerId !== event.pointerId) return;
    interactionRef.current = null;
    if (workspaceRef.current?.hasPointerCapture(event.pointerId)) {
      workspaceRef.current.releasePointerCapture(event.pointerId);
    }
  };

  const handleConfirm = async () => {
    if (!sourceUrl || !imageSize.width) {
      toast.error("Please wait for the selected image to load.");
      return;
    }

    setProcessing(true);
    try {
      onConfirm(await cropEventImage(sourceUrl, crop));
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Unable to crop the image.",
      );
    } finally {
      setProcessing(false);
    }
  };

  const cropStyle = {
    left: `${crop.x * 100}%`,
    top: `${crop.y * 100}%`,
    width: `${crop.width * 100}%`,
    height: `${crop.height * 100}%`,
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && !processing) onCancel();
      }}
    >
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Crop Event Banner</DialogTitle>
          <DialogDescription>
            Drag the frame to select an area. Drag a corner to resize it. Use
            Allow White Space if you need to include areas outside the image.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div
            ref={viewportRef}
            className="relative aspect-[4/1] w-full overflow-auto rounded-md border bg-muted"
          >
            <div
              ref={workspaceRef}
              className="relative select-none overflow-hidden bg-white shadow-inner"
              style={{
                width: `${viewZoom * 100}%`,
                aspectRatio: "4 / 1",
                touchAction: "none",
              }}
              onPointerMove={handlePointerMove}
              onPointerUp={finishInteraction}
              onPointerCancel={finishInteraction}
            >
              {sourceUrl && imagePlacement && (
                <img
                src={sourceUrl}
                alt="Source event banner"
                draggable={false}
                className="pointer-events-none absolute block"
                style={{
                  left: `${imagePlacement.left}%`,
                  top: `${imagePlacement.top}%`,
                  width: `${imagePlacement.width}%`,
                  height: `${imagePlacement.height}%`,
                }}
                />
              )}

              {sourceUrl && !imagePlacement && (
                <img
                src={sourceUrl}
                alt=""
                className="pointer-events-none absolute h-px w-px opacity-0"
                onLoad={(event) => {
                  setImageSize({
                    width: event.currentTarget.naturalWidth,
                    height: event.currentTarget.naturalHeight,
                  });
                }}
                />
              )}

              {imagePlacement && (
                <div
                className="absolute cursor-move border-2 border-emerald-500 shadow-[0_0_0_9999px_rgba(0,0,0,0.5)]"
                style={cropStyle}
                onPointerDown={beginMove}
              >
                <div className="pointer-events-none absolute inset-0 grid grid-cols-3 grid-rows-3">
                  {Array.from({ length: 9 }).map((_, index) => (
                    <span key={index} className="border border-white/35" />
                  ))}
                </div>

                {(["nw", "ne", "sw", "se"] as const).map((corner) => (
                  <button
                    key={corner}
                    type="button"
                    aria-label={`Resize crop from ${corner} corner`}
                    className={`absolute size-5 rounded-sm border-2 border-emerald-600 bg-white shadow ${
                      corner === "nw"
                        ? "-left-2.5 -top-2.5 cursor-nwse-resize"
                        : corner === "ne"
                          ? "-right-2.5 -top-2.5 cursor-nesw-resize"
                          : corner === "sw"
                            ? "-bottom-2.5 -left-2.5 cursor-nesw-resize"
                            : "-bottom-2.5 -right-2.5 cursor-nwse-resize"
                    }`}
                    onPointerDown={(event) => beginResize(event, corner)}
                  />
                ))}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <label htmlFor="event-crop-view-zoom" className="shrink-0 text-sm font-medium">
              View zoom
            </label>
            <input
              id="event-crop-view-zoom"
              type="range"
              min="1"
              max="5"
              step="0.25"
              value={viewZoom}
              disabled={processing}
              className="min-w-32 flex-1"
              onChange={(event) => updateViewZoom(Number(event.target.value))}
            />
            <span className="w-10 text-right text-sm tabular-nums">{viewZoom.toFixed(1)}×</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={processing || viewZoom === 1}
              onClick={() => {
                updateViewZoom(1);
              }}
            >
              Reset view
            </Button>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">
              {constrainToImage
                ? "Image-only mode: white areas cannot be selected"
                : "White-space mode: areas outside the image may be selected"}
              {" · "}Output: 1280 × 320 WEBP
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={processing}
              onClick={toggleImageOnly}
            >
              {constrainToImage ? "Allow White Space" : "Crop Image Only"}
            </Button>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" disabled={processing} onClick={onCancel}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={processing || !imagePlacement}
            onClick={handleConfirm}
          >
            {processing ? "Cropping..." : "Use Cropped Image"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
