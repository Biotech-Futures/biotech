<template>
  <div v-if="layout && cursors.length" class="shared-cursors" :style="layout.frame" aria-hidden="true">
    <div ref="mirror" class="shared-cursors__mirror" :style="layout.mirror">
      <template v-for="part in parts" :key="part.key">
        <span v-if="part.id !== null" class="shared-cursors__marker" :data-cursor="part.id"></span>
        <template v-else>{{ part.text }}</template>
      </template>
    </div>
    <span
      v-for="spot in spots"
      :key="spot.id"
      class="shared-cursors__caret"
      :style="{ left: `${spot.x}px`, top: `${spot.y}px`, height: `${spot.height}px` }"
      data-testid="shared-cursor"
    >
      <span class="shared-cursors__name" :class="{ 'is-shown': spot.labelled }">{{ spot.name }}</span>
    </span>
  </div>
</template>

<script lang="ts">
/** A teammate's name shows beside their cursor this long after they start typing, then goes even if they carry on. */
export const LABEL_MS = 2000
</script>

<script setup lang="ts">
/**
 * Teammates' cursors drawn over a text box, in green, each named briefly as that person starts typing. An
 * invisible copy of the box's text, laid out exactly as the box lays it out, tells where each falls.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type CSSProperties } from 'vue'
import type { CursorSource } from '@/composables/useCoeditedFields'

const props = defineProps<{ source: CursorSource }>()

interface Spot {
  id: number
  name: string
  x: number
  y: number
  height: number
  labelled: boolean
}

// Everything that decides where text wraps, copied from the box.
const COPIED = [
  'fontFamily',
  'fontSize',
  'fontWeight',
  'fontStyle',
  'fontVariant',
  'fontStretch',
  'letterSpacing',
  'wordSpacing',
  'textTransform',
  'textIndent',
  'textAlign',
  'tabSize',
  'direction',
  'paddingTop',
  'paddingRight',
  'paddingBottom',
  'paddingLeft'
] as const

const mirror = ref<HTMLElement | null>(null)
const layout = ref<{ frame: CSSProperties; mirror: CSSProperties } | null>(null)
const spots = ref<Spot[]>([])
const now = ref(Date.now())
let labelTimer: ReturnType<typeof setTimeout> | null = null
let resizeObserver: ResizeObserver | null = null
let watched: HTMLElement | null = null

const cursors = computed(() => props.source.cursors.value)

/** The shown text, split at each cursor. */
const parts = computed(() => {
  const text = props.source.text.value
  const sorted = [...cursors.value].sort((a, b) => a.index - b.index)
  const result: Array<{ key: string; text: string; id: number | null }> = []
  let from = 0
  sorted.forEach((cursor) => {
    const at = Math.min(Math.max(cursor.index, from), text.length)
    result.push({ key: `t${from}`, text: text.slice(from, at), id: null })
    result.push({ key: `c${cursor.id}`, text: '', id: cursor.id })
    from = at
  })
  result.push({ key: `t${from}`, text: text.slice(from), id: null })
  return result
})

function measure() {
  const box = props.source.target()
  // A hidden box (e.g. swapped for a teammate's live panel) has no layout to draw over.
  if (!box || box.offsetParent === null) {
    layout.value = null
    return
  }
  const style = getComputedStyle(box)
  const single = box.tagName === 'INPUT'
  const copied = Object.fromEntries(COPIED.map((name) => [name, style[name]])) as CSSProperties
  const innerHeight = box.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)
  layout.value = {
    frame: {
      top: `${box.offsetTop + box.clientTop}px`,
      left: `${box.offsetLeft + box.clientLeft}px`,
      width: `${box.clientWidth}px`,
      height: `${box.clientHeight}px`
    },
    mirror: {
      ...copied,
      width: `${box.clientWidth}px`,
      height: `${box.clientHeight}px`,
      // A one-line box centres its line; a text area wraps as typed.
      lineHeight: single ? `${innerHeight}px` : style.lineHeight,
      whiteSpace: single ? 'pre' : 'pre-wrap',
      overflowWrap: single ? 'normal' : 'break-word'
    }
  }
}

async function place() {
  await nextTick()
  const box = props.source.target()
  const copy = mirror.value
  if (!box || !copy || !layout.value) {
    spots.value = []
    return
  }
  const byId = new Map(cursors.value.map((cursor) => [cursor.id, cursor]))
  const next: Spot[] = []
  copy.querySelectorAll<HTMLElement>('[data-cursor]').forEach((marker) => {
    const cursor = byId.get(Number(marker.dataset.cursor))
    if (!cursor) return
    const x = marker.offsetLeft - box.scrollLeft
    const y = marker.offsetTop - box.scrollTop
    const height = marker.offsetHeight
    // Cursors scrolled out of the box are not drawn over the page around it.
    if (y + height <= 0 || y >= box.clientHeight || x < 0 || x > box.clientWidth) return
    const labelled = cursor.startedAt !== null && now.value - cursor.startedAt < LABEL_MS
    next.push({ id: cursor.id, name: cursor.name, x, y, height, labelled })
  })
  spots.value = next
}

/** Hides each name LABEL_MS after its typing started. */
function scheduleLabels() {
  if (labelTimer) clearTimeout(labelTimer)
  labelTimer = null
  now.value = Date.now()
  const due = cursors.value
    .map((cursor) => (cursor.startedAt === null ? Infinity : cursor.startedAt + LABEL_MS - now.value))
    .filter((wait) => wait > 0 && wait !== Infinity)
  if (due.length) labelTimer = setTimeout(scheduleLabels, Math.min(...due))
  void place()
}

function watchBox() {
  const box = props.source.target()
  if (box === watched) return
  watched?.removeEventListener('scroll', onScroll)
  resizeObserver?.disconnect()
  watched = box
  if (!box) return
  box.addEventListener('scroll', onScroll, { passive: true })
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      measure()
      void place()
    })
    resizeObserver.observe(box)
  }
}

function onScroll() {
  void place()
}

watch(
  () => cursors.value.length > 0,
  (any) => {
    if (!any) return
    watchBox()
    measure()
  },
  { immediate: true }
)
watch(parts, () => void place())
watch(cursors, scheduleLabels)

onMounted(() => {
  watchBox()
  measure()
  scheduleLabels()
})

onBeforeUnmount(() => {
  if (labelTimer) clearTimeout(labelTimer)
  watched?.removeEventListener('scroll', onScroll)
  resizeObserver?.disconnect()
})
</script>

<style scoped>
.shared-cursors {
  position: absolute;
  pointer-events: none;
}

.shared-cursors__mirror {
  position: absolute;
  top: 0;
  left: 0;
  box-sizing: border-box;
  overflow: hidden;
  visibility: hidden;
}

.shared-cursors__marker {
  display: inline-block;
  width: 0;
  height: 1.15em;
  vertical-align: text-bottom;
}

.shared-cursors__caret {
  position: absolute;
  width: 2px;
  margin-left: -1px;
  background: var(--accent);
}

.shared-cursors__name {
  position: absolute;
  bottom: 100%;
  left: 0;
  padding: 0 0.3rem;
  border-radius: 2px;
  background: var(--accent);
  color: #fff;
  font-size: 0.7rem;
  line-height: 1.4;
  white-space: nowrap;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.shared-cursors__name.is-shown {
  opacity: 1;
}

@media (prefers-reduced-motion: reduce) {
  .shared-cursors__name {
    transition: none;
  }
}
</style>
