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
      <!-- As Release Marks: who the finalists are isn't settled until
           every team, extensions included, is done submitting. -->
      <p
        v-if="data && !data.times_shown && data.submissions_open"
        class="finalist-presentation__banner finalist-presentation__banner--warn"
      >
        Submissions are still open (including extensions) - time slots can be shown once the
        window has closed.
      </p>
      <HideShowSwitch
        v-if="data"
        :on="data.times_shown"
        :disabled="isSaving || (!data.times_shown && data.submissions_open)"
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
        <AppDataTable
          :columns="allocateColumns"
          :rows="teamRows"
          row-key="id"
          :selectable="false"
          :page-size="DATA_TABLE_ALL"
          :sort="NO_SORT"
          search-placeholder="Group name"
          empty-message="No finalist teams yet."
        >
          <template #cell-group="{ row }">
            <span class="finalist-presentation__cell--strong">{{ teamOf(row).group_name }}</span>
          </template>
          <template #cell-answered="{ row }">
            <span
              v-if="teamOf(row).answered_at"
              :title="teamOf(row).answered_by ? `By ${teamOf(row).answered_by}` : undefined"
            >
              {{ formatSubmitted(teamOf(row).answered_at) }}
            </span>
            <span v-else class="finalist-presentation__muted">No response</span>
          </template>
          <template #cell-allocate="{ row }">
            <select
              class="finalist-presentation__allocate-select"
              :aria-label="`Time for ${teamOf(row).group_name}`"
              :value="teamOf(row).allocated_slot_id ?? ''"
              :disabled="allocating === teamOf(row).group_id"
              @change="allocate(teamOf(row), $event)"
            >
              <option value="">Not allocated</option>
              <option v-for="slot in columns" :key="slot.id" :value="slot.id">
                {{ formatTime(slot.starts_at) }} – {{ formatTime(slot.ends_at) }}
              </option>
            </select>
          </template>
          <!-- A column for each time: its heading as written, and a tick where
               the team said it can make it. -->
          <template v-for="slot in columns" :key="`head-${slot.id}`" #[`head-slot-${slot.id}`]="{ column }">
            <span class="finalist-presentation__time-head">{{ column.label }}</span>
          </template>
          <template v-for="slot in columns" :key="`cell-${slot.id}`" #[`cell-slot-${slot.id}`]="{ row }">
            <i
              v-if="teamOf(row).slot_ids.includes(slot.id)"
              class="fas fa-check"
              title="Can make it"
              aria-label="Can make it"
            ></i>
            <span v-else class="finalist-presentation__muted" aria-label="Can't make it">—</span>
          </template>
        </AppDataTable>
        <p v-if="allocateError" class="finalist-presentation__error" role="alert">{{ allocateError }}</p>
      </template>
    </section>

    <section class="card finalist-presentation__submissions">
      <h3 class="finalist-presentation__section-title">Finalist Submissions</h3>
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
      <AppDataTable
        v-else
        :columns="submissionColumns"
        :rows="submissionRows"
        row-key="id"
        :selectable="false"
        :page-size="DATA_TABLE_ALL"
        :sort="NO_SORT"
        search-placeholder="Group name"
        empty-message="No finalist teams yet."
        :action-columns="2"
      >
        <template #cell-group="{ row }">
          <span class="finalist-presentation__cell--strong">{{ slidesOf(row).group_name }}</span>
        </template>
        <template #cell-submitted="{ row }">
          <template v-if="slidesOf(row).submitted">{{ formatSubmitted(slidesOf(row).submitted_at) }}</template>
          <span v-else class="finalist-presentation__muted">Not submitted yet</span>
        </template>
        <!-- Open | Download. A PDF opens in a new tab; PowerPoint can't show in
             the browser, so it only downloads. The name is on hover. -->
        <template #actions="{ row, column }">
          <template v-if="slidesOf(row).submitted">
            <a
              v-if="column === 0 && fileType(slidesOf(row).file_name) === 'PDF'"
              :href="presentationSlidesUrl(slidesOf(row).group_id)"
              target="_blank"
              rel="noopener"
              class="btn btn-outline btn-sm"
              :title="slidesOf(row).file_name"
            >
              Open
            </a>
            <a
              v-else-if="column === 1"
              :href="presentationSlidesDownloadUrl(slidesOf(row).group_id)"
              class="btn btn-outline btn-sm"
              :title="slidesOf(row).file_name"
            >
              Download
            </a>
          </template>
        </template>
      </AppDataTable>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import AppDataTable, { type DataTableColumn, type DataTableSort } from '@/components/AppDataTable.vue'
import {
  addPresentationSlot,
  allocatePresentationSlot,
  deletePresentationSlot,
  fetchPresentationResponses,
  fetchPresentationSlides,
  fetchPresentationSlots,
  presentationSlidesDownloadUrl,
  presentationSlidesUrl,
  setPresentationTimesShown,
  updatePresentationSlot,
  type PresentationResponseTeam,
  type PresentationSlidesTeam,
  type PresentationSlot,
  type PresentationSlots
} from '@/utils/managementAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { DATA_TABLE_ALL } from '@/utils/dataTable'
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

// Both tables keep the teams in the order they come; nothing sorts them.
const NO_SORT: DataTableSort = { key: '', direction: 'asc' }

// Allocate Slots: each team as a row, with plain text for search; the team
// itself for the cells drawn here.
const teamRows = computed(() =>
  teams.value.map((team) => ({
    id: team.group_id,
    team,
    group: team.group_name,
    answered: team.answered_at ? formatSubmitted(team.answered_at) : 'No response',
    allocate: slotLabel(columns.value.find((slot) => slot.id === team.allocated_slot_id)) || 'Not allocated'
  }))
)

const teamOf = (row: Record<string, unknown>) => row.team as PresentationResponseTeam

// Group, Answered, Allocate, then a column for each time, centred, the
// team's given time tinted.
const allocateColumns = computed<DataTableColumn[]>(() => [
  { key: 'group', label: 'Group', sortable: false },
  { key: 'answered', label: 'Answered', sortable: false },
  { key: 'allocate', label: 'Allocate', sortable: false },
  ...columns.value.map((slot) => ({
    key: `slot-${slot.id}`,
    label: slotLabel(slot),
    sortable: false,
    align: 'center' as const,
    cellClass: (row: Record<string, unknown>) => ({
      'finalist-presentation__tick': true,
      'is-allocated': teamOf(row).allocated_slot_id === slot.id
    })
  }))
])

// Giving a team its time.
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

// Finalist Submissions: each finalist team's slides.
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

// Finalist Submissions: each team as a row, with plain text for search.
const submissionColumns: DataTableColumn[] = [
  { key: 'group', label: 'Group', sortable: false },
  { key: 'submitted', label: 'Submitted', sortable: false },
  { key: 'type', label: 'Type', sortable: false }
]

const submissionRows = computed(() =>
  slidesTeams.value.map((team) => ({
    id: team.group_id,
    team,
    group: team.group_name,
    submitted: team.submitted ? formatSubmitted(team.submitted_at) : 'Not submitted yet',
    type: team.submitted ? fileType(team.file_name) : '—'
  }))
)

const slidesOf = (row: Record<string, unknown>) => row.team as PresentationSlidesTeam

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

// "9:30 – 10:00".
const slotLabel = (slot: PresentationSlot | undefined) =>
  slot ? `${formatTime(slot.starts_at)} – ${formatTime(slot.ends_at)}` : ''

// "17/10/26 23:06", as the other management tables write it.
const formatSubmitted = (iso: string | null) => {
  if (!iso) return ''
  const at = new Date(iso)
  const date = at.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })
  return `${date} ${at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
}

// "PDF", "PPTX" or "PPT", from the file's name.
const fileType = (name: string) => (name.includes('.') ? name.split('.').pop()!.toUpperCase() : '')

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

/* As Release Marks' notice while submissions are open. */
.finalist-presentation__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

.finalist-presentation__banner--warn {
  background: color-mix(in srgb, #ff8c00 12%, transparent);
  color: #ff8c00;
}

/* As the switch on System Emails. */
.finalist-presentation__switch-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--teal);
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

/* Times read as written, not in the heading's capitals. */
.finalist-presentation__time-head {
  text-transform: none;
  line-height: 1.3;
}

.finalist-presentation__tick .fa-check {
  color: var(--dark-green);
}

/* The time the team has been given: a green tint and outline, apart from
   the hover's. The cell is the shared table's, so this reaches in. */
.finalist-presentation__allocate :deep(.finalist-presentation__tick.is-allocated) {
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
  color: var(--teal);
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
  color: var(--teal);
}

.finalist-presentation__time:focus {
  outline: none;
  border-color: var(--dark-green);
}
</style>
