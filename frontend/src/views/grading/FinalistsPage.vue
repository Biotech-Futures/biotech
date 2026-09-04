<template>
  <div class="finalists">
    <section class="card finalists__add">
      <div class="card-header">
        <h3 class="card-title">Add Finalist</h3>
      </div>
      <p class="finalists__hint">
        Enter the group's ID to add them as a finalist.
      </p>
      <form class="finalists__form" @submit.prevent="add">
        <div class="finalists__input-wrap">
          <i class="fas fa-magnifying-glass finalists__search-icon" aria-hidden="true"></i>
          <input
            v-model="groupId"
            type="number"
            min="1"
            placeholder="Group ID"
            class="finalists__input"
            aria-label="Group ID"
          />
        </div>
        <button type="submit" class="btn btn-primary btn-sm" :disabled="isMutating">
          Add as Finalist
        </button>
      </form>
    </section>

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
      <p v-if="isLoadingCandidates" class="finalists__hint">Loading…</p>
      <div v-else class="finalists__scroll">
        <table class="finalists__table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Group</th>
              <th>Late</th>
              <th v-for="c in candidateComponents" :key="c.code" :title="c.name">{{ c.code }}</th>
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
            <tr v-if="candidates.length === 0">
              <td :colspan="candidateComponents.length + 7" class="finalists__empty">No groups.</td>
            </tr>
            <tr v-for="r in candidates" :key="r.group_id">
              <td class="finalists__muted">#{{ r.group_id }}</td>
              <td class="finalists__cell--strong">{{ r.group_name }}</td>
              <td>
                <span v-if="r.is_late" class="finalists__late">
                  Late<template v-if="r.late_by"> by {{ r.late_by }}</template>
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
                  {{ r.markers.join(', ') }}
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
                  Add as Finalist
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
                <span v-else class="finalists__muted">No submission</span>
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
              <th>Flagged at</th>
              <th>Flagged by</th>
              <th>Notified at</th>
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
              <td>{{ new Date(f.flagged_at).toLocaleString() }}</td>
              <td>{{ f.flagged_by ?? '—' }}</td>
              <td>
                <span v-if="f.notified" class="finalists__notified">
                  <i class="fas fa-envelope-circle-check" aria-hidden="true"></i>
                  {{ f.notified_at ? new Date(f.notified_at).toLocaleString() : 'Sent' }}
                </span>
                <span v-else class="finalists__muted">—</span>
              </td>
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

const list = ref<FinalistListResponse | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionMessage = ref('')
const isMutating = ref(false)
const groupId = ref('')

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

const candidates = computed(() => candidatesResp.value?.rows ?? [])
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
  const n = Number(groupId.value)
  actionMessage.value = ''
  actionError.value = ''
  if (!Number.isFinite(n) || n <= 0) {
    actionError.value = 'Enter a numeric group ID.'
    return
  }
  isMutating.value = true
  try {
    await addFinalist(n)
    groupId.value = ''
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

.finalists__input-wrap {
  position: relative;
  width: 20rem;
}

.finalists__search-icon {
  position: absolute;
  left: 0.65rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.8rem;
  pointer-events: none;
}

.finalists__input {
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem 0.45rem 2rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.finalists__input:focus {
  outline: none;
  border-color: var(--dark-green);
}

/* Hide the native number spinners — IDs are typed, not stepped. */
.finalists__input {
  appearance: textfield;
  -moz-appearance: textfield;
}

.finalists__input::-webkit-inner-spin-button,
.finalists__input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* Only the tables run full width; the add card stays compact. */
.finalists__add {
  max-width: 48rem;
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

.finalists__late {
  color: var(--danger);
  font-weight: 600;
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

.finalists__notified {
  color: var(--dark-green);
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
</style>
