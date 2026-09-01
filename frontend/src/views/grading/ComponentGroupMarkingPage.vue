<template>
  <div>
    <p v-if="isLoading" class="component-marking__hint">Loading…</p>

    <div v-else-if="loadError" class="card component-marking__error">
      <p>Failed to load group {{ groupId }}.</p>
      <p class="component-marking__error-detail">{{ loadError }}</p>
      <div class="component-marking__error-actions">
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
        <RouterLink :to="`/grading/components/${code}`" class="btn btn-outline btn-sm">
          Back to list
        </RouterLink>
      </div>
    </div>

    <div v-else-if="payload && !block" class="card component-marking__error">
      <p>No such component "{{ code }}" for this group.</p>
      <RouterLink :to="`/grading/components/${code}`" class="btn btn-outline btn-sm">
        Back to list
      </RouterLink>
    </div>

    <div v-else-if="payload && block" class="component-marking">
      <div class="component-marking__header">
        <h2 class="component-marking__title">
          {{ block.component.name }}: {{ payload.group.group_name }}
          <span class="component-marking__id">#{{ groupId }}</span>
        </h2>
        <div class="component-marking__nav">
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="prevId == null"
            @click="goto(prevId)"
          >
            <i class="fas fa-chevron-left" aria-hidden="true"></i> Prev
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="nextId == null"
            @click="goto(nextId)"
          >
            Next <i class="fas fa-chevron-right" aria-hidden="true"></i>
          </button>
          <RouterLink :to="`/grading/components/${code}`" class="btn btn-outline btn-sm">
            List
          </RouterLink>
        </div>
      </div>

      <p v-if="actionError" class="component-marking__banner component-marking__banner--error">
        {{ actionError }}
      </p>
      <p v-if="saveStatus === 'saved'" class="component-marking__banner component-marking__banner--ok">
        Marks saved.
      </p>

      <div class="component-marking__pane">
        <SubmissionPreview
          :submission="block.submission"
          :component="block.component"
          :last-grader-name="currentRow?.last_grader_name"
          :grader-names="currentRow?.grader_names"
        />
        <RubricForm
          :submission="block.submission"
          :criteria="block.criteria"
          :grades="block.grades"
          :is-saving="saveStatus === 'saving'"
          @save="saveMarks"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RubricForm from '@/components/grading/RubricForm.vue'
import SubmissionPreview from '@/components/grading/SubmissionPreview.vue'
import {
  fetchComponentRows,
  fetchGroupMarking,
  saveGradesBulk,
  type ComponentListPayload,
  type GradeBulkItem,
  type GroupMarkingPayload
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const route = useRoute()
const router = useRouter()
const code = computed(() => String(route.params.code || ''))
const groupId = computed(() => Number(route.params.groupId))

const payload = ref<GroupMarkingPayload | null>(null)
const rows = ref<ComponentListPayload | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const saveStatus = ref<'idle' | 'saving' | 'saved'>('idle')

const block = computed(
  () => payload.value?.components.find((b) => b.component.code === code.value) ?? null
)

const currentRow = computed(
  () => rows.value?.rows.find((r) => r.group_id === groupId.value) ?? null
)

// Prev/next from the component row list, skipping groups without a submission
// — no point navigating to an empty marking pane.
const prevId = computed(() => {
  const list = rows.value?.rows ?? []
  const idx = list.findIndex((r) => r.group_id === groupId.value)
  if (idx < 0) return null
  const back = list
    .slice(0, idx)
    .reverse()
    .find((r) => r.submission_id != null)
  return back?.group_id ?? null
})

const nextId = computed(() => {
  const list = rows.value?.rows ?? []
  const idx = list.findIndex((r) => r.group_id === groupId.value)
  if (idx < 0) return null
  const fwd = list.slice(idx + 1).find((r) => r.submission_id != null)
  return fwd?.group_id ?? null
})

const load = async () => {
  if (!code.value || !Number.isFinite(groupId.value) || groupId.value <= 0) return
  isLoading.value = true
  loadError.value = ''
  try {
    // Rows drive prev/next and marker info; the group payload drives the pane.
    const [groupPayload, rowsPayload] = await Promise.all([
      fetchGroupMarking(groupId.value),
      fetchComponentRows(code.value)
    ])
    payload.value = groupPayload
    rows.value = rowsPayload
  } catch (err) {
    payload.value = null
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

watch(
  () => [code.value, groupId.value],
  () => {
    saveStatus.value = 'idle'
    actionError.value = ''
    void load()
  },
  { immediate: true }
)

const goto = (id: number | null) => {
  if (id == null) return
  void router.push(`/grading/components/${code.value}/${id}`)
}

const saveMarks = async (items: GradeBulkItem[]) => {
  saveStatus.value = 'saving'
  actionError.value = ''
  try {
    await saveGradesBulk(items)
    // Refetch both: grades for the form, rows for progress + marker columns.
    const [groupPayload, rowsPayload] = await Promise.all([
      fetchGroupMarking(groupId.value),
      fetchComponentRows(code.value)
    ])
    payload.value = groupPayload
    rows.value = rowsPayload
    saveStatus.value = 'saved'
  } catch (err) {
    saveStatus.value = 'idle'
    actionError.value = `Save failed: ${apiErrorFromUnknown(err).message}`
  }
}
</script>

<style scoped>
.component-marking__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.component-marking__error p {
  margin: 0 0 0.5rem;
}

.component-marking__error-detail {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.component-marking__error-actions {
  display: flex;
  gap: 0.5rem;
}

.component-marking {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.component-marking__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.component-marking__title {
  margin: 0;
  font-size: 1.35rem;
}

.component-marking__id {
  color: var(--text-muted);
  font-size: 0.9rem;
  font-weight: 400;
}

.component-marking__nav {
  display: flex;
  gap: 0.35rem;
}

.component-marking__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.component-marking__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.component-marking__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

.component-marking__pane {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 900px) {
  .component-marking__pane {
    grid-template-columns: 1fr;
  }
}
</style>
