<template>
  <!-- The finalists' slides: when teams stop being able to hand them in, then
       what each has handed in. -->
  <div class="finalist-submissions">
    <!-- As Submission Deadline: the time as it is, then the form to change it.
         Headed as a Management page's first card is. -->
    <section class="card finalist-close">
      <div class="card-header">
        <h3 class="card-title">Finalist Submissions</h3>
      </div>
      <!-- Its subheading, as Finalist Presentation's Presentation Times. -->
      <h3 class="finalist-presentation__section-title">Close Submissions</h3>
      <p class="finalist-close__hint">
        Finalist teams can upload, change and submit their slides until this time. After it,
        nothing more can be submitted, though admins can still make changes for a team. Times are
        Sydney time.
      </p>

      <p v-if="isLoading" class="finalist-close__hint">Loading…</p>

      <div v-else-if="loadError" class="finalist-close__load-error">
        <p>Failed to load. {{ loadError }}</p>
        <button type="button" class="btn btn-outline btn-field" @click="load">Try again</button>
      </div>

      <template v-else>
        <p v-if="!close" class="finalist-close__row">
          <i class="fas fa-lock-open" aria-hidden="true"></i>
          No closing time set - finalist teams can keep submitting.
        </p>
        <template v-else>
          <p
            class="finalist-close__row"
            :class="close.is_open ? 'finalist-close__state--open' : 'finalist-close__state--closed'"
          >
            <i :class="close.is_open ? 'fas fa-lock-open' : 'fas fa-lock'" aria-hidden="true"></i>
            {{ close.is_open ? 'Finalist submissions open' : 'Finalist submissions closed' }}
          </p>
          <p class="finalist-close__row">
            Closes:
            <strong>{{ formatSydneyStatement(close.closes_at) }}</strong>
          </p>
          <p v-if="close.set_by" class="finalist-close__row finalist-close__muted">
            Set by {{ close.set_by }} on {{ formatSydneyStatement(close.created_at) }}
          </p>
        </template>
      </template>

      <form class="finalist-close__form" @submit.prevent="confirmOpen = true">
        <SydneyDateTimeFields
          v-model="closesAtLocal"
          date-label="Closing Date"
          required
        />
        <button type="submit" class="btn btn-primary btn-field" :disabled="isSaving || !closesAtLocal">
          {{ isSaving ? 'Saving…' : 'Save Closing Time' }}
        </button>
      </form>

      <p v-if="actionError" class="finalist-close__banner" role="alert">{{ actionError }}</p>
    </section>

    <div v-if="confirmOpen" class="finalist-close__overlay" @click.self="confirmOpen = false">
      <div class="finalist-close__dialog" role="dialog" aria-modal="true" aria-label="Confirm closing time">
        <h4 class="finalist-close__dialog-title">
          {{ close ? 'Change when finalist submissions close?' : 'Close finalist submissions?' }}
        </h4>
        <p class="finalist-close__dialog-body">
          Finalist teams can submit until <strong>{{ pendingLabel }}</strong>. They see the closing
          time straight away.
        </p>
        <div class="finalist-close__dialog-actions">
          <button type="button" class="btn btn-outline btn-field" @click="confirmOpen = false">
            Cancel
          </button>
          <button type="button" class="btn btn-primary btn-field" :disabled="isSaving" @click="save">
            {{ isSaving ? 'Saving…' : 'Confirm' }}
          </button>
        </div>
      </div>
    </div>

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
        <button type="button" class="btn btn-outline btn-field" @click="loadSlides">Try again</button>
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
        <!-- As Grading's By Group: how many teams have handed theirs in. -->
        <template #stats>
          <span>{{ submittedCount }}/{{ slidesTeams.length }} Submitted</span>
        </template>
        <!-- Every team's slides, zipped: the green button. -->
        <template #search-side>
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="!anySlides || isDownloadingZip"
            @click="downloadSlides"
          >
            <i class="fas fa-download" aria-hidden="true"></i>
            {{ isDownloadingZip ? 'Preparing…' : 'Download All' }}
          </button>
        </template>
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
      <p v-if="zipError" class="finalist-presentation__error" role="alert">{{ zipError }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppDataTable, { type DataTableColumn, type DataTableSort } from '@/components/AppDataTable.vue'
import SydneyDateTimeFields from '@/components/management/SydneyDateTimeFields.vue'
import {
  downloadPresentationSlidesZip,
  fetchFinalistSubmissionsClose,
  fetchPresentationSlides,
  presentationSlidesDownloadUrl,
  presentationSlidesUrl,
  saveFinalistSubmissionsClose,
  type FinalistSubmissionsClose,
  type PresentationSlidesTeam
} from '@/utils/managementAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { DATA_TABLE_ALL } from '@/utils/dataTable'
import {
  formatEventCalendarDay,
  formatShortDateTime,
  formatSydneyStatement,
  fromSydneyDateTimeInput,
  sydneyToday,
  toSydneyDateTimeInput
} from '@/utils/date'

// The closing time card: the time in force, or none while they stay open.
const close = ref<FinalistSubmissionsClose | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const isSaving = ref(false)
const confirmOpen = ref(false)

// Sydney's "YYYY-MM-DDTHH:MM": today at 23:59 until a closing time is set;
// then that time.
const closesAtLocal = ref(`${sydneyToday()}T23:59`)

// The picked time read back for the confirm dialog, in Sydney as it was picked.
const pendingLabel = computed(() => formatSydneyStatement(fromSydneyDateTimeInput(closesAtLocal.value)))

const load = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    close.value = (await fetchFinalistSubmissionsClose()).close
    if (close.value) closesAtLocal.value = toSydneyDateTimeInput(close.value.closes_at)
  } catch (err) {
    close.value = null
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

const save = async () => {
  actionError.value = ''
  isSaving.value = true
  try {
    // Sydney's time picked, sent as the instant it is.
    close.value = (await saveFinalistSubmissionsClose(fromSydneyDateTimeInput(closesAtLocal.value)!)).close
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    confirmOpen.value = false
    isSaving.value = false
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

// The teams in the order they come; nothing sorts them.
const NO_SORT: DataTableSort = { key: '', direction: 'asc' }

// Each team as a row, with plain text for search.
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

// "3/28 Submitted": the finalist teams that have handed their slides in.
const submittedCount = computed(() => slidesTeams.value.filter((team) => team.submitted).length)

const anySlides = computed(() => slidesTeams.value.some((team) => team.submitted))

const isDownloadingZip = ref(false)
const zipError = ref('')

const downloadSlides = async () => {
  isDownloadingZip.value = true
  zipError.value = ''
  try {
    await downloadPresentationSlidesZip()
  } catch (err) {
    zipError.value = `Failed to download the slides. ${apiErrorFromUnknown(err).message}`
  } finally {
    isDownloadingZip.value = false
  }
}

// "Friday, 16th October 2026".
const slidesDue = computed(() => formatEventCalendarDay(slidesDueOn.value))

// "17/10/26 23:06", as the other management tables write it.
const formatSubmitted = (iso: string | null) => (iso ? formatShortDateTime(iso) : '')

// "PDF", "PPTX" or "PPT", from the file's name.
const fileType = (name: string) => (name.includes('.') ? name.split('.').pop()!.toUpperCase() : '')

onMounted(() => {
  void load()
  void loadSlides()
})
</script>

<style scoped>
.finalist-submissions {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* The closing time card, as the Submission Deadline card. */
.finalist-close__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.finalist-close__row {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}

.finalist-close__muted {
  color: var(--text-muted);
}

.finalist-close__state--open {
  color: var(--dark-green);
  font-weight: 600;
}

.finalist-close__state--closed {
  color: var(--danger);
  font-weight: 600;
}

.finalist-close__load-error {
  color: var(--danger);
}

.finalist-close__form {
  margin-top: 1rem;
  display: flex;
  align-items: flex-end;
  gap: 1rem;
  flex-wrap: wrap;
}

.finalist-close__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0.75rem 0 0;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.finalist-close__overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.finalist-close__dialog {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  padding: 1.25rem 1.5rem;
  max-width: 26rem;
  width: 100%;
}

.finalist-close__dialog-title {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
}

.finalist-close__dialog-body {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: var(--teal);
}

.finalist-close__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

/* Finalist Submissions, as it was on Finalist Presentation. */
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

.finalist-presentation__muted {
  color: var(--text-muted);
}

.finalist-presentation__cell--strong {
  font-weight: 600;
}
</style>
