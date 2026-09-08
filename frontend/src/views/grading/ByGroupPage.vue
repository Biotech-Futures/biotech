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
              <th>Late</th>
              <th v-for="c in components" :key="c.code" :title="c.name">{{ c.code }}</th>
              <th>Total</th>
              <th>Marker</th>
              <th class="by-group__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="rows.length === 0">
              <td :colspan="components.length + 6" class="by-group__empty">No groups.</td>
            </tr>
            <tr v-for="r in rows" :key="r.group_id">
              <td class="by-group__muted">#{{ r.group_id }}</td>
              <td class="by-group__cell--strong">{{ r.group_name }}</td>
              <td>
                <span v-if="r.is_late" class="by-group__late">
                  Late<template v-if="r.late_by"> by {{ r.late_by }}</template>
                </span>
                <span v-else class="by-group__muted">—</span>
              </td>
              <td v-for="c in components" :key="c.code">
                <span v-if="r.marks[c.code] != null">{{ r.marks[c.code] }}</span>
                <span v-else class="by-group__muted">—</span>
              </td>
              <td class="by-group__cell--strong">
                <span v-if="r.total != null">{{ r.total }}</span>
                <span v-else class="by-group__muted">—</span>
              </td>
              <td>
                <span v-if="r.markers.length" class="by-group__marker" :title="markerTooltip(r)">
                  {{ r.markers.join(', ') }}
                </span>
                <span v-else class="by-group__muted">—</span>
              </td>
              <td class="by-group__cell--right">
                <RouterLink
                  v-if="r.has_submission"
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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import GroupSearchInput from '@/components/grading/GroupSearchInput.vue'
import {
  fetchFinalistCandidates,
  type FinalistCandidateRow,
  type FinalistCandidatesResponse
} from '@/utils/gradingAPI'
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

// Same payload the finalists ranking uses: every group with per-component
// totals and markers, sorted highest first — a marker's worklist.
const resp = ref<FinalistCandidatesResponse | null>(null)
const isLoading = ref(false)

const rows = computed(() => resp.value?.rows ?? [])
const components = computed(() => resp.value?.components ?? [])

// One line per rubric criterion with whoever last marked it; falls back to
// the flat marker list when no per-criterion data exists.
const markerTooltip = (r: FinalistCandidateRow) =>
  r.criterion_markers?.length
    ? r.criterion_markers.map((m) => `${m.label}: ${m.marker}`).join('\n')
    : `Marked by: ${r.markers.join(', ')}`

onMounted(async () => {
  isLoading.value = true
  try {
    resp.value = await fetchFinalistCandidates()
  } catch (err) {
    resp.value = null
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

.by-group__marker {
  cursor: help;
}

.by-group__empty {
  color: var(--text-muted);
  text-align: center;
  padding: 1rem;
}
</style>
