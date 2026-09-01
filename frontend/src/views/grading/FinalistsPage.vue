<template>
  <div class="finalists">
    <section class="card finalists__add">
      <h3 class="finalists__section-title">
        <i class="fas fa-star" aria-hidden="true"></i> Add finalist
      </h3>
      <p class="finalists__hint">
        Look up group IDs from the group marking page or the Django admin.
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
        <label class="finalists__notify">
          <input v-model="notify" type="checkbox" />
          Send notification email
        </label>
        <button type="submit" class="btn btn-primary btn-sm" :disabled="isMutating">
          Flag as finalist
        </button>
      </form>
      <p class="finalists__email-note">
        Email requires <code>GRADING_FINALIST_EMAIL_ENABLED=true</code> on the backend;
        otherwise the flag is set but no email is sent (safe default).
      </p>
    </section>

    <p v-if="actionError" class="finalists__banner finalists__banner--error">{{ actionError }}</p>
    <p v-if="actionMessage" class="finalists__banner finalists__banner--ok">{{ actionMessage }}</p>

    <section>
      <h3 class="finalists__section-title">Current finalists</h3>
      <p v-if="isLoading" class="finalists__hint">Loading…</p>
      <div v-else-if="loadError" class="card">
        <p class="finalists__load-error">Failed to load. {{ loadError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
      </div>
      <div v-else class="finalists__scroll">
        <table class="finalists__table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Flagged at</th>
              <th>Notified</th>
              <th class="finalists__cell--right">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="finalists.length === 0">
              <td colspan="4" class="finalists__empty">No finalists yet.</td>
            </tr>
            <tr v-for="f in finalists" :key="f.group_id">
              <td class="finalists__cell--strong">
                {{ f.group_name }} <span class="finalists__muted">#{{ f.group_id }}</span>
              </td>
              <td>{{ new Date(f.flagged_at).toLocaleString() }}</td>
              <td>
                <span v-if="f.notified" class="finalists__notified">
                  <i class="fas fa-envelope-circle-check" aria-hidden="true"></i> Sent
                </span>
                <span v-else class="finalists__muted">
                  <i class="far fa-envelope" aria-hidden="true"></i> —
                </span>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  addFinalist,
  fetchFinalists,
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
const groupId = ref('')
const notify = ref(false)

const finalists = computed(() => list.value?.finalists ?? [])

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
    await addFinalist(n, notify.value)
    groupId.value = ''
    actionMessage.value = notify.value
      ? 'Finalist flagged + notification queued.'
      : 'Finalist flagged.'
    await load()
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
  max-width: 48rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.finalists__section-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 1.05rem;
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
  width: 11rem;
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

.finalists__notify {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.9rem;
}

.finalists__email-note {
  color: var(--text-muted);
  font-size: 0.78rem;
  margin: 0.75rem 0 0;
}

.finalists__email-note code {
  background: var(--bg-light);
  border-radius: 4px;
  padding: 0.05rem 0.3rem;
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

.finalists__cell--right {
  text-align: right;
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
