<template>
  <!-- Under an email box (or a student's School), once it's left
       (registration/emailFieldCheck): its check under way, or a warning to
       correct it or confirm it. A hard problem is the box's own error instead. -->
  <p v-if="state?.status === 'checking'" class="email-check-note email-check-note--checking" role="status">
    Checking this {{ subject }}…
  </p>
  <div v-else-if="state?.status === 'soft'" class="email-check-note email-check-note--warning" role="status">
    <span>{{ state.message }}</span>
    <label v-if="confirmable" class="email-check-note__confirm">
      <input
        type="checkbox"
        :checked="confirmed"
        :data-test="`${id}-confirm`"
        @change="$emit('confirm', ($event.target as HTMLInputElement).checked)"
      />
      <span>{{ subject === 'school' ? 'Yes, this school is correct' : 'Yes, this address is correct' }}</span>
    </label>
  </div>
</template>

<script setup lang="ts">
import type { EmailBoxState } from '@/registration/emailFieldCheck'

withDefaults(
  defineProps<{
    /** The box's own id, for its tick's. */
    id: string
    state?: EmailBoxState
    confirmed?: boolean
    /** What the box holds: an email, or a school. */
    subject?: 'email' | 'school'
    /** With a tick to confirm the warning (registration's); without, it's
     *  only shown (an admin's form). */
    confirmable?: boolean
  }>(),
  { state: undefined, confirmed: false, subject: 'email', confirmable: true },
)

defineEmits<{ confirm: [confirmed: boolean] }>()
</script>

<style scoped>
.email-check-note {
  margin: 0.35rem 0 0;
  font-size: 0.875rem;
  line-height: 1.45;
}

.email-check-note--checking {
  color: var(--text-muted);
}

/* A warning: amber, as the page's other warnings are, its tick under it. */
.email-check-note--warning {
  display: grid;
  gap: 0.4rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid rgba(180, 120, 0, 0.35);
  border-radius: 6px;
  background: rgba(255, 193, 7, 0.1);
  color: var(--teal);
}

.email-check-note__confirm {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  cursor: pointer;
}

.email-check-note__confirm input {
  width: 16px;
  height: 16px;
  accent-color: var(--dark-green);
}
</style>
