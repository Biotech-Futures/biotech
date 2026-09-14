<template>
  <div ref="pane" class="split" :class="{ 'split--dragging': dragging }" :style="paneStyle">
    <div class="split__side"><slot name="left" /></div>
    <div
      class="split__divider"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize panels"
      :aria-valuenow="Math.round(leftPct ?? 50)"
      aria-valuemin="25"
      aria-valuemax="75"
      tabindex="0"
      @pointerdown="startDrag"
      @keydown="onKeydown"
    ></div>
    <div class="split__side"><slot name="right" /></div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  /** Cap for the right pane before any drag — the left pane takes the rest. */
  rightMax?: string
}>()

const MIN_PCT = 25
const MAX_PCT = 75

const pane = ref<HTMLDivElement | null>(null)
// null = untouched: the right pane sizes to its content cap (rightMax) and
// the left pane gets everything else. A drag switches to explicit percentages.
const leftPct = ref<number | null>(null)
const dragging = ref(false)

const paneStyle = computed(() => {
  if (leftPct.value === null) {
    const right = props.rightMax ? `fit-content(${props.rightMax})` : 'minmax(0, 1fr)'
    return { '--split-cols': `minmax(0, 1fr) auto ${right}` }
  }
  return { '--split-cols': `${leftPct.value}% auto minmax(0, 1fr)` }
})

const clamp = (pct: number) => Math.min(MAX_PCT, Math.max(MIN_PCT, pct))

const startDrag = (event: PointerEvent) => {
  const el = pane.value
  const handle = event.currentTarget as HTMLElement
  if (!el) return
  event.preventDefault()
  dragging.value = true
  handle.setPointerCapture(event.pointerId)
  const rect = el.getBoundingClientRect()

  const move = (e: PointerEvent) => {
    leftPct.value = clamp(((e.clientX - rect.left) / rect.width) * 100)
  }
  const stop = () => {
    dragging.value = false
    handle.removeEventListener('pointermove', move)
    handle.removeEventListener('pointerup', stop)
    handle.removeEventListener('pointercancel', stop)
  }
  handle.addEventListener('pointermove', move)
  handle.addEventListener('pointerup', stop)
  handle.addEventListener('pointercancel', stop)
}

// Keyboard access for the separator: arrow keys nudge the split.
const currentPct = (): number => {
  if (leftPct.value !== null) return leftPct.value
  // Untouched: measure where the divider actually sits right now.
  const el = pane.value
  const handle = el?.querySelector('.split__divider')
  if (el && handle) {
    const paneRect = el.getBoundingClientRect()
    const handleRect = handle.getBoundingClientRect()
    if (paneRect.width) return ((handleRect.left - paneRect.left) / paneRect.width) * 100
  }
  return 50
}

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowLeft') {
    leftPct.value = clamp(currentPct() - 2)
    e.preventDefault()
  } else if (e.key === 'ArrowRight') {
    leftPct.value = clamp(currentPct() + 2)
    e.preventDefault()
  }
}
</script>

<style scoped>
.split {
  display: grid;
  grid-template-columns: var(--split-cols, minmax(0, 1fr) auto minmax(0, 1fr));
  align-items: start;
}

/* While dragging, stop text selection from fighting the gesture. */
.split--dragging {
  user-select: none;
  cursor: col-resize;
}

.split__side {
  min-width: 0;
}

.split__divider {
  width: 4px;
  align-self: stretch;
  margin: 0 0.5rem;
  border-radius: 999px;
  background: var(--border-light);
  cursor: col-resize;
  touch-action: none;
}

.split__divider:hover,
.split--dragging .split__divider {
  background: var(--dark-green);
}

.split__divider:focus-visible {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

@media (max-width: 900px) {
  .split {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .split__divider {
    display: none;
  }
}
</style>
