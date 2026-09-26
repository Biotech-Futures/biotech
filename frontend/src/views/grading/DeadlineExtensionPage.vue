<template>
  <div class="extensions">
    <section class="card">
      <div class="card-header">
        <h3 class="card-title">Extend Deadline</h3>
      </div>
      <p class="extensions__hint">
        Search by the group's name to extend their deadline. Times are in your local
        timezone ({{ localTimeZone }}). Students see the closing time; the server quietly
        keeps accepting for the grace hours after it.
      </p>
      <!-- Granting is the Grant button only: Enter in a field (e.g. the
           search box) must never grant an extension. -->
      <form class="extensions__form" @submit.prevent>
        <label class="extensions__field extensions__field--group">
          <span>Search</span>
          <GroupSearchInput ref="picker" v-model="groupQuery" />
        </label>
        <label class="extensions__field">
          <span>Extended until</span>
          <input
            v-model="untilLocal"
            type="datetime-local"
            :min="minLocal || undefined"
            required
            class="extensions__input"
          />
        </label>
        <label class="extensions__field">
          <span>Grace hours</span>
          <input
            v-model.number="graceHours"
            type="number"
            min="0"
            max="72"
            class="extensions__input extensions__input--grace"
          />
        </label>
        <label class="extensions__field extensions__field--reason">
          <span>Reason (optional)</span>
          <textarea
            v-model="reason"
            rows="3"
            placeholder="e.g. school closure"
            class="extensions__input extensions__input--reason"
          ></textarea>
        </label>
        <button
          type="button"
          class="btn btn-primary btn-sm"
          :disabled="isSaving || !groupQuery || !untilLocal"
          @click="save"
        >
          {{ isSaving ? 'Saving…' : 'Grant' }}
        </button>
      </form>
      <p v-if="actionError" class="extensions__banner extensions__banner--error">{{ actionError }}</p>
      <p v-if="savedMessage" class="extensions__banner extensions__banner--ok">{{ savedMessage }}</p>
    </section>

    <section class="card">
      <div class="card-header">
        <h3 class="card-title">Current Extensions</h3>
      </div>
      <p v-if="isLoading" class="extensions__hint">Loading…</p>
      <div v-else-if="loadError" class="extensions__load-error">
        <p>Failed to load. {{ loadError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
      </div>
      <div v-else class="extensions__scroll">
        <table class="extensions__table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Extension</th>
              <th>Grace</th>
              <th>Status</th>
              <th>Granted by</th>
              <th>Revoked by</th>
              <th class="extensions__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="extensions.length === 0">
              <td colspan="7" class="extensions__empty">No extensions granted.</td>
            </tr>
            <template v-for="e in extensions" :key="e.id">
              <tr :class="{ 'extensions__row--with-reason': e.reason }">
                <td class="extensions__cell--strong">{{ e.group_name }}</td>
                <td>{{ `${new Date(e.extended_until).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })} ${new Date(e.extended_until).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}` }}</td>
                <td>{{ e.grace_hours ? `+${e.grace_hours}h` : '—' }}</td>
                <td>
                  <span :class="`extensions__status--${extensionStatus(e).state}`">
                    {{ extensionStatus(e).label }}
                  </span>
                </td>
                <td>{{ e.granted_by ?? '—' }}</td>
                <td>{{ e.revoked_by ?? '—' }}</td>
                <td class="extensions__cell--right">
                  <button
                    v-if="!e.revoked_at"
                    type="button"
                    class="btn btn-outline btn-sm"
                    :disabled="isSaving"
                    @click="revoke(e.group_id)"
                  >
                    Revoke
                  </button>
                  <span v-else class="extensions__muted">Revoked</span>
                </td>
              </tr>
              <!-- The reason gets a full-width row of its own so multi-line
                   text can wrap; the pair reads as one record. -->
              <tr v-if="e.reason" class="extensions__reason-row">
                <td colspan="7">
                  <span class="extensions__muted">Reason:</span> {{ e.reason }}
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="overwriteWarning" class="extensions__overlay" @click.self="overwriteWarning = null">
      <div
        class="extensions__dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Extension already exists"
      >
        <h4 class="extensions__dialog-title">This group already has an extension</h4>
        <p class="extensions__dialog-body">
          <strong>{{ overwriteWarning.groupName }}</strong> is already extended until
          <strong>{{ overwriteWarning.until }}</strong>. Granting a new extension replaces
          the current one.
        </p>
        <div class="extensions__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="overwriteWarning = null">
            Cancel
          </button>
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="isSaving"
            @click="performSave(overwriteWarning.id)"
          >
            {{ isSaving ? 'Saving…' : 'Replace extension' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useFlashMessage } from '@/composables/useFlashMessage'
import {
  fetchGroupExtensions,
  fetchSubmissionDeadline,
  removeGroupExtension,
  saveGroupExtension,
  type GroupExtension
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { describeBrowserTimeZone } from '@/utils/date'
import GroupSearchInput from '@/components/grading/GroupSearchInput.vue'

const localTimeZone = describeBrowserTimeZone()

const extensions = ref<GroupExtension[]>([])
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const { message: savedMessage, show: flashSaved } = useFlashMessage()
const isSaving = ref(false)

const picker = ref<InstanceType<typeof GroupSearchInput> | null>(null)
const groupQuery = ref('')
// Defaults to today at 23:59 — extensions are almost always end-of-day,
// so the admin only has to adjust the date.
const defaultUntilLocal = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T23:59`
}
const untilLocal = ref(defaultUntilLocal())
const graceHours = ref(24)
const reason = ref('')

// Active until the extended date; In grace while the extension's own grace
// hours still accept; Expired after that — mirroring the deadline card.
const extensionStatus = (e: {
  extended_until: string
  grace_hours: number
  revoked_at: string | null
}) => {
  if (e.revoked_at) return { state: 'expired', label: 'Revoked' }
  const until = new Date(e.extended_until).getTime()
  const graceEnd = until + (e.grace_hours || 0) * 3_600_000
  const now = Date.now()
  if (now <= until) return { state: 'active', label: 'Active' }
  if (now <= graceEnd) return { state: 'grace', label: 'In grace' }
  return { state: 'expired', label: 'Expired' }
}

// Picker floor: the calendar refuses anything at or before the current
// deadline (an earlier "extension" would shorten the team's window). The
// server enforces the same rule as backstop.
const minLocal = ref('')

const loadDeadlineFloor = async () => {
  try {
    const deadline = (await fetchSubmissionDeadline()).deadline
    if (deadline) {
      const d = new Date(deadline.closes_at)
      const pad = (n: number) => String(n).padStart(2, '0')
      minLocal.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
    }
  } catch {
    minLocal.value = ''
  }
}

const load = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    extensions.value = (await fetchGroupExtensions()).extensions
  } catch (err) {
    extensions.value = []
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

// Warning shown when the picked group already has an active extension —
// granting again replaces it, so the admin must confirm on purpose.
const overwriteWarning = ref<{ id: number; groupName: string; until: string } | null>(null)

const save = async () => {
  actionError.value = ''
  savedMessage.value = ''
  const id = picker.value?.resolveId() ?? null
  if (id == null) {
    actionError.value = 'No group matches that name.'
    return
  }
  const existing = extensions.value.find((e) => e.group_id === id && !e.revoked_at)
  if (existing) {
    overwriteWarning.value = {
      id,
      groupName: existing.group_name,
      until: `${new Date(existing.extended_until).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })} ${new Date(existing.extended_until).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
    }
    return
  }
  await performSave(id)
}

const performSave = async (id: number) => {
  isSaving.value = true
  try {
    const iso = new Date(untilLocal.value).toISOString()
    await saveGroupExtension(id, iso, graceHours.value || 0, reason.value)
    flashSaved('Extension granted.')
    groupQuery.value = ''
    untilLocal.value = defaultUntilLocal()
    graceHours.value = 24
    reason.value = ''
    await load()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isSaving.value = false
    overwriteWarning.value = null
  }
}

const revoke = async (id: number) => {
  actionError.value = ''
  savedMessage.value = ''
  isSaving.value = true
  try {
    await removeGroupExtension(id)
    await load()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isSaving.value = false
  }
}

onMounted(() => {
  void load()
  void loadDeadlineFloor()
})
</script>

<style scoped>
.extensions {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.extensions__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.extensions__form {
  display: flex;
  align-items: flex-end;
  gap: 1rem;
  flex-wrap: wrap;
}

.extensions__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--charcoal);
}

.extensions__status--active {
  color: var(--dark-green);
  font-weight: 600;
}

/* Same yellow as the deadline card's grace state. */
.extensions__status--grace {
  color: #eab308;
  font-weight: 600;
}

.extensions__status--expired {
  color: var(--text-muted);
  font-weight: 600;
}

/* Full row of its own, below the other fields. */
.extensions__field--reason {
  flex-basis: 100%;
}

.extensions__input--reason {
  resize: vertical;
  min-height: 4.5rem;
  font-family: inherit;
}

.extensions__input {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.extensions__input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.extensions__field--group {
  width: 16rem;
}

.extensions__input--grace {
  width: 5.5rem;
}

.extensions__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0.75rem 0 0;
}

.extensions__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.extensions__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

.extensions__load-error {
  color: var(--danger);
}

.extensions__scroll {
  overflow-x: auto;
}

.extensions__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.extensions__table th,
.extensions__table td {
  padding: 0.55rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  white-space: nowrap;
}

.extensions__table thead th {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.extensions__table tbody tr:last-child td {
  border-bottom: none;
}

/* A data row followed by its reason row reads as one record: no divider
   between the pair — the border after the reason row separates records. */
.extensions__row--with-reason td {
  border-bottom: none;
}

.extensions__reason-row td {
  white-space: normal;
  font-size: 0.85rem;
  padding-top: 0;
  padding-left: 1.5rem;
}

.extensions__empty {
  text-align: center;
  color: var(--text-muted);
  padding: 1.5rem 0.75rem;
}

.extensions__cell--strong {
  font-weight: 600;
}

.extensions__table .extensions__cell--right {
  text-align: right;
}

.extensions__muted {
  color: var(--text-muted);
}

/* Replace-extension warning — same treatment as the deadline confirm. */
.extensions__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.extensions__dialog {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  padding: 1.25rem 1.5rem;
  max-width: 26rem;
  width: 100%;
}

.extensions__dialog-title {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
}

.extensions__dialog-body {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: var(--charcoal);
}

.extensions__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
