<template>
  <div class="finalists">
    <p v-if="actionError" class="finalists__banner finalists__banner--error">{{ actionError }}</p>
    <p v-if="actionMessage" class="finalists__banner finalists__banner--ok">{{ actionMessage }}</p>

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
          <form class="finalists__form" @submit.prevent="add">
            <GroupSearchInput
              ref="picker"
              v-model="groupQuery"
              class="finalists__picker"
              :show-suggestions="false"
            />
          </form>
        </div>
      </div>
      <p v-if="isLoadingCandidates" class="finalists__hint">Loading…</p>
      <div v-else class="finalists__scroll finalists__scroll--flush">
        <table class="finalists__table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Group</th>
              <th>Late</th>
              <th v-for="c in candidateComponents" :key="c.code" :title="c.name">
                {{ c.code === 'PROTOTYPE' ? 'PROT.' : c.code }}
              </th>
              <th>Total</th>
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
              <td :colspan="candidateComponents.length + 7" class="finalists__empty">
                {{ groupQuery.trim() ? 'No groups match your search.' : 'No groups.' }}
              </td>
            </tr>
            <tr v-for="r in candidates" :key="r.group_id">
              <td class="finalists__muted">#{{ r.group_id }}</td>
              <td class="finalists__cell--strong">{{ r.group_name }}</td>
              <td>
                <span v-if="r.is_late" class="finalists__late">
                  {{ r.late_by || 'Late' }}
                </span>
                <span v-else class="finalists__muted">—</span>
              </td>
              <td v-for="c in candidateComponents" :key="c.code">
                <span v-if="r.marks[c.code] != null">{{ r.marks[c.code] }}</span>
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
              <th>ID</th>
              <th>Group</th>
              <th>Flagged Date</th>
              <th>Flagged Time</th>
              <th>Flagged by</th>
              <th class="finalists__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="finalists.length === 0">
              <td colspan="6" class="finalists__empty">No finalists yet.</td>
            </tr>
            <tr v-for="f in finalists" :key="f.group_id">
              <td class="finalists__muted">#{{ f.group_id }}</td>
              <td class="finalists__cell--strong">{{ f.group_name }}</td>
              <td>{{ new Date(f.flagged_at).toLocaleDateString('en-GB') }}</td>
              <td>{{ new Date(f.flagged_at).toLocaleTimeString([], { hourCycle: 'h23' }) }}</td>
              <td>{{ f.flagged_by ?? '—' }}</td>
              <td class="finalists__cell--right">
                <button
                  type="button"
                  class="btn btn-outline btn-sm"
                  :disabled="isMutating"
                  @click="remove(f.group_id)"
                >
                  Remove
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      </template>
    </section>
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
  type FinalistListResponse
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import GroupSearchInput from '@/components/grading/GroupSearchInput.vue'

const list = ref<FinalistListResponse | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionMessage = ref('')
const isMutating = ref(false)
const picker = ref<InstanceType<typeof GroupSearchInput> | null>(null)
const groupQuery = ref('')

const finalists = computed(() => list.value?.finalists ?? [])

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

// Live-filter the Group Marks table by the search text (name or ID),
// matching the other marking tables; resolveId still powers the Add button.
const candidates = computed(() => {
  const rows = candidatesResp.value?.rows ?? []
  const q = groupQuery.value.trim().toLowerCase()
  if (!q) return rows
  return rows.filter(
    (r) => r.group_name.toLowerCase().includes(q) || String(r.group_id).includes(q)
  )
})
const candidateComponents = computed(() => candidatesResp.value?.components ?? [])

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

const addFromRow = async (id: number) => {
  actionMessage.value = ''
  actionError.value = ''
  isMutating.value = true
  try {
    await addFinalist(id)
    await Promise.all([load(), loadCandidates()])
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isMutating.value = false
  }
}

const add = async () => {
  actionMessage.value = ''
  actionError.value = ''
  const id = picker.value?.resolveId() ?? null
  if (id == null) {
    actionError.value = 'No group matches that name or ID.'
    return
  }
  isMutating.value = true
  try {
    await addFinalist(id)
    groupQuery.value = ''
    await Promise.all([load(), loadCandidates()])
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isMutating.value = false
  }
}

const remove = async (id: number) => {
  actionMessage.value = ''
  actionError.value = ''
  isMutating.value = true
  try {
    await removeFinalist(id)
    actionMessage.value = 'Finalist removed.'
    await Promise.all([load(), loadCandidates()])
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isMutating.value = false
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
}

.finalists__search-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  /* Same width as the By Component page's search box. */
  max-width: 252px;
}

.finalists__search-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
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

.finalists__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

.finalists__load-error {
  color: var(--danger);
  margin-bottom: 0.5rem;
}

.finalists__scroll {
  overflow-x: auto;
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

.finalists__table tbody tr:last-child td {
  border-bottom: none;
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
