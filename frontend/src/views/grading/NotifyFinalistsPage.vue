<template>
  <p
    v-if="UNDER_CONSTRUCTION"
    style="background: #fff8e1; border: 1px solid #f5d97e; border-radius: 8px; color: #8a6d1a; font-size: 0.85rem; padding: 0.6rem 0.85rem; margin: 0 0 0.75rem"
  >
    <i class="fas fa-hammer" aria-hidden="true"></i>
    The backend for this page is still being built.
  </p>
  <div class="notify-finalists">
    <section class="card notify-finalists__email-section">
      <div class="card-header">
        <h3 class="card-title">Send Email Notification</h3>
      </div>
      <p class="notify-finalists__hint">
        Send a notification email to the finalist teams. Tick Notify on specific teams
        to email only those.
      </p>
      <div class="notify-finalists__email-actions">
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
      <p v-if="lastEmailed" class="notify-finalists__last-emailed">
        Last Emailed at {{ new Date(lastEmailed.notified_at!).toLocaleString() }}<template
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
              <th>ID</th>
              <th>Group</th>
              <th>Notified at</th>
              <th class="notify-finalists__cell--center">Notify</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="finalists.length === 0">
              <td colspan="4" class="notify-finalists__empty">No finalists yet.</td>
            </tr>
            <tr v-for="f in finalists" :key="f.group_id">
              <td class="notify-finalists__muted">#{{ f.group_id }}</td>
              <td class="notify-finalists__cell--strong">{{ f.group_name }}</td>
              <td>
                <span v-if="f.notified" class="notify-finalists__notified">
                  <i class="fas fa-envelope-circle-check" aria-hidden="true"></i>
                  {{ f.notified_at ? new Date(f.notified_at).toLocaleString() : 'Sent' }}
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchFinalists, notifyFinalists, type FinalistListResponse } from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

// Flip to false once the backend flow is signed off.
const UNDER_CONSTRUCTION = true

const list = ref<FinalistListResponse | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionMessage = ref('')
const sendingMode = ref<'all' | 'selected' | null>(null)

const finalists = computed(() => list.value?.finalists ?? [])

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

onMounted(load)

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

/* No divider under the heading — the hint line sits directly beneath it. */
.notify-finalists__email-section .card-header {
  border-bottom: none;
  padding-bottom: 0;
  margin-bottom: 0;
}

.notify-finalists__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
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
