<template>
  <div>
    <p v-if="isLoading" class="component-table__hint">Loading…</p>

    <div v-else-if="loadError" class="card component-table__error">
      <p>Failed to load component "{{ code }}".</p>
      <p class="component-table__error-detail">{{ loadError }}</p>
      <div class="component-table__error-actions">
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
        <RouterLink to="/grading/by-component" class="btn btn-outline btn-sm">Back</RouterLink>
      </div>
    </div>

    <div v-else-if="payload" class="component-table">
      <div class="component-table__header">
        <h2 class="component-table__title">{{ payload.component.name }}</h2>
        <div class="component-table__actions">
          <p class="component-table__stats">
            {{ submittedCount }}/{{ payload.rows.length }} submitted ·
            {{ fullyMarkedCount }}/{{ submittedCount }} fully marked
          </p>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="job.isBusy.value"
            @click="startJob('zip')"
          >
            <i class="fas fa-download" aria-hidden="true"></i> Zip
          </button>
          <button
            v-if="payload.component.code === 'SAQ'"
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="job.isBusy.value"
            @click="startJob('xlsx')"
          >
            <i class="fas fa-download" aria-hidden="true"></i> XLSX
          </button>
          <BulkUploadDialog :code="code" @applied="onUploadApplied" />
        </div>
      </div>

      <p v-if="job.isBusy.value" class="component-table__banner component-table__banner--info">
        {{ jobBusyLabel }}
      </p>
      <p v-else-if="job.phase.value === 'done'" class="component-table__banner component-table__banner--ok">
        Download ready — check your browser downloads.
      </p>
      <p v-else-if="job.phase.value === 'failed'" class="component-table__banner component-table__banner--error">
        {{ job.error.value }}
      </p>
      <p v-if="uploadMessage" class="component-table__banner component-table__banner--ok">
        {{ uploadMessage }}
      </p>

      <div class="component-table__scroll">
        <table class="component-table__table">
          <thead>
            <tr>
              <th>
                <button type="button" class="component-table__sort" @click="setSort('id')">
                  ID <i :class="sortIcon('id')" aria-hidden="true"></i>
                </button>
              </th>
              <th>Group</th>
              <th>Submitted</th>
              <th>
                <button type="button" class="component-table__sort" @click="setSort('time')">
                  Time <i :class="sortIcon('time')" aria-hidden="true"></i>
                </button>
              </th>
              <th>Late</th>
              <th>
                <button type="button" class="component-table__sort" @click="setSort('progress')">
                  Progress <i :class="sortIcon('progress')" aria-hidden="true"></i>
                </button>
              </th>
              <th>Marker</th>
              <th class="component-table__cell--right">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="displayRows.length === 0">
              <td colspan="8" class="component-table__empty">No groups.</td>
            </tr>
            <tr v-for="r in displayRows" :key="r.group_id">
              <td>{{ r.group_id }}</td>
              <td class="component-table__cell--strong">{{ r.group_name }}</td>
              <td>
                <template v-if="r.submission_id != null && r.submitted_at">
                  {{ new Date(r.submitted_at).toLocaleDateString() }}
                </template>
                <span v-else class="component-table__muted">—</span>
              </td>
              <td>
                <template v-if="r.submission_id != null && r.submitted_at">
                  {{ new Date(r.submitted_at).toLocaleTimeString() }}
                </template>
                <span v-else class="component-table__muted">—</span>
              </td>
              <td>{{ r.is_late ? 'Yes' : '—' }}</td>
              <td>
                <span v-if="r.submission_id != null" class="component-table__progress">
                  <i
                    :class="isDone(r) ? 'fas fa-circle-check component-table__done' : 'far fa-circle component-table__pending'"
                    aria-hidden="true"
                  ></i>
                  {{ progressLabel(r) }}
                </span>
                <span v-else class="component-table__muted">—</span>
              </td>
              <td>
                <span
                  v-if="r.last_grader_name"
                  class="component-table__marker"
                  :title="`Marked by: ${r.grader_names.join(', ')}`"
                >
                  {{ r.last_grader_name }}
                  <i
                    v-if="r.grader_names.length > 1"
                    class="fas fa-users component-table__marker-icon"
                    aria-hidden="true"
                  ></i>
                </span>
                <span v-else class="component-table__muted">—</span>
              </td>
              <td class="component-table__cell--right">
                <RouterLink
                  v-if="r.submission_id != null"
                  :to="`/grading/components/${code}/${r.group_id}`"
                  class="btn btn-outline btn-sm"
                >
                  Open
                </RouterLink>
                <span v-else class="component-table__muted">No submission</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div>
        <RouterLink to="/grading/by-component" class="btn btn-outline btn-sm">Back</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import BulkUploadDialog from '@/components/grading/BulkUploadDialog.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import {
  fetchComponentRows,
  type ComponentListPayload,
  type ComponentRow
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const route = useRoute()
const code = computed(() => String(route.params.code || ''))

const payload = ref<ComponentListPayload | null>(null)
const isLoading = ref(false)
const loadError = ref('')

const job = useJobPolling()
const uploadMessage = ref('')

const jobBusyLabel = computed(() => {
  if (job.phase.value === 'downloading') return 'Downloading…'
  return 'Preparing export… this can take a moment for large cohorts.'
})

const startJob = (format: 'zip' | 'xlsx') => {
  uploadMessage.value = ''
  void job.start(code.value, format)
}

const onUploadApplied = async (written: number) => {
  uploadMessage.value = `Marks applied — wrote ${written} row${written === 1 ? '' : 's'}.`
  await load()
}

type SortKey = 'id' | 'time' | 'progress'
const sortKey = ref<SortKey>('time')
const sortDirection = ref<'asc' | 'desc'>('desc')

const load = async () => {
  if (!code.value) return
  isLoading.value = true
  loadError.value = ''
  try {
    payload.value = await fetchComponentRows(code.value)
  } catch (err) {
    payload.value = null
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

watch(
  code,
  () => {
    uploadMessage.value = ''
    void load()
  },
  { immediate: true }
)

const submittedCount = computed(
  () => payload.value?.rows.filter((r) => r.submission_id != null).length ?? 0
)

const criteriaTotal = computed(() => payload.value?.criteria_total ?? 0)

const fullyMarkedCount = computed(
  () =>
    payload.value?.rows.filter(
      (r) => r.submission_id != null && criteriaTotal.value > 0 && r.criteria_graded >= criteriaTotal.value
    ).length ?? 0
)

const isDone = (r: ComponentRow) =>
  r.submission_id != null && criteriaTotal.value > 0 && r.criteria_graded >= criteriaTotal.value

const progressLabel = (r: ComponentRow) =>
  criteriaTotal.value > 0 ? `${r.criteria_graded}/${criteriaTotal.value}` : '—'

const setSort = (key: SortKey) => {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDirection.value = key === 'time' ? 'desc' : 'asc'
  }
}

const sortIcon = (key: SortKey) => {
  if (sortKey.value !== key) return 'fas fa-sort component-table__sort-icon component-table__sort-icon--idle'
  return sortDirection.value === 'asc'
    ? 'fas fa-sort-up component-table__sort-icon'
    : 'fas fa-sort-down component-table__sort-icon'
}

const sortValue = (r: ComponentRow): number | string | null => {
  if (sortKey.value === 'id') return r.group_id
  if (sortKey.value === 'time') return r.submitted_at
  return r.submission_id != null ? r.criteria_graded : null
}

const displayRows = computed(() => {
  const rows = [...(payload.value?.rows ?? [])]
  const dir = sortDirection.value === 'asc' ? 1 : -1
  rows.sort((a, b) => {
    const va = sortValue(a)
    const vb = sortValue(b)
    // Nulls (no submission / no timestamp) always sort last.
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
    if (va < vb) return -1 * dir
    if (va > vb) return 1 * dir
    return 0
  })
  // Sorting by progress: keep unsubmitted rows pinned at the bottom regardless
  // of direction, so admins never mistake "0/N" for a legitimate low score.
  if (sortKey.value === 'progress') {
    return [
      ...rows.filter((r) => r.submission_id != null),
      ...rows.filter((r) => r.submission_id == null)
    ]
  }
  return rows
})
</script>

<style scoped>
.component-table__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.component-table__error p {
  margin: 0 0 0.5rem;
}

.component-table__error-detail {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.component-table__error-actions {
  display: flex;
  gap: 0.5rem;
}

.component-table {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.component-table__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.component-table__title {
  margin: 0;
  font-size: 1.35rem;
}

.component-table__stats {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.component-table__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.component-table__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.component-table__banner--info {
  background: color-mix(in srgb, var(--info) 12%, transparent);
  color: var(--info);
}

.component-table__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

.component-table__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.component-table__scroll {
  overflow-x: auto;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-elevated);
}

.component-table__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.component-table__table th,
.component-table__table td {
  padding: 0.55rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  white-space: nowrap;
}

.component-table__table thead th {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.component-table__table tbody tr:last-child td {
  border-bottom: none;
}

.component-table__sort {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.component-table__sort:hover {
  color: var(--dark-green);
}

.component-table__sort-icon {
  font-size: 0.7rem;
}

.component-table__sort-icon--idle {
  color: var(--border-light);
}

.component-table__empty {
  text-align: center;
  color: var(--text-muted);
  padding: 2rem 0.75rem;
}

.component-table__cell--strong {
  font-weight: 600;
}

.component-table__cell--right {
  text-align: right;
}

.component-table__muted {
  color: var(--text-muted);
}

.component-table__progress {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.component-table__done {
  color: var(--success);
}

.component-table__pending {
  color: var(--text-muted);
}

.component-table__marker {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.component-table__marker-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
}
</style>
