<template>
  <!-- When students, mentors and supervisors see the pages admins always do:
       set as Challenge Start's date is, by a date and time. -->
  <section class="card supervisor-pages">
    <p v-if="isLoading" class="supervisor-pages__hint">Loading…</p>

    <div v-else class="supervisor-pages__panel">
      <h3 class="supervisor-pages__title">Pages Visibility</h3>
      <p class="supervisor-pages__hint">
        Shows or hides Home, Groups, Events, Announcements and Resources for students, supervisors and
        mentors. While hidden, students and mentors see their profile page and supervisors only see
        Supervisor portal pages like My Profile, Students and Groups.
      </p>

      <p
        class="supervisor-pages__state"
        :class="shown ? 'supervisor-pages__state--ok' : 'supervisor-pages__state--warn'"
        data-test="pages-visibility-state"
      >
        <i :class="shown ? 'fas fa-eye' : 'fas fa-eye-slash'" aria-hidden="true"></i>
        {{ stateText }}
      </p>

      <!-- As Challenge Start's: the date, then who last set it. -->
      <div class="supervisor-pages__saved" data-test="pages-visibility-saved">
        <p>
          Shown from:
          <strong>{{ saved.shown_from ? formatStatementTime(saved.shown_from) : 'Not set' }}</strong>
        </p>
        <p v-if="saved.set_by" class="supervisor-pages__muted" data-test="pages-visibility-set-by">
          Set by {{ saved.set_by }}
          <template v-if="saved.updated_at">on {{ formatStatementTime(saved.updated_at) }}</template>
        </p>
      </div>

      <form class="supervisor-pages__form" @submit.prevent="save">
        <label class="supervisor-pages__field">
          <span>Shown from</span>
          <AppDateTimePicker
            v-model="shownFromLocal"
            class="app-input app-input--compact"
            data-test="pages-visibility-date"
            default-time="23:59"
            clearable
          />
        </label>
        <div class="supervisor-pages__actions">
          <button type="submit" class="btn btn-primary btn-sm" :disabled="isSaving || !shownFromLocal">
            Save Date
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="isSaving || !saved.shown_from"
            @click="write(null)"
          >
            Clear Date
          </button>
        </div>
      </form>

      <p v-if="error" class="supervisor-pages__error" role="alert">{{ error }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppDateTimePicker from '@/components/AppDateTimePicker.vue'
import { setSupervisorPages, useSupervisorPages } from '@/composables/useSupervisorPages'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatStatementTime, fromLocalDateTimeInput, toLocalDateTimeInput } from '@/utils/date'
import {
  fetchSupervisorPages,
  saveSupervisorPages,
  type SupervisorPagesState,
} from '@/utils/managementAPI'

// Whether they're shown now, following the time (as the menu does).
const { shown } = useSupervisorPages()
const isLoading = ref(true)
const isSaving = ref(false)
const error = ref('')
// As the server has it, and as the picker has it (local, timezone-less).
const saved = ref<SupervisorPagesState>({ shown: false, shown_from: null })
const shownFromLocal = ref('')

const stateText = computed(() => {
  if (shown.value) return 'Students, mentors and supervisors can see these pages'
  if (saved.value.shown_from) return `Hidden until ${formatStatementTime(saved.value.shown_from)}`
  return 'Hidden: no date set'
})

// Saved or loaded: the card, and every menu in this tab, follow it.
const show = (state: SupervisorPagesState) => {
  saved.value = state
  shownFromLocal.value = toLocalDateTimeInput(state.shown_from)
  setSupervisorPages(state)
}

const write = async (shownFrom: string | null) => {
  isSaving.value = true
  error.value = ''
  try {
    show(await saveSupervisorPages({ shown_from: shownFrom }))
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The date could not be saved.').message
  } finally {
    isSaving.value = false
  }
}

const save = () => write(fromLocalDateTimeInput(shownFromLocal.value))

onMounted(async () => {
  try {
    show(await fetchSupervisorPages())
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The date could not be loaded.').message
  } finally {
    isLoading.value = false
  }
})
</script>

<style scoped>
/* Laid out as the Release Results cards. */
.supervisor-pages,
.supervisor-pages__panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.supervisor-pages__title {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0;
}

.supervisor-pages__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.supervisor-pages__state {
  font-weight: 600;
  font-size: 0.9rem;
  margin: 0;
}

.supervisor-pages__state--ok {
  color: var(--dark-green);
}

.supervisor-pages__state--warn {
  color: #eab308;
}

/* The date and who set it, the field and its buttons: as Challenge Start's. */
.supervisor-pages__saved {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}

.supervisor-pages__saved p {
  margin: 0;
}

.supervisor-pages__muted {
  color: var(--text-muted);
}

.supervisor-pages__form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem;
}

.supervisor-pages__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--teal);
}

.supervisor-pages__actions {
  display: flex;
  gap: 0.75rem;
}

.supervisor-pages__error {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}
</style>
