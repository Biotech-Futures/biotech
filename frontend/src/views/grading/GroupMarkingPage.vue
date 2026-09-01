<template>
  <div>
    <p v-if="isLoading" class="group-marking__hint">Loading marking payload…</p>

    <div v-else-if="loadError" class="card group-marking__error">
      <p>Failed to load marking payload for group {{ groupId }}.</p>
      <p class="group-marking__error-detail">{{ loadError }}</p>
      <div class="group-marking__error-actions">
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
        <RouterLink to="/grading/by-group" class="btn btn-outline btn-sm">Back</RouterLink>
      </div>
    </div>

    <div v-else-if="payload" class="group-marking">
      <div class="group-marking__header">
        <h2 class="group-marking__title">
          {{ payload.group.group_name }}
          <span class="group-marking__id">#{{ groupId }}</span>
        </h2>
        <div class="group-marking__header-actions">
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="isDownloading"
            @click="downloadAll"
          >
            <i class="fas fa-download" aria-hidden="true"></i>
            {{ isDownloading ? 'Preparing…' : 'Download all' }}
          </button>
          <RouterLink to="/grading/by-group" class="btn btn-outline btn-sm">Back</RouterLink>
        </div>
      </div>

      <p v-if="actionError" class="group-marking__banner group-marking__banner--error">
        {{ actionError }}
      </p>
      <p v-if="saveStatus === 'saved'" class="group-marking__banner group-marking__banner--ok">
        Marks saved.
      </p>

      <div class="group-marking__tabs" role="tablist" aria-label="Components">
        <button
          v-for="block in payload.components"
          :key="block.component.code"
          type="button"
          role="tab"
          :aria-selected="block.component.code === effectiveCode"
          class="group-marking__tab"
          :class="{ 'group-marking__tab--active': block.component.code === effectiveCode }"
          @click="activeCode = block.component.code"
        >
          {{ block.component.name }}
        </button>
      </div>

      <div v-if="activeBlock" class="group-marking__pane">
        <SubmissionPreview :submission="activeBlock.submission" :component="activeBlock.component" />
        <RubricForm
          :submission="activeBlock.submission"
          :criteria="activeBlock.criteria"
          :grades="activeBlock.grades"
          :is-saving="saveStatus === 'saving'"
          @save="saveMarks"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import RubricForm from '@/components/grading/RubricForm.vue'
import SubmissionPreview from '@/components/grading/SubmissionPreview.vue'
import {
  downloadGroupZip,
  fetchGroupMarking,
  saveGradesBulk,
  type GradeBulkItem,
  type GroupMarkingPayload
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const route = useRoute()
const groupId = computed(() => Number(route.params.groupId))

const payload = ref<GroupMarkingPayload | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const saveStatus = ref<'idle' | 'saving' | 'saved'>('idle')
const isDownloading = ref(false)
const activeCode = ref<string | null>(null)

const effectiveCode = computed(
  () => activeCode.value ?? payload.value?.components[0]?.component.code ?? null
)

const activeBlock = computed(
  () => payload.value?.components.find((b) => b.component.code === effectiveCode.value) ?? null
)

const load = async () => {
  if (!Number.isFinite(groupId.value) || groupId.value <= 0) return
  isLoading.value = true
  loadError.value = ''
  try {
    payload.value = await fetchGroupMarking(groupId.value)
  } catch (err) {
    payload.value = null
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

// Reload when navigating between groups; reset the tab so the first component
// shows for the new group rather than a stale selection.
watch(
  groupId,
  () => {
    activeCode.value = null
    saveStatus.value = 'idle'
    actionError.value = ''
    void load()
  },
  { immediate: true }
)

const saveMarks = async (items: GradeBulkItem[]) => {
  saveStatus.value = 'saving'
  actionError.value = ''
  try {
    await saveGradesBulk(items)
    // Refetch so grades (ids, graded_by) mirror the server after the upsert.
    payload.value = await fetchGroupMarking(groupId.value)
    saveStatus.value = 'saved'
  } catch (err) {
    saveStatus.value = 'idle'
    actionError.value = `Save failed: ${apiErrorFromUnknown(err).message}`
  }
}

const downloadAll = async () => {
  isDownloading.value = true
  actionError.value = ''
  try {
    await downloadGroupZip(groupId.value)
  } catch (err) {
    actionError.value = `Download failed: ${apiErrorFromUnknown(err).message}`
  } finally {
    isDownloading.value = false
  }
}
</script>

<style scoped>
.group-marking__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.group-marking__error p {
  margin: 0 0 0.5rem;
}

.group-marking__error-detail {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.group-marking__error-actions {
  display: flex;
  gap: 0.5rem;
}

.group-marking {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.group-marking__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.group-marking__title {
  margin: 0;
  font-size: 1.35rem;
}

.group-marking__id {
  color: var(--text-muted);
  font-size: 0.9rem;
  font-weight: 400;
}

.group-marking__header-actions {
  display: flex;
  gap: 0.5rem;
}

.group-marking__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.group-marking__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.group-marking__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

.group-marking__tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  border-bottom: 1px solid var(--border-light);
}

.group-marking__tab {
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  background: none;
  padding: 0.4rem 0.8rem;
  font-size: 0.9rem;
  font-family: inherit;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  transition:
    color 0.15s ease,
    border-color 0.15s ease,
    background-color 0.15s ease;
}

.group-marking__tab:hover {
  color: var(--charcoal);
}

.group-marking__tab--active {
  color: var(--dark-green);
  border-bottom-color: var(--dark-green);
  background: var(--accent-green-soft);
}

.group-marking__pane {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 900px) {
  .group-marking__pane {
    grid-template-columns: 1fr;
  }
}
</style>
