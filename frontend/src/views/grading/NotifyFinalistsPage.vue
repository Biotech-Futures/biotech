<template>
  <div class="notify-finalists">
    <section class="card notify-finalists__setup">
      <div class="card-header">
        <h3 class="card-title">Notify Finalists</h3>
      </div>
      <h3 class="notify-finalists__section-title">Email Details</h3>
      <p class="notify-finalists__hint">
        These go into the finalist email. Set them before sending.
      </p>
      <p v-if="detailsError" class="notify-finalists__load-error">
        Failed to load the email details. {{ detailsError }}
      </p>
      <template v-else-if="details">
        <div class="notify-finalists__fields">
          <label v-for="field in DATE_FIELDS" :key="field.key" class="notify-finalists__field">
            <span>{{ field.label }}</span>
            <input
              v-model="form[field.key]"
              type="date"
              :min="details.today"
              :class="{ 'is-invalid': saveTried && isPast(field.key) }"
            />
          </label>
          <label class="notify-finalists__field notify-finalists__field--wide">
            <span>Registration Link</span>
            <input v-model="form.registration_url" type="url" placeholder="https://…" />
          </label>
        </div>
        <p v-if="pastDatesMessage" class="notify-finalists__field-error" role="alert">
          {{ pastDatesMessage }}
        </p>
        <div class="notify-finalists__email-actions">
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="savingDetails"
            @click="saveDetails"
          >
            {{ savingDetails ? 'Saving…' : 'Save' }}
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="loadingPreview"
            @click="openPreview"
          >
            {{ loadingPreview ? 'Loading…' : 'Preview Email' }}
          </button>
        </div>
      </template>
    </section>

    <section class="card notify-finalists__email-section">
      <h3 class="notify-finalists__section-title">Send Email Notification</h3>
      <p class="notify-finalists__hint">
        Send a notification email to the finalist teams. Tick Notify on specific teams
        to email only those.
      </p>
      <!-- Same status line as Release Marks. A team only counts as notified
           once every member got the email. -->
      <p
        v-if="finalists.length"
        class="notify-finalists__status"
        :class="allNotified ? 'notify-finalists__status--ok' : 'notify-finalists__status--warn'"
      >
        <i
          :class="allNotified ? 'fas fa-envelope-circle-check' : 'fas fa-envelope'"
          aria-hidden="true"
        ></i>
        {{ allNotified ? 'Emails are sent to every group member' : 'Emails are not sent to every group member' }}
      </p>
      <!-- A notified team is one where every member got the email. -->
      <p v-if="finalists.length" class="notify-finalists__counts">
        Students: {{ studentsEmailed }} of {{ studentsTotal }} emailed
      </p>
      <p v-if="sendBlockedReason" class="notify-finalists__blocked">{{ sendBlockedReason }}</p>
      <div class="notify-finalists__email-actions">
        <button
          type="button"
          class="btn btn-primary btn-sm"
          :disabled="sendingMode !== null || !canSend"
          @click="sendEmails('all')"
        >
          {{ sendingMode === 'all' ? 'Sending…' : 'Send Email to All Groups' }}
        </button>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          :disabled="sendingMode !== null || !canSend || selectedIds.size === 0"
          @click="sendEmails('selected')"
        >
          {{ sendingMode === 'selected' ? 'Sending…' : 'Send Email to Selected Groups' }}
        </button>
      </div>
      <p v-if="lastEmailed" class="notify-finalists__last-emailed">
        Last Emailed at
        {{ `${new Date(lastEmailed.notified_at!).toLocaleDateString('en-GB')} ${new Date(lastEmailed.notified_at!).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}` }}<template
          v-if="lastEmailed.notified_by"
        >
          by {{ lastEmailed.notified_by }}</template
        >.
      </p>
    </section>

    <p v-if="actionError" class="notify-finalists__banner notify-finalists__banner--error">
      {{ actionError }}
    </p>
    <p v-if="actionMessage" class="notify-finalists__banner notify-finalists__banner--ok">
      {{ actionMessage }}
    </p>

    <section>
      <h3 class="card-title notify-finalists__list-title">Finalist Teams</h3>
      <p v-if="isLoading" class="notify-finalists__hint">Loading…</p>
      <div v-else-if="loadError" class="card">
        <p class="notify-finalists__load-error">Failed to load. {{ loadError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
      </div>
      <div v-else class="notify-finalists__scroll">
        <table class="notify-finalists__table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Notified at</th>
              <th class="notify-finalists__cell--center">Notify</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="finalists.length === 0">
              <td colspan="3" class="notify-finalists__empty">No finalists yet.</td>
            </tr>
            <tr v-for="f in finalists" :key="f.group_id">
              <td class="notify-finalists__cell--strong">{{ f.group_name }}</td>
              <td>
                <span v-if="f.notified" class="notify-finalists__notified">
                  <i class="fas fa-envelope-circle-check" aria-hidden="true"></i>
                  {{
                    f.notified_at
                      ? `${new Date(f.notified_at).toLocaleDateString('en-GB')} ${new Date(f.notified_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
                      : 'Sent'
                  }}
                </span>
                <span v-else class="notify-finalists__muted">—</span>
              </td>
              <td class="notify-finalists__cell--center">
                <input
                  type="checkbox"
                  class="notify-finalists__checkbox"
                  :checked="selectedIds.has(f.group_id)"
                  :disabled="f.notified"
                  :aria-label="`Notify ${f.group_name} by email`"
                  @change="toggleSelected(f.group_id)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="pendingSendMode" class="notify-finalists__overlay" @click.self="pendingSendMode = null">
        <div
          class="notify-finalists__dialog"
          role="dialog"
          aria-modal="true"
          aria-label="Send notification emails"
        >
          <h3 class="notify-finalists__dialog-title">
            <i class="fas fa-envelope" aria-hidden="true"></i> Send notification emails?
          </h3>
          <p class="notify-finalists__dialog-text">{{ confirmText }}</p>
          <div class="notify-finalists__dialog-actions">
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="sendingMode !== null"
              @click="pendingSendMode = null"
            >
              Cancel
            </button>
            <button
              type="button"
              class="btn btn-primary btn-sm"
              :disabled="sendingMode !== null"
              @click="confirmSend"
            >
              {{ sendingMode !== null ? 'Sending…' : 'Send' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="preview" class="notify-finalists__overlay" @click.self="preview = null">
        <div
          class="notify-finalists__dialog notify-finalists__dialog--preview"
          role="dialog"
          aria-modal="true"
          aria-label="Email preview"
        >
          <h3 class="notify-finalists__dialog-title">
            <i class="fas fa-envelope-open-text" aria-hidden="true"></i> {{ preview.subject }}
          </h3>
          <p class="notify-finalists__dialog-text">
            As the members of {{ preview.group_name }} would get it. Nothing has been sent.
          </p>
          <!-- The frame is as tall as the email and this box scrolls, like
               any page section; scrolling inside a frame in a pop-up is
               unreliable across browsers. sandbox without allow-scripts: the
               email is shown, never run, and its links stay inert;
               allow-same-origin only lets fitPreview measure its height. -->
          <div class="notify-finalists__preview-body">
            <iframe
              class="notify-finalists__preview-frame"
              :srcdoc="preview.html"
              title="Email preview"
              sandbox="allow-same-origin"
              scrolling="no"
              @load="fitPreview"
            ></iframe>
          </div>
          <div class="notify-finalists__dialog-actions">
            <button type="button" class="btn btn-outline btn-sm" @click="preview = null">
              Close
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useFlashMessage } from '@/composables/useFlashMessage'
import {
  fetchFinalistEmailDetails,
  fetchFinalists,
  notifyFinalists,
  previewFinalistEmail,
  updateFinalistEmailDetails,
  type FinalistEmailDetails,
  type FinalistEmailFields,
  type FinalistEmailPreview,
  type FinalistListResponse
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const list = ref<FinalistListResponse | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const { message: actionMessage, show: flashAction } = useFlashMessage()
const sendingMode = ref<'all' | 'selected' | null>(null)

const finalists = computed(() => list.value?.finalists ?? [])
const allNotified = computed(() => finalists.value.every((f) => f.notified))
const studentsTotal = computed(() => finalists.value.reduce((n, f) => n + f.students, 0))
const studentsEmailed = computed(() =>
  finalists.value.reduce((n, f) => n + (f.notified ? f.students : 0), 0)
)

// Teams ticked in the Notify column. Empty selection = email all un-notified.
const selectedIds = ref(new Set<number>())

const toggleSelected = (id: number) => {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

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

// The finalist email's details: saved values, and the form being edited.
const DATE_FIELDS = [
  { key: 'symposium_date', label: 'Symposium Date' },
  { key: 'confirm_by', label: 'Confirm Attendance By' },
  { key: 'slides_due', label: 'Slides Due' }
] as const
type DateField = (typeof DATE_FIELDS)[number]['key']

const details = ref<FinalistEmailDetails | null>(null)
const detailsError = ref('')
const savingDetails = ref(false)
const form = ref({ symposium_date: '', confirm_by: '', slides_due: '', registration_url: '' })

const showDetails = (d: FinalistEmailDetails) => {
  details.value = d
  form.value = {
    symposium_date: d.symposium_date ?? '',
    confirm_by: d.confirm_by ?? '',
    slides_due: d.slides_due ?? '',
    registration_url: d.registration_url ?? ''
  }
}

// The form as the API takes it: a blank date is no date.
const formFields = (): FinalistEmailFields => ({
  symposium_date: form.value.symposium_date || null,
  confirm_by: form.value.confirm_by || null,
  slides_due: form.value.slides_due || null,
  registration_url: form.value.registration_url.trim()
})

const detailsChanged = computed(() => {
  const d = details.value
  if (!d) return false
  const f = formFields()
  return (
    f.symposium_date !== d.symposium_date ||
    f.confirm_by !== d.confirm_by ||
    f.slides_due !== d.slides_due ||
    f.registration_url !== (d.registration_url ?? '')
  )
})

// A date before today (the server's, in Sydney). ISO dates compare as text.
const isPast = (key: DateField) => {
  const value = form.value[key]
  return Boolean(value && details.value && value < details.value.today)
}

// Dates before today are only pointed out once Save is pressed: then they
// stop the save, get a red border, and are named above the Save button.
const saveTried = ref(false)
const pastDates = computed(() => DATE_FIELDS.filter(({ key }) => isPast(key)))
const pastDatesMessage = computed(() => {
  if (!saveTried.value || !pastDates.value.length) return ''
  const labels = pastDates.value.map((f) => f.label)
  const named =
    labels.length === 1
      ? labels[0]
      : `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`
  return `${named} can't be before today.`
})

const loadDetails = async () => {
  detailsError.value = ''
  try {
    showDetails(await fetchFinalistEmailDetails())
  } catch (err) {
    detailsError.value = apiErrorFromUnknown(err).message
  }
}

const saveDetails = async () => {
  actionMessage.value = ''
  actionError.value = ''
  saveTried.value = true
  if (pastDates.value.length) return
  savingDetails.value = true
  try {
    showDetails(await updateFinalistEmailDetails(formFields()))
    saveTried.value = false
    flashAction('Email details saved.')
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    savingDetails.value = false
  }
}

// Why the Send buttons are off, if they are; empty when sending is allowed.
const sendBlockedReason = computed(() => {
  if (detailsError.value) return 'The email details could not be loaded.'
  const d = details.value
  if (!d) return ''
  if (detailsChanged.value) return 'Save the email details before sending.'
  if (!d.complete) return 'Fill in and save every email detail above before sending.'
  if (d.dates_in_past.length) {
    return 'Some email dates are before today. Update and save them before sending.'
  }
  return ''
})
const canSend = computed(() => details.value !== null && !sendBlockedReason.value)

// The email exactly as a finalist would get it, for the details as typed.
const preview = ref<FinalistEmailPreview | null>(null)
const loadingPreview = ref(false)

// Grow the frame to the whole email, so only the dialog's box scrolls.
const fitPreview = (event: Event) => {
  const frame = event.target as HTMLIFrameElement
  const page = frame.contentDocument?.documentElement
  if (page) frame.style.height = `${page.scrollHeight}px`
}

const openPreview = async () => {
  actionError.value = ''
  loadingPreview.value = true
  try {
    preview.value = await previewFinalistEmail(formFields())
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    loadingPreview.value = false
  }
}

onMounted(() => {
  void load()
  void loadDetails()
})

// The most recent successful email send across all finalists.
const lastEmailed = computed(() => {
  const rows = finalists.value.filter((f) => f.notified_at)
  if (rows.length === 0) return null
  return rows.reduce((a, b) => (a.notified_at! > b.notified_at! ? a : b))
})

// Which send is awaiting confirmation in the dialog; null = dialog closed.
const pendingSendMode = ref<'all' | 'selected' | null>(null)

const confirmText = computed(() => {
  if (pendingSendMode.value === 'all') {
    return 'This will send the notification email to every finalist team that has not been notified yet.'
  }
  const count = selectedIds.value.size
  return `This will send the notification email to the ${count} selected ${count === 1 ? 'team' : 'teams'}.`
})

const sendEmails = (mode: 'all' | 'selected') => {
  if (mode === 'selected' && selectedIds.value.size === 0) return
  pendingSendMode.value = mode
}

const confirmSend = async () => {
  const mode = pendingSendMode.value
  if (!mode) return
  actionMessage.value = ''
  actionError.value = ''
  sendingMode.value = mode
  try {
    const result = await notifyFinalists(mode === 'selected' ? [...selectedIds.value] : undefined)
    flashAction(
      result.sent > 0
        ? `Sent ${result.sent} notification ${result.sent === 1 ? 'email' : 'emails'}.`
        : 'No emails sent — every finalist team is already notified or has no members to email.'
    )
    selectedIds.value = new Set()
    await load()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    sendingMode.value = null
    pendingSendMode.value = null
  }
}
</script>

<style scoped>
.notify-finalists {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.notify-finalists__email-section {
  max-width: 48rem;
}

/* Laid out like Document Setup: the page title over a divider, then a
   section heading ("Directors" there, "Email Details" here). */
.notify-finalists__setup {
  max-width: 48rem;
}

.notify-finalists__section-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.notify-finalists__fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.85rem 1rem;
  margin-bottom: 1rem;
  /* A field's error line mustn't stretch its neighbours' boxes. */
  align-items: start;
}

.notify-finalists__field {
  display: grid;
  gap: 0.3rem;
  font-size: 0.9rem;
}

.notify-finalists__field > span {
  color: var(--text-muted);
}

.notify-finalists__field input.is-invalid {
  border-color: var(--danger);
}

/* Above the Save button, once Save found a date before today. */
.notify-finalists__field-error {
  color: var(--danger);
  font-size: 0.85rem;
  margin: 0 0 0.75rem;
}

/* Same boxes as Document Setup's text fields. */
.notify-finalists__field input {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.notify-finalists__field input:focus {
  outline: none;
  border-color: var(--dark-green);
}

/* A web address needs the whole row. */
.notify-finalists__field--wide {
  grid-column: 1 / -1;
}

.notify-finalists__blocked {
  color: #b8860b;
  font-size: 0.85rem;
  margin: 0 0 0.75rem;
}

/* Wider than the confirm dialog; two classes so it wins over that rule. */
.notify-finalists__dialog.notify-finalists__dialog--preview {
  max-width: 44rem;
  /* Always fits the window; the email box below takes what is left. */
  max-height: calc(100vh - 2rem);
}

.notify-finalists__preview-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  /* Scrolling stops at the box's edge instead of moving the page behind. */
  overscroll-behavior: contain;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #eef0ee;
}

/* Its height is set to the email's own once loaded (fitPreview). */
.notify-finalists__preview-frame {
  display: block;
  width: 100%;
  height: 60vh;
  border: 0;
}

.notify-finalists__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

/* As the Release Marks status line. */
.notify-finalists__status {
  font-weight: 600;
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

.notify-finalists__status--ok {
  color: var(--dark-green);
}

.notify-finalists__status--warn {
  color: #eab308;
}

/* The size of the hint lines. */
.notify-finalists__counts {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

.notify-finalists__email-actions {
  display: flex;
  gap: 1.25rem;
}

.notify-finalists__last-emailed {
  color: var(--text-muted);
  font-size: 0.85rem;
  font-style: normal;
  margin: 1rem 0 0;
}

.notify-finalists__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.notify-finalists__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.notify-finalists__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

.notify-finalists__list-title {
  margin-bottom: 0.5rem;
}

.notify-finalists__load-error {
  margin: 0 0 0.5rem;
}

.notify-finalists__scroll {
  overflow-x: auto;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-elevated);
}

.notify-finalists__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.notify-finalists__table th,
.notify-finalists__table td {
  padding: 0.55rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  white-space: nowrap;
}

.notify-finalists__table thead th {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.notify-finalists__table tbody tr:last-child td {
  border-bottom: none;
}

.notify-finalists__empty {
  text-align: center;
  color: var(--text-muted);
  padding: 1.5rem 0.75rem;
}

.notify-finalists__cell--strong {
  font-weight: 600;
}

.notify-finalists__table .notify-finalists__cell--center {
  text-align: center;
}

.notify-finalists__checkbox {
  width: 1.25rem;
  height: 1.25rem;
  accent-color: var(--dark-green);
  cursor: pointer;
  vertical-align: middle;
}

.notify-finalists__checkbox:disabled {
  cursor: not-allowed;
}

.notify-finalists__muted {
  color: var(--text-muted);
}

.notify-finalists__notified {
  color: var(--dark-green);
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.notify-finalists__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.notify-finalists__dialog {
  background: var(--surface-elevated);
  color: var(--charcoal);
  border-radius: 10px;
  box-shadow: 0 10px 40px var(--shadow);
  width: 100%;
  max-width: 26rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.notify-finalists__dialog-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
  margin: 0;
}

.notify-finalists__dialog-title i {
  color: var(--dark-green);
}

.notify-finalists__dialog-text {
  color: var(--text-muted);
  font-size: 0.92rem;
  margin: 0;
}

.notify-finalists__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
