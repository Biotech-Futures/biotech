<template>
  <div class="finalists">
    <p v-if="actionError" class="finalists__banner finalists__banner--error">{{ actionError }}</p>

    <section>
      <h3 class="card-title finalists__list-title">
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
      <div class="card finalists__search-card">
        <div class="finalists__search-field">
          <span class="finalists__search-label">Search</span>
          <!-- Plain filter: no form, so Enter never flags a group. Flagging
               goes through each row's Add button only. -->
          <div class="finalists__form">
            <GroupSearchInput
              v-model="groupQuery"
              class="finalists__picker"
              :show-suggestions="false"
            />
          </div>
        </div>
        <p v-if="candidatesResp" class="finalists__stats">
          {{ fullyMarkedCount }}/{{ submittedCount }} Fully Marked ·
          {{ finalistCount }} Added as {{ finalistCount === 1 ? 'Finalist' : 'Finalists' }}
        </p>
        <div class="finalists__search-side">
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
        </div>
      </div>
      <p v-if="isLoadingCandidates" class="finalists__hint">Loading…</p>
      <div v-else class="finalists__scroll finalists__scroll--flush">
        <table class="finalists__table">
          <thead>
            <tr>
              <th :aria-sort="ariaSort('group')">
                <button type="button" class="finalists__sort-btn" @click="toggleSort('group')">
                  Group <i class="fas" :class="sortIcon('group')" aria-hidden="true"></i>
                </button>
              </th>
              <th>Late</th>
              <th v-for="c in markColumns" :key="c.key" :title="c.title" :aria-sort="ariaSort(c.key)">
                <button type="button" class="finalists__sort-btn" @click="toggleSort(c.key)">
                  {{ c.label }} <i class="fas" :class="sortIcon(c.key)" aria-hidden="true"></i>
                </button>
              </th>
              <th :aria-sort="ariaSort('total')">
                <button type="button" class="finalists__sort-btn" @click="toggleSort('total')">
                  Total <i class="fas" :class="sortIcon('total')" aria-hidden="true"></i>
                </button>
              </th>
              <th>
                Marker
                <i
                  class="fas fa-circle-info finalists__marker-info"
                  data-tip="Hover over a marker's name to see who marked each part."
                  aria-hidden="true"
                ></i>
              </th>
              <th class="finalists__cell--right">Finalist</th>
              <th class="finalists__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="candidates.length === 0">
              <td :colspan="markColumns.length + 6" class="finalists__empty">
                {{ groupQuery.trim() ? 'No groups match your search.' : 'No groups.' }}
              </td>
            </tr>
            <template v-for="r in candidates" :key="r.group_id">
              <tr :class="{ 'finalists__row--with-details': showDetails }">
                <td class="finalists__cell--strong">{{ r.group_name }}</td>
                <td>
                  <span v-if="r.is_late" class="finalists__late">
                    {{ r.late_by || 'Late' }}
                  </span>
                  <span v-else class="finalists__muted">—</span>
                </td>
                <td v-for="c in markColumns" :key="c.key">
                  <span v-if="notMarkedCompletely(r, c.key)" title="Not Marked Completely">
                    {{ markOf(r, c.key) ?? '' }}<span class="finalists__incomplete">*</span>
                  </span>
                  <span v-else-if="markOf(r, c.key) != null">{{ markOf(r, c.key) }}</span>
                  <span v-else class="finalists__muted">—</span>
                </td>
                <td class="finalists__cell--strong">
                  <span v-if="r.total != null">{{ r.total }}</span>
                  <span v-else class="finalists__muted">—</span>
                </td>
                <td>
                  <span
                    v-if="r.markers.length"
                    class="finalists__marker"
                    :title="markerTooltip(r)"
                  >
                    {{ r.markers[0] }}
                    <i
                      v-if="r.markers.length > 1"
                      class="fas fa-users finalists__marker-icon"
                      aria-hidden="true"
                    ></i>
                  </span>
                  <span v-else class="finalists__muted">—</span>
                </td>
                <td class="finalists__cell--right">
                  <button
                    v-if="!r.is_finalist"
                    type="button"
                    class="btn btn-outline btn-sm"
                    :disabled="isMutating"
                    @click="addFromRow(r.group_id)"
                  >
                    Add
                  </button>
                  <span v-else class="finalists__muted">Added</span>
                </td>
                <td class="finalists__cell--right">
                  <RouterLink
                    v-if="r.has_submission"
                    :to="`/grading/groups/${r.group_id}`"
                    class="btn btn-outline btn-sm"
                  >
                    Open
                  </RouterLink>
                  <span v-else class="finalists__muted">No sub.</span>
                </td>
              </tr>
              <!-- The project's details get a full-width row of their own so
                   long text can wrap; the pair reads as one group. -->
              <tr v-if="showDetails" class="finalists__details-row">
                <td :colspan="markColumns.length + 6">
                  <!-- Wraps to the visible width, not the table's, and a long
                       value wraps in line with itself, after its label. -->
                  <div class="finalists__details">
                    <div class="finalists__detail">
                      <span class="finalists__muted">Title:</span>
                      <span>{{ r.project_title || '—' }}</span>
                    </div>
                    <div class="finalists__detail-line">
                      <div class="finalists__detail">
                        <span class="finalists__muted">Category:</span>
                        <span>{{ r.project_category || '—' }}</span>
                      </div>
                      <div class="finalists__detail">
                        <span class="finalists__muted">Solution Category:</span>
                        <span>{{ r.solution_category || '—' }}</span>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
      </template>
    </section>

    <section>
      <h3 class="card-title finalists__list-title">
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
      <div v-else class="finalists__scroll">
        <table class="finalists__table">
          <thead>
            <tr>
              <th>#</th>
              <th>Group</th>
              <th>Flagged at</th>
              <th>Flagged by</th>
              <th>Late</th>
              <th>Total</th>
              <th>
                Marker
                <i
                  class="fas fa-circle-info finalists__marker-info"
                  data-tip="Hover over a marker's name to see who marked each part."
                  aria-hidden="true"
                ></i>
              </th>
              <th class="finalists__cell--right"></th>
              <th class="finalists__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="finalists.length === 0">
              <td colspan="9" class="finalists__empty">No finalists yet.</td>
            </tr>
            <tr v-for="(f, i) in finalistsInOrder" :key="f.group_id">
              <td class="finalists__muted">{{ finalistsInOrder.length - i }}</td>
              <td class="finalists__cell--strong">{{ f.group_name }}</td>
              <td>{{ `${new Date(f.flagged_at).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })} ${new Date(f.flagged_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}` }}</td>
              <td>{{ f.flagged_by ?? '—' }}</td>
              <td>
                <span v-if="candidatesByGroup.get(f.group_id)?.is_late" class="finalists__late">
                  {{ candidatesByGroup.get(f.group_id)!.late_by || 'Late' }}
                </span>
                <span v-else class="finalists__muted">—</span>
              </td>
              <td class="finalists__cell--strong">
                <span v-if="totalsByGroup.get(f.group_id) != null">
                  {{ totalsByGroup.get(f.group_id) }}
                </span>
                <span v-else class="finalists__muted">—</span>
              </td>
              <td>
                <span
                  v-if="candidatesByGroup.get(f.group_id)?.markers.length"
                  class="finalists__marker"
                  :title="markerTooltip(candidatesByGroup.get(f.group_id)!)"
                >
                  {{ candidatesByGroup.get(f.group_id)!.markers[0] }}
                  <i
                    v-if="candidatesByGroup.get(f.group_id)!.markers.length > 1"
                    class="fas fa-users finalists__marker-icon"
                    aria-hidden="true"
                  ></i>
                </span>
                <span v-else class="finalists__muted">—</span>
              </td>
              <td class="finalists__cell--right">
                <button
                  type="button"
                  class="btn btn-outline btn-sm"
                  :disabled="isMutating"
                  @click="pendingRemoval = f"
                >
                  Remove
                </button>
              </td>
              <td class="finalists__cell--right">
                <RouterLink :to="`/grading/groups/${f.group_id}`" class="btn btn-outline btn-sm">
                  Open
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
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
import GroupSearchInput from '@/components/grading/GroupSearchInput.vue'

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
const sortIcon = (key: string) =>
  sort.value?.key !== key ? 'fa-sort' : sort.value.direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down'
const ariaSort = (key: string) =>
  sort.value?.key !== key ? 'none' : sort.value.direction === 'asc' ? 'ascending' : 'descending'
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

// The Group Marks ranking keyed by group, so the Current Finalists table
// can show each finalist's total and marker.
const candidatesByGroup = computed(
  () => new Map((candidatesResp.value?.rows ?? []).map((r) => [r.group_id, r]))
)
const totalsByGroup = computed(
  () => new Map((candidatesResp.value?.rows ?? []).map((r) => [r.group_id, r.total]))
)

// The optional parts: one a team sent that still has unmarked criteria gets
// an asterisk, after its mark so far or alone when nothing is marked yet; a
// dash is left for parts never submitted.
const OPTIONAL_PARTS = new Set(['REPORT', 'PROTOTYPE'])
const notMarkedCompletely = (r: FinalistCandidateRow, code: string) =>
  OPTIONAL_PARTS.has(code) && r.incomplete.includes(code)
// The key above the table, whenever there is a column the asterisk can appear in.
const showsIncompleteKey = computed(() =>
  candidateComponents.value.some((c) => OPTIONAL_PARTS.has(c.code))
)

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

.finalists__list-title {
  margin-bottom: 0.5rem;
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

.finalists__form {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.finalists__picker {
  width: 100%;
}

/* Search card sits flush on the Group Marks table — same outline treatment
   as the other marking tables: table border instead of the card shadow,
   square shared edge, the table's own top border draws the divider. */
.finalists__search-card,
.finalists__search-card:hover {
  padding: 1rem;
  margin-bottom: 0;
  border: 1px solid var(--border-light);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  box-shadow: none;
  /* Search on the left, the asterisk key on the right, both on the bottom line. */
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
}

.finalists__search-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  /* Same width as the By Component page's search box. */
  flex: 0 1 252px;
  max-width: 252px;
}

/* Centered between the search box and the buttons, as on the component pages. */
.finalists__stats {
  margin: 0 auto;
  color: var(--charcoal);
  font-size: 0.9rem;
}

.finalists__search-side {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  /* Stays right-aligned even when the card wraps it onto its own line, as
     on the component pages. */
  margin-left: auto;
}

.finalists__legend {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.finalists__search-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
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
  color: var(--charcoal);
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

.finalists__scroll {
  overflow-x: auto;
  /* Lets the details rows size to the visible width (cqw). */
  container-type: inline-size;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-elevated);
}

/* The Group Marks table joins the search card above it. */
.finalists__scroll--flush {
  border-radius: 0 0 8px 8px;
}

.finalists__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.finalists__table th,
.finalists__table td {
  padding: 0.55rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  white-space: nowrap;
}

.finalists__table thead th {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

/* A header that sorts: the header's own look, and a pointer. */
.finalists__sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0;
  border: none;
  background: transparent;
  font: inherit;
  letter-spacing: inherit;
  text-transform: inherit;
  color: inherit;
  cursor: pointer;
}

.finalists__sort-btn .fas {
  font-size: 0.7rem;
  opacity: 0.6;
}

.finalists__table tbody tr:last-child td {
  border-bottom: none;
}

.finalists__row--with-details td {
  border-bottom: none;
}

.finalists__details-row td {
  white-space: normal;
  font-size: 0.85rem;
  padding-top: 0;
  padding-left: 1.5rem;
}

/* Held in view while the table scrolls sideways, and as wide as the
   visible part of it less the cell's indent, so long text wraps there. */
.finalists__details {
  position: sticky;
  left: 1.5rem;
  max-width: calc(100cqw - 2.25rem);
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

.finalists__empty {
  text-align: center;
  color: var(--text-muted);
  padding: 1.5rem 0.75rem;
}

.finalists__cell--strong {
  font-weight: 600;
}

/* Scoped under the table selector so this outweighs the generic th/td rule
   that sets text-align: left. */
.finalists__table .finalists__cell--right {
  text-align: right;
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

.finalists__marker-info {
  font-size: 0.75rem;
  color: var(--text-muted);
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
