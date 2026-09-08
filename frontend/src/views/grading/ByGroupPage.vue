<template>
  <div class="by-group">
    <div class="card by-group__search-card">
      <div class="card-header">
        <h3 class="card-title">Mark by Group</h3>
      </div>
      <p class="by-group__hint">
        Every component for a single group. Search by group name or ID.
      </p>
      <form class="by-group__form" @submit.prevent="open">
        <GroupSearchInput ref="picker" v-model="query" class="by-group__picker" @select="goTo" />
        <button type="submit" class="btn btn-primary btn-sm">Open</button>
      </form>
      <p v-if="error" class="by-group__error">{{ error }}</p>
    </div>

    <section>
      <h3 class="card-title by-group__list-title">Groups</h3>
      <p v-if="isLoading" class="by-group__hint">Loading…</p>
      <div v-else class="by-group__scroll">
        <table class="by-group__table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Group</th>
              <th>Submitted</th>
              <th>Time</th>
              <th>Late</th>
              <th>Progress</th>
              <th>Marker</th>
              <th class="by-group__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="rows.length === 0">
              <td colspan="8" class="by-group__empty">No groups.</td>
            </tr>
            <tr v-for="r in rows" :key="r.group_id">
              <td class="by-group__muted">#{{ r.group_id }}</td>
              <td class="by-group__cell--strong">{{ r.group_name }}</td>
              <td>
                <template v-if="r.submission_id != null && r.submitted_at">
                  {{ new Date(r.submitted_at).toLocaleDateString() }}
                </template>
                <span v-else class="by-group__muted">—</span>
              </td>
              <td>
                <template v-if="r.submission_id != null && r.submitted_at">
                  {{ new Date(r.submitted_at).toLocaleTimeString() }}
                </template>
                <span v-else class="by-group__muted">—</span>
              </td>
              <td>
                <span v-if="r.is_late" class="by-group__late">
                  Late<template v-if="r.late_by"> by {{ r.late_by }}</template>
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
                  {{ r.markers.join(', ') }}
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
                <span v-else class="by-group__muted">No submission</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import GroupSearchInput from '@/components/grading/GroupSearchInput.vue'
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
    error.value = 'No group matches that name or ID.'
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

/* Only the table runs full width; the search card stays compact. */
.by-group__search-card {
  max-width: 36rem;
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

.by-group__list-title {
  margin-bottom: 0.75rem;
}

.by-group__scroll {
  overflow-x: auto;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-radius: 8px;
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

.by-group__late {
  color: #b45309;
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

.by-group__marker {
  cursor: help;
}

.by-group__empty {
  color: var(--text-muted);
  text-align: center;
  padding: 1rem;
}
</style>
