<template>
  <div
    ref="box"
    class="live-text"
    :class="{ 'live-text--single': rows === 1 }"
    :style="{ height: height ? `${height}px` : `calc(${rows} * 1.55em + 1.4rem + 2px)` }"
    role="textbox"
    aria-readonly="true"
    data-testid="live-text"
  >{{ before }}<span ref="caretEl" class="live-text__caret" aria-hidden="true"></span>{{ after }}</div>
</template>

<script setup lang="ts">
/** A teammate's text as they type it: read-only, eased in between updates, with their cursor in green. */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { SEND_TEXT_MS } from '@/composables/useLiveRoom'

const props = withDefaults(
  defineProps<{ text: string; caret: number | null; rows?: number; height?: number | null }>(),
  { rows: 5, height: null }
)

const box = ref<HTMLElement | null>(null)
const caretEl = ref<HTMLElement | null>(null)
const shown = ref(props.text)
let frame = 0

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

// Added text is typed out over the gap until the next update, so arrivals read as typing, not jumps.
watch(
  () => props.text,
  (next) => {
    cancelAnimationFrame(frame)
    const start = shown.value
    if (!next.startsWith(start) || next.length - start.length < 2 || reducedMotion()) {
      shown.value = next
      return
    }
    const added = next.slice(start.length)
    const began = performance.now()
    const step = (now: number) => {
      const progress = Math.min(1, (now - began) / SEND_TEXT_MS)
      shown.value = start + added.slice(0, Math.ceil(added.length * progress))
      if (progress < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
  }
)

// Typing at the end follows the text as it eases in; elsewhere the cursor stays where it is.
const caretAt = computed(() => {
  if (props.caret === null || props.caret >= props.text.length) return shown.value.length
  return Math.min(props.caret, shown.value.length)
})
const before = computed(() => shown.value.slice(0, caretAt.value))
const after = computed(() => shown.value.slice(caretAt.value))

watch(caretAt, async () => {
  await nextTick()
  const container = box.value
  const caret = caretEl.value
  if (!container || !caret) return
  const top = caret.offsetTop - container.offsetTop
  if (top < container.scrollTop) container.scrollTop = top
  else if (top + caret.offsetHeight > container.scrollTop + container.clientHeight) {
    container.scrollTop = top + caret.offsetHeight - container.clientHeight
  }
})

onBeforeUnmount(() => cancelAnimationFrame(frame))
</script>

<style scoped>
.live-text {
  background: var(--field-disabled-bg);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  overflow-y: auto;
  cursor: default;
}

.live-text--single {
  white-space: pre;
  overflow: hidden;
}

.live-text__caret {
  display: inline-block;
  width: 2px;
  height: 1.15em;
  margin: 0 -1px;
  vertical-align: text-bottom;
  background: var(--accent);
  animation: live-caret-blink 1s steps(1) infinite;
}

@keyframes live-caret-blink {
  50% {
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-text__caret {
    animation: none;
  }
}
</style>
