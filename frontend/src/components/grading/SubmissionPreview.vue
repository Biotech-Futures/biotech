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

    <pre v-if="submission.text" class="submission-preview__text">{{ submission.text }}</pre>

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
      :src="fileUrl"
      :title="`${component.name} preview`"
      class="submission-preview__frame"
    ></iframe>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { resolveApiFileUrl, type Submission, type SubmissionComponent } from '@/utils/gradingAPI'

const props = defineProps<{
  submission: Submission | null
  component: SubmissionComponent
  lastGraderName?: string | null
  graderNames?: string[]
}>()

const fileUrl = computed(() => resolveApiFileUrl(props.submission?.file_url ?? null))

const submittedLabel = computed(() =>
  props.submission ? new Date(props.submission.submitted_at).toLocaleString() : ''
)

const markerTooltip = computed(() => {
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

.submission-preview__link {
  font-size: 0.9rem;
  color: var(--dark-green);
  text-decoration: underline;
  word-break: break-all;
}

.submission-preview__frame {
  width: 100%;
  height: 60vh;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-elevated);
}
</style>
