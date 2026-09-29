<template>
  <!-- The finalists' presentations at the Symposium: the times they can
       present, which change year to year. -->
  <div class="finalist-presentation">
    <section class="card finalist-presentation__setup">
      <div class="card-header">
        <h3 class="card-title">Finalist Presentation</h3>
      </div>
      <h3 class="finalist-presentation__section-title">Presentation Times</h3>
      <p class="finalist-presentation__hint">
        Each finalist student will tick every time they can make. The times change each year, so
        add, change or remove them until they're final.
      </p>
      <p class="finalist-presentation__hint">
        <template v-if="symposiumDay">
          They're on the Symposium day, {{ symposiumDay }}, set on
          <RouterLink to="/management/notify-finalists">Notify Finalists</RouterLink>.
        </template>
        <template v-else>
          They're on the Symposium day. Set its date on
          <RouterLink to="/management/notify-finalists">Notify Finalists</RouterLink>.
        </template>
      </p>

      <p v-if="isLoading" class="finalist-presentation__hint">Loading…</p>
      <div v-else-if="loadError" class="finalist-presentation__load-error">
        <p>Failed to load the times. {{ loadError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
      </div>
      <template v-else-if="data">
        <div class="finalist-presentation__scroll">
          <table class="finalist-presentation__table">
            <thead>
              <tr>
                <th>Start</th>
                <th>End</th>
                <th class="finalist-presentation__cell--right"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!data.slots.length">
                <td colspan="3" class="finalist-presentation__empty">No times yet.</td>
              </tr>
              <tr v-for="slot in data.slots" :key="slot.id">
                <template v-if="editingId === slot.id">
                  <td>
                    <input v-model="edit.starts_at" type="time" class="finalist-presentation__time" aria-label="Start" />
                  </td>
                  <td>
                    <input v-model="edit.ends_at" type="time" class="finalist-presentation__time" aria-label="End" />
                  </td>
                  <td class="finalist-presentation__cell--right">
                    <div class="finalist-presentation__row-actions">
                      <button
                        type="button"
                        class="btn btn-primary btn-sm"
                        :disabled="isSaving || !edit.starts_at || !edit.ends_at"
                        @click="saveEdit(slot.id)"
                      >
                        Save
                      </button>
                      <button type="button" class="btn btn-outline btn-sm" :disabled="isSaving" @click="cancelEdit">
                        Cancel
                      </button>
                    </div>
                  </td>
                </template>
                <template v-else>
                  <td>{{ formatTime(slot.starts_at) }}</td>
                  <td>{{ formatTime(slot.ends_at) }}</td>
                  <td class="finalist-presentation__cell--right">
                    <div class="finalist-presentation__row-actions">
                      <button type="button" class="btn btn-outline btn-sm" :disabled="isSaving" @click="startEdit(slot)">
                        Edit
                      </button>
                      <button type="button" class="btn btn-outline btn-sm" :disabled="isSaving" @click="remove(slot.id)">
                        Remove
                      </button>
                    </div>
                  </td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- After adding, the next time starts where this one ended and runs
             as long, so a run of times goes in quickly. -->
        <div class="finalist-presentation__add">
          <label class="finalist-presentation__field">
            <span>Start</span>
            <input v-model="draft.starts_at" type="time" class="finalist-presentation__time" />
          </label>
          <label class="finalist-presentation__field">
            <span>End</span>
            <input v-model="draft.ends_at" type="time" class="finalist-presentation__time" />
          </label>
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="isSaving || !draft.starts_at || !draft.ends_at"
            @click="add"
          >
            {{ isSaving ? 'Saving…' : 'Add Time' }}
          </button>
        </div>
        <p v-if="actionError" class="finalist-presentation__error" role="alert">{{ actionError }}</p>
      </template>
    </section>

    <section class="card finalist-presentation__responses">
      <h3 class="finalist-presentation__section-title">Finalist Response</h3>
      <p class="finalist-presentation__hint">
        The times each finalist student said they can make. Each student answers for themselves.
      </p>
      <p v-if="isLoadingResponses" class="finalist-presentation__hint">Loading…</p>
      <div v-else-if="responsesError" class="finalist-presentation__load-error">
        <p>Failed to load the responses. {{ responsesError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="loadResponses">Try again</button>
      </div>
      <div v-else class="finalist-presentation__scroll">
        <table class="finalist-presentation__table finalist-presentation__table--responses">
          <thead>
            <tr>
              <th>Group</th>
              <th>Student</th>
              <th v-for="slot in columns" :key="slot.id" class="finalist-presentation__time-col">
                {{ formatTime(slot.starts_at) }} – {{ formatTime(slot.ends_at) }}
              </th>
              <th>Answered</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!teams.length">
              <td :colspan="columns.length + 3" class="finalist-presentation__empty">
                No finalist teams yet.
              </td>
            </tr>
            <template v-for="team in teams" :key="team.group_id">
              <tr v-if="!team.students.length">
                <td class="finalist-presentation__cell--strong">{{ team.group_name }}</td>
                <td :colspan="columns.length + 2" class="finalist-presentation__muted">No students</td>
              </tr>
              <!-- The group's name spans its students' rows. -->
              <tr v-for="(student, index) in team.students" :key="student.user_id">
                <td
                  v-if="index === 0"
                  :rowspan="team.students.length"
                  class="finalist-presentation__cell--strong finalist-presentation__group-cell"
                >
                  {{ team.group_name }}
                </td>
                <td>{{ student.name }}</td>
                <template v-if="student.responded">
                  <td v-for="slot in columns" :key="slot.id" class="finalist-presentation__tick">
                    <i
                      v-if="student.slot_ids.includes(slot.id)"
                      class="fas fa-check"
                      title="Can make it"
                      aria-label="Can make it"
                    ></i>
                    <span v-else class="finalist-presentation__muted" aria-label="Can't make it">—</span>
                  </td>
                  <td>{{ formatAnswered(student.updated_at) }}</td>
                </template>
                <td v-else :colspan="columns.length + 1" class="finalist-presentation__muted">
                  No response yet
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  addPresentationSlot,
  deletePresentationSlot,
  fetchPresentationResponses,
  fetchPresentationSlots,
  updatePresentationSlot,
  type PresentationResponseTeam,
  type PresentationSlot,
  type PresentationSlots
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const data = ref<PresentationSlots | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const isSaving = ref(false)
const actionError = ref('')

const draft = reactive({ starts_at: '', ends_at: '' })
const editingId = ref<number | null>(null)
const edit = reactive({ starts_at: '', ends_at: '' })

const load = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    data.value = await fetchPresentationSlots()
  } catch (err) {
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

// Finalist Response: each finalist student's answer.
const teams = ref<PresentationResponseTeam[]>([])
const isLoadingResponses = ref(false)
const responsesError = ref('')

const loadResponses = async () => {
  isLoadingResponses.value = true
  responsesError.value = ''
  try {
    teams.value = (await fetchPresentationResponses()).teams
  } catch (err) {
    responsesError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoadingResponses.value = false
  }
}

// A column for each time listed above, so it follows every change there.
const columns = computed(() => data.value?.slots ?? [])

onMounted(() => {
  void load()
  void loadResponses()
})

// "Friday, 23 October 2026", as the finalist email words the day.
const symposiumDay = computed(() => {
  const iso = data.value?.symposium_date
  if (!iso) return ''
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year!, month! - 1, day).toLocaleDateString('en-AU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  })
})

const minutesOf = (hhmm: string) => {
  const [hours, minutes] = hhmm.split(':').map(Number)
  return hours! * 60 + minutes!
}

const hhmmOf = (total: number) =>
  `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`

// 24 hour, no am or pm: "9:30", "13:00".
const clock = (hours: number, minutes: number) => `${hours}:${String(minutes).padStart(2, '0')}`

const formatTime = (hhmm: string) => {
  const total = minutesOf(hhmm)
  return clock(Math.floor(total / 60), total % 60)
}

// "29 Sept, 15:10".
const formatAnswered = (iso: string | null) => {
  if (!iso) return ''
  const at = new Date(iso)
  return `${at.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })}, ${clock(at.getHours(), at.getMinutes())}`
}

// Every change answers with the whole list, which replaces the one shown.
const run = async (change: () => Promise<PresentationSlots>): Promise<boolean> => {
  isSaving.value = true
  actionError.value = ''
  try {
    data.value = await change()
    return true
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
    return false
  } finally {
    isSaving.value = false
  }
}

const add = async () => {
  const fields = { starts_at: draft.starts_at, ends_at: draft.ends_at }
  if (!(await run(() => addPresentationSlot(fields)))) return
  const length = minutesOf(fields.ends_at) - minutesOf(fields.starts_at)
  const nextEnd = minutesOf(fields.ends_at) + length
  draft.starts_at = fields.ends_at
  draft.ends_at = length > 0 && nextEnd < 24 * 60 ? hhmmOf(nextEnd) : ''
}

const startEdit = (slot: PresentationSlot) => {
  editingId.value = slot.id
  edit.starts_at = slot.starts_at
  edit.ends_at = slot.ends_at
  actionError.value = ''
}

const cancelEdit = () => {
  editingId.value = null
  actionError.value = ''
}

const saveEdit = async (id: number) => {
  if (await run(() => updatePresentationSlot(id, { starts_at: edit.starts_at, ends_at: edit.ends_at }))) {
    editingId.value = null
  }
}

const remove = async (id: number) => {
  await run(() => deletePresentationSlot(id))
}
</script>

<style scoped>
.finalist-presentation {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.finalist-presentation__setup {
  max-width: 48rem;
}

.finalist-presentation__section-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.finalist-presentation__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.finalist-presentation__hint a {
  color: var(--dark-green);
}

.finalist-presentation__load-error,
.finalist-presentation__error {
  color: var(--danger);
  font-size: 0.9rem;
}

.finalist-presentation__error {
  margin: 0.75rem 0 0;
}

.finalist-presentation__scroll {
  overflow-x: auto;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-elevated);
  margin-bottom: 1rem;
}

.finalist-presentation__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.finalist-presentation__table th,
.finalist-presentation__table td {
  padding: 0.55rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  white-space: nowrap;
}

.finalist-presentation__table thead th {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.finalist-presentation__table tbody tr:last-child td {
  border-bottom: none;
}

/* Scoped under the table so it outweighs the text-align: left above. */
.finalist-presentation__table .finalist-presentation__cell--right {
  text-align: right;
}

.finalist-presentation__row-actions {
  display: inline-flex;
  gap: 0.5rem;
}

.finalist-presentation__empty {
  color: var(--text-muted);
  text-align: center;
}

.finalist-presentation__muted {
  color: var(--text-muted);
}

.finalist-presentation__cell--strong {
  font-weight: 600;
}

/* Spans its students' rows, so it sits at the top of them. */
.finalist-presentation__table--responses .finalist-presentation__group-cell {
  vertical-align: top;
}

/* Times read as written, not in the header's capitals. */
.finalist-presentation__table thead .finalist-presentation__time-col {
  text-transform: none;
  text-align: center;
  line-height: 1.3;
}

/* Scoped under the table so it outweighs the text-align: left above. */
.finalist-presentation__table .finalist-presentation__tick {
  text-align: center;
}

.finalist-presentation__tick .fa-check {
  color: var(--dark-green);
}

.finalist-presentation__add {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem 1rem;
}

.finalist-presentation__field {
  display: grid;
  gap: 0.3rem;
  font-size: 0.9rem;
}

.finalist-presentation__field > span {
  color: var(--text-muted);
}

/* Same boxes as the date fields on Notify Finalists. */
.finalist-presentation__time {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.35rem 0.55rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.finalist-presentation__time:focus {
  outline: none;
  border-color: var(--dark-green);
}
</style>
