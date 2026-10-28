<template>
  <!-- Checking the registration's email addresses before it's submitted: one
       line and a slim bar, just above Submit. -->
  <div class="email-check" role="status" aria-live="polite">
    <p class="email-check__text">
      <strong>Checking email addresses</strong>
      <template v-if="progress.phase === 'queued'"> · Waiting for earlier checks to finish…</template>
      <template v-else>
        · {{ progress.done }} of {{ progress.total }} checked<template v-if="remaining">
          · {{ remaining }}</template
        >
      </template>
    </p>
    <!-- No value while waiting: an indeterminate bar. -->
    <progress
      v-if="progress.phase === 'queued'"
      class="email-check__bar"
      aria-label="Waiting for earlier email checks"
    ></progress>
    <progress
      v-else
      class="email-check__bar"
      :value="progress.done"
      :max="Math.max(progress.total, 1)"
      :aria-label="`${progress.done} of ${progress.total} email addresses checked`"
    ></progress>
  </div>
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
  margin: 1.25rem 0 1rem;
}

.email-check__text {
  margin: 0 0 0.4rem;
  font-size: 0.9rem;
  color: var(--registration-muted, var(--text-muted));
}

.email-check__text strong {
  font-weight: 600;
  color: var(--registration-ink, var(--charcoal));
}

/* The site's green on a light track, in place of the browser's own bar. */
.email-check__bar {
  display: block;
  inline-size: 100%;
  block-size: 4px;
  border: 0;
  border-radius: 999px;
  overflow: hidden;
  appearance: none;
  background: var(--registration-line, var(--border-light));
}

.email-check__bar::-webkit-progress-bar {
  background: var(--registration-line, var(--border-light));
}

.email-check__bar::-webkit-progress-value {
  background: var(--registration-green, var(--dark-green));
  transition: inline-size 0.3s ease;
}

.email-check__bar::-moz-progress-bar {
  background: var(--registration-green, var(--dark-green));
}

/* Waiting: a short stretch of green moving across. */
.email-check__bar:indeterminate {
  background: linear-gradient(
      90deg,
      transparent 0 35%,
      var(--registration-green, var(--dark-green)) 35% 65%,
      transparent 65%
    )
    var(--registration-line, var(--border-light));
  background-size: 200% 100%;
  animation: email-check-slide 1.2s linear infinite;
}

.email-check__bar:indeterminate::-webkit-progress-bar {
  background: transparent;
}

.email-check__bar:indeterminate::-moz-progress-bar {
  background: transparent;
}

@keyframes email-check-slide {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: -100% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .email-check__bar:indeterminate {
    animation: none;
  }
}
</style>
