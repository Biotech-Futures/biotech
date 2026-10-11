<template>
  <div
    ref="handle"
    class="stretch-handle"
    role="separator"
    aria-orientation="horizontal"
    aria-label="Drag to resize the answer box"
    :aria-valuemin="minHeight"
    :aria-valuemax="MAX_STRETCH_PX"
    :aria-valuenow="height ?? minHeight"
    tabindex="0"
    data-testid="stretch-handle"
    @pointerdown="start"
    @keydown.up.prevent="nudge(-KEY_STEP_PX)"
    @keydown.down.prevent="nudge(KEY_STEP_PX)"
  ></div>
</template>

<script setup lang="ts">
/** A grip along the bottom border of the box above it: drag it, or use the arrow keys, to resize the box. */
import { onBeforeUnmount, onMounted, ref } from 'vue'

/** About 20 lines: room to see a whole answer, without the box running down the page. */
const MAX_STRETCH_PX = 520
const KEY_STEP_PX = 24

const props = defineProps<{ height: number | null }>()
const emit = defineEmits<{ 'update:height': [height: number] }>()

const handle = ref<HTMLElement | null>(null)
// The box's own size before any stretching, so it never shrinks below it.
const minHeight = ref(0)
let startY = 0
let startHeight = 0

const boxHeight = () => handle.value?.parentElement?.offsetHeight ?? 0
const clamp = (value: number) => Math.round(Math.min(MAX_STRETCH_PX, Math.max(minHeight.value, value)))

// Measured at the first touch, as the box may be hidden when the page loads.
function measureMin() {
  if (!minHeight.value) minHeight.value = boxHeight()
}

function nudge(by: number) {
  measureMin()
  emit('update:height', clamp((props.height ?? boxHeight()) + by))
}

function move(event: PointerEvent) {
  emit('update:height', clamp(startHeight + event.clientY - startY))
}

function stop() {
  window.removeEventListener('pointermove', move)
  window.removeEventListener('pointerup', stop)
}

function start(event: PointerEvent) {
  event.preventDefault()
  measureMin()
  startY = event.clientY
  startHeight = props.height ?? boxHeight()
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', stop)
}

onMounted(measureMin)
onBeforeUnmount(stop)
</script>

<style scoped>
.stretch-handle {
  position: absolute;
  left: 0.5rem;
  right: 0.5rem;
  bottom: -5px;
  height: 10px;
  cursor: ns-resize;
  touch-action: none;
}

.stretch-handle::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 3px;
  width: 36px;
  height: 4px;
  margin-left: -18px;
  border-radius: 2px;
  background: var(--field-border);
  opacity: 0.6;
  transition: opacity 0.15s ease;
}

.stretch-handle:hover::after,
.stretch-handle:focus-visible::after {
  opacity: 1;
}

.stretch-handle:focus-visible {
  outline: none;
}

.stretch-handle:focus-visible::after {
  background: var(--accent);
}
</style>
