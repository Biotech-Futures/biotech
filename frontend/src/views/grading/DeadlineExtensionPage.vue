<template>
  <div class="extensions">
    <section class="card">
      <div class="card-header">
        <h3 class="card-title">Extend Deadline</h3>
      </div>
      <p class="extensions__hint">
        Enter the group's ID to extend their deadline. Times are in your local timezone.
      </p>
      <form class="extensions__form" @submit.prevent="save">
        <label class="extensions__field">
          <span>Group ID</span>
          <input
            v-model="groupId"
            type="number"
            min="1"
            required
            class="extensions__input extensions__input--narrow"
          />
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
        <label class="extensions__field extensions__field--grow">
          <span>Reason (optional)</span>
          <input
            v-model="reason"
            type="text"
            placeholder="e.g. school closure"
            class="extensions__input"
          />
        </label>
        <button
          type="submit"
          class="btn btn-primary btn-sm"
          :disabled="isSaving || !groupId || !untilLocal"
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
              <th>ID</th>
              <th>Group</th>
              <th>Extended until</th>
              <th>Reason</th>
              <th>Granted by</th>
              <th class="extensions__cell--right"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="extensions.length === 0">
              <td colspan="6" class="extensions__empty">No extensions granted.</td>
            </tr>
            <tr v-for="e in extensions" :key="e.group_id">
              <td class="extensions__muted">#{{ e.group_id }}</td>
              <td class="extensions__cell--strong">{{ e.group_name }}</td>
              <td>{{ new Date(e.extended_until).toLocaleString() }}</td>
              <td>{{ e.reason || '—' }}</td>
              <td>{{ e.granted_by ?? '—' }}</td>
              <td class="extensions__cell--right">
                <button
                  type="button"
                  class="btn btn-outline btn-sm"
                  :disabled="isSaving"
                  @click="revoke(e.group_id)"
                >
                  Revoke
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
import { onMounted, ref } from 'vue'
import {
  fetchGroupExtensions,
  fetchSubmissionDeadline,
  removeGroupExtension,
  saveGroupExtension,
  type GroupExtension
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const extensions = ref<GroupExtension[]>([])
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const savedMessage = ref('')
const isSaving = ref(false)

const groupId = ref('')
const untilLocal = ref('')
const reason = ref('')

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

const save = async () => {
  actionError.value = ''
  savedMessage.value = ''
  isSaving.value = true
  try {
    const iso = new Date(untilLocal.value).toISOString()
    await saveGroupExtension(Number(groupId.value), iso, reason.value)
    savedMessage.value = 'Extension granted.'
    groupId.value = ''
    untilLocal.value = ''
    reason.value = ''
    await load()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isSaving.value = false
  }
}

const revoke = async (id: number) => {
  actionError.value = ''
  savedMessage.value = ''
  isSaving.value = true
  try {
    await removeGroupExtension(id)
    savedMessage.value = 'Extension revoked.'
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

.extensions__field--grow {
  flex: 1;
  min-width: 14rem;
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

.extensions__input--narrow {
  width: 7rem;
}

/* Hide the native number spinners — IDs are typed, not stepped. */
.extensions__input--narrow {
  appearance: textfield;
  -moz-appearance: textfield;
}

.extensions__input--narrow::-webkit-inner-spin-button,
.extensions__input--narrow::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
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
</style>
