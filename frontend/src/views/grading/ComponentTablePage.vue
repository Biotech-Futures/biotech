<template>
  <div>
    <div class="tab-bar" role="tablist" aria-label="Component">
      <button
        v-for="c in COMPONENTS"
        :key="c.code"
        type="button"
        role="tab"
        :aria-selected="c.code === code"
        class="tab-pill"
        :class="{ active: c.code === code }"
        @click="switchComponent(c.code)"
      >
        {{ c.name }}
      </button>
    </div>

    <p v-if="isLoading" class="component-table__hint">Loading…</p>

    <div v-else-if="loadError" class="card component-table__error">
      <p>Failed to load component "{{ code }}".</p>
      <p class="component-table__error-detail">{{ loadError }}</p>
      <div class="component-table__error-actions">
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
      </div>
    </div>

    <div v-else-if="payload" class="component-table">
      <p v-if="job.isBusy.value" class="component-table__banner component-table__banner--ok">
        Processing files for Download
      </p>
      <p v-if="job.phase.value === 'failed'" class="component-table__banner component-table__banner--error">
        {{ job.error.value }}
      </p>
      <p v-if="uploadMessage" class="component-table__banner component-table__banner--ok">
        {{ uploadMessage }}
      </p>

      <!-- Every group at once, searched and sorted here. -->
      <AppDataTable
        :columns="columns"
        :rows="tableRows"
        row-key="group_id"
        :selectable="false"
        :page-size="DATA_TABLE_ALL"
        v-model:search="searchQuery"
        search-placeholder="Group name"
        :sort="tableSort"
        :empty-message="searchQuery.trim() ? 'No groups match your search.' : 'No groups.'"
        @update:sort="setSort($event.key as SortKey)"
      >
        <template #stats>
          {{ submittedCount }}/{{ payload.rows.length }} Submitted ·
          {{ fullyMarkedCount }}/{{ submittedCount }} Fully Marked
        </template>
        <template #search-side>
          <!-- SAQ asks which format; the others download their uploads. -->
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="job.isBusy.value"
            @click="onDownload"
          >
            <i class="fas fa-download" aria-hidden="true"></i> Download
          </button>
          <BulkUploadDialog :code="code" :year="payload.year" @applied="onUploadApplied" />
        </template>

        <template #head-marker>
          Marker
          <i
            class="fas fa-circle-info component-table__marker-info"
            data-tip="Hover over a marker's name to see who marked each part."
            aria-hidden="true"
          ></i>
        </template>

        <template #cell-group="{ row }">
          <span class="component-table__cell--strong">{{ rowOf(row).group_name }}</span>
        </template>
        <template #cell-time="{ row }">
          <template v-if="rowOf(row).submission_id != null && rowOf(row).submitted_at">
            {{ new Date(rowOf(row).submitted_at!).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' }) }}
            {{
              new Date(rowOf(row).submitted_at!).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                hourCycle: 'h23'
              })
            }}
          </template>
          <span v-else class="component-table__muted">—</span>
        </template>
        <template #cell-late="{ row }">
          <span v-if="rowOf(row).is_late" class="component-table__late">
            {{ rowOf(row).late_by || 'Late' }}
          </span>
          <span v-else class="component-table__muted">—</span>
        </template>
        <template #cell-progress="{ row }">
          <span v-if="rowOf(row).submission_id != null" class="component-table__progress">
            <i
              :class="isDone(rowOf(row)) ? 'fas fa-circle-check component-table__done' : 'far fa-circle component-table__pending'"
              aria-hidden="true"
            ></i>
            {{ progressLabel(rowOf(row)) }}
          </span>
          <span v-else class="component-table__muted">—</span>
        </template>
        <template #cell-marks="{ row }">
          <span v-if="rowOf(row).marks_total != null">{{ rowOf(row).marks_total }}</span>
          <span v-else class="component-table__muted">—</span>
        </template>
        <template #cell-marker="{ row }">
          <span
            v-if="rowOf(row).last_grader_name"
            class="component-table__marker"
            :title="markerTooltip(rowOf(row))"
          >
            {{ rowOf(row).last_grader_name }}
            <i
              v-if="rowOf(row).grader_names.length > 1"
              class="fas fa-users component-table__marker-icon"
              aria-hidden="true"
            ></i>
          </span>
          <span v-else class="component-table__muted">—</span>
        </template>

        <template #actions="{ row }">
          <RouterLink
            v-if="rowOf(row).submission_id != null"
            :to="`/grading/components/${code}/${rowOf(row).group_id}`"
            class="btn btn-outline btn-sm"
          >
            Open
          </RouterLink>
          <span v-else class="component-table__muted">No sub.</span>
        </template>
      </AppDataTable>
    </div>
  </div>

  <!-- SAQ's answers, in the format picked. Styled as Upload marks. -->
  <Teleport to="body">
    <div v-if="choosingFormat" class="component-table__overlay" @click.self="choosingFormat = false">
      <div class="component-table__dialog" role="dialog" aria-modal="true" aria-label="Download SAQs">
        <div class="component-table__dialog-head">
          <h3 class="component-table__dialog-title">Download Short Answer Questions</h3>
          <button
            type="button"
            class="component-table__dialog-close"
            aria-label="Close"
            @click="choosingFormat = false"
          >
            &times;
          </button>
        </div>
        <ul class="component-table__formats">
          <li v-for="option in SAQ_FORMATS" :key="option.format">
            <button type="button" class="btn btn-outline btn-sm" @click="pickFormat(option.format)">
              <i class="fas fa-download" aria-hidden="true"></i> {{ option.label }}
            </button>
            <span class="component-table__format-desc">{{ option.desc }}</span>
          </li>
        </ul>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppDataTable, { type DataTableColumn, type DataTableSort } from '@/components/AppDataTable.vue'
import BulkUploadDialog from '@/components/grading/BulkUploadDialog.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import {
  fetchComponentRows,
  type ComponentDownloadFormat,
  type ComponentListPayload,
  type ComponentRow
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { DATA_TABLE_ALL } from '@/utils/dataTable'

const route = useRoute()
const router = useRouter()
const code = computed(() => String(route.params.code || ''))

// Component codes are hard-coded to match the backend seed migration.
const COMPONENTS: { code: string; name: string }[] = [
  { code: 'SAQ', name: 'Short Answer Questions' },
  { code: 'POSTER', name: 'A2 Poster' },
  { code: 'REPORT', name: 'Scientific Report' },
  { code: 'PROTOTYPE', name: 'Prototype' }
]

const switchComponent = (target: string) => {
  if (target === code.value) return
  void router.push(`/grading/components/${target}`)
}

const payload = ref<ComponentListPayload | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const searchQuery = ref('')

const job = useJobPolling()
const uploadMessage = ref('')

const startJob = (format: ComponentDownloadFormat) => {
  uploadMessage.value = ''
  void job.start(code.value, format)
}

// SAQ's answers come three ways; the other components' uploads one.
const SAQ_FORMATS: { format: ComponentDownloadFormat; label: string; desc: string }[] = [
  { format: 'xlsx', label: 'xlsx', desc: "Every group's answers and marks in one spreadsheet." },
  { format: 'pdf', label: 'pdf', desc: "Each group's answers as its own PDF, zipped." },
  { format: 'zip', label: 'txt', desc: "Each group's answers as its own text file, zipped." }
]
const choosingFormat = ref(false)

const onDownload = () => {
  if (payload.value?.component.code === 'SAQ') choosingFormat.value = true
  else startJob('zip')
}

const pickFormat = (format: ComponentDownloadFormat) => {
  choosingFormat.value = false
  startJob(format)
}

const groupCount = (n: number) => `${n} group${n === 1 ? '' : 's'}`

// "Marks applied. Overwrote existing records for 2 groups and wrote new
// records for 1 group." Counted in groups, like the upload preview.
const appliedMessage = ({ overwritten, created }: { overwritten: number; created: number }) => {
  const parts: string[] = []
  if (overwritten) parts.push(`overwrote existing records for ${groupCount(overwritten)}`)
  if (created) parts.push(`wrote new records for ${groupCount(created)}`)
  if (!parts.length) return 'Marks applied. No records changed.'
  const detail = parts.join(' and ')
  return `Marks applied. ${detail.charAt(0).toUpperCase()}${detail.slice(1)}.`
}

const onUploadApplied = async (counts: { overwritten: number; created: number }) => {
  uploadMessage.value = appliedMessage(counts)
  await load()
}

type SortKey = 'group' | 'time' | 'progress'

// Numeric-aware so "BTF-2" sorts before "BTF-10", matching the sidebar.
const nameCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })
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
    searchQuery.value = ''
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

// One line per rubric position with whoever last marked it; falls back to the
// flat grader list for rows with no per-criterion data.
const markerTooltip = (r: ComponentRow) =>
  r.criterion_markers?.length
    ? r.criterion_markers.map((m) => `${m.n}: ${m.marker}`).join('\n')
    : `Marked by: ${r.grader_names.join(', ')}`

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

const tableSort = computed<DataTableSort>(() => ({ key: sortKey.value, direction: sortDirection.value }))

const columns: DataTableColumn[] = [
  { key: 'group', label: 'Group' },
  { key: 'time', label: 'Submitted' },
  { key: 'late', label: 'Late', sortable: false },
  { key: 'progress', label: 'Progress' },
  { key: 'marks', label: 'Marks', sortable: false },
  { key: 'marker', label: 'Marker', sortable: false }
]

const sortValue = (r: ComponentRow): number | string | null => {
  if (sortKey.value === 'time') return r.submitted_at
  return r.submission_id != null ? r.criteria_graded : null
}

const displayRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  let rows = [...(payload.value?.rows ?? [])]
  if (query) {
    rows = rows.filter((r) => r.group_name.toLowerCase().includes(query))
  }
  const dir = sortDirection.value === 'asc' ? 1 : -1
  rows.sort((a, b) => {
    if (sortKey.value === 'group') return nameCollator.compare(a.group_name, b.group_name) * dir
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

const tableRows = computed(() => displayRows.value as unknown as Record<string, unknown>[])
const rowOf = (row: Record<string, unknown>) => row as unknown as ComponentRow
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

/* The format picker, as the Upload marks dialog. */
.component-table__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.component-table__dialog {
  background: var(--surface-elevated);
  color: var(--teal);
  border-radius: 10px;
  box-shadow: 0 10px 40px var(--shadow);
  width: 100%;
  max-width: 30rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.component-table__dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.component-table__dialog-title {
  margin: 0;
  font-size: 1.15rem;
}

.component-table__dialog-close {
  border: none;
  background: none;
  font-size: 1.5rem;
  line-height: 1;
  color: var(--text-muted);
  cursor: pointer;
}

.component-table__dialog-close:hover {
  color: var(--teal);
}

.component-table__formats {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.component-table__formats li {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* The buttons line up, whatever their label. */
.component-table__formats .btn {
  min-width: 5.5rem;
  justify-content: center;
}

.component-table__format-desc {
  color: var(--text-muted);
  font-size: 0.85rem;
}

/* A message above the table, outlined like it. */
.component-table__banner {
  padding: 0.5rem 1rem;
  font-size: 0.9rem;
  margin: 0;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-radius: 8px;
}

.component-table__banner--info {
  color: var(--info);
}

.component-table__banner--ok {
  color: var(--dark-green);
}

.component-table__banner--error {
  color: var(--danger);
}

.component-table__cell--strong {
  font-weight: 600;
}

.component-table__muted {
  color: var(--text-muted);
}

/* Same orange as the Release Marks page's warn banner. */
.component-table__late {
  color: #ff8c00;
  font-weight: 600;
}

/* On the Dark Green heading row, a lighter shade of its white text. */
.component-table__marker-info {
  font-size: 0.75rem;
  color: inherit;
  opacity: 0.75;
  margin-left: 0.2rem;
  position: relative;
}

/* Instant tooltip — native title has an uncontrollable hover delay. */
.component-table__marker-info::after {
  content: attr(data-tip);
  position: absolute;
  left: 0;
  top: 1.4rem;
  z-index: 20;
  display: none;
  background: #333;
  color: #fff;
  font: 400 10px/1.4 var(--font-family, sans-serif);
  text-transform: none;
  letter-spacing: normal;
  padding: 0.35rem 0.55rem;
  border-radius: 6px;
  white-space: normal;
  width: max-content;
  max-width: 10rem;
}

.component-table__marker-info:hover::after {
  display: block;
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
