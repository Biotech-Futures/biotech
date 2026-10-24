<template>
  <!-- Email Checks: how much QuickEmailVerification credit each key has left,
       and today's lookups. Read only: the checks themselves keep it up to date. -->
  <section class="card email-checks">
    <div class="card-header email-checks__header">
      <h3 class="card-title">Email Checks</h3>
      <button
        type="button"
        class="btn btn-outline btn-sm"
        :disabled="isLoading"
        data-test="email-checks-refresh"
        @click="load"
      >
        <i class="fas fa-rotate-right" aria-hidden="true"></i>
        {{ isLoading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>
    <p class="email-checks__hint">
      Registration checks each email address with QuickEmailVerification. It uses the free key first
      and the paid key once the free one runs out.
    </p>

    <p v-if="error" class="email-checks__error" role="alert">{{ error }}</p>
    <p v-if="credits?.sandbox" class="email-checks__notice" data-test="email-checks-sandbox">
      Checks are running against QuickEmailVerification's test service, so they don't use real credit.
    </p>

    <p v-if="!credits && isLoading" class="email-checks__hint">Loading…</p>
    <template v-else-if="credits">
      <div class="email-checks__keys">
        <article
          v-for="key in keys"
          :key="key.name"
          class="email-checks__key"
          :data-test="`email-checks-${key.name.toLowerCase()}`"
        >
          <h4 class="email-checks__key-title">{{ key.name }} key</h4>
          <p class="email-checks__key-role">{{ key.role }}</p>
          <dl class="email-checks__rows">
            <div class="email-checks__row">
              <dt>Status</dt>
              <dd :class="`email-checks__status--${key.status.tone}`">{{ key.status.text }}</dd>
            </div>
            <div class="email-checks__row">
              <dt>Credits left</dt>
              <dd>{{ key.remaining }}</dd>
            </div>
            <div class="email-checks__row">
              <dt>Last reported</dt>
              <dd>{{ key.reported }}</dd>
            </div>
            <div v-if="key.alerts" class="email-checks__row">
              <dt>Low-credit alerts</dt>
              <dd>
                <span
                  v-for="alert in key.alerts"
                  :key="alert.level"
                  class="email-checks__alert"
                  :class="{ 'is-sent': alert.sent }"
                >
                  {{ count(alert.level) }}{{ alert.sent ? ' (sent)' : '' }}
                </span>
              </dd>
            </div>
          </dl>
        </article>
      </div>

      <dl class="email-checks__rows email-checks__today" data-test="email-checks-today">
        <div class="email-checks__row">
          <dt>Lookups today</dt>
          <dd>
            {{ credits.dailyCap ? `${count(credits.lookupsToday)} of ${count(credits.dailyCap)}` : `${count(credits.lookupsToday)} (no daily limit)` }}
          </dd>
        </div>
      </dl>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchEmailCheckCredits, type EmailCheckCredits, type EmailCheckKey } from '@/utils/adminAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatShortDateTime } from '@/utils/date'

const credits = ref<EmailCheckCredits | null>(null)
const isLoading = ref(false)
const error = ref('')

const count = (value: number) => value.toLocaleString('en-AU')

// A key: set or not, out of credit (until when), or working.
const statusOf = (key: EmailCheckKey) => {
  if (!key.configured) return { text: 'Not set', tone: 'muted' }
  if (key.exhausted) {
    return { text: `Out of credit until ${formatShortDateTime(key.retryAt) || 'later'}`, tone: 'danger' }
  }
  return { text: 'Working', tone: 'ok' }
}

const describe = (name: string, role: string, key: EmailCheckKey) => ({
  name,
  role,
  status: statusOf(key),
  remaining: key.remaining == null ? 'Not reported yet' : count(key.remaining),
  reported: key.updatedAt ? formatShortDateTime(key.updatedAt) : '—'
})

// The free key, then the paid one with its alert levels, lowest first.
const keys = computed(() => {
  const data = credits.value
  if (!data) return []
  return [
    { ...describe('Free', 'Tried first.', data.free), alerts: null },
    {
      ...describe('Paid', 'Used once the free key runs out. The low-credit alerts follow it.', data.paid),
      alerts: [...data.thresholds].sort((a, b) => a - b).map((level) => ({ level, sent: data.paid.alertedThresholds.includes(level) }))
    }
  ]
})

const load = async () => {
  isLoading.value = true
  error.value = ''
  try {
    credits.value = await fetchEmailCheckCredits()
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The email check credits could not be loaded.').message
  } finally {
    isLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* Laid out as Management's other cards. */
.email-checks {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.email-checks__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.email-checks__hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

/* The two keys side by side, one under the other when there isn't room. */
.email-checks__keys {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 1rem;
}

.email-checks__key {
  padding: 1rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
}

.email-checks__key-title {
  margin: 0;
  color: var(--dark-green);
  font-size: 1rem;
}

.email-checks__key-role {
  margin: 0.2rem 0 0.6rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.email-checks__rows {
  margin: 0;
}

.email-checks__row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border-light);
}

.email-checks__row:last-child {
  border-bottom: none;
}

.email-checks__row dt {
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: 600;
}

.email-checks__row dd {
  margin: 0;
  color: var(--teal);
  text-align: right;
}

.email-checks__status--ok {
  color: var(--dark-green);
}

.email-checks__status--danger {
  color: var(--danger);
}

.email-checks__status--muted {
  color: var(--text-muted);
}

.email-checks__alert + .email-checks__alert::before {
  content: ', ';
}

.email-checks__alert.is-sent {
  color: var(--danger);
}

.email-checks__today {
  max-width: 24rem;
}

.email-checks__notice {
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  background: color-mix(in srgb, var(--warning) 14%, transparent);
  color: var(--teal);
  font-size: 0.9rem;
}

.email-checks__error {
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
  font-size: 0.9rem;
}
</style>
