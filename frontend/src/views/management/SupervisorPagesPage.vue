<template>
  <!-- Whether supervisors see the pages everyone else does. -->
  <section class="card supervisor-pages">
    <p v-if="isLoading" class="supervisor-pages__hint">Loading…</p>

    <div v-else class="supervisor-pages__panel">
      <h3 class="supervisor-pages__title">Supervisor Visibility</h3>
      <p class="supervisor-pages__hint">
        Shows or hides Home, Groups, Events, Announcements and Resources for supervisors. While
        hidden, supervisors only see Supervisor portal pages like My Profile, My Students and My
        Groups.
      </p>

      <p
        class="supervisor-pages__state"
        :class="shown ? 'supervisor-pages__state--ok' : 'supervisor-pages__state--warn'"
      >
        <i :class="shown ? 'fas fa-eye' : 'fas fa-eye-slash'" aria-hidden="true"></i>
        {{ shown ? 'Supervisors can see these pages' : 'These pages are hidden from supervisors' }}
      </p>

      <p v-if="error" class="supervisor-pages__error">{{ error }}</p>

      <HideShowSwitch
        :on="shown"
        :disabled="isSaving"
        label="Show Home, Groups, Events, Announcements and Resources to supervisors"
        @change="onSwitch({ shown: $event })"
      />

      <!-- Their Registration page, on a row of its own. -->
      <div class="supervisor-pages__row">
        <h3 class="supervisor-pages__title">Supervisor Registration</h3>
        <p class="supervisor-pages__hint">
          Shows or hides the Registration page for supervisors. While hidden, supervisors can't
          register students.
        </p>

        <p
          class="supervisor-pages__state"
          :class="
            registrationShown ? 'supervisor-pages__state--ok' : 'supervisor-pages__state--warn'
          "
        >
          <i :class="registrationShown ? 'fas fa-eye' : 'fas fa-eye-slash'" aria-hidden="true"></i>
          {{
            registrationShown
              ? 'Supervisors can register students'
              : "Supervisors can't register students"
          }}
        </p>

        <HideShowSwitch
          :on="registrationShown"
          :disabled="isSaving"
          label="Show the Registration page to supervisors"
          @change="onSwitch({ registration_shown: $event })"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { loadSupervisorPages, setSupervisorPages, useSupervisorPages } from '@/composables/useSupervisorPages'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { saveSupervisorPages, type SupervisorPagesState } from '@/utils/managementAPI'
import HideShowSwitch from './HideShowSwitch.vue'

const { shown, registrationShown } = useSupervisorPages()
const isLoading = ref(true)
const isSaving = ref(false)
const error = ref('')

const onSwitch = async (change: Partial<SupervisorPagesState>) => {
  isSaving.value = true
  error.value = ''
  try {
    setSupervisorPages(await saveSupervisorPages(change))
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The change could not be saved.').message
  } finally {
    isSaving.value = false
  }
}

onMounted(async () => {
  await loadSupervisorPages(true)
  isLoading.value = false
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

/* The Registration page's switch, below a line. */
.supervisor-pages__row {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--border-light);
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

.supervisor-pages__error {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}
</style>
