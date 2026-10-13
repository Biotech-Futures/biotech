<template>
  <div class="analytics-page">
    <header class="page-heading">
      <div>
        <div class="breadcrumb">
            <RouterLink to="/dashboard">Home</RouterLink>
            <span class="breadcrumb-separator">›</span>
            <span>Analytics</span>
        </div>
        <div class="title-row">
          <div>
            <h1>Analytics</h1>
            <p class="page-subtitle">Admin overview of participation, programme activity and platform usage.</p>
          </div>
          
        </div>
      </div>

      <div class="page-actions">
        <label class="date-range">
          <i class="fas fa-calendar"></i>
          <select v-model.number="selectedYear" aria-label="Analytics year">
            <option v-for="year in availableAnalyticsYears" :key="year" :value="year">
              {{ year }}
            </option>
          </select>
        </label>
        <button
          class="analytics-refresh-button"
          type="button"
          :disabled="isLoading"
          @click="refreshAnalytics"
        >
          <i class="fas fa-rotate-right" aria-hidden="true"></i>
          Refresh
        </button>
        <button class="export-button" type="button" :disabled="exportDisabled || exporting" @click="exportCsv">
          <i class="fas fa-download"></i>
          Export CSV
        </button>
      </div>
    </header>

    <p v-if="exportError" role="alert">{{ exportError }}</p>

    <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />

    <p v-if="unavailableSources.length" class="partial-data-notice" role="status">
      Some analytics modules are unavailable. Available statistics are shown below;
      unavailable values are marked with a dash. Export requires all data sources.
    </p>

    <AnalyticsDataState
      :loading="isLoading"
      :error="loadError"
      :empty="isEmpty"
      empty-message="No participant, group, resource or delivery records are available in the current database. Generate or load a dataset, then refresh this page."
      @retry="refreshAnalytics"
    >
    <section class="attention-panel">
      <div class="attention-heading">
        <div>
          <h2><i class="fas fa-triangle-exclamation"></i> Attention Required</h2>
          <p>Items worth checking before the next programme review.</p>
        </div>
        <button
          v-if="displayedAttentionItems.length"
          type="button"
          class="view-all-button"
          :aria-expanded="showAllIssues"
          aria-controls="attention-issue-details"
          @click="showAllIssues = !showAllIssues"
        >
          {{ showAllIssues ? 'Hide Issues ↑' : 'View All Issues →' }}
        </button>
      </div>

      <div v-if="displayedAttentionItems.length" class="attention-grid">
        <article
          v-for="item in displayedAttentionItems"
          :key="item.label"
          class="attention-item"
          :class="`attention-${item.tone}`"
        >
          <span class="attention-icon"><i :class="item.icon"></i></span>
          <div>
            <strong>{{ item.value }}</strong>
            <p>{{ item.label }}</p>
          </div>
        </article>
      </div>

      <div v-else class="attention-empty-state">
        <i class="fas fa-circle-check" aria-hidden="true"></i>
        <span>{{ unavailableSources.length ? 'No issues in the available data. Some modules could not be checked.' : 'No issues currently require attention.' }}</span>
      </div>

      <Transition name="issues-expand">
        <div
          v-if="showAllIssues"
          id="attention-issue-details"
          class="attention-issue-details"
        >
          <article
            v-for="issue in attentionIssueDetails"
            :key="`detail-${issue.label}`"
            class="attention-detail-row"
          >
            <div class="attention-detail-main">
              <span class="attention-detail-icon">
                <i :class="issue.icon"></i>
              </span>

              <div class="attention-detail-copy">
                <div class="attention-detail-title">
                  <strong>{{ issue.value }}</strong>
                  <span>{{ issue.label }}</span>
                </div>
                <p>{{ issue.description }}</p>
              </div>
            </div>

            <RouterLink class="attention-detail-button" :to="issue.to">
              {{ issue.action }}
              <span aria-hidden="true">→</span>
            </RouterLink>
          </article>
        </div>
      </Transition>
    </section>

    <section class="summary-grid" aria-label="Analytics summary">
      <article
        v-for="item in overviewSummary"
        :key="item.label"
        class="summary-card"
        :class="`tone-${item.tone}`"
      >
        <div class="summary-copy">
          <p class="card-label">{{ item.label }}</p>
          <strong class="summary-value">{{ item.value }}</strong>
          <span class="summary-trend">{{ item.trend || 'Current period' }}</span>
        </div>
        <div class="summary-visual">
          <small class="summary-helper">{{ item.helper }}</small>
        </div>
      </article>
    </section>

    <section class="module-grid" aria-label="Detailed analytics areas">
      <article
        v-for="module in displayedModules"
        :key="module.key"
        class="module-card"
        :class="`tone-${module.tone}`"
      >
        <div class="module-heading">
          <h2>{{ module.title }}</h2>
        </div>

        <div class="metric-line" :class="{ 'registration-metric-line': module.key === 'registration' }">
          <strong>{{ module.value }}</strong>

          <select
            v-if="module.key === 'registration'"
            v-model="registrationPeriod"
            class="module-period-select registration-value-period-select"
            aria-label="Registration chart period"
            @click.stop
          >
            <option value="day">Day</option>
            <option value="week">Week</option>
            <option value="month">Month</option>
            <option value="year">Year</option>
          </select>

          <span v-else>{{ module.unit }}</span>
        </div>
        <p v-if="!module.unavailable" class="module-helper">{{ module.helper }}</p>

        <p v-if="module.unavailable" class="module-unavailable" role="status">{{ module.helper }}</p>
        <div v-else-if="module.breakdown?.length" class="breakdown-list">
          <div
            v-for="row in module.breakdown"
            :key="row.label"
            class="breakdown-row interactive-chart-row"
            @mouseenter="showTooltip($event, row.label, row.value, module.title)"
            @mousemove="moveTooltip"
            @mouseleave="hideTooltip"
          >
            <div class="breakdown-label">
              <span>{{ row.label }}</span>
              <strong>{{ row.value }}</strong>
            </div>
            <div class="progress-track">
              <span :style="{ width: `${row.percent ?? 0}%` }"></span>
            </div>
          </div>
        </div>

        <div v-else-if="module.key === 'email'" class="quota-wrap">
          <div
            class="quota-ring interactive-chart-mark"
            :style="{ '--quota': `${module.chart[0]}%` }"
            @mouseenter="showTooltip($event, module.title, `${module.chart[0]}% of daily quota`, `${module.value} ${module.unit}`)"
            @mousemove="moveTooltip"
            @mouseleave="hideTooltip"
          >
            <strong>{{ module.chart[0] }}%</strong>
            <span>of daily quota</span>
          </div>
        </div>

        <div
          v-else-if="module.key === 'mentors'"
          class="single-progress interactive-chart-row"
          @mouseenter="showTooltip($event, module.title, `${module.chart[0]}% utilised`, `${module.value} ${module.unit}`)"
          @mousemove="moveTooltip"
          @mouseleave="hideTooltip"
        >
          <div class="progress-track large">
            <span :style="{ width: `${module.chart[0]}%` }"></span>
          </div>
          <strong>{{ module.chart[0] }}%</strong>
        </div>

        <div
          v-else-if="['registration', 'activity', 'messages'].includes(module.key)"
          class="overview-axis-chart"
        >
          <div class="overview-y-axis" aria-hidden="true">
            <span v-for="tick in moduleAxisTicks(module.chart, module.key)" :key="tick">{{ tick }}</span>
          </div>

          <div v-if="module.key === 'messages'" class="mini-bars overview-axis-plot" aria-hidden="true">
            <div
              v-for="(value, index) in module.chart"
              :key="index"
              class="overview-bar-item"
            >
              <strong
                class="overview-bar-value"
                :style="{ bottom: `calc(${moduleBarHeight(value, module.chart)}% + 3px)` }"
              >{{ value }}</strong>
              <span
                class="interactive-chart-mark overview-bar-mark"
                :style="{ height: `${moduleBarHeight(value, module.chart)}%` }"
                @mouseenter="showTooltip($event, `${module.title} · point ${index + 1}`, String(value), module.unit)"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              ></span>
            </div>
          </div>

          <div v-else class="mini-line-wrap overview-axis-plot" aria-hidden="true">
            <svg viewBox="0 0 200 70" class="module-line">
              <polyline
                :points="axisLinePoints(module.chart, 200, 70)"
                fill="none"
                stroke="currentColor"
                stroke-width="3"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <g
                v-for="point in axisLinePointObjects(module.chart, 200, 70)"
                :key="point.index"
              >
                <text
                  :x="point.x"
                  :y="point.y < 18 ? point.y + 14 : point.y - 7"
                  text-anchor="middle"
                  class="overview-point-value"
                >{{ point.value }}</text>
                <circle
                  :cx="point.x"
                  :cy="point.y"
                  r="4"
                  class="module-line-point interactive-svg-point"
                  @mouseenter="showTooltip($event, `${module.title} · ${modulePointLabel(module.key, point.index)}`, String(point.value), module.unit)"
                  @mousemove="moveTooltip"
                  @mouseleave="hideTooltip"
                />
              </g>
              <line x1="0" y1="62" x2="200" y2="62" class="line-baseline" />
            </svg>
          </div>
        </div>

        <div v-else class="mini-line-wrap" aria-hidden="true">
          <svg viewBox="0 0 200 70" class="module-line">
            <polyline
              :points="linePoints(module.chart, 200, 70)"
              fill="none"
              stroke="currentColor"
              stroke-width="3"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <circle
              v-for="point in linePointObjects(module.chart, 200, 70)"
              :key="point.index"
              :cx="point.x"
              :cy="point.y"
              r="4"
              class="module-line-point interactive-svg-point"
              @mouseenter="showTooltip($event, `${module.title} · point ${point.index + 1}`, String(point.value), module.unit)"
              @mousemove="moveTooltip"
              @mouseleave="hideTooltip"
            />
            <line x1="0" y1="62" x2="200" y2="62" class="line-baseline" />
          </svg>
        </div>

        <div class="module-footer">
        <button
            type="button"
            class="view-details-button"
            @click.stop.prevent="handleViewDetails(module.key)"
            >
            View details
            <span>→</span>
        </button>

        </div>
      </article>
    </section>


    <transition name="toast">
      <div v-if="selectedModule" class="analytics-toast">
        {{ selectedModule }} detail page can be connected next.
      </div>
    </transition>

    <ChartTooltip
      :visible="tooltip.visible"
      :x="tooltip.x"
      :y="tooltip.y"
      :title="tooltip.title"
      :value="tooltip.value"
      :detail="tooltip.detail"
    />
    </AnalyticsDataState>
</div>
</template>

<script setup lang="ts">
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AnalyticsDataState from '@/components/analytics/AnalyticsDataState.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import type { AnalyticsYearData } from '@/types/analytics'
import {
  buildOverviewAnalytics,
  buildRegistrationAnalytics,
  liveAnalyticsYear,
  loadOverviewAnalyticsBundle,
  type OverviewAnalyticsBundle,
} from '@/utils/liveAnalyticsData'
import { useRouter } from 'vue-router'
import { downloadReportCsv } from '@/utils/reportExport'

const currentYear = new Date().getFullYear()
const availableAnalyticsYears = ref<number[]>([currentYear])
const selectedYear = ref(currentYear)
const selectedData = ref<AnalyticsYearData>({ summary: [], modules: [], attention: [] })
const registrationTrend = ref<Array<{ date: string; students: number; mentors: number }>>([])
const loadError = ref('')
const isLoading = ref(true)
const isEmpty = ref(false)
const hasLoaded = ref(false)
const exporting = ref(false)
const exportError = ref('')
const unavailableSources = ref<string[]>([])
const exportDisabled = computed(() => isLoading.value || !!loadError.value || isEmpty.value || !hasLoaded.value || selectedData.value.modules.some((module) => module.unavailable))

const overviewSummary = computed(() => {
  const originalSummary = selectedData.value.summary
  const participants = originalSummary.find((item) => item.label === 'Total Participants')
  const loggedIn = originalSummary.find((item) => item.label === 'Logged In')
  const helper = participants?.helper ?? ''

  const readCount = (pattern: RegExp) => {
    const match = helper.match(pattern)
    return participants?.unavailable ? '—' : match ? Number(match[1]) : 0
  }

  return [
    {
      label: 'Total Students',
      value: readCount(/(\d+)\s*students?/i),
      trend: `${selectedYear.value}`,
      helper: 'Registered student participants',
      icon: 'fas fa-user',
      tone: 'green',
      source: 'live-api',
    },
    {
      label: 'Total Mentors',
      value: readCount(/(\d+)\s*mentors?/i),
      trend: `${selectedYear.value}`,
      helper: 'Registered mentors',
      icon: 'fas fa-user-tie',
      tone: 'green',
      source: 'live-api',
    },
    {
      label: 'Total Supervisors',
      value: readCount(/(\d+)\s*supervisors?/i),
      trend: `${selectedYear.value}`,
      helper: 'Registered supervisors',
      icon: 'fas fa-user-shield',
      tone: 'green',
      source: 'live-api',
    },
    loggedIn
      ? { ...loggedIn, icon: 'fas fa-chart-line' }
      : {
          label: 'Logged In', value: '—', trend: `${selectedYear.value}`,
          helper: 'No login data available', icon: 'fas fa-chart-line', tone: 'green', source: 'live-api',
        },
  ]
})

const registrationPeriod = ref<'day' | 'week' | 'month' | 'year'>('year')

const dateLabel = (date: Date, options: Intl.DateTimeFormatOptions) =>
  date.toLocaleDateString('en-AU', { ...options, timeZone: 'UTC' })

const registrationPeriodData = computed(() => {
  const counts = new Map<string, number>()
  for (const row of registrationTrend.value) {
    counts.set(row.date, row.students + row.mentors)
  }
  const dates = [...counts.keys()].sort()
  const fallbackDate = new Date(Date.UTC(selectedYear.value, 11, 31))
  const latest = dates.length ? new Date(`${dates[dates.length - 1]}T00:00:00Z`) : fallbackDate

  if (registrationPeriod.value === 'year') {
    const byYear = new Map<number, number>()
    for (const [date, value] of counts) {
      const year = Number(date.slice(0, 4))
      byYear.set(year, (byYear.get(year) ?? 0) + value)
    }
    const years = [...byYear.keys()].sort((a, b) => a - b)
    return {
      values: years.map((year) => byYear.get(year) ?? 0),
      labels: years.map(String),
      unit: 'latest year',
      helper: 'Account creation dates for current participants by year.',
    }
  }

  if (registrationPeriod.value === 'month') {
    const endMonth = latest.getUTCFullYear() === selectedYear.value ? latest.getUTCMonth() + 1 : 12
    const values = Array.from({ length: endMonth }, () => 0)
    for (const [date, value] of counts) {
      const parsed = new Date(`${date}T00:00:00Z`)
      if (parsed.getUTCFullYear() === selectedYear.value && parsed.getUTCMonth() < values.length) values[parsed.getUTCMonth()]! += value
    }
    return {
      values,
      labels: Array.from({ length: endMonth }, (_, month) =>
        new Date(Date.UTC(selectedYear.value, month, 1)).toLocaleDateString('en-AU', { month: 'short', timeZone: 'UTC' }),
      ),
      unit: 'latest month',
      helper: `Monthly registrations stored for ${selectedYear.value}.`,
    }
  }

  const days = registrationPeriod.value === 'week' ? 56 : 7
  const bucketDays = registrationPeriod.value === 'week' ? 7 : 1
  const bucketCount = Math.ceil(days / bucketDays)
  const values = Array.from({ length: bucketCount }, () => 0)
  const labels: string[] = []

  for (let index = 0; index < bucketCount; index += 1) {
    const bucketEnd = new Date(latest)
    bucketEnd.setUTCDate(latest.getUTCDate() - (bucketCount - 1 - index) * bucketDays)
    const bucketStart = new Date(bucketEnd)
    bucketStart.setUTCDate(bucketEnd.getUTCDate() - bucketDays + 1)
    for (const [date, value] of counts) {
      const parsed = new Date(`${date}T00:00:00Z`)
      if (parsed >= bucketStart && parsed <= bucketEnd) values[index] += value
    }
    labels.push(
      bucketDays === 1
        ? dateLabel(bucketEnd, { day: '2-digit', month: 'short' })
        : `${dateLabel(bucketStart, { day: '2-digit', month: 'short' })} – ${dateLabel(bucketEnd, { day: '2-digit', month: 'short' })}`,
    )
  }

  return {
    values,
    labels,
    unit: registrationPeriod.value === 'week' ? 'latest week' : 'latest day',
    helper: registrationPeriod.value === 'week'
      ? 'New registrations over the most recent 8 database weeks.'
      : 'New registrations over the most recent 7 database days.',
  }
})

const recentSevenDayLabels = computed(() => {
  const activityModule = selectedData.value.modules.find((item) => item.key === 'activity')
  const length = activityModule?.chart.length ?? 7
  return Array.from({ length }, (_, index) => `Day ${index + 1}`)
})
const recentSevenDayLabel = (index: number) => recentSevenDayLabels.value[index] ?? `Day ${index + 1}`

const modulePointLabel = (key: string, index: number) => {
  if (key === 'registration') return registrationPeriodData.value.labels[index] ?? `Point ${index + 1}`
  if (key === 'activity') return recentSevenDayLabel(index)
  return `Point ${index + 1}`
}

const displayedModules = computed(() =>
  selectedData.value.modules.map((module) => {
    if (module.unavailable) return { ...module, icon: moduleIcons[module.key] ?? module.icon }
    if (module.key === 'registration') {
      const period = registrationPeriodData.value
      return {
        ...module,
        icon: moduleIcons[module.key] ?? module.icon,
        chart: period.values,
        value: period.values[period.values.length - 1] ?? 0,
        title: 'New Registrations',
        unit: period.unit,
        helper: period.helper,
      }
    }
    if (module.key === 'activity') {
      return {
        ...module,
        icon: moduleIcons[module.key] ?? module.icon,
        value: module.chart[module.chart.length - 1] ?? module.value,
        unit: 'Daily Active',
        helper: 'Daily active users over the most recent 7 database days.',
      }
    }
    if (module.key === 'groups') {
      const withMentor = module.breakdown?.find((item) => item.label.toLowerCase().includes('with mentor'))
      return {
        ...module,
        icon: moduleIcons[module.key] ?? module.icon,
        title: 'Groups',
        value: module.value,
        unit: 'groups',
        helper: withMentor ? `${withMentor.value} groups currently have a mentor.` : module.helper,
      }
    }
    if (module.key === 'mentors') {
      return { ...module, icon: moduleIcons[module.key] ?? module.icon, title: 'Mentor Coverage' }
    }
    return { ...module, icon: moduleIcons[module.key] ?? module.icon }
  }),
)

function overviewBundleIsEmpty(bundle: OverviewAnalyticsBundle) {
  const hasParticipants = bundle.users.some((user) =>
    ['student', 'mentor', 'supervisor'].includes((user.role ?? '').toLowerCase()),
  )
  const hasResourceActivity = bundle.resourceAnalytics.total_clicks > 0
    || bundle.resourceAnalytics.unique_users > 0
    || bundle.resourceAnalytics.active_resources > 0
    || bundle.resourceAnalytics.top_resources.length > 0
    || bundle.resourceAnalytics.clicks_by_day.length > 0
  const hasEmailActivity = bundle.emailAnalytics.recent_deliveries.length > 0
    || bundle.emailAnalytics.mailboxes.some((mailbox) =>
      mailbox.totals.attempted > 0
      || mailbox.totals.delivered > 0
      || mailbox.totals.failed > 0
      || mailbox.totals.delivery_runs > 0,
    )
  return !hasParticipants
    && bundle.groups.length === 0
    && bundle.resources.length === 0
    && !hasResourceActivity
    && !hasEmailActivity
}

const analyticsRefreshBusy = ref(false)
const { lastUpdated, refreshFailed, markUpdated, markRefreshFailed } = useAnalyticsRefresh(async () => { if (!analyticsRefreshBusy.value) await loadAnalytics(true, true) })

async function loadAnalytics(force = false, preserveFilters = false) {
  if (analyticsRefreshBusy.value) return
  analyticsRefreshBusy.value = true
  if (!preserveFilters || !lastUpdated.value) isLoading.value = true
  loadError.value = ''
  try {
    const bundle = await loadOverviewAnalyticsBundle(force)
    unavailableSources.value = bundle.unavailableSources ?? []
    const year = liveAnalyticsYear(bundle)
    selectedYear.value = year
    availableAnalyticsYears.value = [year]
    selectedData.value = buildOverviewAnalytics(bundle)
    registrationTrend.value = buildRegistrationAnalytics(bundle).trend
    isEmpty.value = unavailableSources.value.length === 0 && overviewBundleIsEmpty(bundle)
    hasLoaded.value = true
    markUpdated()
  } catch (error) {
    if (preserveFilters && lastUpdated.value) { markRefreshFailed(); return }
    console.error('Failed to load analytics overview from the backend.', error)
    loadError.value = 'Analytics data could not be loaded from the backend. Check the API and try again.'
    hasLoaded.value = false
  } finally {
    analyticsRefreshBusy.value = false
    isLoading.value = false
  }
}

function refreshAnalytics() {
  return loadAnalytics(true)
}

onMounted(() => loadAnalytics())

const moduleIcons: Record<string, string> = {
  registration: 'fas fa-user-plus',
  users: 'fas fa-user',
  groups: 'fas fa-users',
  mentors: 'fas fa-user-tie',
  activity: 'fas fa-wave-square',
  messages: 'fas fa-comments',
  resources: 'fas fa-book',
  email: 'fas fa-envelope-circle-check',
}

const attentionIcons: Record<string, string> = {
  'Students not assigned to groups': 'fas fa-user-plus',
  'Groups without mentors': 'fas fa-users',
  'Inactive mentors': 'fas fa-user-tie',
  'Deactivated accounts': 'fas fa-user',
  'Missing guardian details': 'fas fa-user-shield',
  'Guardian approvals pending': 'fas fa-user-check',
  'Email usage approaching limit': 'fas fa-envelope-circle-check',
}

const displayedAttentionItems = computed(() =>
  selectedData.value.attention.map((item) => ({
    ...item,
    icon: attentionIcons[item.label] ?? 'fas fa-circle-exclamation',
  })),
)

const showAllIssues = ref(false)

const attentionIssueMeta: Record<
  string,
  {
    description: (value: number | string) => string
    action: string
    to: string
  }
> = {
  'Students not assigned to groups': {
    description: (value) =>
      `${value} students currently need a group assignment. Review group structure and allocation to identify where they can be placed.`,
    action: 'Review Groups',
    to: '/analytics/groups#students-not-assigned',
  },
  'Groups without mentors': {
    description: (value) =>
      `${value} groups currently have no mentor assigned. Review group allocation and mentor coverage.`,
    action: 'Review Groups',
    to: '/analytics/groups#groups-without-mentors',
  },
  'Inactive mentors': {
    description: (value) =>
      `${value} mentors are currently inactive. Review mentor status, allocation and recent engagement.`,
    action: 'Review Mentors',
    to: '/analytics/activity?role=Mentor&issue=inactive-mentors#user-activity-details',
  },
  'Deactivated accounts': {
    description: (value) =>
      `${value} user accounts are deactivated. Review user status and account activity.`,
    action: 'Review Users',
    to: '/analytics/activity?issue=deactivated#user-activity-details',
  },
  'Missing guardian details': {
    description: (value) =>
      `${value} registration records are missing guardian details and may require follow-up.`,
    action: 'Review Registration',
    to: '/analytics/registration?issue=missing_guardian#registration-follow-up',
  },
  'Guardian approvals pending': {
    description: (value) =>
      `${value} guardian approvals are still pending. Review registration completion and follow-up records.`,
    action: 'Review Registration',
    to: '/analytics/registration?issue=awaiting_approval#registration-follow-up',
  },
  'Email usage approaching limit': {
    description: () =>
      'Rolling 24-hour email usage is approaching the sending limit. Review current email usage before sending more messages.',
    action: 'Review Email Usage',
    to: '/analytics/email#rolling-mailbox-usage',
  },
}

const attentionIssueDetails = computed(() =>
  displayedAttentionItems.value.map((item) => {
    const meta = attentionIssueMeta[item.label]

    return {
      ...item,
      description:
        meta?.description(item.value) ??
        `${item.value} records currently require attention in this analytics area.`,
      action: meta?.action ?? 'View Details',
      to: meta?.to ?? '/analytics',
    }
  }),
)
const selectedModule = ref('')
const tooltip = ref({
  visible: false,
  x: 0,
  y: 0,
  title: '',
  value: '',
  detail: '',
})

const showTooltip = (event: MouseEvent, title: string, value: string, detail = '') => {
  tooltip.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    title,
    value,
    detail,
  }
}

const moveTooltip = (event: MouseEvent) => {
  tooltip.value.x = event.clientX
  tooltip.value.y = event.clientY
}

const hideTooltip = () => {
  tooltip.value.visible = false
}

let toastTimer: number | undefined

const linePoints = (values: number[], width: number, height: number) => {
  if (!values.length) return ''
  const max = Math.max(...values, 1)
  const min = Math.min(...values)
  const range = Math.max(max - min, 1)
  return values
    .map((value, index) => {
      const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width
      const y = height - 10 - ((value - min) / range) * (height - 24)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

const linePointObjects = (values: number[], width: number, height: number) => {
  if (!values.length) return []
  const max = Math.max(...values, 1)
  const min = Math.min(...values)
  const range = Math.max(max - min, 1)

  return values.map((value, index) => ({
    index,
    value,
    x: values.length === 1 ? width / 2 : (index / (values.length - 1)) * width,
    y: height - 10 - ((value - min) / range) * (height - 24),
  }))
}


const niceStep = (range: number) => {
  const safeRange = Math.max(range, 1)
  const roughStep = safeRange / 2
  const magnitude = 10 ** Math.floor(Math.log10(roughStep))
  const normalised = roughStep / magnitude

  if (normalised <= 1) return 1 * magnitude
  if (normalised <= 2) return 2 * magnitude
  if (normalised <= 5) return 5 * magnitude
  return 10 * magnitude
}

const moduleAxisRange = (values: number[], key?: string) => {
  if (!values.length) return { min: 0, max: 10, mid: 5 }

  const rawMin = Math.min(...values)
  const rawMax = Math.max(...values)

  // Bars should keep a zero baseline so their height remains visually honest.
  if (key === 'messages') {
    const step = niceStep(rawMax)
    const max = Math.ceil(rawMax / step) * step
    return { min: 0, max, mid: max / 2 }
  }

  // For the line cards, use a rounded lower bound close to the data minimum.
  // This avoids wasting most of the small chart on an unused 0–40 range while
  // still keeping some visual room below the lowest point.
  const spread = Math.max(rawMax - rawMin, 1)
  const step = niceStep(spread)
  const min = Math.floor(rawMin / step) * step
  let max = Math.ceil(rawMax / step) * step

  if (min === max) max = min + step

  // Give the top label a little breathing room if the maximum lands exactly
  // on the top tick.
  if (rawMax >= max) max += step

  return { min, max, mid: min + (max - min) / 2 }
}

const axisLinePoints = (values: number[], width: number, height: number) => {
  if (!values.length) return ''
  const { min, max } = moduleAxisRange(values)
  const plotTop = 8
  const baseline = height - 8
  const plotHeight = baseline - plotTop
  // Keep the first and last points slightly inside the SVG so value labels
  // are not clipped by the card edge.
  const plotLeft = 10
  const plotRight = width - 18
  const range = Math.max(max - min, 1)

  return values
    .map((value, index) => {
      const x = values.length === 1
        ? width / 2
        : plotLeft + (index / (values.length - 1)) * (plotRight - plotLeft)
      const y = baseline - ((value - min) / range) * plotHeight
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

const axisLinePointObjects = (values: number[], width: number, height: number) => {
  if (!values.length) return []
  const { min, max } = moduleAxisRange(values)
  const plotTop = 8
  const baseline = height - 8
  const plotHeight = baseline - plotTop
  // Keep the first and last points slightly inside the SVG so value labels
  // are not clipped by the card edge.
  const plotLeft = 10
  const plotRight = width - 18
  const range = Math.max(max - min, 1)

  return values.map((value, index) => ({
    index,
    value,
    x: values.length === 1
      ? width / 2
      : plotLeft + (index / (values.length - 1)) * (plotRight - plotLeft),
    y: baseline - ((value - min) / range) * plotHeight,
  }))
}

const moduleAxisTicks = (values: number[], key?: string) => {
  const { min, max, mid } = moduleAxisRange(values, key)
  return [Math.round(max), Math.round(mid), Math.round(min)]
}

const moduleBarHeight = (value: number, values: number[]) => {
  const { max } = moduleAxisRange(values, 'messages')
  return Math.max(8, (value / max) * 100)
}

const router = useRouter()

const handleViewDetails = async (key: string) => {
  if (key === 'registration') {
    await router.push('/analytics/registration')
    return
  }

  if (key === 'users') {
    await router.push('/analytics/users')
    return
  }

  if (key === 'groups') {
    await router.push('/analytics/groups')
    return
  }

  if (key === 'mentors') {
    await router.push('/analytics/mentors')
    return
  }

  if (key === 'activity') {
    await router.push('/analytics/activity')
    return
  }

  if (key === 'messages') {
    await router.push('/analytics/messages')
    return
  }

  if (key === 'resources') {
    await router.push('/analytics/resources')
    return
  }

  if (key === 'email') {
    await router.push('/analytics/email')
    return
  }

  window.alert('This analytics page is not available yet.')
}

const exportCsv = async () => {
  exporting.value = true
  exportError.value = ''
  try {
    await downloadReportCsv(new URLSearchParams({
      report: 'overview', year: String(selectedYear.value), registration_period: registrationPeriod.value,
    }), 'overview')
  } catch (error) {
    exportError.value = error instanceof Error ? error.message : 'The report could not be downloaded.'
  } finally {
    exporting.value = false
  }
}

onBeforeUnmount(() => window.clearTimeout(toastTimer))
</script>

<style src="@/assets/analytics-theme.css">
.overview-point-value {
  fill: #173f43;
  font-size: 8px;
  font-weight: 800;
  pointer-events: none;
}
.overview-axis-chart .mini-bars {
  overflow: visible;
}
.overview-bar-item {
  position: relative;
  flex: 1 1 0;
  max-width: 30px;
  height: 78px;
}
.overview-bar-item .overview-bar-mark {
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 100%;
  max-width: 26px;
  min-height: 8px;
  transform: translateX(-50%);
}
.overview-bar-value {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  color: #173f43;
  font-size: 9px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
  pointer-events: none;
}


/* Registration period selector sits beside the main registration value. */
.registration-metric-line {
  display: flex;
  align-items: center;
  gap: 12px;
}

.registration-value-period-select {
  width: 92px;
  min-width: 92px;
  height: 40px;
  padding: 0 32px 0 12px;
  border: 1px solid #BAD7B8;
  border-radius: 10px;
  background: #FFFFFF;
  color: #174243;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

</style>

<style scoped>

.module-heading {
  align-items: flex-start;
}

.module-period-select {
  height: 32px;
  padding: 0 26px 0 9px;
  border: 1px solid #bad7b8;
  border-radius: 9px;
  background: #ffffff;
  color: #174243;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.module-period-select:focus {
  outline: 2px solid rgba(1, 113, 81, 0.16);
  outline-offset: 1px;
}
.view-details-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;

  min-width: 116px;
  height: 40px;
  padding: 0 16px;

  border: 1px solid #9ea9a7;
  border-radius: 8px;

  background: #ffffff;
  color: #243f3c;

  font-size: 14px;
  font-weight: 500;
  text-decoration: none;

  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    transform 0.15s ease;
}

.view-details-button:hover {
  background: #f4f8f7;
  border-color: #017151;
  color: #017151;
  text-decoration: none;
}

.view-details-button:active {
  transform: translateY(1px);
}

.analytics-page {
  padding: 28px 32px 40px;
  min-height: 100%;
  background: #f7faf9;
  color: #153f3c;
}


.analytics-breadcrumb {
  margin: 0 0 14px;
  color: #53675f;
  font-size: 0.9rem;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.title-row h1 {
  margin: 0;
  color: #163f3c;
  font-size: 36px;
  line-height: 1.15;
  font-weight: 800;
}

.page-subtitle {
  margin: 8px 0 0;
  color: #617572;
  font-size: 16px;
  line-height: 1.45;
}

.demo-badge,
.mock-label {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 9px;
  background: #fff6dd;
  color: #174243;
  border: 1px solid #F1E5A6;
  font-size: 0.72rem;
  font-weight: 700;
}


.date-range {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  width: 120px;
  height: 46px;
  padding: 0 13px;
  border: 1px solid #d7e3e0;
  border-radius: 12px;
  background: #ffffff;
  color: #174243;
  font-size: 14px;
  font-weight: 700;
}

.date-range select {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.export-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 142px;
  height: 46px;
  padding: 0 16px;
  border: 1px solid #5EA99E;
  border-radius: 12px;
  background: #ffffff;
  color: #017151;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;
}

.export-button:hover {
  background: #ecf8f4;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.summary-card,
.module-card {
  background: #fff;
  border: 1px solid #e1e9e6;
  border-radius: 12px;
  box-shadow: 0 8px 22px rgba(16, 32, 27, 0.035);
}

.summary-card {
  min-height: 94px;
  padding: 12px 14px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.summary-copy {
  display: flex;
  flex-direction: column;
}

.card-label {
  margin: 0;
  color: #4d6461;
  font-size: 14px;
  font-weight: 700;
}

.summary-value {
  margin-top: 5px;
  font-size: clamp(2rem, 2.4vw, 2.75rem);
  line-height: 1;
  color: #12261f;
}

.summary-trend {
  margin-top: 7px;
  color: currentColor;
  font-size: 0.76rem;
  font-weight: 700;
}

.summary-visual {
  min-width: 112px;
  max-width: 138px;
  display: flex;
  align-items: flex-end;
  flex-direction: column;
  justify-content: space-between;
  gap: 8px;
}

.summary-helper {
  margin-top: auto;
  color: #7a8984;
  font-size: 0.66rem;
  line-height: 1.28;
  text-align: right;
}

.attention-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: color-mix(in srgb, currentColor 11%, white);
}

.sparkline {
  width: 104px;
  height: 34px;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.module-card {
  min-height: 268px;
  padding: 18px;
  display: flex;
  flex-direction: column;
}

.module-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.module-heading h2 {
  margin: 0;
  color: #163f3c;
  font-size: 18px;
  font-weight: 700;
}

.metric-line {
  display: flex;
  align-items: baseline;
  gap: 7px;
  margin-top: 12px;
}

.metric-line strong {
  color: #10201b;
  font-size: 2rem;
  line-height: 1;
}

.metric-line span {
  color: #52655e;
  font-size: 14px;
}

.module-helper {
  margin: 7px 0 12px;
  min-height: 38px;
  color: #617572;
  font-size: 13px;
  line-height: 1.4;
}

.breakdown-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-top: 2px;
}

.breakdown-label {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: #40544d;
  font-size: 13px;
}

.progress-track {
  position: relative;
  height: 7px;
  overflow: hidden;
  border-radius: 999px;
  background: #e9eeec;
}

.progress-track.large {
  height: 16px;
}

.progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: currentColor;
}

.single-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 24px;
}

.single-progress .progress-track {
  flex: 1;
}

.mini-bars {
  height: 80px;
  margin: 3px 0 0;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
}

.mini-bars span {
  flex: 1;
  max-width: 26px;
  min-height: 12px;
  border-radius: 3px 3px 0 0;
  background: color-mix(in srgb, currentColor 72%, white);
}

.mini-line-wrap {
  flex: 1;
  display: flex;
  align-items: flex-end;
}

.module-line {
  width: 100%;
  height: 82px;
  overflow: visible;
}

.line-baseline {
  stroke: #dce6e2;
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

.quota-wrap {
  flex: 1;
  display: grid;
  place-items: center;
}

.quota-ring {
  --quota: 62%;
  width: 88px;
  aspect-ratio: 1;
  border-radius: 50%;
  display: grid;
  place-items: center;
  align-content: center;
  background: conic-gradient(currentColor var(--quota), #edf0ef 0);
  position: relative;
  isolation: isolate;
}

.quota-ring::after {
  content: '';
  position: absolute;
  inset: 12px;
  border-radius: 50%;
  background: #fff;
}

.quota-ring strong,
.quota-ring span {
  position: relative;
  z-index: 2;
}

.quota-ring strong {
  font-size: 1.35rem;
}

.quota-ring span {
  margin-top: -4px;
  color: #6a7974;
  font-size: 0.58rem;
}

.module-footer {
  margin-top: auto;
  padding-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.details-button,
.view-all-button {
  border: 1px solid color-mix(in srgb, currentColor 45%, white);
  border-radius: 7px;
  background: color-mix(in srgb, currentColor 7%, white);
  color: #2f3440;
  font-size: 0.72rem;
  cursor: pointer;
}

.details-button {
  padding: 8px 11px;
}

.details-button:hover {
  transform: translateY(-1px);
}

.attention-panel {
  margin-top: 0;
  margin-bottom: 18px;
  padding: 12px 13px 13px;
  border: 1px solid #BAD7B8;
  border-radius: 11px;
  background: #fff9f9;
}

.attention-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 9px;
}

.attention-heading h2 {
  margin: 0;
  font-size: 0.92rem;
  color: #273a34;
}

.attention-heading h2 i {
  color: #017151;
  margin-right: 7px;
}

.attention-heading p {
  margin: 3px 0 0;
  color: #7c8884;
  font-size: 0.68rem;
}

.view-all-button {
  padding: 7px 10px;
  color: #017151;
}

.attention-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 7px;
}

.attention-item {
  position: relative;
  min-height: 66px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 9px;
  border: 1px solid #ebefed;
  border-radius: 8px;
  background: #fff;
}

.attention-icon {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
}

.attention-item strong {
  font-size: 0.86rem;
}

.attention-item p {
  margin: 2px 0 0;
  color: #687872;
  font-size: 0.59rem;
  line-height: 1.2;
}

.mock-dot {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #F1E5A6;
  color: #174243;
  font-size: 0.5rem;
  font-weight: 800;
}

.tone-blue { color: #39687B; }
.tone-purple { color: #5EA99E; }
.tone-teal { color: #174243; }
.tone-orange { color: #017151; }
.attention-red { color: #174243; }
.attention-orange { color: #017151; }
.attention-purple { color: #5EA99E; }
.attention-blue { color: #39687B; }
.attention-teal { color: #174243; }

.analytics-toast {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 50;
  padding: 11px 14px;
  border-radius: 9px;
  background: #173029;
  color: #fff;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
  font-size: 0.8rem;
}

.toast-enter-active,
.toast-leave-active { transition: 0.2s ease; }
.toast-enter-from,
.toast-leave-to { opacity: 0; transform: translateY(8px); }


.interactive-chart-mark,
.interactive-chart-row,
.interactive-svg-point {
  cursor: pointer;
}

.interactive-chart-mark {
  transition: filter 0.15s ease, opacity 0.15s ease;
}

.interactive-chart-mark:hover {
  filter: brightness(0.94) saturate(1.08);
}

.interactive-chart-row {
  transition: background-color 0.15s ease;
}

.interactive-chart-row:hover {
  background: rgba(236, 248, 244, 0.62);
}

.module-line-point {
  fill: currentColor;
  stroke: #ffffff;
  stroke-width: 2;
}

@media (max-width: 1200px) {
  .summary-grid,
  .module-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .attention-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}

@media (max-width: 760px) {
  .analytics-page { padding: 18px 14px 24px; }
  .page-heading { grid-template-columns: 1fr; }
  .page-actions { width: 100%; flex-wrap: wrap; }
  .date-range { flex: 1; }
  .summary-grid,
  .module-grid,
  .attention-grid { grid-template-columns: 1fr; }
  .summary-card { min-height: 94px; }
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

.breadcrumb-separator {
  color: #9aaaa7;
}

.page-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 24px;
  margin-bottom: 22px;
}

.page-heading h1 {
  margin: 0;
  color: #163f3c;
  font-size: 36px;
  line-height: 1.15;
  font-weight: 800;
}

.page-heading p {
  margin: 8px 0 0;
  color: #617572;
  font-size: 16px;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  align-self: start;
  margin: 0;
  flex-shrink: 0;
}

/* BTF overview chart colours: use tertiary palette so charts are visually
   separated from the primary dark-green KPI treatment. */
.module-card.tone-blue .mini-bars span,
.module-card.tone-blue .module-line {
  color: #39687B !important;
}
.module-card.tone-purple .mini-bars span,
.module-card.tone-purple .module-line {
  color: #5EA99E !important;
}
.module-card.tone-teal .mini-bars span,
.module-card.tone-teal .module-line {
  color: #174243 !important;
}
.module-card.tone-orange .mini-bars span,
.module-card.tone-orange .module-line {
  color: #39687B !important;
}

.module-card .mini-bars span {
  background: currentColor !important;
}

/* Issue controls use official brand colours only. */
.view-all-button {
  color: #017151 !important;
  border-color: #BAD7B8 !important;
  background: #FFFFFF !important;
}
.view-all-button:hover {
  background: #BAD7B8 !important;
}

.overview-axis-chart { display:grid; grid-template-columns:28px minmax(0,1fr); gap:8px; align-items:stretch; min-height:82px; margin-top:8px; }
.overview-y-axis { display:flex; flex-direction:column; justify-content:space-between; padding:2px 0 8px; color:#6b7b77; font-size:10px; text-align:right; }
.overview-axis-plot { min-width:0; }
.overview-axis-chart .mini-bars { height:78px; align-items:end; }
.overview-axis-chart .mini-line-wrap { margin-top:0; }

.overview-point-value {
  fill: #173f43;
  font-size: 8px;
  font-weight: 800;
  pointer-events: none;
}
.overview-axis-chart .mini-bars {
  overflow: visible;
}
.overview-bar-item {
  position: relative;
  flex: 1 1 0;
  max-width: 30px;
  height: 78px;
}
.overview-bar-item .overview-bar-mark {
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 100%;
  max-width: 26px;
  min-height: 8px;
  transform: translateX(-50%);
}
.overview-bar-value {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  color: #173f43;
  font-size: 9px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
  pointer-events: none;
}



/* Expandable Attention Required details */
.attention-issue-details {
  display: grid;
  gap: 8px;
  margin-top: 11px;
  padding-top: 11px;
  border-top: 1px solid #e1e9e6;
}

.attention-detail-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
  min-height: 72px;
  padding: 12px 14px;
  border: 1px solid #e4ebe8;
  border-radius: 10px;
  background: #ffffff;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease;
}

.attention-detail-row:hover {
  border-color: #bad7b8;
  box-shadow: 0 6px 16px rgba(23, 66, 67, 0.06);
}

.attention-detail-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.attention-detail-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border-radius: 10px;
  background: #e4f0e2;
  color: #017151;
  font-size: 15px;
}

.attention-detail-copy {
  min-width: 0;
}

.attention-detail-title {
  display: flex;
  align-items: baseline;
  gap: 9px;
  color: #163f3c;
}

.attention-detail-title strong {
  color: #017151;
  font-size: 18px;
  line-height: 1;
}

.attention-detail-title span {
  font-size: 13px;
  font-weight: 700;
}

.attention-detail-copy p {
  margin: 4px 0 0;
  max-width: 820px;
  color: #687872;
  font-size: 11px;
  line-height: 1.4;
}

.attention-detail-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 126px;
  height: 36px;
  padding: 0 12px;
  border: 1px solid #9fd8c7;
  border-radius: 8px;
  background: #ffffff;
  color: #017151;
  font-size: 11px;
  font-weight: 700;
  text-decoration: none;
  white-space: nowrap;
}

.attention-detail-button:hover {
  border-color: #017151;
  background: #ecf8f4;
  color: #017151;
  text-decoration: none;
}

.issues-expand-enter-active,
.issues-expand-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.issues-expand-enter-from,
.issues-expand-leave-to {
  opacity: 0;
  transform: translateY(-5px);
}

@media (max-width: 760px) {
  .attention-detail-row {
    grid-template-columns: 1fr;
  }

  .attention-detail-button {
    width: 100%;
  }

  .attention-detail-title {
    align-items: flex-start;
    flex-direction: column;
    gap: 3px;
  }
}



/* Compact expanded issue cards */
.attention-issue-details {
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 10px !important;
}

.attention-detail-row {
  grid-template-columns: 1fr !important;
  align-content: space-between !important;
  min-height: 150px !important;
  padding: 14px !important;
  gap: 12px !important;
}

.attention-detail-main {
  align-items: flex-start !important;
}

.attention-detail-copy p {
  max-width: none !important;
}

.attention-detail-button {
  width: 100% !important;
  min-width: 0 !important;
  justify-self: stretch !important;
}

@media (max-width: 1100px) {
  .attention-issue-details {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }
}

@media (max-width: 680px) {
  .attention-issue-details {
    grid-template-columns: 1fr !important;
  }
}


.attention-empty-state {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 54px;
  padding: 11px 13px;
  border: 1px solid #e1e9e6;
  border-radius: 9px;
  background: #f7fbf9;
  color: #4f6964;
  font-size: 12px;
  font-weight: 700;
}

.attention-empty-state i {
  color: #017151;
}

</style>
