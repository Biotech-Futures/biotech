<template>
  <div>
    <div class="component-table__switcher" role="tablist" aria-label="Component">
      <button
        v-for="c in COMPONENTS"
        :key="c.code"
        type="button"
        role="tab"
        :aria-selected="c.code === code"
        class="component-table__switch"
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
      <div class="card component-table__search-card">
        <div class="component-table__search-field">
          <label class="component-table__search-label" for="component-group-search">Search</label>
          <div class="component-table__search">
            <i class="fas fa-magnifying-glass component-table__search-icon" aria-hidden="true"></i>
            <input
              id="component-group-search"
              v-model="searchQuery"
              type="search"
              class="component-table__search-input"
              placeholder="Group name"
              aria-label="Search groups"
            />
          </div>
        </div>
        <p class="component-table__stats">
          {{ submittedCount }}/{{ payload.rows.length }} Submitted ·
          {{ fullyMarkedCount }}/{{ submittedCount }} Fully Marked
        </p>
        <div class="component-table__actions">
            <button
              v-if="payload.component.code === 'SAQ'"
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="job.isBusy.value"
              @click="startJob('xlsx')"
            >
              <i class="fas fa-download" aria-hidden="true"></i> XLSX
            </button>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="job.isBusy.value"
              @click="startJob('zip')"
            >
              <i class="fas fa-download" aria-hidden="true"></i> Download
            </button>
            <BulkUploadDialog :code="code" @applied="onUploadApplied" />
          </div>
      </div>

      <p v-if="job.phase.value === 'failed'" class="component-table__banner component-table__banner--error">
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
                <button type="button" class="component-table__sort" @click="setSort('group')">
                  Group <i :class="sortIcon('group')" aria-hidden="true"></i>
                </button>
              </th>
              <th>
                <button type="button" class="component-table__sort" @click="setSort('time')">
                  Submitted <i :class="sortIcon('time')" aria-hidden="true"></i>
                </button>
              </th>
              <th>Late</th>
              <th>
                <button type="button" class="component-table__sort" @click="setSort('progress')">
                  Progress <i :class="sortIcon('progress')" aria-hidden="true"></i>
                </button>
              </th>
              <th>Marks</th>
              <th>
                Marker
                <i
                  class="fas fa-circle-info component-table__marker-info"
                  data-tip="Hover over a marker's name to see who marked each part."
                  aria-hidden="true"
                ></i>
              </th>
              <th class="component-table__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="displayRows.length === 0">
              <td colspan="7" class="component-table__empty">
                {{ searchQuery.trim() ? 'No groups match your search.' : 'No groups.' }}
              </td>
            </tr>
            <tr v-for="r in displayRows" :key="r.group_id">
              <td class="component-table__cell--strong">{{ r.group_name }}</td>
              <td>
                <template v-if="r.submission_id != null && r.submitted_at">
                  {{ new Date(r.submitted_at).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' }) }}
                  {{
                    new Date(r.submitted_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                      hourCycle: 'h23'
                    })
                  }}
                </template>
                <span v-else class="component-table__muted">—</span>
              </td>
              <td>
                <span v-if="r.is_late" class="component-table__late">
                  {{ r.late_by || 'Late' }}
                </span>
                <span v-else class="component-table__muted">—</span>
              </td>
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
                <span v-if="r.marks_total != null">{{ r.marks_total }}</span>
                <span v-else class="component-table__muted">—</span>
              </td>
              <td>
                <span
                  v-if="r.last_grader_name"
                  class="component-table__marker"
                  :title="markerTooltip(r)"
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
                <span v-else class="component-table__muted">No sub.</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BulkUploadDialog from '@/components/grading/BulkUploadDialog.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import {
  fetchComponentRows,
  type ComponentListPayload,
  type ComponentRow
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

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

const startJob = (format: 'zip' | 'xlsx') => {
  uploadMessage.value = ''
  void job.start(code.value, format)
}

const onUploadApplied = async (written: number) => {
  uploadMessage.value = `Marks applied - wrote ${written} row${written === 1 ? '' : 's'}.`
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

const sortIcon = (key: SortKey) => {
  if (sortKey.value !== key) return 'fas fa-sort component-table__sort-icon component-table__sort-icon--idle'
  return sortDirection.value === 'asc'
    ? 'fas fa-sort-up component-table__sort-icon'
    : 'fas fa-sort-down component-table__sort-icon'
}

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
</script>

<style scoped>
/* Segmented pill switcher, matching the Events page view tabs. */
.component-table__switcher {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.3rem;
  margin-bottom: 1.75rem;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 999px;
  box-shadow: 0 1px 2px var(--shadow);
}

.component-table__switch {
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: 999px;
  padding: 0.5rem 1.1rem;
  font-weight: 600;
  font-size: 0.92rem;
  font-family: inherit;
  cursor: pointer;
  transition:
    color 0.18s ease,
    background-color 0.18s ease;
}

.component-table__switch:hover:not(.active) {
  color: var(--charcoal);
  background: var(--accent-green-soft);
}

.component-table__switch.active {
  background: var(--dark-green);
  color: #fff;
  box-shadow: 0 1px 3px rgba(1, 113, 81, 0.3);
}

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

/* Search card — same treatment as the Admin Groups page's group search.
   The negative margin cancels both the global .card margin-bottom and the
   column gap (1rem) so the card sits flush against the table. */
.component-table__search-card,
.component-table__search-card:hover {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 1rem;
  margin-bottom: -1rem;
  /* Flush against the table below — square off the shared edge and use the
     table's outline instead of the card shadow. The table's own top border
     draws the divider, so no border-bottom here. */
  border: 1px solid var(--border-light);
  border-bottom: none;
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  box-shadow: none;
}

.component-table__search-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  flex: 1 1 140px;
  /* Explicit floor — otherwise the input's intrinsic minimum (~170px)
     wins and crowds the stats out of the row. */
  min-width: 155px;
  max-width: 252px;
}

.component-table__search-field .component-table__search-input {
  min-width: 0;
}

.component-table__search-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.component-table__search {
  position: relative;
  width: 100%;
}

.component-table__search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.85rem;
  pointer-events: none;
}

.component-table__search-input {
  width: 100%;
  height: 40px;
  /* Slim right padding — text clips at the content edge, so a wide pad
     cuts the placeholder well short of the visible border. */
  padding: 0.5rem 0 0.5rem 2rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
}

.component-table__stats {
  color: var(--charcoal);
  font-size: 0.9rem;
  /* Auto inline margins center the stats between the search box and the
     export buttons. */
  margin: 0 auto;
}

.component-table__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  /* Stays right-aligned even when the card wraps it onto its own line. */
  margin-left: auto;
}

/* Styled like the boxes it sits between: same background and outline as the
   search card and table, no radius, side borders only — the card above and
   the table below draw the horizontal edges. */
.component-table__banner {
  padding: 0.5rem 1rem;
  font-size: 0.9rem;
  /* Negative bottom margin cancels the column gap so the banner sits flush
     against the table below, like the search card does. */
  margin: 0 0 -1rem;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-top: none;
  border-bottom: none;
  border-radius: 0;
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

.component-table__scroll {
  overflow-x: auto;
  border: 1px solid var(--border-light);
  border-radius: 0 0 8px 8px;
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
  /* Buttons don't pick up the header's uppercase styling on their own. */
  text-transform: inherit;
  letter-spacing: inherit;
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

/* Scoped under the table selector so this outweighs the generic th/td rule
   that sets text-align: left. */
.component-table__table .component-table__cell--right {
  text-align: right;
}

.component-table__muted {
  color: var(--text-muted);
}

/* Same orange as the Release Marks page's warn banner. */
.component-table__late {
  color: #ff8c00;
  font-weight: 600;
}

.component-table__marker-info {
  font-size: 0.75rem;
  color: var(--text-muted);
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
