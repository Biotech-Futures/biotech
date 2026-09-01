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
      <h3 class="card-title finalists__list-title">Current Finalists</h3>
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
              <th>Notified</th>
              <th class="finalists__cell--center">Notify</th>
              <th class="finalists__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="finalists.length === 0">
              <td colspan="7" class="finalists__empty">No finalists yet.</td>
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
              <td class="finalists__cell--center">
                <input
                  type="checkbox"
                  class="finalists__notify-checkbox"
                  :checked="selectedIds.has(f.group_id)"
                  :disabled="f.notified"
                  :aria-label="`Notify ${f.group_name} by email`"
                  @change="toggleSelected(f.group_id)"
                />
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
    </section>

    <section class="card finalists__email-section">
      <div class="card-header">
        <h3 class="card-title">Send Email Notification</h3>
      </div>
      <p class="finalists__hint">
        Send a notification email to the finalist teams. Tick Notify on specific teams
        to email only those.
      </p>
      <div class="finalists__email-actions">
        <button
          type="button"
          class="btn btn-primary btn-sm"
          :disabled="sendingMode !== null"
          @click="sendEmails('all')"
        >
          {{ sendingMode === 'all' ? 'Sending…' : 'Send Email to All Groups' }}
        </button>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          :disabled="sendingMode !== null || selectedIds.size === 0"
          @click="sendEmails('selected')"
        >
          {{ sendingMode === 'selected' ? 'Sending…' : 'Send Email to Selected Groups' }}
        </button>
      </div>
      <p v-if="lastEmailed" class="finalists__last-emailed">
        Last Emailed at {{ new Date(lastEmailed.notified_at!).toLocaleString() }}<template
          v-if="lastEmailed.notified_by"
        >
          by {{ lastEmailed.notified_by }}</template
        >.
      </p>
    </section>

    <Teleport to="body">
      <div v-if="pendingSendMode" class="finalists__overlay" @click.self="pendingSendMode = null">
        <div
          class="finalists__dialog"
          role="dialog"
          aria-modal="true"
          aria-label="Send notification emails"
        >
          <h3 class="finalists__dialog-title">
            <i class="fas fa-envelope" aria-hidden="true"></i> Send notification emails?
          </h3>
          <p class="finalists__dialog-text">{{ confirmText }}</p>
          <div class="finalists__dialog-actions">
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  addFinalist,
  fetchFinalists,
  notifyFinalists,
  removeFinalist,
  type FinalistListResponse
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const list = ref<FinalistListResponse | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionMessage = ref('')
const isMutating = ref(false)
const sendingMode = ref<'all' | 'selected' | null>(null)
const groupId = ref('')

const finalists = computed(() => list.value?.finalists ?? [])

// Teams ticked in the Select column. Empty selection = email all un-notified.
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

onMounted(load)

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
    await load()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isMutating.value = false
  }
}

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
    actionMessage.value =
      result.sent > 0
        ? `Sent ${result.sent} notification ${result.sent === 1 ? 'email' : 'emails'}.`
        : 'No emails sent — every finalist team is already notified, or email is disabled on the backend.'
    selectedIds.value = new Set()
    await load()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    sendingMode.value = null
    pendingSendMode.value = null
  }
}

const remove = async (id: number) => {
  actionMessage.value = ''
  actionError.value = ''
  isMutating.value = true
  try {
    await removeFinalist(id)
    actionMessage.value = 'Finalist removed.'
    await load()
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

.finalists__email-actions {
  display: flex;
  gap: 1.25rem;
}

.finalists__last-emailed {
  color: var(--text-muted);
  font-size: 0.85rem;
  font-style: normal;
  margin: 1rem 0 0;
}

.finalists__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.finalists__dialog {
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

.finalists__dialog-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
  margin: 0;
}

.finalists__dialog-title i {
  color: var(--dark-green);
}

.finalists__dialog-text {
  color: var(--text-muted);
  font-size: 0.92rem;
  margin: 0;
}

.finalists__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

/* Only the finalists table runs full width; the two cards stay compact. */
.finalists__add,
.finalists__email-section {
  max-width: 48rem;
}

/* No divider under the heading — the hint line sits directly beneath it. */
.finalists__email-section .card-header {
  border-bottom: none;
  padding-bottom: 0;
  margin-bottom: 0;
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

.finalists__table .finalists__cell--center {
  text-align: center;
}

.finalists__notify-checkbox {
  width: 1.25rem;
  height: 1.25rem;
  accent-color: var(--dark-green);
  cursor: pointer;
  vertical-align: middle;
}

.finalists__notify-checkbox:disabled {
  cursor: not-allowed;
}

.finalists__muted {
  color: var(--text-muted);
  font-weight: 400;
}

.finalists__notified {
  color: var(--dark-green);
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
</style>
