<template>
  <section class="email-monitoring-page">
    <div class="page-heading">
      <div class="heading-copy">
        <div class="breadcrumb">
          <RouterLink to="/dashboard">Home</RouterLink>
          <span>›</span>
          <RouterLink to="/analytics">Analytics</RouterLink>
          <span>›</span>
          <span>Email Monitoring</span>
        </div>

        <div class="title-line">
          <h1>Email Monitoring</h1>
          
        </div>
        <p>Monitor rolling 24-hour email usage and identify periods of high sending volume.</p>
      </div>

      <div class="page-actions">
        <button type="button" class="analytics-refresh-button" :disabled="isLoading" @click="refreshAnalytics">
          <i class="fas fa-rotate-right"></i>
          Refresh
        </button>

        <button type="button" class="export-button" :disabled="exportDisabled" @click="exportCsv">
          <i class="fas fa-download"></i>
          Export CSV
        </button>
      </div>
    </div>

    <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />

    <AnalyticsDataState
      :loading="isLoading"
      :error="loadError"
      :empty="isEmpty"
      empty-message="No tracked email delivery records are available in the current database. Send an email or load a dataset, then refresh this page."
      @retry="refreshAnalytics"
    >
    <section class="kpi-grid">
      <article
        v-for="mailbox in mailboxSummaries"
        :key="mailbox.email"
        class="kpi-card mailbox-kpi"
      >
        <span class="kpi-icon"><i class="fas fa-envelope"></i></span>
        <div>
          <span class="kpi-label">{{ mailbox.email }}</span>
          <strong>{{ mailbox.currentUsage.toLocaleString() }}</strong>
          <small>{{ mailbox.percent }}% of {{ mailbox.quotaLimit.toLocaleString() }} rolling 24-hour quota</small>
        </div>
      </article>

      <article class="kpi-card">
        <span class="kpi-icon"><i class="fas fa-envelope-open-text"></i></span>
        <div>
          <span class="kpi-label">Combined 24-Hour Usage</span>
          <strong>{{ combinedUsage.toLocaleString() }}</strong>
          <small>Across tracked sending mailboxes</small>
        </div>
      </article>

      <article class="kpi-card">
        <span class="kpi-icon"><i class="fas fa-clock"></i></span>
        <div>
          <span class="kpi-label">Latest Recorded UTC Hour</span>
          <strong>{{ data.sentLastHour }}</strong>
          <small>{{ latestRecordedHourLabel }} · attempted recipients</small>
        </div>
      </article>

      <article class="kpi-card peak-hour-kpi">
        <span class="kpi-icon"><i class="fas fa-chart-line"></i></span>
        <div>
          <span class="kpi-label">Peak Hour</span>
          <strong class="text-value">{{ peakHourTimeLabel }}</strong>
          <small>{{ peakHourDetailLabel }}</small>
        </div>
      </article>
    </section>

    <section class="overall-stats-section">
      <div class="section-heading-row">
        <div>
          <h2>Overall Email Stats</h2>
          <p>Delivery totals from the rolling 24-hour backend window only. Provider engagement metrics are shown only when recorded.</p>
        </div>
      </div>

      <div class="overall-stats-grid">
        <article class="overall-stat-card">
          <div class="overall-stat-top">
            <span class="overall-stat-icon"><i class="fas fa-envelope"></i></span>
            <div>
              <span class="overall-stat-label">Emails Delivered</span>
              <strong>{{ compactNumber(data.overallStats.delivered) }}</strong>
            </div>
          </div>
          <div class="overall-stat-meta two-col">
            <div>
              <span>Sent</span>
              <strong>{{ compactNumber(data.overallStats.sent) }}</strong>
            </div>
            <div>
              <span>Failed</span>
              <strong>{{ data.overallStats.failed.toLocaleString() }}</strong>
            </div>
          </div>
        </article>

        <article class="overall-stat-card">
          <div class="overall-stat-top">
            <span class="overall-stat-icon"><i class="fas fa-arrow-pointer"></i></span>
            <div>
              <span class="overall-stat-label">Emails Clicked</span>
              <strong>{{ optionalMetric(data.overallStats.clicked, true) }}</strong>
            </div>
          </div>
          <div class="overall-stat-meta two-col">
            <div>
              <span>Opened</span>
              <strong>{{ optionalMetric(data.overallStats.opened, true) }}</strong>
            </div>
            <div>
              <span>Marked as Spam</span>
              <strong>{{ optionalMetric(data.overallStats.spam) }}</strong>
            </div>
          </div>
        </article>

        <article class="overall-stat-card">
          <div class="overall-stat-top">
            <span class="overall-stat-icon"><i class="fas fa-paper-plane"></i></span>
            <div>
              <span class="overall-stat-label">Average attempted recipients per delivery run</span>
              <strong>{{ optionalMetric(data.overallStats.averageSentPerUser) }}</strong>
            </div>
          </div>
          <div class="overall-stat-meta two-col">
            <div>
              <span>Average Opened</span>
              <strong>{{ optionalMetric(data.overallStats.averageOpenedPerUser) }}</strong>
            </div>
            <div>
              <span>Average Clicked</span>
              <strong>{{ optionalMetric(data.overallStats.averageClickedPerUser) }}</strong>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section class="analytics-card email-logs-card">
      <div class="section-heading-row logs-heading">
        <div>
          <h2>Email Logs</h2>
          <p>Recent announcement delivery runs.</p>
        </div>

        <div class="log-actions">
          <input
            v-model.trim="logSearch"
            type="search"
            class="log-search"
            placeholder="Search email logs"
            aria-label="Search email logs"
          />
          <label class="status-filter">
            <select v-model="logStatus" aria-label="Filter email logs by status">
              <option value="all">All statuses</option>
              <option value="Delivered">Delivered</option>
              <option value="Partial">Partial</option>
              <option value="Failed">Failed</option>
            </select>
          </label>
          <button type="button" class="download-logs-button" @click="exportLogsCsv">
            <i class="fas fa-download"></i>
            Export logs
          </button>
        </div>
      </div>

      <div class="email-log-table-wrap">
        <table class="email-log-table">
          <thead>
            <tr>
              <th>Sender</th>
              <th>Sender Email</th>
              <th>Recipient</th>
              <th>Recipient Email</th>
              <th>Email Title</th>
              <th>Sent At</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in filteredLogs" :key="log.id">
              <td>{{ log.sender }}</td>
              <td>{{ log.senderEmail }}</td>
              <td>{{ log.recipient }}</td>
              <td>{{ log.recipientEmail }}</td>
              <td class="email-title-cell">{{ log.title }}</td>
              <td>{{ log.sentAt }}</td>
              <td>
                <span class="log-status" :class="log.status.toLowerCase()">
                  {{ log.status }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="logs-footer">
        <span>{{ filteredLogs.length }} log entries shown</span>
      </div>
    </section>


    <section class="analytics-grid top-grid">
      <article id="rolling-mailbox-usage" class="analytics-card quota-card">
        <div class="card-heading">
          <div>
            <h2>Rolling 24-Hour Mailbox Usage</h2>
            <p>Each sending mailbox has its own independent limit of 3,000 emails.</p>
          </div>
        </div>

        <div class="mailbox-quota-list">
          <div
            v-for="mailbox in mailboxSummaries"
            :key="mailbox.email"
            class="mailbox-quota-row"
            :class="{ 'low-remaining': mailbox.isLowRemaining }"
          >
            <div
              class="quota-ring compact-ring"
              :style="{
                '--quota': `${mailbox.percent}%`,
                '--quota-color': mailbox.isLowRemaining ? '#017151' : '#BAD7B8',
              }"
            >
              <div class="quota-center">
                <strong>{{ mailbox.percent }}%</strong>
                <span>used</span>
              </div>
            </div>

            <div class="mailbox-quota-copy">
              <strong class="mailbox-address">{{ mailbox.email }}</strong>
              <div class="mailbox-progress">
                <span :style="{ width: `${mailbox.percent}%` }"></span>
              </div>

              <div class="mailbox-stat-row">
                <span>
                  Used
                  <strong>{{ mailbox.currentUsage.toLocaleString() }}</strong>
                </span>
                <span>
                  Remaining
                  <strong>{{ mailbox.remaining.toLocaleString() }}</strong>
                </span>
                <span>
                  Limit
                  <strong>{{ mailbox.quotaLimit.toLocaleString() }}</strong>
                </span>
              </div>
            </div>

          </div>
        </div>
      </article>

      <article class="analytics-card categories-card">
        <div class="card-heading">
          <div>
            <h2>Email Volume by Type</h2>
            <p>Breakdown of attempted recipients in the current 24-hour window.</p>
          </div>
        </div>

        <div class="category-list">
          <div v-for="item in data.categories" :key="item.label" class="category-row">
            <div class="category-label">
              <span class="legend-dot" :style="{ background: item.color }"></span>
              <span>{{ item.label }}</span>
            </div>
            <div class="category-track">
              <span
                :style="{
                  width: `${(item.value / maxCategoryValue) * 100}%`,
                  background: item.color,
                }"
              ></span>
            </div>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="analytics-card email-status-role-card">
      <div class="card-heading role-attribution-heading">
        <div>
          <h2>Email Delivery Attribution by Current Role</h2>
          <p>
            Delivery results from the rolling 24-hour window<span v-if="analyticsSnapshotLabel">
            ending {{ analyticsSnapshotLabel }}</span>. Attribution uses the current-audience basis
            only when an announcement currently has one supported role audience and no group
            audience. This is not a send-time historical role snapshot.
          </p>
        </div>
        <span
          class="role-attribution-badge"
          :class="data.roleAttribution.available && data.roleAttribution.complete ? 'complete' : 'partial'"
        >
          {{ roleAttributionCoverageLabel }}
        </span>
      </div>

      <div v-if="!data.roleAttribution.available" class="role-attribution-note unavailable">
        No delivery run in the rolling 24-hour window<span v-if="analyticsSnapshotLabel">
        ending {{ analyticsSnapshotLabel }}</span> can be attributed to a single supported role.
        Opened status is also unavailable because provider events are not persisted.
      </div>

      <template v-else>
        <div class="role-attribution-summary">
          <span>
            {{ data.roleAttribution.trackedDeliveryRuns.toLocaleString() }} attributed delivery
            run{{ data.roleAttribution.trackedDeliveryRuns === 1 ? '' : 's' }}
          </span>
          <span>{{ data.roleAttribution.trackedAttempted.toLocaleString() }} attributed attempts</span>
          <span>{{ data.roleAttribution.trackedDelivered.toLocaleString() }} attributed delivered</span>
          <span>{{ data.roleAttribution.trackedFailed.toLocaleString() }} attributed failed</span>
          <span v-if="data.roleAttribution.unattributedDeliveryRuns">
            {{ data.roleAttribution.unattributedDeliveryRuns.toLocaleString() }} unattributed delivery
            run{{ data.roleAttribution.unattributedDeliveryRuns === 1 ? '' : 's' }}
          </span>
          <span v-if="data.roleAttribution.unattributedAttempted">
            {{ data.roleAttribution.unattributedAttempted.toLocaleString() }} unattributed attempts
          </span>
          <span v-if="data.roleAttribution.unattributedDeliveryRuns">
            {{ data.roleAttribution.unattributedDelivered.toLocaleString() }} unattributed delivered
          </span>
          <span v-if="data.roleAttribution.unattributedDeliveryRuns">
            {{ data.roleAttribution.unattributedFailed.toLocaleString() }} unattributed failed
          </span>
        </div>

        <div
          v-if="!data.roleAttribution.complete"
          class="role-attribution-note partial"
        >
          Global, group, mixed-role, and unsupported audiences are excluded from role rows and
          reported above as unattributed. Role totals therefore do not equal overall email totals.
        </div>

        <div class="status-role-legend" aria-label="Email role delivery legend">
          <span><i class="status-role-dot delivered"></i>Delivered</span>
          <span><i class="status-role-dot failed"></i>Failed</span>
          <span class="unavailable-metric">Opened: Unavailable</span>
        </div>

        <div class="status-role-chart">
          <div v-for="row in data.statusByRole" :key="row.role" class="status-role-row">
            <span class="status-role-name">
              <strong>{{ row.role }}</strong>
              <small>{{ row.trackedDeliveries }} delivery run{{ row.trackedDeliveries === 1 ? '' : 's' }}</small>
            </span>
            <div class="status-role-track">
              <span
                v-if="row.delivered"
                class="status-role-segment delivered"
                :style="{ width: `${statusRolePercent(row, 'delivered')}%` }"
                @mouseenter="showTooltip($event, row.role, `${row.delivered.toLocaleString()} delivered`, `${row.attempted.toLocaleString()} attributed attempts`)"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              ></span>
              <span
                v-if="row.failed"
                class="status-role-segment failed"
                :style="{ width: `${statusRolePercent(row, 'failed')}%` }"
                @mouseenter="showTooltip($event, row.role, `${row.failed.toLocaleString()} failed`, `${row.attempted.toLocaleString()} attributed attempts`)"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              ></span>
            </div>
            <span class="status-role-total">{{ row.attempted.toLocaleString() }} attempted</span>
          </div>
        </div>
        <div class="axis-title">Attributed recipient attempts</div>
      </template>
    </section>

    <section class="analytics-grid chart-grid">
      <article class="analytics-card wide-card">
        <div class="card-heading">
          <div>
            <h2>Recorded UTC Hour Buckets in the Rolling 24-Hour Window</h2>
            <p>Each bucket keeps its complete UTC date and hour so boundary hours are not merged.</p>
          </div>
        </div>

        <div class="chart-with-y-axis">
          <div class="y-axis">
            <span v-for="tick in yAxisTicks" :key="tick">{{ tick }}</span>
          </div>

          <div class="bar-chart-area">
            <div class="bar-grid-lines">
              <span v-for="n in 5" :key="n"></span>
            </div>

            <div
              class="bars mailbox-volume-bars"
              :style="{ minWidth: `max(100%, ${Math.max(data.hourlyUsage.length, 1) * 120}px)` }"
            >
              <div
                v-for="point in data.hourlyUsage"
                :key="point.label"
                class="bar-column mailbox-hour-column"
              >
                <div class="mailbox-bar-pair">
                  <div
                    class="single-mailbox-bar info-mailbox-bar"
                    :style="{ height: `${(point.info / maxHourlyValue) * 100}%` }"
                    @mouseenter="showTooltip($event, point.label, `${point.info} emails`, 'info@biotechfutures.org')"
                    @mousemove="moveTooltip"
                    @mouseleave="hideTooltip"
                  ></div>
                  <div
                    class="single-mailbox-bar connect-mailbox-bar"
                    :style="{ height: `${(point.connect / maxHourlyValue) * 100}%` }"
                    @mouseenter="showTooltip($event, point.label, `${point.connect} emails`, 'connect@biotechfutures.org')"
                    @mousemove="moveTooltip"
                    @mouseleave="hideTooltip"
                  ></div>
                </div>
                <span>{{ point.label }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="axis-footer dual-mailbox-axis-footer">
          <div class="axis-title">Number of Emails</div>
          <div class="mailbox-legend mailbox-legend-dual">
            <span class="legend-item">
              <span class="legend-dot legend-dot-info"></span>
              <span>info@biotechfutures.org</span>
            </span>
            <span class="legend-item">
              <span class="legend-dot legend-dot-connect"></span>
              <span>connect@biotechfutures.org</span>
            </span>
          </div>
        </div>
      </article>
    </section>



    <section class="analytics-grid chart-grid">
      <article class="analytics-card wide-card">
        <div class="card-heading">
          <div>
            <h2>Announcement Deliveries per Day</h2>
          </div>
        </div>

        <div class="chart-with-y-axis">
          <div class="y-axis">
            <span v-for="tick in verificationYAxisTicks" :key="tick">{{ tick }}</span>
          </div>
          <div class="bar-chart-area verification-chart-area">
            <div class="verification-limit-line" :style="{ bottom: `${verificationLimitPosition}%` }"></div>
            <div class="bar-grid-lines"><span v-for="n in 5" :key="n"></span></div>
            <div class="bars verification-bars">
              <div v-for="point in verificationDaily" :key="point.label" class="bar-column">
                <div class="bar-value">{{ point.value }}</div>
                <div
                  class="two-tone-bar-track verification-two-tone"
                  @mouseenter="showTooltip($event, point.label, `${point.value} total delivery attempts`, `${Math.max(verificationDailyBaseLimit - point.value, 0)} remaining before mailbox limit`)"
                  @mousemove="moveTooltip"
                  @mouseleave="hideTooltip"
                >
                  <span
                    class="two-tone-used verification-used"
                    :style="{ height: `${Math.min((point.value / verificationDailyBaseLimit) * 100, 100)}%` }"
                  ></span>
                  <span
                    class="two-tone-remaining"
                    :style="{ height: `${Math.max(100 - (point.value / verificationDailyBaseLimit) * 100, 0)}%` }"
                  ></span>
                </div>
                <span>{{ point.label }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="axis-footer">
          <div class="axis-title">Total Delivery Attempts</div>
        </div>
      </article>
    </section>

    <section class="analytics-grid lower-grid">
      <article class="analytics-card alerts-card">
        <div class="card-heading">
          <div>
            <h2>Recent Monitoring Events</h2>
            <p>Quota and sending-volume events from the local database.</p>
          </div>
        </div>

        <div class="table-wrap monitoring-events-scroll">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Event</th>
                <th>Details</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="alert in data.alerts" :key="alert.id">
                <td>{{ alert.time }}</td>
                <td>{{ alert.type }}</td>
                <td>{{ alert.detail }}</td>
                <td>
                  <span class="table-status" :class="{ monitoring: alert.status === 'Monitoring' }">
                    {{ alert.status }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="analytics-card insight-card">
        <AnalyticsKeyInsights
          :items="emailInsightItems"
          description="Summarises rolling mailbox quota usage and the highest-volume recorded hour."
        />
      </article>
    </section>

    <ChartTooltip
      :visible="tooltip.visible"
      :x="tooltip.x"
      :y="tooltip.y"
      :title="tooltip.title"
      :value="tooltip.value"
      :detail="tooltip.detail"
    />
    </AnalyticsDataState>
  </section>
</template>

<script setup lang="ts">
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import AnalyticsKeyInsights from '@/components/analytics/AnalyticsKeyInsights.vue'
import AnalyticsDataState from '@/components/analytics/AnalyticsDataState.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import { useRoute } from 'vue-router'
import type { EmailMonitoringData } from '@/types/analytics'
import {
  buildEmailMonitoring,
  loadEmailMonitoringAnalyticsBundle,
  type EmailAnalyticsBundle,
} from '@/utils/liveAnalyticsData'

const route = useRoute()
const data = ref<EmailMonitoringData>({
  mailboxes: [],
  sentLastHour: 0,
  peakHourLabel: '—',
  peakHourValue: 0,
  hourlyUsage: [],
  verificationDaily: [],
  verificationDailyBaseLimit: 3000,
  statusByRole: [],
  roleAttribution: {
    basis: 'current_single_role_audience',
    available: false,
    complete: false,
    trackedDeliveryRuns: 0,
    unattributedDeliveryRuns: 0,
    trackedAttempted: 0,
    unattributedAttempted: 0,
    trackedDelivered: 0,
    unattributedDelivered: 0,
    trackedFailed: 0,
    unattributedFailed: 0,
  },
  categories: [],
  alerts: [],
  overallStats: {
    delivered: 0, sent: 0, failed: 0, clicked: null, opened: null, spam: null,
    averageSentPerUser: null, averageOpenedPerUser: null, averageClickedPerUser: null,
  },
  logs: [],
})
const loadError = ref('')
const isLoading = ref(true)
const isEmpty = ref(false)
const hasLoaded = ref(false)
const exportDisabled = computed(() => isLoading.value || !!loadError.value || isEmpty.value || !hasLoaded.value)
const analyticsSnapshotAt = ref<string | null>(null)
const logSearch = ref('')
const logStatus = ref('all')

const filteredLogs = computed(() => {
  const query = logSearch.value.toLowerCase()

  return data.value.logs.filter((log) => {
    const matchesStatus = logStatus.value === 'all' || log.status === logStatus.value
    const haystack = [
      log.sender,
      log.senderEmail,
      log.recipient,
      log.recipientEmail,
      log.title,
      log.sentAt,
      log.status,
    ]
      .join(' ')
      .toLowerCase()

    return matchesStatus && (!query || haystack.includes(query))
  })
})



function compactNumber(value: number) {
  if (value >= 1000) {
    const compact = value / 1000
    return `${Number.isInteger(compact) ? compact.toFixed(0) : compact.toFixed(1)}k`
  }
  return value.toLocaleString()
}

function optionalMetric(value: number | null, compact = false) {
  if (value === null) return 'Unavailable'
  return compact ? compactNumber(value) : value.toLocaleString()
}

const mailboxSummaries = computed(() =>
  data.value.mailboxes.map((mailbox) => {
    const percent = Math.round((mailbox.currentUsage / mailbox.quotaLimit) * 100)
    return {
      ...mailbox,
      percent,
      remaining: Math.max(mailbox.quotaLimit - mailbox.currentUsage, 0),
      isLowRemaining: percent >= 80,
    }
  }),
)

const combinedUsage = computed(() =>
  mailboxSummaries.value.reduce((sum, mailbox) => sum + mailbox.currentUsage, 0),
)

function utcTimestampLabel(value: string | null) {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ''
  return `${parsed.toISOString().slice(0, 16).replace('T', ' ')} UTC`
}

const analyticsSnapshotLabel = computed(() => utcTimestampLabel(analyticsSnapshotAt.value))
const latestRecordedHourLabel = computed(
  () => data.value.hourlyUsage[data.value.hourlyUsage.length - 1]?.label ?? 'Unavailable',
)

const peakHourParts = computed(() => {
  const match = data.value.peakHourLabel.match(/^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+UTC$/)
  if (!match) return { date: '', time: data.value.peakHourLabel || 'Unavailable' }
  return { date: match[1]!, time: `${match[2]} UTC` }
})
const peakHourDateLabel = computed(() => peakHourParts.value.date)
const peakHourTimeLabel = computed(() => peakHourParts.value.time)
const peakHourDetailLabel = computed(() =>
  `${peakHourDateLabel.value ? `${peakHourDateLabel.value} · ` : ''}${data.value.peakHourValue} attempted recipients`,
)
const emailInsightItems = computed(() => [
  ...mailboxSummaries.value.map((mailbox) => ({
    key: mailbox.email,
    value: `${mailbox.percent}%`,
    text: `${mailbox.email} has used ${mailbox.currentUsage.toLocaleString()} of its ${mailbox.quotaLimit.toLocaleString()} rolling 24-hour quota.`,
  })),
  {
    key: 'peak-hour',
    value: data.value.peakHourLabel,
    text: 'is the highest-volume period in the current window.',
  },
])
const roleAttributionCoverageLabel = computed(() => {
  if (!data.value.roleAttribution.available) return 'Unavailable under current-audience basis'
  return data.value.roleAttribution.complete
    ? 'Complete under current-audience basis'
    : 'Partial under current-audience basis'
})

const verificationDailyBaseLimit = computed(() =>
  data.value.verificationDailyBaseLimit ?? 100,
)

const verificationDaily = computed(() => data.value.verificationDaily)

const maxVerificationValue = computed(() =>
  Math.max(...data.value.verificationDaily.map((point) => point.value), data.value.verificationDailyBaseLimit, 1),
)

const verificationYAxisTicks = computed(() => {
  const max = maxVerificationValue.value
  const step = Math.ceil(max / 4 / 10) * 10
  return [step * 4, step * 3, step * 2, step, 0]
})

const verificationLimitPosition = computed(() =>
  Math.min((data.value.verificationDailyBaseLimit / maxVerificationValue.value) * 100, 100),
)

type EmailStatusRoleRow = EmailMonitoringData['statusByRole'][number]
function statusRolePercent(row: EmailStatusRoleRow, key: 'delivered' | 'failed') {
  return (row[key] / Math.max(row.attempted, 1)) * 100
}

const maxHourlyValue = computed(() =>
  Math.max(
    ...data.value.hourlyUsage.flatMap((item) => [item.info, item.connect]),
    1,
  ),
)

const maxCategoryValue = computed(() =>
  Math.max(...data.value.categories.map((item) => item.value), 1),
)

const yAxisTicks = computed(() => {
  const top = Math.ceil(maxHourlyValue.value / 100) * 100
  return [top, Math.round(top * 0.75), Math.round(top * 0.5), Math.round(top * 0.25), 0]
})

const tooltip = ref({
  visible: false,
  x: 0,
  y: 0,
  title: '',
  value: '',
  detail: '',
})

function showTooltip(event: MouseEvent, title: string, value: string, detail = '') {
  tooltip.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    title,
    value,
    detail,
  }
}

function moveTooltip(event: MouseEvent) {
  tooltip.value.x = event.clientX
  tooltip.value.y = event.clientY
}

function hideTooltip() {
  tooltip.value.visible = false
}

function emailBundleIsEmpty(bundle: EmailAnalyticsBundle) {
  const email = bundle.emailAnalytics
  return email.mailboxes.length === 0
    && email.recent_deliveries.length === 0
    && email.hourly.length === 0
    && email.daily.length === 0
}

const analyticsRefreshBusy = ref(false)
const { lastUpdated, refreshFailed, markUpdated, markRefreshFailed } = useAnalyticsRefresh(async () => { if (!analyticsRefreshBusy.value) await loadAnalytics(true, true) })

async function loadAnalytics(force = false, preserveFilters = false) {
  if (analyticsRefreshBusy.value) return
  analyticsRefreshBusy.value = true
  if (!preserveFilters || !lastUpdated.value) isLoading.value = true
  loadError.value = ''
  try {
    const bundle = await loadEmailMonitoringAnalyticsBundle(force)
    analyticsSnapshotAt.value = bundle.emailAnalytics.snapshot_at ?? null
    data.value = buildEmailMonitoring(bundle)
    isEmpty.value = emailBundleIsEmpty(bundle)
    hasLoaded.value = true
    markUpdated()
  } catch (error) {
    if (preserveFilters && lastUpdated.value) { markRefreshFailed(); return }
    console.error('Failed to load email monitoring analytics from the backend.', error)
    loadError.value = 'Email analytics could not be loaded from the backend. Check the API and try again.'
    analyticsSnapshotAt.value = null
    hasLoaded.value = false
  } finally {
    analyticsRefreshBusy.value = false
    isLoading.value = false
  }
}

function refreshAnalytics() {
  return loadAnalytics(true)
}

function exportLogsCsv() {
  const rows: (string | number)[][] = [
    ['Sender', 'Sender Email', 'Recipient', 'Recipient Email', 'Email Title', 'Sent At', 'Status'],
    ...filteredLogs.value.map((log) => [
      log.sender,
      log.senderEmail,
      log.recipient,
      log.recipientEmail,
      log.title,
      log.sentAt,
      log.status,
    ]),
  ]

  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'email-logs.csv'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}


onMounted(() => loadAnalytics())

async function scrollToDeepLinkTarget(hash: string) {
  if (!hash) return

  await nextTick()

  const scroll = () => {
    const target = document.getElementById(hash.replace(/^#/, ''))
    if (!target) return
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // Vue Router / async layout can still adjust scroll position after mount.
  // Run again after layout settles so the final position is the requested section.
  requestAnimationFrame(() => requestAnimationFrame(scroll))
  window.setTimeout(scroll, 120)
  window.setTimeout(scroll, 320)
}

watch(
  () => route.hash,
  (hash) => {
    scrollToDeepLinkTarget(hash)
  },
  { immediate: true },
)

function exportCsv() {
  const rows: (string | number)[][] = [
    ['Email Monitoring'],
    [],
    ['Metric', 'Value'],
    ...mailboxSummaries.value.flatMap((mailbox) => [
      [`${mailbox.email} - 24-Hour Usage`, mailbox.currentUsage],
      [`${mailbox.email} - Quota Limit`, mailbox.quotaLimit],
      [`${mailbox.email} - Quota Used (%)`, mailbox.percent],
      [`${mailbox.email} - Remaining`, mailbox.remaining],
    ]),
    ['Combined 24-Hour Usage', combinedUsage.value],
    ['Mailbox Limit', data.value.verificationDailyBaseLimit],
    ...data.value.verificationDaily.map((point) => [`Delivery Attempts - ${point.label}`, point.value]),
    ['Rolling 24-Hour Window End (UTC)', analyticsSnapshotLabel.value || 'Unavailable'],
    ['Latest Recorded UTC Hour', latestRecordedHourLabel.value],
    ['Latest Recorded UTC Hour Attempts', data.value.sentLastHour],
    ['Peak Hour', data.value.peakHourLabel],
    ['Peak Hour Attempted Recipients', data.value.peakHourValue],
    [],
    ['Overall Email Stats'],
    ['Emails Delivered', data.value.overallStats.delivered],
    ['Emails Sent', data.value.overallStats.sent],
    ['Emails Failed', data.value.overallStats.failed],
    ['Emails Clicked', optionalMetric(data.value.overallStats.clicked)],
    ['Emails Opened', optionalMetric(data.value.overallStats.opened)],
    ['Marked as Spam', optionalMetric(data.value.overallStats.spam)],
    ['Average Attempted Recipients per Delivery Run', optionalMetric(data.value.overallStats.averageSentPerUser)],
    ['Average Opened per User', optionalMetric(data.value.overallStats.averageOpenedPerUser)],
    ['Average Clicked per User', optionalMetric(data.value.overallStats.averageClickedPerUser)],
    [],
    ['Role Attribution'],
    ['Basis', 'Current single-role announcement audience; not a send-time historical role snapshot'],
    ['Availability', data.value.roleAttribution.available ? 'Available' : 'Unavailable'],
    [
      'Coverage',
      !data.value.roleAttribution.available
        ? 'Unavailable'
        : data.value.roleAttribution.complete
          ? 'Complete'
          : 'Partial',
    ],
    ['Attributed Delivery Runs', data.value.roleAttribution.trackedDeliveryRuns],
    ['Unattributed Delivery Runs', data.value.roleAttribution.unattributedDeliveryRuns],
    ['Attributed Attempts', data.value.roleAttribution.trackedAttempted],
    ['Unattributed Attempts', data.value.roleAttribution.unattributedAttempted],
    ['Attributed Delivered', data.value.roleAttribution.trackedDelivered],
    ['Unattributed Delivered', data.value.roleAttribution.unattributedDelivered],
    ['Attributed Failed', data.value.roleAttribution.trackedFailed],
    ['Unattributed Failed', data.value.roleAttribution.unattributedFailed],
    ['Role', 'Attributed Delivery Runs', 'Attempted', 'Delivered', 'Failed', 'Opened'],
    ...(data.value.roleAttribution.available
      ? data.value.statusByRole.map((row) => [
          row.role,
          row.trackedDeliveries,
          row.attempted,
          row.delivered,
          row.failed,
          optionalMetric(row.opened),
        ])
      : [['Unavailable', '', '', '', '', 'Unavailable']]),
    [],
    ['Hour', 'info@biotechfutures.org', 'connect@biotechfutures.org', 'Combined'],
    ...data.value.hourlyUsage.map((item) => [
      item.label,
      item.info,
      item.connect,
      item.info + item.connect,
    ]),
    [],
    ['Email Type', 'Messages'],
    ...data.value.categories.map((item) => [item.label, item.value]),
  ]

  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'email-monitoring.csv'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
</script>

<style src="@/assets/analytics-theme.css"></style>

<style scoped>
.email-monitoring-page {
  min-height: 100%;
  padding: 28px 32px 40px;
  background: #f7faf9;
  color: #174243;
}

.page-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  margin-bottom: 22px;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
  color: #59706e;
  font-size: 14px;
}


.breadcrumb a {
  color: #59706e;
  text-decoration: none;
}




.breadcrumb a:hover {
  color: #017151;
  text-decoration: underline;
}
.title-line {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

h1 {
  margin: 0;
}


.heading-copy > p {
  margin: 8px 0 0;
  color: #617572;
  font-size: 16px;
}
.page-heading h1 {
  margin: 0;
  color: #163f3c;
  font-size: 36px;
  line-height: 1.15;
  font-weight: 800;
}



.demo-badge {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid #BAD7B8;
  border-radius: 999px;
  background: #F1E5A6;
  color: #174243;
  font-size: 12px;
  font-weight: 700;
}


.page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  align-self: start;
  margin: 0;
}

.refresh-button,
.export-button {
  height: 46px;
  border-radius: 12px;
  background: #ffffff;
  font-size: 14px;
  font-weight: 700;
}

.refresh-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  width: 120px;
  padding: 0 13px;
  border: 1px solid #d7e3e0;
  color: #174844;
  cursor: pointer;
}

.export-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 142px;
  padding: 0 16px;
  border: 1px solid #9fd8c7;
  color: #017151;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;
}

.refresh-button:hover,
.export-button:hover {
  background: #ecf8f4;
  border-color: #74c9b3;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}

.kpi-card,
.analytics-card {
  border: 1px solid #d7e2de;
  border-radius: 12px;
  background: #fff;
}

.kpi-card {
  min-width: 0;
  min-height: 122px;
  display: flex;
  gap: 12px;
  padding: 16px;
}

.kpi-icon {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  place-items: center;
  border-radius: 10px;
  background: #e7f1e6;
  color: #017151;
}

.kpi-card > div {
  min-width: 0;
  display: grid;
  grid-template-rows: 34px 38px 34px;
}

.kpi-label {
  color: #52615c;
  font-size: 12px;
  font-weight: 700;
}

.kpi-card strong {
  margin: 0;
  color: #174243;
  font-size: 30px;
  line-height: 38px;
}

.kpi-card strong.text-value {
  font-size: 25px;
}

.kpi-card small {
  color: #667873;
  font-size: 11px;
  line-height: 15px;
}

.analytics-grid {
  display: grid;
  gap: 14px;
  margin-bottom: 14px;
}

.top-grid {
  grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
}

.lower-grid {
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
}

.analytics-card {
  min-width: 0;
  padding: 16px;
}

.card-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.card-heading h2 {
  margin: 0;
  color: #174243;
  font-size: 18px;
}

.card-heading p {
  margin: 4px 0 0;
  color: #667873;
  font-size: 12px;
}

.status-pill,
.table-status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 9px;
  border-radius: 999px;
  background: #e7f1e6;
  color: #017151;
  font-size: 11px;
  font-weight: 700;
}

.status-pill.warning,
.table-status.monitoring {
  background: #f1e5a6;
  color: #174243;
}

.quota-layout {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 34px;
  min-height: 240px;
}

.quota-ring {
  --quota: 62%;
  --quota-color: #BAD7B8;
  position: relative;
  isolation: isolate;
  width: 170px;
  height: 170px;
  border-radius: 50%;
  background: conic-gradient(var(--quota-color) var(--quota), #e9efec 0);
}

.quota-ring::after {
  content: '';
  position: absolute;
  inset: 24px;
  border-radius: 50%;
  background: #fff;
}

.quota-center {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: grid;
  place-content: center;
  text-align: center;
}

.quota-center strong {
  color: #174243;
  font-size: 34px;
}

.quota-center span {
  color: #667873;
  font-size: 11px;
}

.quota-details {
  display: grid;
  gap: 13px;
  min-width: 150px;
}

.quota-details div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 22px;
  border-bottom: 1px solid #e9efec;
  padding-bottom: 8px;
}

.quota-details span {
  color: #667873;
  font-size: 12px;
}

.quota-details strong {
  color: #174243;
  font-size: 16px;
}

.category-list {
  display: grid;
  gap: 16px;
  padding-top: 8px;

  max-height: 220px;
  overflow-y: auto;
  padding-right: 8px;
}

.category-row {
  display: grid;
  grid-template-columns: 140px minmax(80px, 1fr) 50px;
  align-items: center;
  gap: 10px;
}

.category-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #174243;
  font-size: 12px;
  font-weight: 700;
}

.legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.category-track {
  height: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: #e9efec;
}

.category-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.category-row > strong {
  color: #174243;
  font-size: 12px;
  text-align: right;
}

.chart-with-y-axis {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 8px;
  min-height: 330px;
}

.y-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 5px 0 36px;
  color: #667873;
  font-size: 10px;
  text-align: right;
}

.bar-chart-area {
  position: relative;
  min-width: 0;
  height: 330px;
  border-left: 1px solid #d7e2de;
  border-bottom: 1px solid #d7e2de;
}

.bar-grid-lines {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  pointer-events: none;
}

.bar-grid-lines span {
  border-top: 1px solid #e9efec;
}

.bars {
  position: absolute;
  inset: 0 10px 0;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  align-items: end;
  gap: 10px;
}

.bar-column {
  min-width: 0;
  height: 100%;
  display: grid;
  grid-template-rows: 24px minmax(0, 1fr) 28px;
  align-items: end;
  text-align: center;
}

.bar-value {
  color: #174243;
  font-size: 10px;
  font-weight: 700;
}

.bar {
  width: 65%;
  max-width: 34px;
  min-height: 2px;
  justify-self: center;
  border-radius: 4px 4px 0 0;
  background: #39687b;
  cursor: pointer;
}

.bar-column > span {
  align-self: center;
  color: #667873;
  font-size: 10px;
}

.axis-title {
  margin-top: 7px;
  color: #667873;
  font-size: 10px;
  font-weight: 700;
  text-align: center;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 680px;
  border-collapse: collapse;
}

th,
td {
  padding: 10px;
  border-bottom: 1px solid #e9efec;
  color: #52615c;
  font-size: 12px;
  text-align: left;
}

th {
  background: #f0f3f2;
  color: #174243;
  font-size: 11px;
}

.insight-list {
  display: grid;
  gap: 10px;
}

.insight-row {
  display: grid;
  grid-template-columns: 82px 1fr;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 9px;
  background: #f7faf9;
}

.insight-value {
  color: #017151;
  font-size: 20px;
  font-weight: 700;
}

.insight-row p {
  margin: 0;
  color: #667873;
  font-size: 11px;
}


.overall-stats-section {
  margin-bottom: 12px;
}

.section-heading-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.section-heading-row h2 {
  margin: 0;
  color: #174243;
  font-size: 18px;
}

.section-heading-row p {
  margin: 4px 0 0;
  color: #667873;
  font-size: 12px;
}

.overall-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border: 1px solid #d7e2de;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}

.overall-stat-card {
  min-width: 0;
  min-height: 150px;
  padding: 10px 16px;
  border-right: 1px solid #d7e2de;
  text-align: center;
}


.overall-stat-card:last-child {
  border-right: 0;
}

.overall-stat-top {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
}


.overall-stat-icon {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  place-items: center;
  color: #017151;
  font-size: 16px;
}

.overall-stat-label {
  display: block;
  margin-bottom: 2px;
  color: #52615c;
  font-size: 11px;
  font-weight: 700;
}

.overall-stat-top strong {
  color: #174243;
  font-size: 22px;
  line-height: 1.05;
}

.overall-stat-meta {
  margin-top: 7px;
}

.overall-stat-meta.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  text-align: center;
}

.overall-stat-meta div {
  min-width: 0;
}

.overall-stat-meta span {
  display: block;
  color: #667873;
  font-size: 10px;
}

.overall-stat-meta strong {
  display: block;
  margin-top: 3px;
  color: #174243;
  font-size: 12px;
}

.email-logs-card {
  margin-bottom: 14px;
}

.logs-heading {
  align-items: center;
}

.log-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.log-search,
.status-filter select,
.download-logs-button {
  height: 38px;
  border: 1px solid #bad7b8;
  border-radius: 9px;
  background: #fff;
  color: #174243;
  font: inherit;
  font-size: 11px;
}

.log-search {
  width: 210px;
  padding: 0 11px;
}

.status-filter select {
  min-width: 125px;
  padding: 0 10px;
}

.download-logs-button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 11px;
  color: #017151;
  font-weight: 700;
  cursor: pointer;
}

.email-log-table-wrap {
  max-height: 430px;
  overflow-y: auto;
  overflow-x: hidden;
  border: 1px solid #d7e2de;
  border-radius: 10px;
}

.email-log-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
}

.email-log-table thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f0f3f2;
}

.email-log-table th,
.email-log-table td {
  padding: 8px 7px;
  overflow-wrap: anywhere;
  word-break: break-word;
  vertical-align: top;
  line-height: 1.35;
  font-size: 10px;
}

.email-log-table th:nth-child(1) { width: 10%; }
.email-log-table th:nth-child(2) { width: 16%; }
.email-log-table th:nth-child(3) { width: 12%; }
.email-log-table th:nth-child(4) { width: 16%; }
.email-log-table th:nth-child(5) { width: 24%; }
.email-log-table th:nth-child(6) { width: 12%; }
.email-log-table th:nth-child(7) { width: 10%; }

.email-title-cell {
  min-width: 0;
  color: #39687b;
}

.log-status {
  display: inline-flex;
  min-height: 22px;
  align-items: center;
  justify-content: center;
  max-width: 100%;
  padding: 0 7px;
  border-radius: 999px;
  background: #E7F1E6;
  color: #017151;
  font-size: 9px;
  font-weight: 700;
  line-height: 1.1;
  white-space: normal;
  text-align: center;
  overflow-wrap: anywhere;
}

.log-status.opened {
  background: #e4f0ee;
  color: #174243;
}

.log-status.partial {
  background: #fff4d0;
  color: #715400;
}

.log-status.failed {
  background: #f1e5a6;
  color: #174243;
}

.logs-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
  color: #667873;
  font-size: 10px;
}

.mailbox-quota-list {
  display: grid;
  gap: 14px;
}

.mailbox-quota-row {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  align-items: center;
  gap: 20px;
  padding: 14px 0;
  border-bottom: 1px solid #e9efec;
}

.mailbox-quota-row:last-child {
  border-bottom: 0;
}

.compact-ring {
  width: 104px;
  height: 104px;
}

.compact-ring::after {
  inset: 15px;
}

.compact-ring .quota-center strong {
  font-size: 24px;
}

.mailbox-quota-copy {
  min-width: 0;
}

.mailbox-address {
  display: block;
  margin-bottom: 10px;
  color: #174243;
  font-size: 14px;
}

.mailbox-progress {
  height: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: #e9efec;
}

.mailbox-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #BAD7B8;
}

.mailbox-quota-row.low-remaining .mailbox-progress span {
  background: #017151;
}

.mailbox-stat-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 10px;
}

.mailbox-stat-row > span {
  color: #667873;
  font-size: 10px;
}

.mailbox-stat-row strong {
  display: block;
  margin-top: 2px;
  color: #174243;
  font-size: 12px;
}

.mailbox-kpi .kpi-label {
  overflow-wrap: anywhere;
}

.peak-hour-kpi .text-value {
  white-space: nowrap;
}

.peak-hour-kpi small {
  white-space: normal;
}

@media (max-width: 1250px) {
  .overall-stats-grid {
    grid-template-columns: 1fr;
  }

  .overall-stat-card {
    border-right: 0;
    border-bottom: 1px solid #d7e2de;
  }

  .overall-stat-card:last-child {
    border-bottom: 0;
  }

  .section-heading-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .top-grid,
  .lower-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 780px) {
  .mailbox-quota-row {
    grid-template-columns: 1fr;
    justify-items: center;
    text-align: center;
  }

  .mailbox-quota-copy {
    width: 100%;
  }

  .mailbox-stat-row {
    grid-template-columns: repeat(3, 1fr);
  }

  .email-monitoring-page {
    padding: 20px 16px;
  }

  .page-heading {
    grid-template-columns: 1fr;
  }

  .page-actions {
    flex-wrap: wrap;
  }

  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .quota-layout {
    flex-direction: column;
  }
}

/* Email log table visual refinements */
.email-log-table tbody tr {
  transition: background-color 0.15s ease;
}

.email-log-table tbody tr:hover {
  background: rgba(186, 215, 184, 0.45);
}

@media (max-width: 1100px) {
  .email-log-table th,
  .email-log-table td {
    padding: 7px 5px;
    font-size: 9px;
  }

  .log-status {
    padding: 0 5px;
    font-size: 9px;
  }
}

/* Final visual alignment */
.email-log-table tbody tr:hover,
.email-log-table tbody tr:hover td,
.alerts-card tbody tr:hover,
.alerts-card tbody tr:hover td {
  background: rgba(186, 215, 184, 0.42) !important;
}

.email-log-table .log-status {
  min-width: 58px;
  min-height: 22px;
  padding: 0 7px;
  font-size: 9px;
}

.email-log-table .log-status.delivered {
  background: rgba(186, 215, 184, 0.52);
  color: #017151;
}

.email-log-table .log-status.opened {
  background: rgba(94, 169, 158, 0.16);
  color: #174243;
}

.email-log-table .log-status.partial {
  background: #fff4d0;
  color: #715400;
}

.email-log-table .log-status.failed {
  background: #F1E5A6;
  color: #174243;
}


/* Exact Users Analytics header/control alignment */
.email-monitoring-page .page-heading h1 {
  margin: 0;
  color: #163f3c;
  font-size: 36px;
  line-height: 1.15;
  font-weight: 800;
}

.email-monitoring-page .heading-copy > p {
  margin: 8px 0 0;
  color: #617572;
  font-size: 16px;
}

.email-monitoring-page .page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  align-self: start;
  margin: 0;
}

.email-monitoring-page .refresh-button {
  width: 120px;
  height: 46px;
  padding: 0 13px;
  border: 1px solid #9fd8c7;
  border-radius: 12px;
  background: #ffffff;
  color: #017151;
  font-size: 14px;
  font-weight: 700;
}

.email-monitoring-page .export-button {
  width: 142px;
  height: 46px;
  padding: 0 16px;
  border: 1px solid #9fd8c7;
  border-radius: 12px;
  background: #ffffff;
  color: #017151;
  font-size: 14px;
  font-weight: 700;
}

.verification-limit-badge { display:inline-flex; align-items:center; min-height:28px; padding:0 9px; border:1px solid #BAD7B8; border-radius:999px; background:rgba(241,229,166,.55); color:#174243; font-size:11px; font-weight:700; }
.verification-chart-area { position:relative; }
.verification-limit-line { position:absolute; right:10px; left:10px; z-index:2; border-top:1px dashed #39687B; pointer-events:none; }
.verification-limit-line span { position:absolute; right:0; bottom:4px; padding:2px 6px; border-radius:6px; background:#fff; color:#39687B; font-size:10px; font-weight:700; }
.verification-bars { grid-template-columns:repeat(7,minmax(0,1fr)); }
.verification-bar { background:#5EA99E; }

/* Large-data chart handling: keep all values in one horizontal row */
.email-monitoring-page .chart-grid .wide-card {
  overflow: hidden;
}

.email-monitoring-page .bar-chart-area {
  overflow-x: auto;
  overflow-y: hidden;
}

.email-monitoring-page .bars {
  display: flex;
  min-width: max(100%, 1320px);
  gap: 16px;
  align-items: stretch;
  padding: 0 12px;
}

.email-monitoring-page .verification-bars {
  min-width: max(100%, 900px);
}

.email-monitoring-page .bar-column {
  flex: 1 0 44px;
  min-width: 44px;
}

.two-tone-bar-track {
  position: relative;
  display: flex;
  width: 34px;
  height: 100%;
  flex-direction: column-reverse;
  justify-self: center;
  overflow: hidden;
  border-radius: 5px 5px 0 0;
  background: #e5efec;
  cursor: pointer;
}

.two-tone-used,
.two-tone-remaining {
  display: block;
  width: 100%;
  flex: 0 0 auto;
}

.hourly-used {
  background: #39687B;
}

.verification-used {
  background: #5EA99E;
}

.two-tone-remaining {
  background: #BAD7B8;
  opacity: 0.55;
}

/* Keep long monitoring history inside the card */
.monitoring-events-scroll {
  max-height: 360px;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}

.monitoring-events-scroll thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f0f3f2;
}

.axis-footer {
  position: relative;
  min-height: 24px;
  margin-top: 7px;
}

.axis-footer .axis-title {
  margin-top: 0;
  text-align: center;
}

.mailbox-legend {
  position: absolute;
  right: 6px;
  top: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #617571;
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}

.mailbox-legend .legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.legend-dot-volume {
  background: #39687B;
}

.legend-dot-verification {
  background: #5EA99E;
}

/* Dual-mailbox rolling-window volume chart */
.mailbox-volume-bars {
  min-width: 100%;
}

.email-monitoring-page .mailbox-hour-column {
  flex: 1 0 112px;
  min-width: 112px;
}

.mailbox-bar-pair {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 4px;
  width: 100%;
  height: 100%;
}

.single-mailbox-bar {
  width: 14px;
  min-height: 2px;
  border-radius: 4px 4px 0 0;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.single-mailbox-bar:hover {
  opacity: 0.8;
}

.info-mailbox-bar {
  background: #39687B;
}

.connect-mailbox-bar {
  background: #5EA99E;
}

.mailbox-legend-dual {
  gap: 14px;
}

.mailbox-legend-dual .legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.legend-dot-info {
  background: #39687B;
}

.legend-dot-connect {
  background: #5EA99E;
}

.dual-mailbox-axis-footer {
  min-height: 30px;
}

/* Fix paired mailbox bars: the pair must occupy the chart plotting row,
   not the 24px value-label row inherited from .bar-column. */
.mailbox-hour-column .mailbox-bar-pair {
  grid-row: 2;
  align-self: stretch;
  height: 100%;
}

.mailbox-hour-column > span {
  grid-row: 3;
  align-self: center;
}

/* Keep both mailbox bars visible from the baseline and avoid clipping. */
.mailbox-hour-column .single-mailbox-bar {
  align-self: flex-end;
}

/* Keep every dated UTC bucket readable; the inline minimum width scales with
   the number of buckets returned by the API. */
.email-monitoring-page .mailbox-volume-bars {
  min-width: 100%;
}


.email-status-role-card { margin-bottom:18px; }
.status-role-legend { display:flex; justify-content:flex-end; gap:18px; margin:4px 0 18px; color:#60736f; font-size:12px; }
.status-role-legend span { display:inline-flex; align-items:center; gap:6px; }
.status-role-dot { width:9px; height:9px; border-radius:50%; display:inline-block; }
.status-role-dot.delivered,.status-role-segment.delivered { background:#017151; }
.status-role-dot.failed,.status-role-segment.failed { background:#F1E5A6; }
.status-role-chart { display:grid; gap:16px; }
.status-role-row { display:grid; grid-template-columns:120px minmax(0,1fr) 110px; gap:14px; align-items:center; color:#174243; font-size:12px; }
.status-role-name { display:grid; gap:2px; }
.status-role-name small { color:#6b7d79; font-size:10px; font-weight:500; }
.status-role-track { display:flex; height:22px; overflow:hidden; border-radius:999px; background:#edf2f0; }
.status-role-segment { height:100%; cursor:pointer; }
.status-role-total { text-align:right; font-weight:700; }
.role-attribution-heading { align-items:flex-start; }
.role-attribution-heading > div { min-width:0; }
.role-attribution-badge { display:inline-flex; align-items:center; align-self:flex-start; flex:0 0 auto; min-height:28px; border-radius:999px; padding:5px 10px; background:#fff4d1; color:#745b00; font-size:11px; font-weight:700; line-height:1.2; white-space:nowrap; }
.role-attribution-badge.complete { background:#ddf2e8; color:#075f47; }
.role-attribution-summary { display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 12px; }
.role-attribution-summary span { border-radius:999px; padding:5px 9px; background:#edf5f2; color:#315b54; font-size:11px; font-weight:600; }
.role-attribution-note { margin:8px 0 14px; padding:10px 12px; border-radius:8px; font-size:11px; line-height:1.5; }
.role-attribution-note.partial { border:1px solid #ead58b; background:#fffaf0; color:#67561a; }
.role-attribution-note.unavailable { border:1px dashed #b8cbc5; background:#f7faf9; color:#526b66; }
.unavailable-metric { color:#6b7d79; font-weight:600; }

@media (max-width: 720px) {
  .role-attribution-heading {
    flex-direction: column;
  }

  .status-role-row {
    grid-template-columns: 1fr;
    gap: 7px;
  }

  .status-role-total {
    text-align: left;
  }

  .status-role-legend {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}

#rolling-mailbox-usage {
  scroll-margin-top: 150px;
}

#rolling-mailbox-usage:target {
  border-color: #9fd8c7;
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.08), 0 8px 22px rgba(16, 32, 27, 0.05);
}


#rolling-mailbox-usage:target {
  border-color: #9fd8c7 !important;
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.08), 0 8px 22px rgba(16, 32, 27, 0.05) !important;
}

</style>
