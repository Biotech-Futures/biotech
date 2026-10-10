<template>
  <div class="by-group">
    <section>
      <p v-if="job.isBusy.value" class="by-group__banner by-group__banner--ok">
        Processing files for Download
      </p>
      <p v-if="job.phase.value === 'failed'" class="by-group__banner by-group__banner--error">
        {{ job.error.value }}
      </p>

      <p v-if="isLoading" class="by-group__hint">Loading…</p>
      <!-- Search and sort stay this page's own; the table shows every row. -->
      <AppDataTable
        v-else
        v-model:search="query"
        :columns="columns"
        :rows="tableRows"
        row-key="group_id"
        :selectable="false"
        :sort="tableSort"
        :page-size="DATA_TABLE_ALL"
        search-placeholder="Group name"
        :empty-message="query.trim() ? 'No groups match your search.' : 'No groups.'"
        @update:sort="setSort($event.key as SortKey)"
        @search-enter="open"
      >
        <!-- Enter in Search opens the group it names; this says when none does. -->
        <template v-if="error" #filters>
          <p class="by-group__error" role="alert">{{ error }}</p>
        </template>
        <template #stats>
          <span class="by-group__stats">
            {{ submittedCount }}/{{ rows.length }} Submitted ·
            {{ fullyMarkedCount }}/{{ submittedCount }} Fully Marked
          </span>
        </template>
        <template #search-side>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="job.isBusy.value"
            @click="job.startAll()"
          >
            <i class="fas fa-download" aria-hidden="true"></i> Download All
          </button>
        </template>

        <template #head-marker>
          Marker
          <i
            class="fas fa-circle-info by-group__marker-info"
            data-tip="Hover over a marker's name to see who marked each part."
            aria-hidden="true"
          ></i>
        </template>

        <template #cell-group="{ row }">
          <span class="by-group__cell--strong">{{ groupOf(row).group_name }}</span>
        </template>
        <template #cell-time="{ row }">
          <template v-if="groupOf(row).submission_id != null && groupOf(row).submitted_at">
            {{ new Date(groupOf(row).submitted_at!).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' }) }}
            {{
              new Date(groupOf(row).submitted_at!).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                hourCycle: 'h23'
              })
            }}
          </template>
          <span v-else class="by-group__muted">—</span>
        </template>
        <template #cell-late="{ row }">
          <span v-if="groupOf(row).is_late" class="by-group__late">
            {{ groupOf(row).late_by || 'Late' }}
          </span>
          <span v-else class="by-group__muted">—</span>
        </template>
        <template #cell-progress="{ row }">
          <span v-if="groupOf(row).submission_id != null" class="by-group__progress">
            <i
              :class="
                groupOf(row).total > 0 && groupOf(row).graded >= groupOf(row).total
                  ? 'fas fa-circle-check by-group__done'
                  : 'far fa-circle by-group__pending'
              "
              aria-hidden="true"
            ></i>
            {{ groupOf(row).total > 0 ? `${groupOf(row).graded}/${groupOf(row).total}` : '—' }}
          </span>
          <span v-else class="by-group__muted">—</span>
        </template>
        <template #cell-marker="{ row }">
          <span v-if="groupOf(row).markers.length" class="by-group__marker" :title="groupOf(row).markerTooltip">
            {{ groupOf(row).markers[0] }}
            <i
              v-if="groupOf(row).markers.length > 1"
              class="fas fa-users by-group__marker-icon"
              aria-hidden="true"
            ></i>
          </span>
          <span v-else class="by-group__muted">—</span>
        </template>

        <template #actions="{ row }">
          <RouterLink
            v-if="groupOf(row).submission_id != null"
            :to="`/grading/groups/${groupOf(row).group_id}`"
            class="btn btn-outline btn-sm"
          >
            Open
          </RouterLink>
          <span v-else class="by-group__muted">No sub.</span>
        </template>
      </AppDataTable>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { DATA_TABLE_ALL } from '@/utils/dataTable'
import { fetchComponentRows } from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const router = useRouter()
const query = ref('')
const error = ref('')

// The one group the search names: an exact name first, else the only
// partial match.
const resolveId = (): number | null => {
  const lower = query.value.trim().toLowerCase()
  if (!lower) return null
  const exact = rows.value.filter((r) => r.group_name.toLowerCase() === lower)
  if (exact.length === 1) return exact[0].group_id
  const partial = rows.value.filter((r) => r.group_name.toLowerCase().includes(lower))
  return partial.length === 1 ? partial[0].group_id : null
}

// Enter in Search opens that group.
const open = () => {
  error.value = ''
  const id = resolveId()
  if (id == null) {
    error.value = 'No group matches that name.'
    return
  }
  void router.push(`/grading/groups/${id}`)
}

// One row per group, aggregated across all four components: progress is
// criteria graded / criteria defined over the components the team actually
// submitted (a team without a report is not marked down for its criteria),
// markers deduped.
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
type SortKey = 'group' | 'time' | 'progress'

// Numeric-aware so "BTF-2" sorts before "BTF-10", matching the sidebar.
const nameCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })
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

const tableSort = computed(() => ({ key: sortKey.value, direction: sortDirection.value }))

const columns: DataTableColumn[] = [
  { key: 'group', label: 'Group' },
  { key: 'time', label: 'Submitted' },
  { key: 'late', label: 'Late', sortable: false },
  { key: 'progress', label: 'Progress' },
  { key: 'marker', label: 'Marker', sortable: false }
]

const sortValue = (r: GroupRow): number | string | null => {
  if (sortKey.value === 'time') return r.submitted_at
  return r.submission_id != null ? r.graded : null
}

const displayRows = computed(() => {
  // Live-filter the table by the search text (group name), matching the
  // By Component page; Enter still jumps to the group it names.
  const q = query.value.trim().toLowerCase()
  let sorted = [...rows.value]
  if (q) {
    sorted = sorted.filter(
      (r) => r.group_name.toLowerCase().includes(q)
    )
  }
  const dir = sortDirection.value === 'asc' ? 1 : -1
  sorted.sort((a, b) => {
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
      ...sorted.filter((r) => r.submission_id != null),
      ...sorted.filter((r) => r.submission_id == null)
    ]
  }
  return sorted
})

const tableRows = computed(() => displayRows.value as unknown as Record<string, unknown>[])
const groupOf = (row: Record<string, unknown>) => row as unknown as GroupRow

onMounted(async () => {
  isLoading.value = true
  try {
    // Components fetch in parallel; one failing (e.g. no rubric yet) just
    // drops its criteria from the totals rather than blanking the table.
    const payloads = (
      await Promise.all(CODES.map((code) => fetchComponentRows(code).catch(() => null)))
    ).filter((p) => p != null)
    if (!payloads.length) throw new Error('Could not load the group list.')

    const byGroup = new Map<number, GroupRow>()
    const tooltipLines = new Map<number, string[]>()

    for (const payload of payloads) {
      for (const r of payload.rows) {
        let g = byGroup.get(r.group_id)
        if (!g) {
          g = {
            group_id: r.group_id,
            group_name: r.group_name,
            submission_id: null,
            submitted_at: null,
            is_late: false,
            late_by: null,
            graded: 0,
            total: 0,
            markers: [],
            markerTooltip: ''
          }
          byGroup.set(r.group_id, g)
          tooltipLines.set(r.group_id, [])
        }
        // A row has a submission only when the team submitted this component:
        // only those count towards the total, and any of them shows the entry
        // (one submission covers every component, so they all agree).
        if (r.submission_id != null) {
          if (g.submission_id == null) {
            g.submission_id = r.submission_id
            g.submitted_at = r.submitted_at
            g.is_late = r.is_late
            g.late_by = r.late_by
          }
          g.total += payload.criteria_total
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

/* Notes above the table while a download is made or after it fails. */
.by-group__banner {
  padding: 0.5rem 1rem;
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-radius: 8px;
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

.by-group__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.by-group__error {
  align-self: center;
  color: var(--danger);
  font-size: 0.85rem;
  margin: 0;
}

.by-group__cell--strong {
  font-weight: 600;
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
</style>
