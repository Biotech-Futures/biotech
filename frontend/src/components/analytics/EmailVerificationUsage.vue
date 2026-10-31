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

    <div v-if="!credits && !usage && isLoading" class="verification-loading">Loading verification usage…</div>

    <template v-else-if="credits || usage">
      <div class="verification-grid">
        <article class="verification-metric daily-metric" data-test="verification-daily">
          <span class="metric-label">Verification Requests Today</span>
          <strong :class="{ unavailable: !usage }">
            {{ usage ? count(todayUsage.requests) : 'Unavailable' }}
          </strong>
          <div v-if="usage && configuredDailyCap" class="daily-progress" aria-hidden="true">
            <span :style="{ width: `${dailyPercent}%` }"></span>
          </div>
          <small v-if="usage && configuredDailyCap">
            {{ count(todayUsage.requests) }} of {{ count(configuredDailyCap) }} configured daily limit
          </small>
          <small v-else-if="usage">
            {{ count(todayUsage.free) }} free · {{ count(todayUsage.paid) }} paid ·
            {{ count(todayUsage.credits) }} credits used (UTC)
          </small>
          <small v-else>
            Daily request history could not be loaded.
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

      <section v-if="usage" class="verification-history" data-test="verification-history">
        <div class="history-heading">
          <div>
            <h3>Daily Verification Requests</h3>
            <p>{{ historyRangeLabel }}</p>
          </div>
          <div class="history-summary" aria-label="Request history totals">
            <span><b>{{ count(usage.totals.requests) }}</b> requests</span>
            <span><b>{{ count(usage.totals.credits) }}</b> credits used</span>
          </div>
        </div>

        <div class="history-legend" aria-hidden="true">
          <span><i class="free"></i>Free key</span>
          <span><i class="paid"></i>Paid key</span>
        </div>

        <div class="history-chart" role="img" :aria-label="historyAriaLabel">
          <div
            v-for="day in historyDays"
            :key="day.date"
            class="history-column"
            :title="day.tooltip"
          >
            <span class="history-value">{{ day.requests || '' }}</span>
            <div class="history-bar-track">
              <span
                v-if="day.free"
                class="history-bar free"
                :style="{ height: `${day.freeHeight}%` }"
              ></span>
              <span
                v-if="day.paid"
                class="history-bar paid"
                :style="{ height: `${day.paidHeight}%` }"
              ></span>
            </div>
            <span class="history-date">{{ day.label }}</span>
          </div>
        </div>
      </section>

      <div class="verification-note">
        <i class="fas fa-circle-info" aria-hidden="true"></i>
        <span>
          Daily history starts when request logging was enabled; earlier usage cannot be reconstructed.
          Cached answers and sandbox requests are excluded. Provider balances are last-reported values, not live balances.
        </span>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import {
  fetchEmailCheckCredits,
  fetchEmailVerificationRequests,
  type EmailCheckCredits,
  type EmailCheckKey,
  type EmailVerificationRequestUsage,
} from '@/utils/adminAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatShortDateTime } from '@/utils/date'

const props = withDefaults(defineProps<{ refreshToken?: number }>(), {
  refreshToken: 0,
})

const credits = ref<EmailCheckCredits | null>(null)
const usage = ref<EmailVerificationRequestUsage | null>(null)
const isLoading = ref(false)
const error = ref('')

const count = (value: number) => value.toLocaleString('en-AU')
const configuredDailyCap = computed(() => credits.value?.dailyCap ?? 0)

function utcDay(date: Date) {
  return date.toISOString().slice(0, 10)
}

function requestRange() {
  const toDate = new Date()
  const fromDate = new Date(toDate)
  fromDate.setUTCDate(fromDate.getUTCDate() - 29)
  return { from: utcDay(fromDate), to: utcDay(toDate) }
}

type AggregatedDay = {
  date: string
  requests: number
  credits: number
  free: number
  paid: number
}

const usageByDate = computed(() => {
  const dates = new Map<string, AggregatedDay>()
  for (const row of usage.value?.days ?? []) {
    const day = dates.get(row.date) ?? { date: row.date, requests: 0, credits: 0, free: 0, paid: 0 }
    day.requests += row.requests
    day.credits += row.credits
    day[row.key] += row.requests
    dates.set(row.date, day)
  }
  return dates
})

const todayUsage = computed<AggregatedDay>(() => {
  const today = utcDay(new Date())
  return usageByDate.value.get(today) ?? { date: today, requests: 0, credits: 0, free: 0, paid: 0 }
})

const dailyPercent = computed(() => {
  if (!configuredDailyCap.value) return 0
  return Math.min(Math.round((todayUsage.value.requests / configuredDailyCap.value) * 100), 100)
})

function parseUtcDay(value: string) {
  return new Date(`${value}T00:00:00Z`)
}

function shortUtcDate(value: string) {
  return new Intl.DateTimeFormat('en-AU', {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  }).format(parseUtcDay(value))
}

const historyDays = computed(() => {
  const data = usage.value
  if (!data) return []
  const first = parseUtcDay(data.from)
  const last = parseUtcDay(data.to)
  const all: AggregatedDay[] = []
  for (const cursor = new Date(first); cursor <= last; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    const date = utcDay(cursor)
    all.push(usageByDate.value.get(date) ?? { date, requests: 0, credits: 0, free: 0, paid: 0 })
  }
  const maximum = Math.max(1, ...all.map((day) => day.requests))
  return all.map((day, index) => ({
    ...day,
    label: index === 0 || index === all.length - 1 || index % 5 === 0 ? shortUtcDate(day.date) : '',
    freeHeight: (day.free / maximum) * 100,
    paidHeight: (day.paid / maximum) * 100,
    tooltip: `${shortUtcDate(day.date)}: ${day.requests} request${day.requests === 1 ? '' : 's'} `
      + `(${day.free} free, ${day.paid} paid), ${day.credits} credit${day.credits === 1 ? '' : 's'} used`,
  }))
})

const historyRangeLabel = computed(() => {
  if (!usage.value) return ''
  return `${shortUtcDate(usage.value.from)}–${shortUtcDate(usage.value.to)} ${usage.value.timezone}`
})

const historyAriaLabel = computed(() => {
  if (!usage.value) return ''
  return `Daily email verification requests from ${usage.value.from} to ${usage.value.to}. `
    + `${usage.value.totals.requests} requests used ${usage.value.totals.credits} credits.`
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
  const [creditsResult, usageResult] = await Promise.allSettled([
    fetchEmailCheckCredits(),
    fetchEmailVerificationRequests(requestRange()),
  ])
  const messages: string[] = []
  if (creditsResult.status === 'fulfilled') {
    credits.value = creditsResult.value
  } else {
    messages.push(apiErrorFromUnknown(creditsResult.reason, 'Verification balances could not be loaded.').message)
  }
  if (usageResult.status === 'fulfilled') {
    usage.value = usageResult.value
  } else {
    messages.push(apiErrorFromUnknown(usageResult.reason, 'Daily verification requests could not be loaded.').message)
  }
  error.value = [...new Set(messages)].join(' ')
  isLoading.value = false
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

.verification-history {
  margin-top: 12px;
  padding: 14px;
  border: 1px solid var(--analytics-ui-border, #d7e5e1);
  border-radius: 13px;
  background: var(--analytics-ui-surface, #fff);
}

.history-heading,
.history-summary,
.history-legend {
  display: flex;
  align-items: center;
}

.history-heading {
  justify-content: space-between;
  gap: 18px;
}

.history-heading h3 {
  margin: 0;
  color: var(--analytics-ui-text, #174243);
  font-size: 15px;
}

.history-heading p {
  margin: 3px 0 0;
  color: var(--analytics-ui-muted, #59706e);
  font-size: 11px;
}

.history-summary {
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.history-summary span {
  padding: 4px 8px;
  border-radius: 999px;
  background: #eef4f2;
  color: var(--analytics-ui-muted, #59706e);
  font-size: 11px;
}

.history-summary b {
  color: var(--analytics-ui-text, #174243);
}

.history-legend {
  justify-content: flex-end;
  gap: 14px;
  margin: 8px 0 4px;
  color: var(--analytics-ui-muted, #59706e);
  font-size: 10px;
}

.history-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.history-legend i {
  width: 9px;
  height: 9px;
  border-radius: 2px;
}

.history-chart {
  display: grid;
  height: 142px;
  grid-template-columns: repeat(30, minmax(10px, 1fr));
  gap: 4px;
  align-items: end;
  padding-top: 8px;
  overflow-x: auto;
}

.history-column {
  display: grid;
  min-width: 10px;
  height: 132px;
  grid-template-rows: 18px 92px 22px;
  align-items: end;
  text-align: center;
}

.history-value {
  align-self: center;
  color: var(--analytics-ui-text, #174243);
  font-size: 9px;
  font-weight: 700;
}

.history-bar-track {
  display: flex;
  width: min(100%, 18px);
  height: 88px;
  align-self: end;
  justify-self: center;
  flex-direction: column-reverse;
  overflow: hidden;
  border-bottom: 1px solid var(--analytics-ui-border, #d7e5e1);
  border-radius: 4px 4px 0 0;
  background: #f2f6f4;
}

.history-bar {
  display: block;
  width: 100%;
  min-height: 1px;
}

.history-bar.free,
.history-legend i.free {
  background: var(--analytics-ui-accent, #017151);
}

.history-bar.paid,
.history-legend i.paid {
  background: var(--analytics-ui-secondary, #39687b);
}

.history-date {
  min-width: 34px;
  align-self: start;
  color: var(--analytics-ui-muted, #73837f);
  font-size: 8px;
  white-space: nowrap;
  transform: translateX(calc((34px - 100%) / -2));
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

  .history-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-summary,
  .history-legend {
    justify-content: flex-start;
  }

}
</style>
