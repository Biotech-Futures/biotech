<template>
  <!-- Under an email box (or a student's School), once it's left
       (registration/emailFieldCheck): its check under way, or a warning to
       correct it. Nothing to tick here: Submit asks, just above its button. A
       hard problem is the box's own error instead. -->
  <p v-if="state?.status === 'checking'" class="email-check-note email-check-note--checking" role="status">
    Checking this {{ subject }}…
  </p>
  <p v-else-if="state?.status === 'soft'" class="email-check-note email-check-note--warning" role="status">
    {{ state.message }}
  </p>
</template>

<script setup lang="ts">
import type { EmailBoxState } from '@/registration/emailFieldCheck'

withDefaults(
  defineProps<{
    state?: EmailBoxState
    /** What the box holds: an email, or a school. */
    subject?: 'email' | 'school'
  }>(),
  { state: undefined, subject: 'email' },
)
</script>

<style scoped>
/* A line under the box, as its error is: amber for a warning. */
.email-check-note {
  margin: 0.35rem 0 0;
  font-size: 0.82rem;
  line-height: 1.35;
}

.email-check-note--checking {
  color: var(--text-muted);
}

.email-check-note--warning {
  color: #b58500;
}
</style>
