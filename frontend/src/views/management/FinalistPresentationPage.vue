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
        Each finalist team will tick every time it can make. The times change each year, so
        add, change or remove them until they're final.
      </p>
      <p class="finalist-presentation__hint">
        <template v-if="symposiumDay">
          They're for the Symposium day, {{ symposiumDay }}, set on
          <RouterLink to="/management/notify-finalists">Notify Finalists</RouterLink>.
        </template>
        <template v-else>
          They're for the Symposium day. Set its date on
          <RouterLink to="/management/notify-finalists">Notify Finalists</RouterLink>.
        </template>
      </p>
      <!-- Typed and shown as they are, so they never shift with anyone's own
           time zone. -->
      <p class="finalist-presentation__hint" data-testid="sydney-time">
        All times are Sydney time<template v-if="sydneyClock">, {{ sydneyClock }} on that day</template>.
        They're entered and shown in Sydney time, whatever time zone you or the finalists are in.
      </p>

      <p v-if="isLoading" class="finalist-presentation__hint">Loading…</p>
      <div v-else-if="loadError" class="finalist-presentation__load-error">
        <p>Failed to load the times. {{ loadError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
      </div>
      <template v-else-if="data">
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
      </template>
    </section>

    <!-- Off until the times are final: finalists only see them once on. -->
    <section class="card">
      <h3 class="finalist-presentation__section-title">Show Time Slots</h3>
      <p class="finalist-presentation__hint">
        Finalists only see the times, to tick the ones they can make, once this is on. Turn it on
        once the times are final.
      </p>
      <HideShowSwitch
        v-if="data"
        :on="data.times_shown"
        :disabled="isSaving"
        label="Show the times to finalists"
        @change="setShown"
      >
        <template #before>
          <span class="finalist-presentation__switch-label">
            {{ data.times_shown ? 'Displayed to Finalists' : 'Hidden from Finalists' }}
          </span>
        </template>
      </HideShowSwitch>
    </section>

    <section class="card finalist-presentation__allocate">
      <h3 class="finalist-presentation__section-title">Allocate Slots</h3>
      <p class="finalist-presentation__hint">
        Give each finalist team a time. Ticks show the times each team said it can make.
      </p>
      <p v-if="isLoadingResponses" class="finalist-presentation__hint">Loading…</p>
      <div v-else-if="responsesError" class="finalist-presentation__load-error">
        <p>Failed to load the teams. {{ responsesError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="loadResponses">Try again</button>
      </div>
      <template v-else>
        <div class="finalist-presentation__scroll">
          <table class="finalist-presentation__table">
            <thead>
              <tr>
                <th>Group</th>
                <th>Answered</th>
                <th>Allocate</th>
                <th v-for="slot in columns" :key="slot.id" class="finalist-presentation__time-col">
                  {{ formatTime(slot.starts_at) }} – {{ formatTime(slot.ends_at) }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!teams.length">
                <td :colspan="columns.length + 3" class="finalist-presentation__empty">
                  No finalist teams yet.
                </td>
              </tr>
              <tr v-for="team in teams" :key="team.group_id">
                <td class="finalist-presentation__cell--strong">{{ team.group_name }}</td>
                <td v-if="team.answered_at" :title="team.answered_by ? `By ${team.answered_by}` : undefined">
                  {{ formatSubmitted(team.answered_at) }}
                </td>
                <td v-else class="finalist-presentation__muted">No response</td>
                <td>
                  <select
                    class="finalist-presentation__allocate-select"
                    :aria-label="`Time for ${team.group_name}`"
                    :value="team.allocated_slot_id ?? ''"
                    :disabled="allocating === team.group_id"
                    @change="allocate(team, $event)"
                  >
                    <option value="">Not allocated</option>
                    <option v-for="slot in columns" :key="slot.id" :value="slot.id">
                      {{ formatTime(slot.starts_at) }} – {{ formatTime(slot.ends_at) }}
                    </option>
                  </select>
                </td>
                <td
                  v-for="slot in columns"
                  :key="slot.id"
                  class="finalist-presentation__tick"
                  :class="{ 'is-allocated': team.allocated_slot_id === slot.id }"
                >
                  <i
                    v-if="team.slot_ids.includes(slot.id)"
                    class="fas fa-check"
                    title="Can make it"
                    aria-label="Can make it"
                  ></i>
                  <span v-else class="finalist-presentation__muted" aria-label="Can't make it">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="allocateError" class="finalist-presentation__error" role="alert">{{ allocateError }}</p>
      </template>
    </section>

    <section class="card finalist-presentation__submissions">
      <h3 class="finalist-presentation__section-title">Finalist Submission</h3>
      <p class="finalist-presentation__hint">
        <template v-if="slidesDue">
          Each finalist team's presentation slides, due {{ slidesDue }}, set on
          <RouterLink to="/management/notify-finalists">Notify Finalists</RouterLink>.
        </template>
        <template v-else>
          Each finalist team's presentation slides. Set the date they're due on
          <RouterLink to="/management/notify-finalists">Notify Finalists</RouterLink>.
        </template>
      </p>
      <p v-if="isLoadingSlides" class="finalist-presentation__hint">Loading…</p>
      <div v-else-if="slidesError" class="finalist-presentation__load-error">
        <p>Failed to load the slides. {{ slidesError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="loadSlides">Try again</button>
      </div>
      <div v-else class="finalist-presentation__scroll">
        <table class="finalist-presentation__table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Submitted</th>
              <th class="finalist-presentation__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!slidesTeams.length">
              <td colspan="3" class="finalist-presentation__empty">No finalist teams yet.</td>
            </tr>
            <tr v-for="team in slidesTeams" :key="team.group_id">
              <td class="finalist-presentation__cell--strong">{{ team.group_name }}</td>
              <template v-if="team.submitted">
                <td>{{ formatSubmitted(team.submitted_at) }}</td>
                <td class="finalist-presentation__cell--right">
                  <!-- Opens the slides in a new tab; the name is on hover. -->
                  <a
                    :href="presentationSlidesUrl(team.group_id)"
                    target="_blank"
                    rel="noopener"
                    class="btn btn-outline btn-sm"
                    :title="team.file_name"
                  >
                    Open
                  </a>
                </td>
              </template>
              <td v-else colspan="2" class="finalist-presentation__muted">Not submitted yet</td>
            </tr>
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
  allocatePresentationSlot,
  deletePresentationSlot,
  fetchPresentationResponses,
  fetchPresentationSlides,
  fetchPresentationSlots,
  presentationSlidesUrl,
  setPresentationTimesShown,
  updatePresentationSlot,
  type PresentationResponseTeam,
  type PresentationSlidesTeam,
  type PresentationSlot,
  type PresentationSlots
} from '@/utils/managementAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { sydneyClockOn } from '@/utils/date'
import HideShowSwitch from '@/views/management/HideShowSwitch.vue'

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

// Each finalist team and the times it said it can make.
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

// Allocate Slots: giving a team its time.
const allocating = ref<number | null>(null)
const allocateError = ref('')

const allocate = async (team: PresentationResponseTeam, event: Event) => {
  const select = event.target as HTMLSelectElement
  const slotId = select.value ? Number(select.value) : null
  allocating.value = team.group_id
  allocateError.value = ''
  try {
    team.allocated_slot_id = (await allocatePresentationSlot(team.group_id, slotId)).slot_id
  } catch (err) {
    allocateError.value = `${team.group_name}: ${apiErrorFromUnknown(err).message}`
    // Back to the time the team still has.
    select.value = team.allocated_slot_id === null ? '' : String(team.allocated_slot_id)
  } finally {
    allocating.value = null
  }
}

// Finalist Submission: each finalist team's slides.
const slidesTeams = ref<PresentationSlidesTeam[]>([])
const slidesDueOn = ref<string | null>(null)
const isLoadingSlides = ref(false)
const slidesError = ref('')

const loadSlides = async () => {
  isLoadingSlides.value = true
  slidesError.value = ''
  try {
    const slides = await fetchPresentationSlides()
    slidesTeams.value = slides.teams
    slidesDueOn.value = slides.slides_due
  } catch (err) {
    slidesError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoadingSlides.value = false
  }
}

onMounted(() => {
  void load()
  void loadResponses()
  void loadSlides()
})

// "Friday, 23 October 2026", as the finalist email words its dates.
const longDate = (iso: string | null | undefined) => {
  if (!iso) return ''
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year!, month! - 1, day).toLocaleDateString('en-AU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  })
}

const symposiumDay = computed(() => longDate(data.value?.symposium_date))
// "AEDT (daylight saving, UTC+11)" on the Symposium day, once it's set.
const sydneyClock = computed(() => {
  const iso = data.value?.symposium_date
  if (!iso) return ''
  const clock = sydneyClockOn(iso)
  return `${clock.name} (${clock.daylight ? 'daylight saving, ' : ''}${clock.offset})`
})
const slidesDue = computed(() => longDate(slidesDueOn.value))

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

// "17/10/26 23:06", as the other management tables write it.
const formatSubmitted = (iso: string | null) => {
  if (!iso) return ''
  const at = new Date(iso)
  const date = at.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })
  return `${date} ${at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
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

// Show the times to finalists once they're final, or hide them again.
const setShown = (shown: boolean) => void run(() => setPresentationTimesShown(shown))

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
  // A removed time is taken from any team given it, so the teams reload.
  if (await run(() => deletePresentationSlot(id))) void loadResponses()
}
</script>

<style scoped>
.finalist-presentation {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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

/* As the switch on System Emails. */
.finalist-presentation__switch-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--charcoal);
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

/* Under Add Time, above the times. */
.finalist-presentation__add + .finalist-presentation__error {
  margin: -0.25rem 0 1rem;
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

/* The time the team has been given: a green tint and outline, apart from
   the header's and hover's pale pink. */
.finalist-presentation__tick.is-allocated {
  background: color-mix(in srgb, var(--dark-green) 14%, transparent);
  box-shadow: inset 0 0 0 1px var(--dark-green);
}

/* Same box as the time fields above. */
.finalist-presentation__allocate-select {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.3rem 0.5rem;
  font-size: 0.85rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.finalist-presentation__add {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem 1rem;
  margin-bottom: 1rem;
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
