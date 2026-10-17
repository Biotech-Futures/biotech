<template>
  <!-- Whether registration is open to the public. -->
  <section class="card registration-open">
    <p v-if="isLoading" class="registration-open__hint">Loading…</p>

    <div v-else class="registration-open__panel">
      <h3 class="registration-open__title">Registration Portal</h3>
      <p class="registration-open__hint">
        Opens or closes registration. While closed, the sign-in page has no Register now button
        and students can't register themselves. A late link still works.
      </p>

      <p
        class="registration-open__state"
        :class="open ? 'registration-open__state--ok' : 'registration-open__state--warn'"
      >
        <i :class="open ? 'fas fa-door-open' : 'fas fa-door-closed'" aria-hidden="true"></i>
        {{ open ? 'Registration is open' : 'Registration is closed' }}
      </p>

      <p v-if="error" class="registration-open__error">{{ error }}</p>

      <HideShowSwitch
        :on="open"
        :disabled="isSaving"
        label="Show the Register now button on the sign-in page"
        @change="onSwitch"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  loadRegistrationOpen,
  setRegistrationOpen,
  useRegistrationOpen,
} from '@/composables/useRegistrationOpen'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { saveRegistrationOpen } from '@/utils/managementAPI'
import HideShowSwitch from './HideShowSwitch.vue'

const { open } = useRegistrationOpen()
const isLoading = ref(true)
const isSaving = ref(false)
const error = ref('')

const onSwitch = async (wanted: boolean) => {
  isSaving.value = true
  error.value = ''
  try {
    setRegistrationOpen((await saveRegistrationOpen(wanted)).open)
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The change could not be saved.').message
  } finally {
    isSaving.value = false
  }
}

onMounted(async () => {
  await loadRegistrationOpen(true)
  isLoading.value = false
})
</script>

<style scoped>
/* Laid out as the Supervisor Visibility card. */
.registration-open,
.registration-open__panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.registration-open__title {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0;
}

.registration-open__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.registration-open__state {
  font-weight: 600;
  font-size: 0.9rem;
  margin: 0;
}

.registration-open__state--ok {
  color: var(--dark-green);
}

.registration-open__state--warn {
  color: #eab308;
}

.registration-open__error {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}
</style>
