<template>
  <div class="signature-pad" :class="{ 'signature-pad--invalid': invalid }">
    <canvas
      ref="canvasRef"
      class="signature-pad__canvas"
      role="img"
      :aria-label="hasInk ? 'Your signature' : 'Signature box. Sign here with your finger, stylus or mouse.'"
      @pointerdown="start"
      @pointermove="move"
      @pointerup="end"
      @pointercancel="end"
      @pointerleave="end"
    ></canvas>
    <span v-if="!hasInk" class="signature-pad__hint" aria-hidden="true">Sign here</span>
    <button
      type="button"
      class="signature-pad__clear"
      :disabled="!hasInk || disabled"
      data-test="signature-clear"
      @click="clear"
    >
      Clear
    </button>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps<{ disabled?: boolean; invalid?: boolean }>()

/** The signature as a transparent PNG data URL, or null once cleared. */
const emit = defineEmits<{ (e: 'change', dataUrl: string | null): void }>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const hasInk = ref(false)
let drawing = false
let last: { x: number; y: number } | null = null
let resizeObserver: ResizeObserver | null = null

// Capped so a high-density phone screen doesn't produce a huge image.
const scale = () => Math.min(window.devicePixelRatio || 1, 2)

function context() {
  const ctx = canvasRef.value?.getContext('2d')
  if (!ctx) return null
  ctx.lineWidth = 2.4 * scale()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = '#10211d'
  return ctx
}

function size() {
  const canvas = canvasRef.value
  if (!canvas) return
  const { width, height } = canvas.getBoundingClientRect()
  const w = Math.round(width * scale())
  const h = Math.round(height * scale())
  if (canvas.width === w && canvas.height === h) return
  // Resizing wipes the canvas, so a signature drawn at the old size is lost.
  canvas.width = w
  canvas.height = h
  if (hasInk.value) clear()
}

function point(event: PointerEvent) {
  const rect = canvasRef.value!.getBoundingClientRect()
  return { x: (event.clientX - rect.left) * scale(), y: (event.clientY - rect.top) * scale() }
}

function start(event: PointerEvent) {
  if (props.disabled || !canvasRef.value) return
  event.preventDefault()
  canvasRef.value.setPointerCapture?.(event.pointerId)
  drawing = true
  last = point(event)
  const ctx = context()
  if (!ctx) return
  // A tap leaves a dot.
  ctx.beginPath()
  ctx.arc(last.x, last.y, ctx.lineWidth / 2, 0, Math.PI * 2)
  ctx.fillStyle = ctx.strokeStyle
  ctx.fill()
  hasInk.value = true
}

function move(event: PointerEvent) {
  if (!drawing || !last) return
  event.preventDefault()
  const next = point(event)
  const ctx = context()
  if (!ctx) return
  ctx.beginPath()
  ctx.moveTo(last.x, last.y)
  ctx.lineTo(next.x, next.y)
  ctx.stroke()
  last = next
}

function end() {
  if (!drawing) return
  drawing = false
  last = null
  emit('change', canvasRef.value?.toDataURL('image/png') ?? null)
}

function clear() {
  const canvas = canvasRef.value
  canvas?.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height)
  hasInk.value = false
  emit('change', null)
}

onMounted(() => {
  size()
  if (typeof ResizeObserver !== 'undefined' && canvasRef.value) {
    resizeObserver = new ResizeObserver(size)
    resizeObserver.observe(canvasRef.value)
  }
})

onBeforeUnmount(() => resizeObserver?.disconnect())

defineExpose({ clear })
</script>

<style scoped>
.signature-pad {
  position: relative;
  border: 1px dashed rgba(16, 33, 29, 0.28);
  border-radius: 12px;
  background: #ffffff;
}

.signature-pad--invalid {
  border-color: rgba(210, 75, 75, 0.6);
}

.signature-pad__canvas {
  display: block;
  width: 100%;
  height: 180px;
  touch-action: none;
  cursor: crosshair;
  border-radius: 12px;
}

.signature-pad__hint {
  position: absolute;
  left: 18px;
  bottom: 16px;
  color: rgba(54, 81, 74, 0.5);
  font-size: 0.95rem;
  pointer-events: none;
}

.signature-pad__clear {
  position: absolute;
  top: 10px;
  right: 10px;
  padding: 6px 12px;
  border: 1px solid rgba(16, 33, 29, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: #36514a;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
}

.signature-pad__clear:disabled {
  opacity: 0.45;
  cursor: default;
}
</style>
