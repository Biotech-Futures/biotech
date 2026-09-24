<template>
  <div class="by-group">
    <section>
      <div class="card by-group__search-card">
        <div class="by-group__search-field">
          <span class="by-group__search-label">Search</span>
          <form class="by-group__form" @submit.prevent="open">
            <GroupSearchInput
              ref="picker"
              v-model="query"
              class="by-group__picker"
              :show-suggestions="false"
              @select="goTo"
            />
          </form>
          <p v-if="error" class="by-group__error">{{ error }}</p>
        </div>
        <p class="by-group__stats">
          {{ submittedCount }}/{{ rows.length }} Submitted ·
          {{ fullyMarkedCount }}/{{ submittedCount }} Fully Marked
        </p>
        <div class="by-group__actions">
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="job.isBusy.value"
            @click="job.startAll()"
          >
            <i class="fas fa-download" aria-hidden="true"></i> Download All
          </button>
        </div>
      </div>

      <p v-if="job.phase.value === 'failed'" class="by-group__banner by-group__banner--error">
        {{ job.error.value }}
      </p>

      <p v-if="isLoading" class="by-group__hint">Loading…</p>
      <div v-else class="by-group__scroll">
        <table class="by-group__table">
          <thead>
            <tr>
              <th>Group</th>
              <th>
                <button type="button" class="by-group__sort" @click="setSort('time')">
                  Submitted At <i :class="sortIcon('time')" aria-hidden="true"></i>
                </button>
              </th>
              <th>Late</th>
              <th>
                <button type="button" class="by-group__sort" @click="setSort('progress')">
                  Progress <i :class="sortIcon('progress')" aria-hidden="true"></i>
                </button>
              </th>
              <th>
                Marker
                <i
                  class="fas fa-circle-info by-group__marker-info"
                  data-tip="Hover over a marker's name to see who marked each part."
                  aria-hidden="true"
                ></i>
              </th>
              <th class="by-group__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="displayRows.length === 0">
              <td colspan="6" class="by-group__empty">
                {{ query.trim() ? 'No groups match your search.' : 'No groups.' }}
              </td>
            </tr>
            <tr v-for="r in displayRows" :key="r.group_id">
              <td class="by-group__cell--strong">{{ r.group_name }}</td>
              <td>
                <template v-if="r.submission_id != null && r.submitted_at">
                  {{ new Date(r.submitted_at).toLocaleDateString('en-GB') }}
                  {{
                    new Date(r.submitted_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                      hourCycle: 'h23'
                    })
                  }}
                </template>
                <span v-else class="by-group__muted">—</span>
              </td>
              <td>
                <span v-if="r.is_late" class="by-group__late">
                  {{ r.late_by || 'Late' }}
                </span>
                <span v-else class="by-group__muted">—</span>
              </td>
              <td>
                <span v-if="r.submission_id != null" class="by-group__progress">
                  <i
                    :class="
                      r.total > 0 && r.graded >= r.total
                        ? 'fas fa-circle-check by-group__done'
                        : 'far fa-circle by-group__pending'
                    "
                    aria-hidden="true"
                  ></i>
                  {{ r.total > 0 ? `${r.graded}/${r.total}` : '—' }}
                </span>
                <span v-else class="by-group__muted">—</span>
              </td>
              <td>
                <span v-if="r.markers.length" class="by-group__marker" :title="r.markerTooltip">
                  {{ r.markers[0] }}
                  <i
                    v-if="r.markers.length > 1"
                    class="fas fa-users by-group__marker-icon"
                    aria-hidden="true"
                  ></i>
                </span>
                <span v-else class="by-group__muted">—</span>
              </td>
              <td class="by-group__cell--right">
                <RouterLink
                  v-if="r.submission_id != null"
                  :to="`/grading/groups/${r.group_id}`"
                  class="btn btn-outline btn-sm"
                >
                  Open
                </RouterLink>
                <span v-else class="by-group__muted">No sub.</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import GroupSearchInput from '@/components/grading/GroupSearchInput.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { fetchComponentRows } from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const router = useRouter()
const picker = ref<InstanceType<typeof GroupSearchInput> | null>(null)
const query = ref('')
const error = ref('')

const goTo = ({ id }: { id: number }) => {
  void router.push(`/grading/groups/${id}`)
}

const open = () => {
  error.value = ''
  const id = picker.value?.resolveId() ?? null
  if (id == null) {
    error.value = 'No group matches that name.'
    return
  }
  void router.push(`/grading/groups/${id}`)
}

// One row per group, aggregated across all four components: progress is
// criteria graded / criteria defined over the whole entry, markers deduped.
const CODES = ['SAQ', 'POSTER', 'REPORT', 'PROTOTYPE']

interface GroupRow {
  group_id: number
  group_name: string
  submission_id: number | null
  submitted_at: string | null
  is_late: boolean
  late_by: string | null
  graded: number
  total: number
  markers: string[]
  markerTooltip: string
}

const rows = ref<GroupRow[]>([])
const isLoading = ref(false)

// The everything-zip (all groups, all components) plus cohort stats — the
// same affordances the per-component table offers.
const job = useJobPolling()

const submittedCount = computed(() => rows.value.filter((r) => r.submission_id != null).length)
const fullyMarkedCount = computed(
  () => rows.value.filter((r) => r.submission_id != null && r.total > 0 && r.graded >= r.total).length
)

// Same sorting behaviour as the per-component tables.
type SortKey = 'time' | 'progress'
const sortKey = ref<SortKey>('time')
const sortDirection = ref<'asc' | 'desc'>('desc')

const setSort = (key: SortKey) => {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDirection.value = key === 'time' ? 'desc' : 'asc'
  }
}

const sortIcon = (key: SortKey) => {
  if (sortKey.value !== key) return 'fas fa-sort by-group__sort-icon by-group__sort-icon--idle'
  return sortDirection.value === 'asc'
    ? 'fas fa-sort-up by-group__sort-icon'
    : 'fas fa-sort-down by-group__sort-icon'
}

const sortValue = (r: GroupRow): number | string | null => {
  if (sortKey.value === 'time') return r.submitted_at
  return r.submission_id != null ? r.graded : null
}

const displayRows = computed(() => {
  // Live-filter the table by the search text (group name), matching the
  // By Component page; the dropdown picker still handles jump-to-group.
  const q = query.value.trim().toLowerCase()
  let sorted = [...rows.value]
  if (q) {
    sorted = sorted.filter(
      (r) => r.group_name.toLowerCase().includes(q)
    )
  }
  const dir = sortDirection.value === 'asc' ? 1 : -1
  sorted.sort((a, b) => {
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
      ...sorted.filter((r) => r.submission_id != null),
      ...sorted.filter((r) => r.submission_id == null)
    ]
  }
  return sorted
})

onMounted(async () => {
  isLoading.value = true
  try {
    // Components fetch in parallel; one failing (e.g. no rubric yet) just
    // drops its criteria from the totals rather than blanking the table.
    const payloads = (
      await Promise.all(CODES.map((code) => fetchComponentRows(code).catch(() => null)))
    ).filter((p) => p != null)
    if (!payloads.length) throw new Error('Could not load the group list.')

    const totalCriteria = payloads.reduce((sum, p) => sum + p.criteria_total, 0)
    const byGroup = new Map<number, GroupRow>()
    const tooltipLines = new Map<number, string[]>()

    for (const payload of payloads) {
      for (const r of payload.rows) {
        let g = byGroup.get(r.group_id)
        if (!g) {
          g = {
            group_id: r.group_id,
            group_name: r.group_name,
            submission_id: r.submission_id,
            submitted_at: r.submitted_at,
            is_late: r.is_late,
            late_by: r.late_by,
            graded: 0,
            total: totalCriteria,
            markers: [],
            markerTooltip: ''
          }
          byGroup.set(r.group_id, g)
          tooltipLines.set(r.group_id, [])
        }
        g.graded += r.criteria_graded
        const names = r.grader_names?.length
          ? r.grader_names
          : r.last_grader_name
            ? [r.last_grader_name]
            : []
        for (const name of names) if (!g.markers.includes(name)) g.markers.push(name)
        for (const m of r.criterion_markers ?? []) {
          tooltipLines.get(r.group_id)!.push(`${payload.component.code} ${m.n}: ${m.marker}`)
        }
      }
    }
    for (const g of byGroup.values()) {
      const lines = tooltipLines.get(g.group_id) ?? []
      g.markerTooltip = lines.length ? lines.join('\n') : `Marked by: ${g.markers.join(', ')}`
    }
    rows.value = [...byGroup.values()].sort((a, b) => a.group_id - b.group_id)
  } catch (err) {
    rows.value = []
    error.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
})
</script>

<style scoped>
.by-group {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* Search card sits flush on the table — same outline treatment as the
   component table page: table border instead of the card shadow, square
   shared edge, and the table's own top border draws the divider. */
.by-group__search-card,
.by-group__search-card:hover {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 1rem;
  margin-bottom: 0;
  border: 1px solid var(--border-light);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  box-shadow: none;
}

.by-group__stats {
  color: var(--charcoal);
  font-size: 0.9rem;
  /* Centered between the search box and the Download All button. */
  margin: 0 auto;
}

.by-group__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  /* Stays right-aligned even when the card wraps it onto its own line. */
  margin-left: auto;
}

/* Styled like the boxes it sits between — see ComponentTablePage. */
.by-group__banner {
  padding: 0.5rem 1rem;
  font-size: 0.9rem;
  margin: 0;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-top: none;
  border-bottom: none;
  border-radius: 0;
}

.by-group__banner--info {
  color: var(--info);
}

.by-group__banner--ok {
  color: var(--dark-green);
}

.by-group__banner--error {
  color: var(--danger);
}

.by-group__search-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  /* Same width as the By Component page's search box; explicit floor so
     the input's intrinsic minimum can't crowd the row. */
  flex: 1 1 140px;
  min-width: 155px;
  max-width: 252px;
}

.by-group__search-field :deep(.group-search__input) {
  min-width: 0;
}

.by-group__search-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.by-group__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.by-group__form {
  display: flex;
  gap: 0.5rem;
}

.by-group__picker {
  flex: 1;
}

.by-group__error {
  color: var(--danger);
  font-size: 0.85rem;
  margin: 0.5rem 0 0;
}

.by-group__scroll {
  overflow-x: auto;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-radius: 0 0 8px 8px;
}

.by-group__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.by-group__table th {
  text-align: left;
  padding: 0.6rem 0.85rem;
  color: var(--text-muted);
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border-bottom: 1px solid var(--border-light);
  white-space: nowrap;
}

.by-group__table td {
  padding: 0.55rem 0.85rem;
  border-bottom: 1px solid var(--border-light);
  color: var(--charcoal);
  white-space: nowrap;
}

.by-group__table tbody tr:last-child td {
  border-bottom: none;
}

.by-group__cell--strong {
  font-weight: 600;
}

.by-group__cell--right {
  text-align: right;
}

.by-group__muted {
  color: var(--text-muted);
}

/* Same orange as the Release Marks page's warn banner. */
.by-group__late {
  color: #ff8c00;
  font-weight: 600;
}

.by-group__progress {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.by-group__done {
  color: var(--dark-green);
}

.by-group__pending {
  color: var(--text-muted);
}

.by-group__sort {
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

.by-group__sort:hover {
  color: var(--dark-green);
}

.by-group__sort-icon {
  font-size: 0.7rem;
}

.by-group__sort-icon--idle {
  color: var(--border-light);
}

/* One name shows; the icon hints there are more markers in the tooltip. */
.by-group__marker {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.by-group__marker-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.by-group__marker-info {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-left: 0.2rem;
  position: relative;
}

/* Instant tooltip — native title has an uncontrollable hover delay. */
.by-group__marker-info::after {
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

.by-group__marker-info:hover::after {
  display: block;
}

.by-group__empty {
  color: var(--text-muted);
  text-align: center;
  padding: 1rem;
}
</style>
