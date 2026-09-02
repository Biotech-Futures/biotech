<template>
  <div v-if="!submission" class="submission-preview__empty">
    No submission uploaded for {{ component.name }}.
  </div>

  <div v-else class="submission-preview">
    <div class="submission-preview__meta">
      <p class="submission-preview__stamp">
        Submitted {{ submittedLabel }}<template v-if="submission.is_late"> (late)</template>
        <template v-if="lastGraderName">
          · Marker:
          <span class="submission-preview__marker" :title="markerTooltip">
            {{ lastGraderName }}
            <i
              v-if="(graderNames?.length ?? 0) > 1"
              class="fas fa-users submission-preview__marker-icon"
              aria-hidden="true"
            ></i>
          </span>
        </template>
      </p>
      <a
        v-if="fileUrl"
        :href="fileUrl"
        target="_blank"
        rel="noreferrer"
        class="btn btn-outline btn-sm"
      >
        Open <i class="fas fa-arrow-up-right-from-square" aria-hidden="true"></i>
      </a>
    </div>

    <div v-if="submission.answers?.length" class="submission-preview__answers">
      <section
        v-for="(block, i) in submission.answers"
        :key="i"
        class="submission-preview__answer"
      >
        <h4 class="submission-preview__question">{{ block.prompt }}</h4>
        <p class="submission-preview__answer-text">{{ block.answer }}</p>
      </section>
    </div>
    <pre v-else-if="submission.text" class="submission-preview__text">{{ submission.text }}</pre>

    <a
      v-if="submission.link"
      :href="submission.link"
      class="submission-preview__link"
      target="_blank"
      rel="noreferrer"
    >
      {{ submission.link }}
    </a>

    <iframe
      v-if="fileUrl"
      ref="frameEl"
      :src="frameUrl ?? undefined"
      :title="`${component.name} preview`"
      class="submission-preview__frame"
      :class="{ 'submission-preview__frame--dragging': draggingHeight }"
      :style="frameHeight != null ? { height: `${frameHeight}px` } : undefined"
    ></iframe>
    <div
      v-if="fileUrl"
      class="submission-preview__resize"
      role="separator"
      aria-orientation="horizontal"
      aria-label="Resize preview height"
      tabindex="0"
      @pointerdown="startHeightDrag"
      @keydown="onHeightKeydown"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { resolveApiFileUrl, type Submission, type SubmissionComponent } from '@/utils/gradingAPI'

const props = defineProps<{
  submission: Submission | null
  component: SubmissionComponent
  lastGraderName?: string | null
  graderNames?: string[]
  /** Latest marker per rubric criterion — one tooltip line per part. */
  criterionMarkers?: { name: string; marker: string }[]
}>()

const fileUrl = computed(() => resolveApiFileUrl(props.submission?.file_url ?? null))

// Ask the browser's PDF viewer to start with the thumbnail sidebar closed.
// Fragment params are viewer hints: Chromium/Adobe honour navpanes=0, pdf.js
// (Firefox) honours pagemode=none; others ignore them. The fragment is never
// sent to the server, so Azure SAS query strings are unaffected.
const frameUrl = computed(() => {
  const url = fileUrl.value
  if (!url) return null
  const isPdf = (() => {
    try {
      return new URL(url, window.location.origin).pathname.toLowerCase().endsWith('.pdf')
    } catch {
      return false
    }
  })()
  return isPdf ? `${url}#navpanes=0&pagemode=none` : url
})

// Drag the bar under the preview to change its height. null = default 80vh.
const MIN_FRAME_PX = 240
const frameEl = ref<HTMLIFrameElement | null>(null)
const frameHeight = ref<number | null>(null)
const draggingHeight = ref(false)

const startHeightDrag = (event: PointerEvent) => {
  const frame = frameEl.value
  const handle = event.currentTarget as HTMLElement
  if (!frame) return
  event.preventDefault()
  draggingHeight.value = true
  handle.setPointerCapture(event.pointerId)
  const startY = event.clientY
  const startHeight = frame.getBoundingClientRect().height

  const move = (e: PointerEvent) => {
    frameHeight.value = Math.max(MIN_FRAME_PX, Math.round(startHeight + (e.clientY - startY)))
  }
  const stop = () => {
    draggingHeight.value = false
    handle.removeEventListener('pointermove', move)
    handle.removeEventListener('pointerup', stop)
    handle.removeEventListener('pointercancel', stop)
  }
  handle.addEventListener('pointermove', move)
  handle.addEventListener('pointerup', stop)
  handle.addEventListener('pointercancel', stop)
}

const onHeightKeydown = (e: KeyboardEvent) => {
  const current = frameHeight.value ?? frameEl.value?.getBoundingClientRect().height ?? 0
  if (e.key === 'ArrowDown') {
    frameHeight.value = Math.round(current + 40)
    e.preventDefault()
  } else if (e.key === 'ArrowUp') {
    frameHeight.value = Math.max(MIN_FRAME_PX, Math.round(current - 40))
    e.preventDefault()
  }
}

const submittedLabel = computed(() =>
  props.submission ? new Date(props.submission.submitted_at).toLocaleString() : ''
)

const markerTooltip = computed(() => {
  // One line per rubric criterion with whoever last marked it.
  if (props.criterionMarkers?.length) {
    return props.criterionMarkers.map((c) => `${c.name}: ${c.marker}`).join('\n')
  }
  const names = props.graderNames?.length
    ? props.graderNames
    : props.lastGraderName
      ? [props.lastGraderName]
      : []
  return names.length ? `Marked by: ${names.join(', ')}` : ''
})
</script>

<style scoped>
.submission-preview__empty {
  border: 1px dashed var(--border-light);
  border-radius: 8px;
  padding: 1.5rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.submission-preview {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.submission-preview__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.submission-preview__stamp {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0;
}

.submission-preview__marker {
  color: var(--charcoal);
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.submission-preview__marker-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.submission-preview__text {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--bg-light);
  padding: 0.75rem;
  font-size: 0.85rem;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 60vh;
  overflow: auto;
}

/* One continuous white sheet behind every answer; the gaps between the
   outlined blocks stay white instead of showing the page background. */
.submission-preview__answers {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  background: #fff;
  padding: 0.85rem;
  border-radius: 8px;
  max-height: 70vh;
  overflow: auto;
}

.submission-preview__question {
  margin: 0 0 0.4rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: #000;
}

/* Only the answer is outlined — like the Mark/Comment inputs beside it —
   while the question sits on the white sheet above the box. */
.submission-preview__answer-text {
  margin: 0;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: #fff;
  padding: 0.85rem 1rem;
  font-size: 0.9rem;
  line-height: 1.55;
  color: var(--text-primary, #1f2937);
  white-space: pre-wrap;
  word-break: break-word;
}

.submission-preview__link {
  font-size: 0.9rem;
  color: var(--dark-green);
  text-decoration: underline;
  word-break: break-all;
}

.submission-preview__frame {
  width: 100%;
  height: 80vh;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-elevated);
}

/* While dragging the handle, keep the iframe from swallowing pointer events. */
.submission-preview__frame--dragging {
  pointer-events: none;
}

.submission-preview__resize {
  height: 4px;
  width: 100%;
  margin: 0.15rem 0 0;
  border-radius: 999px;
  background: var(--border-light);
  cursor: row-resize;
  touch-action: none;
}

.submission-preview__resize:hover,
.submission-preview__resize:active {
  background: var(--dark-green);
}

.submission-preview__resize:focus-visible {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}
</style>
