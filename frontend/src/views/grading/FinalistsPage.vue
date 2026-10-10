<template>
  <div class="finalists">
    <p v-if="actionError" class="finalists__banner finalists__banner--error">{{ actionError }}</p>

    <section>
      <h3 class="subheading">
        <button
          type="button"
          class="finalists__collapse-btn"
          :aria-expanded="showGroupMarks"
          @click="showGroupMarks = !showGroupMarks"
        >
          Group Marks
          <i
            class="fas fa-chevron-down finalists__chevron"
            :class="{ 'finalists__chevron--collapsed': !showGroupMarks }"
            aria-hidden="true"
          ></i>
        </button>
      </h3>
      <template v-if="showGroupMarks">
      <p v-if="isLoadingCandidates" class="finalists__hint">Loading…</p>
      <!-- Search and sort stay this page's own. -->
      <AppDataTable
        v-else
        class="finalists__table finalists__marks-table"
        :columns="marksTableColumns"
        :rows="candidates as unknown as Record<string, unknown>[]"
        row-key="group_id"
        :selectable="false"
        :page-size="DATA_TABLE_ALL"
        v-model:search="groupQuery"
        :sort="sort ?? NO_SORT"
        search-placeholder="Group name"
        :empty-message="groupQuery.trim() ? 'No groups match your search.' : 'No groups.'"
        :action-columns="2"
        :show-all-details="showDetails"
        @update:sort="toggleSort($event.key)"
      >
        <template v-if="candidatesResp" #stats>
          {{ fullyMarkedCount }}/{{ submittedCount }} Fully Marked ·
          {{ finalistCount }} Added as {{ finalistCount === 1 ? 'Finalist' : 'Finalists' }}
        </template>
        <template #search-side>
          <!-- Each group's title and categories stay hidden until asked for. -->
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :aria-pressed="showDetails"
            @click="showDetails = !showDetails"
          >
            {{ showDetails ? 'Hide Details' : 'Show Details' }}
          </button>
          <p v-if="showsIncompleteKey" class="finalists__legend">* Not Marked Completely</p>
        </template>
        <template #head-marker>
          Marker
          <i
            class="fas fa-circle-info finalists__marker-info"
            data-tip="Hover over a marker's name to see who marked each part."
            aria-hidden="true"
          ></i>
        </template>
        <template #cell-group="{ row }">
          <span class="finalists__cell--strong">{{ candidateOf(row).group_name }}</span>
        </template>
        <template #cell-late="{ row }">
          <span v-if="candidateOf(row).is_late" class="finalists__late">
            {{ candidateOf(row).late_by || 'Late' }}
          </span>
          <span v-else class="finalists__muted">—</span>
        </template>
        <template v-for="c in markColumns" :key="c.key" #[`cell-${c.key}`]="{ row }">
          <span v-if="notMarkedCompletely(candidateOf(row), c.key)" title="Not Marked Completely">
            {{ markOf(candidateOf(row), c.key) ?? '' }}<span class="finalists__incomplete">*</span>
          </span>
          <span v-else-if="markOf(candidateOf(row), c.key) != null">{{ markOf(candidateOf(row), c.key) }}</span>
          <span v-else class="finalists__muted">—</span>
        </template>
        <template #cell-total="{ row }">
          <span v-if="candidateOf(row).total != null" class="finalists__cell--strong">
            {{ candidateOf(row).total }}
          </span>
          <span v-else class="finalists__muted">—</span>
        </template>
        <template #cell-marker="{ row }">
          <span
            v-if="candidateOf(row).markers.length"
            class="finalists__marker"
            :title="markerTooltip(candidateOf(row))"
          >
            {{ candidateOf(row).markers[0] }}
            <i
              v-if="candidateOf(row).markers.length > 1"
              class="fas fa-users finalists__marker-icon"
              aria-hidden="true"
            ></i>
          </span>
          <span v-else class="finalists__muted">—</span>
        </template>
        <!-- Add (or Added) | Open (or No sub.) -->
        <template #actions="{ row, column }">
          <template v-if="column === 0">
            <button
              v-if="!candidateOf(row).is_finalist"
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="isMutating"
              @click="addFromRow(candidateOf(row).group_id)"
            >
              Add
            </button>
            <span v-else class="finalists__muted">Added</span>
          </template>
          <template v-else>
            <RouterLink
              v-if="candidateOf(row).has_submission"
              :to="`/grading/groups/${candidateOf(row).group_id}`"
              class="btn btn-outline btn-sm"
            >
              Open
            </RouterLink>
            <span v-else class="finalists__muted">No sub.</span>
          </template>
        </template>
        <!-- The project's details get a full-width row of their own so long
             text can wrap; the pair reads as one group. -->
        <template v-if="showDetails" #row-detail="{ row }">
          <!-- Wraps to the visible width, not the table's, and a long value
               wraps in line with itself, after its label. -->
          <div class="finalists__details">
            <div class="finalists__detail">
              <span class="finalists__muted">Title:</span>
              <span>{{ candidateOf(row).project_title || '—' }}</span>
            </div>
            <div class="finalists__detail-line">
              <div class="finalists__detail">
                <span class="finalists__muted">Category:</span>
                <span>{{ candidateOf(row).project_category || '—' }}</span>
              </div>
              <div class="finalists__detail">
                <span class="finalists__muted">Solution Category:</span>
                <span>{{ candidateOf(row).solution_category || '—' }}</span>
              </div>
            </div>
          </div>
        </template>
      </AppDataTable>
      </template>
    </section>

    <section>
      <h3 class="subheading">
        <button
          type="button"
          class="finalists__collapse-btn"
          :aria-expanded="showCurrentFinalists"
          @click="showCurrentFinalists = !showCurrentFinalists"
        >
          Current Finalists
          <i
            class="fas fa-chevron-down finalists__chevron"
            :class="{ 'finalists__chevron--collapsed': !showCurrentFinalists }"
            aria-hidden="true"
          ></i>
        </button>
      </h3>
      <template v-if="showCurrentFinalists">
      <p v-if="isLoading" class="finalists__hint">Loading…</p>
      <div v-else-if="loadError" class="card">
        <p class="finalists__load-error">Failed to load. {{ loadError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
      </div>
      <!-- Kept in the order picked: no sorting. -->
      <AppDataTable
        v-else
        class="finalists__table"
        :columns="finalistColumns"
        :rows="finalistRows"
        row-key="id"
        :sort="NO_SORT"
        :selectable="false"
        :page-size="DATA_TABLE_ALL"
        search-placeholder="Group name"
        empty-message="No finalists yet."
        :action-columns="2"
      >
        <template #head-marker>
          Marker
          <i
            class="fas fa-circle-info finalists__marker-info"
            data-tip="Hover over a marker's name to see who marked each part."
            aria-hidden="true"
          ></i>
        </template>
        <template #cell-order="{ row }">
          <span class="finalists__muted">{{ row.order }}</span>
        </template>
        <template #cell-group="{ row }">
          <span class="finalists__cell--strong">{{ row.group }}</span>
        </template>
        <template #cell-late="{ row }">
          <span v-if="candidateFor(row)?.is_late" class="finalists__late">
            {{ candidateFor(row)!.late_by || 'Late' }}
          </span>
          <span v-else class="finalists__muted">—</span>
        </template>
        <template #cell-total="{ row }">
          <span v-if="totalsByGroup.get(finalistOf(row).group_id) != null" class="finalists__cell--strong">
            {{ totalsByGroup.get(finalistOf(row).group_id) }}
          </span>
          <span v-else class="finalists__muted">—</span>
        </template>
        <template #cell-marker="{ row }">
          <span
            v-if="candidateFor(row)?.markers.length"
            class="finalists__marker"
            :title="markerTooltip(candidateFor(row)!)"
          >
            {{ candidateFor(row)!.markers[0] }}
            <i
              v-if="candidateFor(row)!.markers.length > 1"
              class="fas fa-users finalists__marker-icon"
              aria-hidden="true"
            ></i>
          </span>
          <span v-else class="finalists__muted">—</span>
        </template>
        <!-- Remove | Open -->
        <template #actions="{ row, column }">
          <button
            v-if="column === 0"
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="isMutating"
            @click="pendingRemoval = finalistOf(row)"
          >
            Remove
          </button>
          <RouterLink v-else :to="`/grading/groups/${finalistOf(row).group_id}`" class="btn btn-outline btn-sm">
            Open
          </RouterLink>
        </template>
      </AppDataTable>
      </template>
    </section>

    <div v-if="pendingRemoval" class="finalists__overlay" @click.self="pendingRemoval = null">
      <div class="finalists__dialog" role="dialog" aria-modal="true" aria-label="Remove finalist">
        <h4 class="finalists__dialog-title">Remove this finalist?</h4>
        <p class="finalists__dialog-body">
          <strong>{{ pendingRemoval.group_name }}</strong> will no longer be a finalist.
          <template v-if="pendingRemoval.notified">
            Their team has already been emailed that they are a finalist.
          </template>
        </p>
        <div class="finalists__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="pendingRemoval = null">
            Cancel
          </button>
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="isMutating"
            @click="remove(pendingRemoval.group_id)"
          >
            {{ isMutating ? 'Removing…' : 'Remove finalist' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  addFinalist,
  fetchFinalistCandidates,
  fetchFinalists,
  removeFinalist,
  type FinalistCandidateRow,
  type FinalistCandidatesResponse,
  type FinalistListResponse,
  type FinalistRow
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import AppDataTable, { type DataTableColumn, type DataTableSort } from '@/components/AppDataTable.vue'
import { DATA_TABLE_ALL } from '@/utils/dataTable'

const list = ref<FinalistListResponse | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const isMutating = ref(false)
const groupQuery = ref('')
const showDetails = ref(false)

const finalists = computed(() => list.value?.finalists ?? [])
// The latest flagged first, each numbered in the order picked: the
// earliest is 1.
const finalistsInOrder = computed(() =>
  [...finalists.value].sort(
    (a, b) =>
      new Date(b.flagged_at).getTime() - new Date(a.flagged_at).getTime() ||
      a.group_name.localeCompare(b.group_name, undefined, { numeric: true })
  )
)

// Collapsible sections — both open by default.
const showGroupMarks = ref(true)
const showCurrentFinalists = ref(true)

const load = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    list.value = await fetchFinalists()
  } catch (err) {
    list.value = null
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

// Group Marks ranking table (per-component totals, marker, add shortcut).
const candidatesResp = ref<FinalistCandidatesResponse | null>(null)
const isLoadingCandidates = ref(false)

const candidateComponents = computed(() => candidatesResp.value?.components ?? [])

// Above the table, as on the component pages: the groups that submitted, and
// how many of them have every part they sent marked.
const submittedCount = computed(
  () => (candidatesResp.value?.rows ?? []).filter((r) => r.has_submission).length
)
const fullyMarkedCount = computed(
  () => (candidatesResp.value?.rows ?? []).filter((r) => r.has_submission && !r.incomplete.length).length
)
// And how many of the groups have been added as finalists.
const finalistCount = computed(() => (candidatesResp.value?.rows ?? []).filter((r) => r.is_finalist).length)

// The SAQ and Poster marks together: the released parts, as the marks
// summary adds them up.
const SAQ_POSTER = 'SAQ_POSTER'
const saqPoster = (r: FinalistCandidateRow): string | null => {
  const parts = [r.marks.SAQ, r.marks.POSTER].filter((mark): mark is string => mark != null)
  return parts.length ? parts.reduce((sum, mark) => sum + Number(mark), 0).toFixed(2) : null
}

// A mark column per part, SAQ&P. straight after the poster's.
const markColumns = computed(() =>
  candidateComponents.value.flatMap((c) => {
    const column = { key: c.code, label: c.code === 'PROTOTYPE' ? 'PRO.' : c.code, title: c.name }
    return c.code === 'POSTER'
      ? [column, { key: SAQ_POSTER, label: 'SAQ&P.', title: 'SAQ and Poster together' }]
      : [column]
  })
)
const markOf = (r: FinalistCandidateRow, key: string): string | null =>
  key === SAQ_POSTER ? saqPoster(r) : key === 'total' ? r.total : (r.marks[key] ?? null)

// Click a header to sort by it, again to reverse. Until then, the server's
// order: highest total first. Group names sort as numbers do (BTF2 before
// BTF10); marks start highest first, and a missing mark always sinks.
const sort = ref<{ key: string; direction: 'asc' | 'desc' } | null>(null)
const toggleSort = (key: string) => {
  sort.value =
    sort.value?.key === key
      ? { key, direction: sort.value.direction === 'asc' ? 'desc' : 'asc' }
      : { key, direction: key === 'group' ? 'asc' : 'desc' }
}
// No column sorted yet: the table is told so, and leaves the server's order.
const NO_SORT: DataTableSort = { key: '', direction: 'asc' }
const byName = (a: FinalistCandidateRow, b: FinalistCandidateRow) =>
  a.group_name.localeCompare(b.group_name, undefined, { numeric: true, sensitivity: 'base' })

// Live-filter the Group Marks table by the search text (group name),
// matching the other marking tables.
const candidates = computed(() => {
  const all = candidatesResp.value?.rows ?? []
  const q = groupQuery.value.trim().toLowerCase()
  const rows = q ? all.filter((r) => r.group_name.toLowerCase().includes(q)) : all
  const order = sort.value
  if (!order) return rows
  const sign = order.direction === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    if (order.key === 'group') return sign * byName(a, b)
    const x = markOf(a, order.key)
    const y = markOf(b, order.key)
    if (x == null || y == null) return x == null && y == null ? byName(a, b) : x == null ? 1 : -1
    return sign * (Number(x) - Number(y)) || byName(a, b)
  })
})

// Group Marks' columns: the group, late, a column per mark, the total and
// the marker. Sorted by the page (toggleSort above), all but Late and Marker.
const marksTableColumns = computed<DataTableColumn[]>(() => [
  { key: 'group', label: 'Group' },
  { key: 'late', label: 'Late', sortable: false },
  ...markColumns.value.map((c) => ({ key: c.key, label: c.label, title: c.title })),
  { key: 'total', label: 'Total' },
  { key: 'marker', label: 'Marker', sortable: false }
])
const candidateOf = (row: Record<string, unknown>) => row as unknown as FinalistCandidateRow

// The Group Marks ranking keyed by group, so the Current Finalists table
// can show each finalist's total and marker.
const candidatesByGroup = computed(
  () => new Map((candidatesResp.value?.rows ?? []).map((r) => [r.group_id, r]))
)
const totalsByGroup = computed(
  () => new Map((candidatesResp.value?.rows ?? []).map((r) => [r.group_id, r.total]))
)

// Current Finalists' columns, none sorted: # is the order they were picked.
const finalistColumns: DataTableColumn[] = [
  { key: 'order', label: '#', sortable: false },
  { key: 'group', label: 'Group', sortable: false },
  { key: 'flaggedAt', label: 'Flagged at', sortable: false },
  { key: 'flaggedBy', label: 'Flagged by', sortable: false },
  { key: 'late', label: 'Late', sortable: false },
  { key: 'total', label: 'Total', sortable: false },
  { key: 'marker', label: 'Marker', sortable: false }
]

const flaggedAtText = (at: string) => {
  const when = new Date(at)
  const date = when.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })
  const time = when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
  return `${date} ${time}`
}

// Each finalist as a table row: plain text for search, and the finalist itself
// for the cells drawn here.
const finalistRows = computed(() =>
  finalistsInOrder.value.map((f, i) => {
    const candidate = candidatesByGroup.value.get(f.group_id)
    return {
      id: f.group_id,
      finalist: f,
      order: finalistsInOrder.value.length - i,
      group: f.group_name,
      flaggedAt: flaggedAtText(f.flagged_at),
      flaggedBy: f.flagged_by ?? '—',
      late: candidate?.is_late ? candidate.late_by || 'Late' : '—',
      total: totalsByGroup.value.get(f.group_id) ?? '—',
      marker: candidate?.markers[0] ?? '—'
    }
  })
)
const finalistOf = (row: Record<string, unknown>) => row.finalist as FinalistRow
const candidateFor = (row: Record<string, unknown>) => candidatesByGroup.value.get(finalistOf(row).group_id)

// A part a team sent that still has unmarked criteria gets an asterisk, after
// its mark so far or alone when nothing is marked yet; a dash is left for
// parts never submitted. SAQ&P. and the total never get one.
const notMarkedCompletely = (r: FinalistCandidateRow, key: string) => r.incomplete.includes(key)
// The key above the table, whenever a group has a part not fully marked.
const showsIncompleteKey = computed(() => (candidatesResp.value?.rows ?? []).some((r) => r.incomplete.length))

// One line per rubric criterion ("SAQ 1: Ada") with whoever last marked it;
// falls back to the flat marker list when no per-criterion data exists.
const markerTooltip = (r: FinalistCandidateRow) =>
  r.criterion_markers?.length
    ? r.criterion_markers.map((m) => `${m.label}: ${m.marker}`).join('\n')
    : `Marked by: ${r.markers.join(', ')}`

const loadCandidates = async () => {
  isLoadingCandidates.value = true
  try {
    candidatesResp.value = await fetchFinalistCandidates()
  } catch (err) {
    candidatesResp.value = null
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoadingCandidates.value = false
  }
}

onMounted(() => {
  void load()
  void loadCandidates()
})

// After adding or removing: both tables update in place, without the
// Loading… that replaces them, so the page keeps its place.
const refreshInPlace = async () => {
  const [finalistList, candidateList] = await Promise.all([fetchFinalists(), fetchFinalistCandidates()])
  list.value = finalistList
  candidatesResp.value = candidateList
}

const addFromRow = async (id: number) => {
  actionError.value = ''
  isMutating.value = true
  try {
    await addFinalist(id)
    await refreshInPlace()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isMutating.value = false
  }
}

// Remove asks first: the row's button opens the popup, its confirm removes.
const pendingRemoval = ref<FinalistRow | null>(null)

const remove = async (id: number) => {
  actionError.value = ''
  isMutating.value = true
  try {
    await removeFinalist(id)
    await refreshInPlace()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isMutating.value = false
    pendingRemoval.value = null
  }
}
</script>

<style scoped>
.finalists {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.finalists__collapse-btn {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.finalists__chevron {
  font-size: 0.75rem;
  color: var(--text-muted);
  transition: transform 0.2s ease;
}

.finalists__chevron--collapsed {
  transform: rotate(-90deg);
}

.finalists__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.finalists__legend {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

/* Remove-finalist confirm — same treatment as the Extend Deadline popups. */
.finalists__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.finalists__dialog {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  padding: 1.25rem 1.5rem;
  max-width: 26rem;
  width: 100%;
}

.finalists__dialog-title {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
}

.finalists__dialog-body {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: var(--teal);
}

.finalists__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.finalists__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.finalists__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.finalists__load-error {
  color: var(--danger);
  margin-bottom: 0.5rem;
}

/* The details rows size to the visible width of Group Marks (cqw). */
.finalists__marks-table :deep(.data-table-wrap) {
  container-type: inline-size;
}

/* Held in view while the table scrolls sideways, and as wide as the
   visible part of it less the cell's indent, so long text wraps there. */
.finalists__details {
  position: sticky;
  left: 1.25rem;
  max-width: calc(100cqw - 2.5rem);
  font-size: 0.85rem;
}

.finalists__detail-line {
  display: flex;
  flex-wrap: wrap;
  column-gap: 1.5rem;
}

/* The value wraps beside its label, its lines lined up after the colon. */
.finalists__detail {
  display: flex;
  gap: 0.3rem;
  min-width: 0;
}

.finalists__detail > :first-child {
  flex: none;
}

.finalists__detail > :last-child {
  min-width: 0;
  overflow-wrap: anywhere;
}

.finalists__cell--strong {
  font-weight: 600;
}

.finalists__muted {
  color: var(--text-muted);
  font-weight: 400;
}

/* Same orange as the Release Marks page's warn banner. */
.finalists__late {
  color: #ff8c00;
  font-weight: 600;
}

/* One name shows; the icon hints there are more markers in the tooltip. */
.finalists__marker {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.finalists__marker-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Beside the Marker heading, in the heading's own colour. */
.finalists__marker-info {
  font-size: 0.75rem;
  color: inherit;
  opacity: 0.8;
  margin-left: 0.2rem;
  position: relative;
}

/* Hover text is the browser's own tooltip (title), like the marker names. */
.finalists__incomplete {
  margin-left: 0.1rem;
  cursor: default;
}

/* Instant tooltip — native title has an uncontrollable hover delay. */
.finalists__marker-info::after {
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

.finalists__marker-info:hover::after {
  display: block;
}

</style>
