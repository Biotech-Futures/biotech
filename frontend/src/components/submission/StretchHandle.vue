<template>
  <div
    ref="handle"
    class="stretch-handle"
    role="separator"
    aria-orientation="horizontal"
    aria-label="Drag to resize the answer box"
    :aria-valuemin="minHeight || undefined"
    :aria-valuemax="maxHeight || undefined"
    :aria-valuenow="height ?? undefined"
    tabindex="0"
    data-testid="stretch-handle"
    @pointerdown="start"
    @keydown.up.prevent="nudge(-1)"
    @keydown.down.prevent="nudge(1)"
  ></div>
</template>

<script setup lang="ts">
/** A grip along the bottom border of the box above it: drag it, or use the arrow keys, to resize the box. */
import { onBeforeUnmount, ref } from 'vue'

const props = withDefaults(defineProps<{ height: number | null; minLines?: number; maxLines?: number }>(), {
  minLines: 5,
  maxLines: 20
})
const emit = defineEmits<{ 'update:height': [height: number] }>()

// Used when the box cannot be measured; the portal's 1.55 line height at 16px, plus padding and border.
const FALLBACK_LINE_PX = 24.8
const FALLBACK_CHROME_PX = 24.4

const handle = ref<HTMLElement | null>(null)
let startY = 0
let startHeight = 0

const box = () => handle.value?.parentElement?.firstElementChild as HTMLElement | null | undefined
const currentHeight = () => props.height ?? handle.value?.parentElement?.offsetHeight ?? 0

/** Pixel size of one line, and of the padding and border around the text. */
function metrics() {
  const element = box()
  const style = element ? getComputedStyle(element) : null
  const line = parseFloat(style?.lineHeight ?? '') || FALLBACK_LINE_PX
  const chrome = style
    ? ['paddingTop', 'paddingBottom', 'borderTopWidth', 'borderBottomWidth']
        .map((key) => parseFloat(style[key as keyof CSSStyleDeclaration] as string) || 0)
        .reduce((sum, value) => sum + value, 0)
    : 0
  return { line, chrome: chrome || FALLBACK_CHROME_PX }
}

function clamp(value: number) {
  const { line, chrome } = metrics()
  const min = props.minLines * line + chrome
  const max = props.maxLines * line + chrome
  return Math.round(Math.min(max, Math.max(min, value)))
}

const minHeight = ref(0)
const maxHeight = ref(0)
function refreshBounds() {
  const { line, chrome } = metrics()
  minHeight.value = Math.round(props.minLines * line + chrome)
  maxHeight.value = Math.round(props.maxLines * line + chrome)
}

function nudge(lines: number) {
  refreshBounds()
  emit('update:height', clamp(currentHeight() + lines * metrics().line))
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
  refreshBounds()
  startY = event.clientY
  startHeight = currentHeight()
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', stop)
}

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
