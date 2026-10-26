<template>
  <section id="email-verification-usage" class="analytics-card verification-usage" data-test="email-verification-usage">
    <div class="verification-heading">
      <div>
        <div class="verification-title-row">
          <span class="verification-title-icon" aria-hidden="true"><i class="fas fa-circle-check"></i></span>
          <h2>Email Verification Usage</h2>
          <span class="snapshot-badge">Balance from last verification</span>
        </div>
        <p>
          Updated after the most recent email verification. Check the QuickEmailVerification account for the live balance.
        </p>
      </div>
    </div>

    <p v-if="error" class="verification-message error" role="alert">{{ error }}</p>
    <p v-if="credits?.sandbox" class="verification-message sandbox" data-test="verification-sandbox">
      Sandbox mode is active. Test lookups do not use credits and are excluded from usage figures.
    </p>

    <div v-if="!credits && isLoading" class="verification-loading">Loading verification usage…</div>

    <template v-else-if="credits">
      <div class="verification-grid">
        <article class="verification-metric daily-metric" data-test="verification-daily">
          <span class="metric-label">Verification Requests Today</span>
          <strong :class="{ unavailable: !dailyTrackingAvailable }">
            {{ dailyTrackingAvailable ? count(credits.lookupsToday) : 'Unavailable' }}
          </strong>
          <div v-if="dailyTrackingAvailable" class="daily-progress" aria-hidden="true">
            <span :style="{ width: `${dailyPercent}%` }"></span>
          </div>
          <small v-if="dailyTrackingAvailable">
            {{ count(credits.lookupsToday) }} of {{ count(credits.dailyCap) }} configured daily limit
          </small>
          <small v-else>
            Accurate daily counting is not enabled yet. Cached and sandbox results are not real lookups.
          </small>
        </article>

        <article
          v-for="key in keys"
          :key="key.id"
          class="verification-metric key-metric"
          :data-test="`verification-${key.id}`"
        >
          <div class="key-heading">
            <span class="metric-label">{{ key.name }} Key Credits</span>
            <span class="key-status" :class="key.status.tone">{{ key.status.text }}</span>
          </div>
          <strong :class="{ unavailable: key.remaining === null }">
            {{ key.remaining === null ? 'Not reported yet' : count(key.remaining) }}
          </strong>
          <small>{{ key.reported }}</small>
          <div v-if="key.alerts.length" class="alert-thresholds">
            <span>Low-credit alerts</span>
            <b v-for="alert in key.alerts" :key="alert.level" :class="{ sent: alert.sent }">
              {{ count(alert.level) }}{{ alert.sent ? ' sent' : '' }}
            </b>
          </div>
        </article>
      </div>

      <div class="verification-note">
        <i class="fas fa-circle-info" aria-hidden="true"></i>
        <span>
          Daily history will become available after a persistent counter is recorded for each real verification request.
          The live provider balance remains available in the QuickEmailVerification account.
        </span>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { fetchEmailCheckCredits, type EmailCheckCredits, type EmailCheckKey } from '@/utils/adminAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatShortDateTime } from '@/utils/date'

const props = withDefaults(defineProps<{ refreshToken?: number }>(), {
  refreshToken: 0,
})

const credits = ref<EmailCheckCredits | null>(null)
const isLoading = ref(false)
const error = ref('')

const count = (value: number) => value.toLocaleString('en-AU')
const dailyTrackingAvailable = computed(() => (credits.value?.dailyCap ?? 0) > 0)
const dailyPercent = computed(() => {
  const data = credits.value
  if (!data?.dailyCap) return 0
  return Math.min(Math.round((data.lookupsToday / data.dailyCap) * 100), 100)
})

function statusOf(key: EmailCheckKey) {
  if (!key.configured) return { text: 'API key not configured', tone: 'muted' }
  if (key.exhausted) {
    const retry = key.retryAt ? formatShortDateTime(key.retryAt) : ''
    return { text: retry ? `Retry ${retry}` : 'Out of credits', tone: 'danger' }
  }
  return { text: 'Available', tone: 'ok' }
}

function describe(id: 'free' | 'paid', name: string, key: EmailCheckKey) {
  return {
    id,
    name,
    remaining: key.remaining,
    reported: key.updatedAt
      ? `Last reported ${formatShortDateTime(key.updatedAt)}`
      : 'No balance has been reported by the provider yet.',
    status: statusOf(key),
    alerts: [] as Array<{ level: number; sent: boolean }>,
  }
}

const keys = computed(() => {
  const data = credits.value
  if (!data) return []
  return [
    describe('free', 'Free', data.free),
    {
      ...describe('paid', 'Paid', data.paid),
      alerts: [...data.thresholds]
        .sort((a, b) => b - a)
        .map((level) => ({ level, sent: data.paid.alertedThresholds.includes(level) })),
    },
  ]
})

async function load() {
  isLoading.value = true
  error.value = ''
  try {
    credits.value = await fetchEmailCheckCredits()
  } catch (unknownError) {
    error.value = apiErrorFromUnknown(
      unknownError,
      'Email verification usage could not be loaded.',
    ).message
  } finally {
    isLoading.value = false
  }
}

onMounted(load)
watch(() => props.refreshToken, () => { void load() })
</script>

<style scoped>
.verification-usage {
  margin-bottom: 18px;
  padding: 18px;
}

.verification-heading,
.verification-title-row,
.key-heading,
.verification-note {
  display: flex;
  align-items: center;
}

.verification-heading {
  justify-content: space-between;
  gap: 20px;
}

.verification-title-row {
  flex-wrap: wrap;
  gap: 10px;
}

.verification-title-row h2 {
  margin: 0;
  color: var(--analytics-ui-heading, #0d3f40);
  font-size: 20px;
}

.verification-title-icon {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 10px;
  background: var(--analytics-ui-icon-bg, #e2f0df);
  color: var(--analytics-ui-accent, #017151);
}

.snapshot-badge,
.key-status,
.alert-thresholds b {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.snapshot-badge {
  background: #eef4f2;
  color: var(--analytics-ui-muted, #59706e);
}

.verification-heading p {
  margin: 5px 0 0 42px;
  color: var(--analytics-ui-muted, #59706e);
  font-size: 14px;
}

.verification-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.verification-metric {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--analytics-ui-border, #d7e5e1);
  border-radius: 13px;
  background: color-mix(in srgb, var(--analytics-ui-surface, #fff) 94%, #dcebdd);
}

.metric-label {
  color: var(--analytics-ui-text, #174243);
  font-size: 13px;
  font-weight: 700;
}

.verification-metric > strong {
  display: block;
  margin: 8px 0 5px;
  color: var(--analytics-ui-accent, #017151);
  font-size: 28px;
  line-height: 1.05;
}

.verification-metric > strong.unavailable {
  color: var(--analytics-ui-muted, #59706e);
  font-size: 20px;
}

.verification-metric small {
  display: block;
  min-height: 30px;
  font-size: 12px;
  color: var(--analytics-ui-muted, #59706e);
  line-height: 1.45;
}

.key-heading {
  justify-content: space-between;
  gap: 12px;
}

.key-status.ok {
  background: #ddefe2;
  color: #017151;
}

.key-status.danger,
.alert-thresholds b.sent {
  background: #f8dfd9;
  color: #a33a2b;
}

.key-status.muted {
  background: #edf1f0;
  color: #667a77;
}

.daily-progress {
  height: 8px;
  margin: 12px 0;
  overflow: hidden;
  border-radius: 999px;
  background: #e5eeeb;
}

.daily-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--analytics-ui-accent, #017151);
}

.alert-thresholds {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  color: var(--analytics-ui-muted, #59706e);
  font-size: 11px;
}

.alert-thresholds b {
  min-height: 22px;
  padding: 0 11px;
  border: 1px solid var(--analytics-ui-border, #bad7b8);
  background: #fff;
  color: var(--analytics-ui-text, #174243);
}

.verification-note {
  align-items: flex-start;
  gap: 10px;
  margin-top: 12px;
  padding: 9px 12px;
  border-radius: 12px;
  background: #f3f7f5;
  color: var(--analytics-ui-muted, #59706e);
  font-size: 12px;
  line-height: 1.45;
}

.verification-note i {
  margin-top: 3px;
  color: var(--analytics-ui-secondary, #39687b);
}

.verification-message,
.verification-loading {
  margin: 18px 0 0;
  padding: 12px 14px;
  border-radius: 12px;
  color: var(--analytics-ui-muted, #59706e);
  background: #f3f7f5;
}

.verification-message.error {
  color: #a33a2b;
  background: #fff0ed;
}

.verification-message.sandbox {
  color: #725a00;
  background: #fff7d8;
}

@media (max-width: 1000px) {
  .verification-grid {
    grid-template-columns: 1fr;
  }

}

@media (max-width: 640px) {
  .verification-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .verification-heading p {
    margin-left: 0;
  }

}
</style>
