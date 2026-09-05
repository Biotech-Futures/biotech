<template>
  <div class="deadline">
    <section class="card deadline__status-card">
      <div class="card-header">
        <h3 class="card-title">Current Deadline</h3>
      </div>

      <p v-if="isLoading" class="deadline__hint">Loading…</p>

      <div v-else-if="loadError" class="deadline__load-error">
        <p>Failed to load. {{ loadError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
      </div>

      <template v-else>
        <p v-if="!deadline" class="deadline__closed">
          <i class="fas fa-lock" aria-hidden="true"></i>
          No deadline set — submissions are <strong>closed</strong>. Students can view the
          submission page but cannot save or submit until a deadline exists.
        </p>
        <template v-else>
          <p class="deadline__row" :class="deadline.is_open ? 'deadline__state--open' : 'deadline__state--closed'">
            <i :class="deadline.is_open ? 'fas fa-lock-open' : 'fas fa-lock'" aria-hidden="true"></i>
            {{ deadline.is_open ? 'Submissions open' : 'Submissions closed' }}
          </p>
          <p class="deadline__row">
            Closes: <strong>{{ new Date(deadline.closes_at).toLocaleString() }}</strong>
            <span v-if="deadline.grace_hours" class="deadline__muted">
              (+ {{ deadline.grace_hours }}h quiet grace)
            </span>
          </p>
          <p v-if="deadline.set_by" class="deadline__row deadline__muted">
            Set by {{ deadline.set_by }}
            <template v-if="deadline.created_at">
              on {{ new Date(deadline.created_at).toLocaleString() }}
            </template>
          </p>
        </template>
      </template>
    </section>

    <section class="card deadline__form-card">
      <div class="card-header">
        <h3 class="card-title">{{ deadline ? 'Change Deadline' : 'Set Deadline' }}</h3>
      </div>
      <p class="deadline__hint">
        Times are in your local timezone. Students see the closing time; the server quietly
        keeps accepting for the grace hours after it.
      </p>

      <form class="deadline__form" @submit.prevent="confirmOpen = true">
        <label class="deadline__field">
          <span>Closes at</span>
          <input v-model="closesAtLocal" type="datetime-local" required class="deadline__input" />
        </label>
        <label class="deadline__field">
          <span>Grace hours</span>
          <input
            v-model.number="graceHours"
            type="number"
            min="0"
            max="72"
            class="deadline__input deadline__input--narrow"
          />
        </label>
        <button type="submit" class="btn btn-primary btn-sm" :disabled="isSaving || !closesAtLocal">
          {{ isSaving ? 'Saving…' : 'Save Deadline' }}
        </button>
      </form>

      <p v-if="actionError" class="deadline__banner deadline__banner--error">{{ actionError }}</p>
      <p v-if="savedMessage" class="deadline__banner deadline__banner--ok">{{ savedMessage }}</p>
    </section>

    <div v-if="confirmOpen" class="deadline__overlay" @click.self="confirmOpen = false">
      <div class="deadline__dialog" role="dialog" aria-modal="true" aria-label="Confirm deadline">
        <h4 class="deadline__dialog-title">
          {{ deadline ? 'Change the submission deadline?' : 'Set the submission deadline?' }}
        </h4>
        <p class="deadline__dialog-body">
          Submissions will close on
          <strong>{{ pendingLabel }}</strong>
          <template v-if="graceHours"> (+ {{ graceHours }}h quiet grace)</template>.
          Students see the new closing time immediately.
        </p>
        <div class="deadline__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="confirmOpen = false">
            Cancel
          </button>
          <button type="button" class="btn btn-primary btn-sm" :disabled="isSaving" @click="save">
            {{ isSaving ? 'Saving…' : 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  fetchSubmissionDeadline,
  saveSubmissionDeadline,
  type SubmissionDeadline
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const deadline = ref<SubmissionDeadline | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const savedMessage = ref('')
const isSaving = ref(false)

const closesAtLocal = ref('')
const graceHours = ref(0)
const confirmOpen = ref(false)

// Human-readable version of the picked time, for the confirm dialog.
const pendingLabel = computed(() =>
  closesAtLocal.value ? new Date(closesAtLocal.value).toLocaleString() : ''
)

const load = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    deadline.value = (await fetchSubmissionDeadline()).deadline
    if (deadline.value) {
      graceHours.value = deadline.value.grace_hours
      // Pre-fill the picker with the current closing time, in local time.
      const d = new Date(deadline.value.closes_at)
      const pad = (n: number) => String(n).padStart(2, '0')
      closesAtLocal.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
    }
  } catch (err) {
    deadline.value = null
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
    // datetime-local is timezone-less; Date() reads it as local time and
    // toISOString() converts to the UTC instant the server stores.
    const iso = new Date(closesAtLocal.value).toISOString()
    deadline.value = (await saveSubmissionDeadline(iso, graceHours.value || 0)).deadline
    savedMessage.value = 'Deadline saved.'
    confirmOpen.value = false
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
    confirmOpen.value = false
  } finally {
    isSaving.value = false
  }
}

onMounted(() => void load())
</script>

<style scoped>
.deadline {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 48rem;
}

.deadline__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.deadline__row {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}

.deadline__muted {
  color: var(--text-muted);
}

.deadline__closed {
  margin: 0;
  font-size: 0.95rem;
}

.deadline__state--open {
  color: var(--dark-green);
  font-weight: 600;
}

.deadline__state--closed {
  color: var(--danger);
  font-weight: 600;
}

.deadline__form {
  display: flex;
  align-items: flex-end;
  gap: 1rem;
  flex-wrap: wrap;
}

.deadline__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--charcoal);
}

.deadline__input {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.deadline__input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.deadline__input--narrow {
  width: 7rem;
}

.deadline__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0.75rem 0 0;
}

.deadline__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.deadline__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

.deadline__load-error {
  color: var(--danger);
}

.deadline__overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.deadline__dialog {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  padding: 1.25rem 1.5rem;
  max-width: 26rem;
  width: 100%;
}

.deadline__dialog-title {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
}

.deadline__dialog-body {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: var(--charcoal);
}

.deadline__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
