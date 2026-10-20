<template>
  <!-- Checking the registration's email addresses before it's submitted. -->
  <section class="email-check" role="status" aria-live="polite" aria-labelledby="email-check-title">
    <h2 id="email-check-title">Checking email addresses</h2>
    <template v-if="progress.phase === 'queued'">
      <p>Waiting for earlier checks to finish…</p>
      <!-- No value: an indeterminate bar. -->
      <progress class="email-check__bar" aria-label="Waiting for earlier email checks"></progress>
    </template>
    <template v-else>
      <p>
        {{ progress.done }} of {{ progress.total }} checked<span v-if="remaining">
          · {{ remaining }}</span
        >
      </p>
      <progress
        class="email-check__bar"
        :value="progress.done"
        :max="Math.max(progress.total, 1)"
        :aria-label="`${progress.done} of ${progress.total} email addresses checked`"
      ></progress>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { formatSecondsRemaining, type EmailCheckProgress } from '@/registration/emailPrecheck'

const props = defineProps<{ progress: EmailCheckProgress }>()

const remaining = computed(() =>
  props.progress.phase === 'running' ? formatSecondsRemaining(props.progress.secondsRemaining) : '',
)
</script>

<style scoped>
.email-check {
  margin-block: 1rem;
  padding: 1rem;
  border: 1px solid var(--registration-line, #c9d3cc);
  background: var(--registration-surface, #fff);
}

.email-check h2 {
  margin: 0 0 0.5rem;
  font-size: 1.125rem;
}

.email-check p {
  margin: 0 0 0.75rem;
}

.email-check__bar {
  display: block;
  inline-size: 100%;
  block-size: 0.75rem;
}
</style>
