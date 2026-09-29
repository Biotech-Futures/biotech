<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="admin-modal crop-dialog"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
      @keydown.esc="onCancel"
      @mousedown.self="onCancel"
    >
      <div class="admin-modal__backdrop" aria-hidden="true"></div>
      <div class="admin-modal__content crop-dialog__content">
        <header class="admin-modal__header">
          <h2 :id="titleId" class="admin-modal__title">Crop Event Banner</h2>
        </header>

        <div class="admin-modal__body crop-dialog__body">
          <p class="crop-dialog__hint">
            Drag the frame to select an area. Drag a corner to resize it. Use
            "Allow White Space" if you need to include areas outside the image.
          </p>

          <div ref="viewportRef" class="crop-dialog__viewport">
            <div
              ref="workspaceRef"
              class="crop-dialog__workspace"
              :style="{ width: `${viewZoom * 100}%` }"
              @pointermove="handlePointerMove"
              @pointerup="finishInteraction"
              @pointercancel="finishInteraction"
            >
              <img
                v-if="sourceUrl && !imagePlacement"
                :src="sourceUrl"
                alt=""
                class="crop-dialog__probe-image"
                @load="onProbeLoad"
              />

              <img
                v-if="sourceUrl && imagePlacement"
                :src="sourceUrl"
                alt="Source event banner"
                draggable="false"
                class="crop-dialog__source-image"
                :style="{
                  left: `${imagePlacement.left}%`,
                  top: `${imagePlacement.top}%`,
                  width: `${imagePlacement.width}%`,
                  height: `${imagePlacement.height}%`
                }"
              />

              <div
                v-if="imagePlacement"
                class="crop-dialog__crop"
                :style="cropStyle"
                @pointerdown="beginMove"
              >
                <div class="crop-dialog__grid">
                  <span v-for="n in 9" :key="n" class="crop-dialog__grid-cell"></span>
                </div>

                <button
                  v-for="corner in CORNERS"
                  :key="corner"
                  type="button"
                  class="crop-dialog__handle"
                  :class="`crop-dialog__handle--${corner}`"
                  :aria-label="`Resize crop from ${corner} corner`"
                  @pointerdown="beginResize($event, corner)"
                ></button>
              </div>
            </div>
          </div>

          <div class="crop-dialog__zoom-row">
            <label for="event-crop-view-zoom" class="crop-dialog__zoom-label">View zoom</label>
            <input
              id="event-crop-view-zoom"
              type="range"
              min="1"
              max="5"
              step="0.25"
              :value="viewZoom"
              :disabled="processing"
              class="crop-dialog__zoom-slider"
              @input="updateViewZoom(Number(($event.target as HTMLInputElement).value))"
            />
            <span class="crop-dialog__zoom-value">{{ viewZoom.toFixed(1) }}&times;</span>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="processing || viewZoom === 1"
              @click="updateViewZoom(1)"
            >
              Reset view
            </button>
          </div>

          <div class="crop-dialog__mode-row">
            <p class="crop-dialog__mode-hint">
              {{
                constrainToImage
                  ? 'Image-only mode: white areas cannot be selected'
                  : 'White-space mode: areas outside the image may be selected'
              }}
              &middot; Output: 1280 &times; 320 WEBP
            </p>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="processing"
              @click="toggleImageOnly"
            >
              {{ constrainToImage ? 'Allow White Space' : 'Crop Image Only' }}
            </button>
          </div>

          <p v-if="errorMessage" class="crop-dialog__error" role="alert">{{ errorMessage }}</p>
        </div>

        <footer class="admin-modal__footer">
          <button type="button" class="btn btn-outline" :disabled="processing" @click="onCancel">
            Cancel
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="processing || !imagePlacement"
            @click="handleConfirm"
          >
            {{ processing ? 'Cropping...' : 'Use Cropped Image' }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { cropEventImage, type EventCropRect } from '@/utils/eventImageCrop'

const props = defineProps<{
  modelValue: boolean
  file: File | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'cancel'): void
  (e: 'confirm', file: File): void
}>()

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})

const instanceId = `event-crop-${Math.random().toString(36).slice(2, 8)}`
const titleId = `${instanceId}-title`

type ResizeCorner = 'nw' | 'ne' | 'sw' | 'se'
const CORNERS: ResizeCorner[] = ['nw', 'ne', 'sw', 'se']

type Interaction =
  | { kind: 'move'; pointerId: number; startX: number; startY: number; initial: EventCropRect }
  | {
      kind: 'resize'
      pointerId: number
      startX: number
      startY: number
      corner: ResizeCorner
      initial: EventCropRect
    }

const FULL_CROP: EventCropRect = { x: 0, y: 0, width: 1, height: 1 }
const MIN_CROP_SIZE = 0.2

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const viewportRef = ref<HTMLDivElement | null>(null)
const workspaceRef = ref<HTMLDivElement | null>(null)

// Plain (non-reactive) interaction/zoom-focus trackers — mirrors useRef in the
// adminweb original, since neither needs to trigger a re-render on its own.
let interaction: Interaction | null = null
let zoomFocus: { x: number; y: number; screenX: number | null; screenY: number | null } = {
  x: 0.5,
  y: 0.5,
  screenX: null,
  screenY: null
}

const sourceUrl = ref('')
const imageSize = ref({ width: 0, height: 0 })
const crop = ref<EventCropRect>({ ...FULL_CROP })
const constrainToImage = ref(true)
const viewZoom = ref(1)
const processing = ref(false)
const errorMessage = ref('')

watch(
  () => props.file,
  (file, _prev, onCleanup) => {
    if (!file) {
      sourceUrl.value = ''
      imageSize.value = { width: 0, height: 0 }
      return
    }

    const objectUrl = URL.createObjectURL(file)
    sourceUrl.value = objectUrl
    crop.value = { ...FULL_CROP }
    constrainToImage.value = true
    viewZoom.value = 1
    imageSize.value = { width: 0, height: 0 }
    errorMessage.value = ''

    onCleanup(() => URL.revokeObjectURL(objectUrl))
  },
  { immediate: true }
)

const onProbeLoad = (event: Event) => {
  const img = event.currentTarget as HTMLImageElement
  imageSize.value = { width: img.naturalWidth, height: img.naturalHeight }
}

// The workspace is the smallest 4:1 area that contains the entire image.
// These percentages place the fixed image inside that white workspace.
const imagePlacement = computed(() => {
  if (!imageSize.value.width || !imageSize.value.height) return null
  const ratio = imageSize.value.width / imageSize.value.height

  if (ratio >= 4) {
    const height = (4 / ratio) * 100
    return { left: 0, top: (100 - height) / 2, width: 100, height }
  }

  const width = (ratio / 4) * 100
  return { left: (100 - width) / 2, top: 0, width, height: 100 }
})

const imageBounds = computed<EventCropRect>(() => {
  const placement = imagePlacement.value
  if (!placement) return { ...FULL_CROP }
  return {
    x: placement.left / 100,
    y: placement.top / 100,
    width: placement.width / 100,
    height: placement.height / 100
  }
})

watch([imageBounds, constrainToImage], ([bounds, constrained]) => {
  if (!imagePlacement.value || !constrained) return
  const size = Math.min(bounds.width, bounds.height)
  crop.value = {
    x: bounds.x + (bounds.width - size) / 2,
    y: bounds.y + (bounds.height - size) / 2,
    width: size,
    height: size
  }
})

const selectionBounds = computed(() => (constrainToImage.value ? imageBounds.value : FULL_CROP))
const maximumSelectionSize = computed(() =>
  Math.min(selectionBounds.value.width, selectionBounds.value.height)
)
const minimumSelectionSize = computed(() => Math.min(MIN_CROP_SIZE, maximumSelectionSize.value))

const placeCropAtCenter = (size: number, centerX: number, centerY: number): EventCropRect => {
  const bounds = selectionBounds.value
  return {
    x: clamp(centerX - size / 2, bounds.x, bounds.x + bounds.width - size),
    y: clamp(centerY - size / 2, bounds.y, bounds.y + bounds.height - size),
    width: size,
    height: size
  }
}

const updateViewZoom = async (requestedZoom: number) => {
  const nextZoom = clamp(requestedZoom, 1, 5)
  const centerX = crop.value.x + crop.value.width / 2
  const centerY = crop.value.y + crop.value.height / 2
  const viewport = viewportRef.value
  // Inverse scaling keeps the frame approximately the same size on screen,
  // while its represented source area shrinks/grows like a phone cropper.
  const nextSize = clamp(
    (crop.value.width * viewZoom.value) / nextZoom,
    minimumSelectionSize.value,
    maximumSelectionSize.value
  )
  crop.value = placeCropAtCenter(nextSize, centerX, centerY)
  zoomFocus = {
    x: centerX,
    y: centerY,
    screenX: viewport ? centerX * viewport.scrollWidth - viewport.scrollLeft : null,
    screenY: viewport ? centerY * viewport.scrollHeight - viewport.scrollTop : null
  }
  viewZoom.value = nextZoom

  await nextTick()
  const el = viewportRef.value
  if (!el) return
  el.scrollLeft = zoomFocus.x * el.scrollWidth - (zoomFocus.screenX ?? el.clientWidth / 2)
  el.scrollTop = zoomFocus.y * el.scrollHeight - (zoomFocus.screenY ?? el.clientHeight / 2)
}

const toggleImageOnly = () => {
  if (constrainToImage.value) {
    constrainToImage.value = false
    return
  }

  const bounds = imageBounds.value
  const size = Math.min(bounds.width, bounds.height)
  constrainToImage.value = true
  crop.value = {
    x: bounds.x + (bounds.width - size) / 2,
    y: bounds.y + (bounds.height - size) / 2,
    width: size,
    height: size
  }
  zoomFocus = {
    x: bounds.x + bounds.width / 2,
    y: bounds.y + bounds.height / 2,
    screenX: null,
    screenY: null
  }
}

const normalizedPointer = (event: PointerEvent) => {
  const bounds = workspaceRef.value?.getBoundingClientRect()
  if (!bounds) return null
  return {
    x: (event.clientX - bounds.left) / bounds.width,
    y: (event.clientY - bounds.top) / bounds.height
  }
}

const beginMove = (event: PointerEvent) => {
  const point = normalizedPointer(event)
  if (!point || processing.value) return
  event.preventDefault()
  workspaceRef.value?.setPointerCapture(event.pointerId)
  interaction = {
    kind: 'move',
    pointerId: event.pointerId,
    startX: point.x,
    startY: point.y,
    initial: crop.value
  }
}

const beginResize = (event: PointerEvent, corner: ResizeCorner) => {
  const point = normalizedPointer(event)
  if (!point || processing.value) return
  event.preventDefault()
  event.stopPropagation()
  workspaceRef.value?.setPointerCapture(event.pointerId)
  interaction = {
    kind: 'resize',
    pointerId: event.pointerId,
    startX: point.x,
    startY: point.y,
    corner,
    initial: crop.value
  }
}

const handlePointerMove = (event: PointerEvent) => {
  const point = normalizedPointer(event)
  if (!interaction || !point || interaction.pointerId !== event.pointerId) return
  event.preventDefault()

  const dx = point.x - interaction.startX
  const dy = point.y - interaction.startY
  const initial = interaction.initial
  const bounds = selectionBounds.value

  if (interaction.kind === 'move') {
    crop.value = {
      ...initial,
      x: clamp(initial.x + dx, bounds.x, bounds.x + bounds.width - initial.width),
      y: clamp(initial.y + dy, bounds.y, bounds.y + bounds.height - initial.height)
    }
    return
  }

  const signs: Record<ResizeCorner, { x: number; y: number }> = {
    nw: { x: -1, y: -1 },
    ne: { x: 1, y: -1 },
    sw: { x: -1, y: 1 },
    se: { x: 1, y: 1 }
  }
  const sign = signs[interaction.corner]
  // Project pointer movement onto the corner diagonal. In normalized space,
  // equal width/height means the crop remains physically 4:1.
  const projectedDelta = (dx * sign.x + dy * sign.y) / 2

  const anchorRight = initial.x + initial.width
  const anchorBottom = initial.y + initial.height
  const maxSizeByCorner: Record<ResizeCorner, number> = {
    nw: Math.min(anchorRight - bounds.x, anchorBottom - bounds.y),
    ne: Math.min(bounds.x + bounds.width - initial.x, anchorBottom - bounds.y),
    sw: Math.min(anchorRight - bounds.x, bounds.y + bounds.height - initial.y),
    se: Math.min(bounds.x + bounds.width - initial.x, bounds.y + bounds.height - initial.y)
  }
  const size = clamp(
    initial.width + projectedDelta,
    minimumSelectionSize.value,
    maxSizeByCorner[interaction.corner]
  )

  const next: EventCropRect = { x: initial.x, y: initial.y, width: size, height: size }
  if (interaction.corner === 'nw' || interaction.corner === 'sw') {
    next.x = anchorRight - size
  }
  if (interaction.corner === 'nw' || interaction.corner === 'ne') {
    next.y = anchorBottom - size
  }
  crop.value = next
}

const finishInteraction = (event: PointerEvent) => {
  if (interaction?.pointerId !== event.pointerId) return
  interaction = null
  if (workspaceRef.value?.hasPointerCapture(event.pointerId)) {
    workspaceRef.value.releasePointerCapture(event.pointerId)
  }
}

const cropStyle = computed(() => ({
  left: `${crop.value.x * 100}%`,
  top: `${crop.value.y * 100}%`,
  width: `${crop.value.width * 100}%`,
  height: `${crop.value.height * 100}%`
}))

const handleConfirm = async () => {
  errorMessage.value = ''
  if (!sourceUrl.value || !imageSize.value.width) {
    errorMessage.value = 'Please wait for the selected image to load.'
    return
  }

  processing.value = true
  try {
    const cropped = await cropEventImage(sourceUrl.value, crop.value)
    emit('confirm', cropped)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to crop the image.'
  } finally {
    processing.value = false
  }
}

const onCancel = () => {
  if (processing.value) return
  emit('cancel')
  open.value = false
}
</script>

<style scoped>
/*
 * Vue's `scoped` styles never leak between components, so the .admin-modal*
 * chrome from ConfirmDialog.vue does not apply here even though this markup
 * reuses those class names for visual consistency — it has to be redefined
 * in every component that uses the pattern (see also ConfirmDialog.vue).
 */
.admin-modal {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.25rem;
}

.admin-modal__backdrop {
  position: absolute;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
}

.admin-modal__content {
  position: relative;
  width: 100%;
  max-width: 480px;
  background-color: var(--white);
  border-radius: 12px;
  box-shadow: 0 24px 60px rgba(7, 17, 15, 0.28);
  animation: admin-modal-in 0.18s ease;
  overflow: hidden;
}

.admin-modal__header {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-light);
}

.admin-modal__title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--charcoal);
  line-height: 1.3;
}

.admin-modal__body {
  padding: 1.25rem 1.5rem;
}

.admin-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem 1.25rem;
  border-top: 1px solid var(--border-light);
  background-color: var(--bg-light);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@keyframes admin-modal-in {
  from {
    opacity: 0;
    transform: translateY(-6px) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-modal__content {
    animation: none;
  }
}

.crop-dialog {
  padding: 1.25rem;
}

.admin-modal__content.crop-dialog__content {
  max-width: 780px;
}

.crop-dialog__body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.crop-dialog__hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
  line-height: 1.5;
}

.crop-dialog__viewport {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 1;
  overflow: auto;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  background-color: var(--bg-light);
}

.crop-dialog__workspace {
  position: relative;
  aspect-ratio: 4 / 1;
  overflow: hidden;
  background-color: var(--white);
  box-shadow: inset 0 0 0 1px rgba(7, 17, 15, 0.06);
  touch-action: none;
  user-select: none;
}

.crop-dialog__probe-image {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.crop-dialog__source-image {
  position: absolute;
  display: block;
  pointer-events: none;
}

.crop-dialog__crop {
  position: absolute;
  cursor: move;
  border: 2px solid #17785f;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5);
}

.crop-dialog__grid {
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(3, 1fr);
  pointer-events: none;
}

.crop-dialog__grid-cell {
  border: 1px solid rgba(255, 255, 255, 0.35);
}

.crop-dialog__handle {
  position: absolute;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: 2px solid #17785f;
  background-color: var(--white);
  box-shadow: 0 1px 4px rgba(7, 17, 15, 0.25);
  padding: 0;
}

.crop-dialog__handle--nw {
  left: -10px;
  top: -10px;
  cursor: nwse-resize;
}

.crop-dialog__handle--ne {
  right: -10px;
  top: -10px;
  cursor: nesw-resize;
}

.crop-dialog__handle--sw {
  left: -10px;
  bottom: -10px;
  cursor: nesw-resize;
}

.crop-dialog__handle--se {
  right: -10px;
  bottom: -10px;
  cursor: nwse-resize;
}

.crop-dialog__zoom-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.crop-dialog__zoom-label {
  flex-shrink: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--charcoal);
}

.crop-dialog__zoom-slider {
  flex: 1;
  min-width: 8rem;
}

.crop-dialog__zoom-value {
  width: 2.5rem;
  text-align: right;
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
}

.crop-dialog__mode-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.crop-dialog__mode-hint {
  margin: 0;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.crop-dialog__error {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}

@media (max-width: 640px) {
  .admin-modal__content.crop-dialog__content {
    max-width: 100%;
  }
}
</style>
