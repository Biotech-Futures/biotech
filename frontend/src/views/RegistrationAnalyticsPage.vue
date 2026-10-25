<template>
  <section class="registration-analytics-page">
    <header class="page-heading">
      <div class="heading-copy">
        <div class="breadcrumb">
          <RouterLink to="/dashboard">Home</RouterLink>
          <span aria-hidden="true">›</span>
          <RouterLink to="/analytics">Analytics</RouterLink>
          <span aria-hidden="true">›</span>
          <span>Registration</span>
        </div>
        <div class="title-line">
          <h1>Registration Analytics</h1>
          
        </div>
        <p>Monitor account creation, guardian completion and records that need follow-up.</p>
      </div>

      <div class="page-actions">
        <div class="analytics-export-stack">
          <AnalyticsExportMenu :options="[SUMMARY_OPTION, DETAILS_OPTION]" :disabled="exportDisabled" @select="exportCsv" />
          <div class="analytics-update-status">
            <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />
          </div>
        </div>
      </div>
    </header>

    <p v-if="exportError" role="alert">{{ exportError }}</p>

    <AnalyticsDataState
      :loading="isLoading"
      :error="loadError"
      :empty="isEmpty"
      empty-message="No student or mentor registration records are available in the current database. Generate or load a dataset, then refresh this page."
      @retry="refreshAnalytics"
    >
    <section class="filter-card sticky-filter-card" aria-label="Registration filters">
      <label>
        <span>Trend start date</span>
        <AnalyticsDatePicker
          :model-value="startDate"
          :min="registrationDataStart"
          :max="endDate || registrationDataEnd"
          :available-years="registrationYears"
          label="Trend start date"
          @update:model-value="updateStartDate"
        />
      </label>
      <label>
        <span>Trend end date</span>
        <AnalyticsDatePicker
          :model-value="endDate"
          :min="startDate || registrationDataStart"
          :max="registrationDataEnd"
          :available-years="registrationYears"
          label="Trend end date"
          @update:model-value="updateEndDate"
        />
      </label>
      <label>
        <span>Trend interval</span>
        <select v-model="interval">
          <option value="day">Day</option>
          <option value="week">Week</option>
          <option value="month">Month</option>
        </select>
      </label>
      <label>
        <span>Follow-up status</span>
        <select v-model="statusFilter">
          <option value="all">All statuses</option>
          <option value="missing_guardian">Missing guardian details</option>
          <option value="awaiting_approval">Awaiting guardian approval</option>
        </select>
      </label>
      <button class="reset-button" type="button" @click="resetFilters">
        <i class="fas fa-rotate-left" aria-hidden="true"></i>
        Reset filters
      </button>
    </section>

    <section class="kpi-grid" aria-label="Recent registration summary">
      <article v-for="card in recentCards" :key="card.label" class="kpi-card">
        <div class="kpi-icon"><BtfIcon :name="card.icon" /></div>
        <div>
          <span class="kpi-label">{{ card.label }}</span>
          <strong><AnalyticsNumber :value="card.total" /></strong>
          <small>{{ card.students }} students · {{ card.mentors }} mentors</small>
        </div>
      </article>
      <article class="kpi-card completion-kpi">
        <div class="kpi-icon"><BtfIcon name="shield" /></div>
        <div>
          <span class="kpi-label">Fully registered students</span>
          <strong><AnalyticsNumber :value="registrationCompletion.guardianApproved" /></strong>
          <small>{{ completionRate }}% have guardian approval</small>
        </div>
      </article>
    </section>

    <section class="primary-grid">
      <article class="analytics-card trend-card">
        <div class="card-heading-row">
          <div>
            <h2>New registrations</h2>
            <p>Student and mentor registrations in the selected date range.</p>
          </div>
          <div class="series-controls" aria-label="Registration series">
            <label
              ><input v-model="visibleSeries" type="checkbox" value="students" /> Students</label
            >
            <label><input v-model="visibleSeries" type="checkbox" value="mentors" /> Mentors</label>
          </div>
        </div>

        <div v-if="groupedTrend.length" class="line-chart-layout">
          <div class="chart-y-axis" aria-hidden="true">
            <span v-for="tick in trendTicks" :key="tick">{{ tick }}</span>
          </div>
          <div class="chart-main">
            <svg viewBox="0 0 720 260" role="img" aria-label="New registrations trend">
              <line
                v-for="index in 5"
                :key="index"
                x1="38"
                x2="700"
                :y1="18 + (index - 1) * 52"
                :y2="18 + (index - 1) * 52"
                class="grid-line"
              />
              <polyline
                v-if="visibleSeries.includes('students')"
                :points="trendPoints('students')"
                class="trend-line student-line"
              />
              <polyline
                v-if="visibleSeries.includes('mentors')"
                :points="trendPoints('mentors')"
                class="trend-line mentor-line"
              />
              <template v-for="series in visibleSeries" :key="series">
                <circle
                  v-for="point in trendDots(series)"
                  :key="`${series}-${point.index}`"
                  :cx="point.x"
                  :cy="point.y"
                  r="5"
                  class="trend-dot"
                  :class="`${series}-dot`"
                  tabindex="0"
                  @mouseenter="showTrendTooltip($event, point.index, series)"
                  @focus="showTrendTooltip($event, point.index, series)"
                  @mousemove="moveTooltip"
                  @mouseleave="hideTooltip"
                  @blur="hideTooltip"
                />
              </template>
            </svg>
            <div class="chart-labels" aria-hidden="true">
              <span
                v-for="point in trendAxisLabels"
                :key="`${point.index}-${point.label}`"
                :style="{ left: `${point.position}%` }"
              >{{ point.label }}</span>
            </div>
            <div class="chart-legend">
              <span><i class="legend-dot student-dot-key"></i>Students</span>
              <span><i class="legend-dot mentor-dot-key"></i>Mentors</span>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">No registrations are available for this date range.</div>
      </article>

      <article class="analytics-card funnel-card">
        <div>
          <h2>Registration completion</h2>
          <p>Current programme-year student registration progress.</p>
        </div>
        <div class="funnel-list">
          <div v-for="(step, index) in funnelSteps" :key="step.label" class="funnel-step">
            <div class="funnel-copy">
              <span>{{ step.label }}</span>
              <strong>{{ step.value }}</strong>
            </div>
            <div
              class="funnel-track"
              role="meter"
              :aria-label="step.label"
              aria-valuemin="0"
              :aria-valuemax="registrationCompletion.registered"
              :aria-valuenow="step.value"
            >
              <span :style="{ width: `${step.percent}%` }"></span>
            </div>
            <small v-if="index === 0">Current programme-year students</small>
            <small v-else
              >{{ step.percent }}% of registered students · {{ step.missing }} outstanding</small
            >
          </div>
        </div>
        <p class="definition-note">
          <BtfIcon name="info" /> Fully registered means parent or guardian permission has been
          received.
        </p>
      </article>
    </section>

    <section class="status-grid">
      <article v-for="chart in issueCharts" :key="chart.issue" class="analytics-card issue-card">
        <div class="card-heading-row">
          <div>
            <h2>{{ chart.title }}</h2>
            <p>Select a bar to filter the follow-up table.</p>
          </div>
          <strong class="issue-total">{{ chart.total }}</strong>
        </div>
        <div class="bar-chart">
          <button
            v-for="bar in chart.bars"
            :key="bar.label"
            class="bar-column"
            :class="{ selected: activeIssue === chart.issue && activeAgeBucket === bar.label }"
            type="button"
            @click="selectIssueBucket(chart.issue, bar.label)"
          >
            <span class="bar-value">{{ bar.value }}</span>
            <span class="bar-track"
              ><span class="bar-fill" :style="{ height: `${bar.height}%` }"></span
            ></span>
            <span class="bar-label">{{ bar.label }}</span>
          </button>
        </div>
        <div class="axis-title">Days since registration</div>
      </article>
    </section>

    <section class="secondary-grid">
      <article class="analytics-card source-card">
        <div>
          <h2>Registration source</h2>
          <p>How current programme-year students entered the registration workflow.</p>
        </div>
        <div class="source-unavailable" role="status">
          <BtfIcon name="info" />
          <div>
            <strong>Unavailable</strong>
            <p>Registration source is not stored in the current database schema.</p>
          </div>
        </div>
      </article>

      <article class="analytics-card follow-up-summary">
        <div>
          <h2>Registration follow-up</h2>
          <p>Outstanding records grouped by the next action required.</p>
        </div>
        <button
          type="button"
          :class="{ active: activeIssue === 'missing_guardian' }"
          @click="selectIssue('missing_guardian')"
        >
          <span class="summary-icon warning"><BtfIcon name="user" /></span>
          <span
            ><strong>{{ issueCount('missing_guardian') }}</strong
            ><small>Missing guardian details</small></span
          >
          <BtfIcon name="chevronRight" />
        </button>
        <button
          type="button"
          :class="{ active: activeIssue === 'awaiting_approval' }"
          @click="selectIssue('awaiting_approval')"
        >
          <span class="summary-icon"><BtfIcon name="mail-check" /></span>
          <span
            ><strong>{{ issueCount('awaiting_approval') }}</strong
            ><small>Awaiting guardian approval</small></span
          >
          <BtfIcon name="chevronRight" />
        </button>
      </article>
    </section>

    <section id="registration-follow-up" class="analytics-card table-card">
      <div class="table-heading">
        <div>
          <h2>Students requiring follow-up</h2>
          <p>{{ filteredRows.length }} records match the current filters.</p>
        </div>
        <label class="table-search">
          <BtfIcon name="search" />
          <input v-model="searchQuery" type="search" placeholder="Search student or supervisor" />
        </label>
      </div>

      <div class="table-tabs" role="tablist" aria-label="Follow-up type">
        <button
          type="button"
          :class="{ active: activeIssue === 'missing_guardian' }"
          @click="selectIssue('missing_guardian')"
        >
          Missing guardian details
          <span>{{ issueCount('missing_guardian') }}</span>
        </button>
        <button
          type="button"
          :class="{ active: activeIssue === 'awaiting_approval' }"
          @click="selectIssue('awaiting_approval')"
        >
          Awaiting approval
          <span>{{ issueCount('awaiting_approval') }}</span>
        </button>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Student</th>
              <th>Supervisor</th>
              <th>Registration date</th>
              <th>Source</th>
              <th>Status</th>
              <th>
                <button
                  type="button"
                  class="sort-button"
                  @click="sortDirection = sortDirection === 'desc' ? 'asc' : 'desc'"
                >
                  Days outstanding
                  <BtfIcon :name="sortDirection === 'desc' ? 'sort-down' : 'sort-up'" />
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in pagedRows"
              :key="row.id"
              class="registration-follow-up-row--clickable"
              role="link"
              tabindex="0"
              @click="openRegistrationStudent(row)"
              @keydown.enter="openRegistrationStudent(row)"
              @keydown.space.prevent="openRegistrationStudent(row)"
            >
              <td>
                <strong>{{ row.student }}</strong
                ><small>{{ row.email }}</small>
              </td>
              <td>{{ row.supervisor }}</td>
              <td>{{ formatDate(row.registrationDate) }}</td>
              <td>
                <span class="source-badge" :class="{ unavailable: row.source === null }">
                  {{ row.source ?? 'Unavailable' }}
                </span>
              </td>
              <td>
                <span class="status-badge" :class="row.issue">{{ issueLabel(row.issue) }}</span>
              </td>
              <td>
                <strong :class="{ overdue: row.daysOutstanding > 28 }"
                  >{{ row.daysOutstanding }} days</strong
                >
              </td>
            </tr>
            <tr v-if="!pagedRows.length">
              <td colspan="6" class="empty-cell">No follow-up records match these filters.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="table-footer">
        <span>Showing {{ pageStart }}–{{ pageEnd }} of {{ filteredRows.length }}</span>
        <div>
          <button type="button" :disabled="page === 1" @click="page--">
            <BtfIcon name="chevronLeft" /> Previous
          </button>
          <span>Page {{ page }} of {{ totalPages }}</span>
          <button type="button" :disabled="page === totalPages" @click="page++">
            Next <BtfIcon name="chevronRight" />
          </button>
        </div>
      </footer>
    </section>

    <ChartTooltip v-bind="tooltip" />
    </AnalyticsDataState>
  </section>
</template>

<script setup lang="ts">
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { useAnalyticsRefreshState } from '@/composables/useAnalyticsRefreshState'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import BtfIcon from '@/components/BtfIcon.vue'
import AnalyticsDataState from '@/components/analytics/AnalyticsDataState.vue'
import AnalyticsDatePicker from '@/components/analytics/AnalyticsDatePicker.vue'
import AnalyticsNumber from '@/components/analytics/AnalyticsNumber.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import type {
  RegistrationFollowUp,
  RegistrationIssue,
  RegistrationTrendPoint,
} from '@/types/analytics'
import {
  buildRegistrationAnalytics,
  loadRegistrationAnalyticsBundle,
} from '@/utils/liveAnalyticsData'
import AnalyticsExportMenu from '@/components/analytics/AnalyticsExportMenu.vue'
import {
  DETAILS_OPTION,
  SUMMARY_OPTION,
  detailsCsv,
  exportFileName,
  figure,
  runExport,
  summaryCsv,
  type ExportKind,
  type SummaryRow,
} from '@/utils/analyticsExport'

const registrationTrend = reactive<RegistrationTrendPoint[]>([])
const registrationCompletion = reactive({ registered: 0, guardianDetails: 0, guardianApproved: 0 })
const registrationFollowUps = reactive<RegistrationFollowUp[]>([])
const loadError = ref('')
const isLoading = ref(true)
const isEmpty = ref(false)
const hasLoaded = ref(false)
const exportDisabled = computed(() => isLoading.value || !!loadError.value || isEmpty.value || !hasLoaded.value)

type Interval = 'day' | 'week' | 'month'
type TrendSeries = 'students' | 'mentors'

const startDate = ref('2026-09-01')
const endDate = ref('2026-09-15')
const interval = ref<Interval>('day')
const registrationDataStart = computed(() => registrationTrend[0]?.date ?? startDate.value)
const registrationDataEnd = computed(() => registrationTrend[registrationTrend.length - 1]?.date ?? endDate.value)
const registrationYears = computed(() => [...new Set(registrationTrend.map((point) => Number(point.date.slice(0, 4))))].sort((a, b) => a - b))

function normaliseRegistrationDates(changed: 'start' | 'end') {
  if (startDate.value < registrationDataStart.value) startDate.value = registrationDataStart.value
  if (startDate.value > registrationDataEnd.value) startDate.value = registrationDataEnd.value
  if (endDate.value < registrationDataStart.value) endDate.value = registrationDataStart.value
  if (endDate.value > registrationDataEnd.value) endDate.value = registrationDataEnd.value
  if (startDate.value > endDate.value) {
    if (changed === 'start') endDate.value = startDate.value
    else startDate.value = endDate.value
  }
}

function updateStartDate(value: string) {
  startDate.value = value
  normaliseRegistrationDates('start')
}

function updateEndDate(value: string) {
  endDate.value = value
  normaliseRegistrationDates('end')
}

function applyDefaultTrendRange() {
  endDate.value = registrationDataEnd.value
  const defaultStart = new Date(`${endDate.value}T00:00:00Z`)
  defaultStart.setUTCDate(defaultStart.getUTCDate() - 7)
  const start = defaultStart.toISOString().slice(0, 10)
  startDate.value = start < registrationDataStart.value ? registrationDataStart.value : start
  const range = validDateRange.value
  interval.value = range ? recommendedInterval(range.start, range.end) : 'day'
}
const statusFilter = ref<'all' | RegistrationIssue>('all')
const activeIssue = ref<RegistrationIssue>('missing_guardian')
const activeAgeBucket = ref('')
const searchQuery = ref('')
const sortDirection = ref<'asc' | 'desc'>('desc')
const visibleSeries = ref<TrendSeries[]>(['students', 'mentors'])
const page = ref(1)
const pageSize = 7
const route = useRoute()
const router = useRouter()

function openRegistrationStudent(row: RegistrationFollowUp) {
  void router.push({
    name: 'admin-users',
    query: { tab: 'students', search: row.email },
    hash: '#admin-users-table',
  })
}

useAnalyticsRefreshState('registration', {
  startDate,
  endDate,
  interval,
  statusFilter,
  activeIssue,
  activeAgeBucket,
  searchQuery,
  sortDirection,
  visibleSeries,
  page,
}, () => !isLoading.value && hasLoaded.value)

const tooltip = ref({ visible: false, x: 0, y: 0, title: '', value: '', detail: '' })

function parseDate(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const date = new Date(`${value}T00:00:00Z`)
  if (!Number.isFinite(date.getTime())) return null
  return date.toISOString().slice(0, 10) === value ? date : null
}

const validDateRange = computed(() => {
  const start = parseDate(startDate.value)
  const end = parseDate(endDate.value)
  return start && end && start <= end ? { start, end } : null
})

function recommendedInterval(start: Date, end: Date): Interval {
  const days = Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1
  if (days <= 45) return 'day'
  if (days <= 240) return 'week'
  return 'month'
}

const filteredTrend = computed(() =>
  validDateRange.value
    ? registrationTrend.filter((point) => point.date >= startDate.value && point.date <= endDate.value)
    : [],
)

const groupedTrend = computed(() => {
  const buckets = new Map<
    string,
    { key: string; label: string; shortLabel: string; students: number; mentors: number }
  >()
  for (const point of filteredTrend.value) {
    const date = parseDate(point.date)
    if (!date) continue
    let key = point.date
    let label = formatDate(point.date)
    let shortLabel = date.toLocaleDateString('en-AU', {
      day: '2-digit',
      month: 'short',
      timeZone: 'UTC',
    })
    if (interval.value === 'week') {
      const monday = new Date(date)
      const day = monday.getUTCDay() || 7
      monday.setUTCDate(monday.getUTCDate() - day + 1)
      key = monday.toISOString().slice(0, 10)
      label = `Week of ${formatDate(key)}`
      shortLabel = monday.toLocaleDateString('en-AU', {
        day: '2-digit',
        month: 'short',
        timeZone: 'UTC',
      })
    } else if (interval.value === 'month') {
      key = point.date.slice(0, 7)
      label = date.toLocaleDateString('en-AU', { month: 'long', year: 'numeric', timeZone: 'UTC' })
      shortLabel = date.toLocaleDateString('en-AU', { month: 'short', timeZone: 'UTC' })
    }
    const existing = buckets.get(key) ?? { key, label, shortLabel, students: 0, mentors: 0 }
    existing.students += point.students
    existing.mentors += point.mentors
    buckets.set(key, existing)
  }
  return [...buckets.values()]
})

const trendAxisLabels = computed(() => {
  const points = groupedTrend.value
  if (!points.length) return []

  const lastIndex = points.length - 1
  const maxLabels = 10
  const step = Math.max(1, Math.ceil(lastIndex / Math.max(maxLabels - 1, 1)))

  return points
    .map((point, index) => ({
      index,
      label: point.shortLabel,
      position: lastIndex === 0 ? 50 : 2 + (index / lastIndex) * 96,
    }))
    .filter(({ index }) => index === 0 || index === lastIndex || index % step === 0)
})

const trendMax = computed(() =>
  Math.max(1, ...groupedTrend.value.flatMap((point) => [point.students, point.mentors])),
)
const trendAxisMax = computed(() => Math.max(4, Math.ceil(trendMax.value / 4) * 4))
const trendTicks = computed(() =>
  Array.from({ length: 5 }, (_, index) => Math.round((trendAxisMax.value * (4 - index)) / 4)),
)

function trendDots(series: TrendSeries) {
  const points = groupedTrend.value
  return points.map((point, index) => ({
    index,
    value: point[series],
    x: points.length === 1 ? 369 : 38 + (index / Math.max(points.length - 1, 1)) * 662,
    y: 226 - (point[series] / trendAxisMax.value) * 208,
  }))
}

function trendPoints(series: TrendSeries) {
  return trendDots(series)
    .map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`)
    .join(' ')
}

function showTrendTooltip(event: MouseEvent | FocusEvent, index: number, series: TrendSeries) {
  const target = event.currentTarget as SVGCircleElement
  const rect = target.getBoundingClientRect()
  const point = groupedTrend.value[index]
  if (!point) return
  tooltip.value = {
    visible: true,
    x: 'clientX' in event ? event.clientX : rect.left,
    y: 'clientY' in event ? event.clientY : rect.top,
    title: point.label,
    value: `${point[series]} ${series}`,
    detail: 'New registrations',
  }
}

function moveTooltip(event: MouseEvent) {
  tooltip.value.x = event.clientX
  tooltip.value.y = event.clientY
}
function hideTooltip() {
  tooltip.value.visible = false
}

function recentBreakdown(days: number, endKey = endDate.value) {
  const end = parseDate(endKey)
  if (!end) return { students: 0, mentors: 0 }
  const start = new Date(end)
  start.setUTCDate(start.getUTCDate() - days + 1)
  const startKey = start.toISOString().slice(0, 10)
  return registrationTrend
    .filter((point) => point.date >= startKey && point.date <= endKey)
    .reduce(
      (sum, point) => ({
        students: sum.students + point.students,
        mentors: sum.mentors + point.mentors,
      }),
      { students: 0, mentors: 0 },
    )
}

const recentCards = computed(() =>
  [
    { label: 'Latest recorded day', ...recentBreakdown(1), icon: 'clock' },
    { label: 'Last 7 days', ...recentBreakdown(7), icon: 'calendar' },
    { label: 'Last 14 days', ...recentBreakdown(14), icon: 'trend' },
  ].map((card) => ({ ...card, total: card.students + card.mentors })),
)

const completionRate = computed(
  () =>
    Math.round(
      registrationCompletion.registered
        ? (registrationCompletion.guardianApproved * 1000) / registrationCompletion.registered
        : 0,
    ) / 10,
)
const funnelSteps = computed(() => [
  {
    label: 'Students registered',
    value: registrationCompletion.registered,
    percent: 100,
    missing: 0,
  },
  {
    label: 'Guardian details provided',
    value: registrationCompletion.guardianDetails,
    percent: Math.round(
      registrationCompletion.registered
        ? (registrationCompletion.guardianDetails * 100) / registrationCompletion.registered
        : 0,
    ),
    missing: registrationCompletion.registered - registrationCompletion.guardianDetails,
  },
  {
    label: 'Guardian approval received',
    value: registrationCompletion.guardianApproved,
    percent: Math.round(
      registrationCompletion.registered
        ? (registrationCompletion.guardianApproved * 100) / registrationCompletion.registered
        : 0,
    ),
    missing: registrationCompletion.registered - registrationCompletion.guardianApproved,
  },
])

const ageBuckets = [
  { label: '0–3', min: 0, max: 3 },
  { label: '4–7', min: 4, max: 7 },
  { label: '8–14', min: 8, max: 14 },
  { label: '15–21', min: 15, max: 21 },
  { label: '22–28', min: 22, max: 28 },
  { label: '>28', min: 29, max: Infinity },
]

function matchesAge(days: number, label: string) {
  const bucket = ageBuckets.find((item) => item.label === label)
  return !bucket || (days >= bucket.min && days <= bucket.max)
}

function barsFor(issue: RegistrationIssue) {
  const rows = registrationFollowUps.filter((row) => row.issue === issue)
  const values = ageBuckets.map(
    (bucket) => rows.filter((row) => matchesAge(row.daysOutstanding, bucket.label)).length,
  )
  const max = Math.max(...values, 1)
  return ageBuckets.map((bucket, index) => ({
    label: bucket.label,
    value: values[index]!,
    height: (values[index]! * 100) / max,
  }))
}

const issueCharts = computed(() => [
  {
    issue: 'missing_guardian' as const,
    title: 'Missing guardian contact details',
    total: issueCount('missing_guardian'),
    bars: barsFor('missing_guardian'),
  },
  {
    issue: 'awaiting_approval' as const,
    title: 'Awaiting guardian approval',
    total: issueCount('awaiting_approval'),
    bars: barsFor('awaiting_approval'),
  },
])

function issueCount(issue: RegistrationIssue) {
  return registrationFollowUps.filter((row) => row.issue === issue).length
}
function issueLabel(issue: RegistrationIssue) {
  return issue === 'missing_guardian' ? 'Missing details' : 'Awaiting approval'
}

const filteredRows = computed(() =>
  registrationFollowUps
    .filter((row) => {
      const query = searchQuery.value.trim().toLowerCase()
      return (
        row.issue === activeIssue.value &&
        (statusFilter.value === 'all' || row.issue === statusFilter.value) &&
        (!activeAgeBucket.value || matchesAge(row.daysOutstanding, activeAgeBucket.value)) &&
        (!query || `${row.student} ${row.email} ${row.supervisor}`.toLowerCase().includes(query))
      )
    })
    .sort((left, right) =>
      sortDirection.value === 'desc'
        ? right.daysOutstanding - left.daysOutstanding
        : left.daysOutstanding - right.daysOutstanding,
    ),
)

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize)))
const pagedRows = computed(() =>
  filteredRows.value.slice((page.value - 1) * pageSize, page.value * pageSize),
)
const pageStart = computed(() => (filteredRows.value.length ? (page.value - 1) * pageSize + 1 : 0))
const pageEnd = computed(() => Math.min(page.value * pageSize, filteredRows.value.length))

watch(
  [statusFilter, activeIssue, activeAgeBucket, searchQuery, sortDirection],
  () => {
    page.value = 1
  },
)
watch([startDate, endDate], () => {
  const range = validDateRange.value
  if (range) interval.value = recommendedInterval(range.start, range.end)
})
watch(statusFilter, (value) => {
  if (value !== 'all') {
    activeIssue.value = value
    activeAgeBucket.value = ''
  }
})
watch(totalPages, (value) => {
  if (page.value > value) page.value = value
})

function selectIssue(issue: RegistrationIssue) {
  activeIssue.value = issue
  statusFilter.value = issue
  activeAgeBucket.value = ''
}

function selectIssueBucket(issue: RegistrationIssue, bucket: string) {
  activeIssue.value = issue
  statusFilter.value = issue
  activeAgeBucket.value = activeAgeBucket.value === bucket ? '' : bucket
}

function resetFilters() {
  applyDefaultTrendRange()
  statusFilter.value = 'all'
  activeIssue.value = 'missing_guardian'
  activeAgeBucket.value = ''
  searchQuery.value = ''
  sortDirection.value = 'desc'
}


const analyticsRefreshBusy = ref(false)
const { lastUpdated, refreshFailed, markUpdated, markRefreshFailed } = useAnalyticsRefresh(async () => { if (!analyticsRefreshBusy.value) await loadAnalytics(true, true) })

async function loadAnalytics(force = false, preserveFilters = false) {
  if (analyticsRefreshBusy.value) return
  analyticsRefreshBusy.value = true
  if (!preserveFilters || !lastUpdated.value) isLoading.value = true
  loadError.value = ''
  try {
    const live = buildRegistrationAnalytics(await loadRegistrationAnalyticsBundle(force))
    registrationTrend.splice(0, registrationTrend.length, ...live.trend)
    Object.assign(registrationCompletion, live.completion)
    registrationFollowUps.splice(0, registrationFollowUps.length, ...live.followUps)
    isEmpty.value = live.trend.length === 0
      && live.completion.registered === 0
      && live.completion.guardianDetails === 0
      && live.completion.guardianApproved === 0
      && live.followUps.length === 0
    hasLoaded.value = true
    markUpdated()
    if (registrationTrend.length && !preserveFilters) {
      applyDefaultTrendRange()
    }
  } catch (error) {
    if (preserveFilters && lastUpdated.value) { markRefreshFailed(); return }
    console.error('Failed to load registration analytics from the backend.', error)
    loadError.value = 'Registration analytics could not be loaded from the backend. Check the API and try again.'
    hasLoaded.value = false
  } finally {
    analyticsRefreshBusy.value = false
    isLoading.value = false
  }
}

function refreshAnalytics() {
  return loadAnalytics(true)
}

onMounted(async () => {
  await loadAnalytics()

  const issue = typeof route.query.issue === 'string' ? route.query.issue : ''

  if (issue === 'missing_guardian' || issue === 'awaiting_approval') {
    activeIssue.value = issue
    statusFilter.value = issue
    activeAgeBucket.value = ''
    searchQuery.value = ''
    page.value = 1
  }

  if (route.hash !== '#registration-follow-up') return

  await nextTick()
  requestAnimationFrame(() => {
    document
      .getElementById('registration-follow-up')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
})

function formatDate(value: string) {
  const date = parseDate(value)
  if (!date) return '—'
  return date.toLocaleDateString('en-AU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

const exportError = ref('')

function registrationSummary() {
  const rows: SummaryRow[] = [
    ...recentCards.value.flatMap((card) => [
      figure('New registrations', `${card.label}: total`, card.total, 'users', `Up to ${endDate.value}`),
      figure('New registrations', `${card.label}: students`, card.students, 'users'),
      figure('New registrations', `${card.label}: mentors`, card.mentors, 'users'),
    ]),
    ...funnelSteps.value.flatMap((step) => [
      figure('Registration completion', step.label, step.value, 'students'),
      figure('Registration completion', `${step.label} (%)`, step.percent, '%', step.missing ? `${step.missing} still missing` : ''),
    ]),
    figure('Registration completion', 'Fully registered', completionRate.value, '%', 'Guardian approval received'),
    ...issueCharts.value.flatMap((chart) => [
      figure('Follow-up', chart.title, chart.total, 'students'),
      ...chart.bars.map((bar) => figure(`Follow-up: ${chart.title}`, `${bar.label} days outstanding`, bar.value, 'students')),
    ]),
    ...groupedTrend.value.flatMap((bucket) => [
      figure('Registration trend (Students)', bucket.key, bucket.students, 'users'),
      figure('Registration trend (Mentors)', bucket.key, bucket.mentors, 'users'),
    ]),
  ]
  return {
    fileName: exportFileName('registration', 'summary', `${startDate.value} to ${endDate.value}`),
    csv: summaryCsv({
      page: 'Registration',
      covers: `Trend ${startDate.value} to ${endDate.value} (UTC); completion and follow-up are current`,
      filters: [['Trend interval', interval.value]],
    }, rows),
  }
}

function registrationDetails() {
  const rows = filteredRows.value.map((row) => [
    row.id,
    row.student,
    row.email,
    row.supervisor === '—' ? '' : row.supervisor,
    row.registrationDate,
    issueLabel(row.issue),
    row.daysOutstanding,
    row.source ?? '',
  ])
  return {
    fileName: exportFileName('registration', 'details', `${issueLabel(activeIssue.value)} ${endDate.value}`),
    csv: detailsCsv(
      ['Student ID', 'Student', 'Email', 'Supervisor', 'Registered', 'Follow-up', 'Days Outstanding', 'Source'],
      rows,
    ),
  }
}

function exportCsv(kind: ExportKind) {
  exportError.value = runExport(kind === 'summary' ? registrationSummary : registrationDetails)
}
</script>

<style src="@/assets/analytics-theme.css"></style>

<style scoped>
.registration-analytics-page {
  min-height: 100%;
  padding: 28px;
  color: var(--analytics-ui-text, var(--btf-teal));
  background: var(--analytics-ui-page, var(--btf-surface));
  font-family: Arial, sans-serif;
  box-sizing: border-box;
}
.registration-analytics-page *,
.registration-analytics-page *::before,
.registration-analytics-page *::after {
  box-sizing: border-box;
}
button,
input,
select {
  font: inherit;
}
h1,
h2,
p {
  margin: 0;
}
h1 {
  font-size: 30px;
  line-height: 1.15;
}
h2 {
  font-size: 18px;
}
.page-heading,
.title-line,
.page-actions,
.card-heading-row,
.table-heading,
.table-footer,
.table-footer > div {
  display: flex;
  align-items: center;
}
.page-heading {
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
}
.heading-copy > p,
.analytics-card > div > p,
.card-heading-row p,
.table-heading p {
  margin-top: 5px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 13px;
}
.breadcrumb {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 12px;
}
.breadcrumb a {
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  text-decoration: none;
}
.title-line {
  gap: 12px;
}
.demo-badge {
  padding: 4px 8px;
  border: 1px solid var(--analytics-ui-border, var(--btf-light-green));
  border-radius: 999px;
  background: color-mix(in srgb, var(--analytics-ui-warning-bg, var(--btf-yellow)) 55%, var(--analytics-ui-surface, white));
  font-size: 11px;
  font-weight: 700;
}
.export-button,
.reset-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 38px;
  padding: 8px 13px;
  border: 1px solid var(--analytics-ui-control-border, var(--btf-mint-green));
  border-radius: 9px;
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  background: var(--analytics-ui-surface, var(--btf-white));
  cursor: pointer;
  font-weight: 700;
}
.export-button:hover,
.reset-button:hover {
  background: color-mix(in srgb, var(--analytics-ui-selected, var(--btf-light-green)) 40%, var(--analytics-ui-surface, white));
}
.filter-card,
.analytics-card,
.kpi-card {
  border: 1px solid var(--analytics-ui-border, var(--btf-border));
  border-radius: 14px;
  background: var(--analytics-ui-surface, var(--btf-white));
  box-shadow: var(--shadow-soft);
}
.filter-card {
  display: grid;
  grid-template-columns: repeat(5, minmax(140px, 1fr)) auto;
  gap: 12px;
  align-items: end;
  padding: 16px;
  margin-bottom: 16px;
}
.filter-card label {
  display: grid;
  gap: 6px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 11px;
  font-weight: 700;
}
.filter-card input,
.filter-card select {
  width: 100%;
  height: 38px;
  padding: 0 10px;
  border: 1px solid var(--analytics-ui-border, var(--btf-border));
  border-radius: 8px;
  color: var(--analytics-ui-text, var(--btf-teal));
  background: var(--analytics-ui-surface, white);
}
.filter-card input:focus,
.filter-card select:focus,
.table-search input:focus {
  outline: 2px solid color-mix(in srgb, var(--analytics-ui-control-border, var(--btf-mint-green)) 55%, transparent);
  border-color: var(--btf-dark-green);
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.kpi-card {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 12px;
  padding: 17px;
}
.kpi-icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 11px;
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  background: color-mix(in srgb, var(--analytics-ui-selected, var(--btf-light-green)) 55%, var(--analytics-ui-surface, white));
}
.kpi-card > div:last-child {
  display: grid;
  gap: 3px;
}
.kpi-label {
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 12px;
  font-weight: 700;
}
.kpi-card strong {
  font-size: 27px;
  line-height: 1.1;
}
.kpi-card small {
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 11px;
}
.primary-grid,
.status-grid,
.secondary-grid {
  display: grid;
  gap: 16px;
  margin-bottom: 16px;
}
.primary-grid {
  grid-template-columns: minmax(0, 1.65fr) minmax(300px, 0.85fr);
}
.status-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.secondary-grid {
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
}
.analytics-card {
  padding: 20px;
  overflow: hidden;
}
.card-heading-row,
.table-heading {
  justify-content: space-between;
  gap: 16px;
}
.series-controls {
  display: flex;
  gap: 12px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 12px;
}
.series-controls label {
  display: flex;
  align-items: center;
  gap: 5px;
}
.line-chart-layout {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 8px;
  margin-top: 22px;
}
.chart-y-axis {
  display: flex;
  height: 260px;
  flex-direction: column;
  justify-content: space-between;
  padding: 10px 0 36px;
  text-align: right;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 10px;
}
.chart-main svg {
  display: block;
  width: 100%;
  height: 260px;
  overflow: visible;
}
.grid-line {
  stroke: var(--analytics-ui-border, var(--btf-border));
  stroke-width: 1;
}
.trend-line {
  fill: none;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.student-line {
  stroke: var(--btf-dark-green);
}
.mentor-line {
  stroke: var(--btf-air-force-blue);
}
.trend-dot {
  cursor: pointer;
  stroke: var(--analytics-ui-surface, white);
  stroke-width: 2;
}
.students-dot,
.student-dot-key {
  fill: var(--btf-dark-green);
  background: var(--btf-dark-green);
}
.mentors-dot,
.mentor-dot-key {
  fill: var(--btf-air-force-blue);
  background: var(--btf-air-force-blue);
}
.chart-labels {
  position: relative;
  height: 28px;
  margin-top: -30px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 9px;
}
.chart-labels span {
  position: absolute;
  top: 0;
  transform: translateX(-50%) rotate(-24deg);
  transform-origin: center;
  white-space: nowrap;
}
.chart-legend {
  display: flex;
  justify-content: center;
  gap: 18px;
  margin-top: 28px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 11px;
}
.legend-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 5px;
  border-radius: 50%;
}
.empty-state,
.empty-cell {
  padding: 48px 12px;
  text-align: center;
  color: var(--analytics-ui-muted, var(--btf-muted));
}
.funnel-list {
  display: grid;
  gap: 19px;
  margin-top: 25px;
}
.funnel-copy {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  font-size: 13px;
}
.funnel-copy strong {
  font-size: 21px;
}
.funnel-track {
  height: 12px;
  margin: 7px 0 5px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--analytics-ui-soft, var(--btf-track));
}
.funnel-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--btf-dark-green);
}
.funnel-step:nth-child(2) .funnel-track span {
  background: var(--btf-mint-green);
}
.funnel-step:nth-child(3) .funnel-track span {
  background: var(--btf-air-force-blue);
}
.funnel-step small {
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 10px;
}
.definition-note {
  display: flex;
  gap: 8px;
  margin-top: 22px !important;
  padding: 10px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--analytics-ui-selected, var(--btf-light-green)) 24%, var(--analytics-ui-surface, white));
  line-height: 1.4;
}
.issue-total {
  font-size: 28px;
}
.bar-chart {
  display: flex;
  height: 245px;
  align-items: end;
  gap: 12px;
  margin-top: 22px;
  padding: 0 6px;
  border-bottom: 1px solid var(--analytics-ui-border, var(--btf-border));
}
.bar-column {
  display: grid;
  height: 215px;
  min-width: 0;
  flex: 1;
  grid-template-rows: 20px 1fr 26px;
  gap: 5px;
  align-items: end;
  padding: 0;
  border: 0;
  color: var(--analytics-ui-muted, var(--btf-muted));
  background: transparent;
  cursor: pointer;
}
.bar-value {
  color: var(--analytics-ui-text, var(--btf-teal));
  font-size: 11px;
  font-weight: 700;
}
.bar-track {
  display: flex;
  width: 100%;
  height: 160px;
  align-items: end;
  border-radius: 6px 6px 0 0;
  background: var(--analytics-ui-soft, var(--btf-track));
  overflow: hidden;
}
.bar-fill {
  display: block;
  width: 100%;
  min-height: 2px;
  border-radius: 6px 6px 0 0;
  background: var(--btf-dark-green);
  transition:
    height 0.18s ease,
    background 0.18s ease;
}
.bar-column:hover .bar-fill,
.bar-column.selected .bar-fill {
  background: var(--btf-air-force-blue);
}
.bar-column.selected .bar-track {
  outline: 3px solid color-mix(in srgb, var(--btf-air-force-blue) 22%, transparent);
}
.bar-label {
  align-self: start;
  font-size: 10px;
}
.axis-title {
  margin-top: 9px;
  text-align: center;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 10px;
}
.source-list {
  display: grid;
  gap: 13px;
  margin-top: 22px;
}
.source-unavailable {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-top: 22px;
  padding: 16px;
  border: 1px solid var(--analytics-ui-border, var(--btf-border));
  border-radius: 10px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  background: var(--btf-surface-muted);
}
.source-unavailable strong {
  display: block;
  color: var(--analytics-ui-text, var(--btf-teal));
}
.source-unavailable p {
  margin: 4px 0 0;
}
.source-row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr) 38px 36px;
  gap: 10px;
  align-items: center;
  padding: 5px;
  border: 0;
  border-radius: 7px;
  color: var(--analytics-ui-text, var(--btf-teal));
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.source-row:hover {
  background: var(--btf-surface-muted);
}
.source-track {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--analytics-ui-soft, var(--btf-track));
}
.source-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--btf-dark-green);
}
.source-row strong,
.source-row small {
  text-align: right;
}
.source-row small {
  color: var(--analytics-ui-muted, var(--btf-muted));
}
.follow-up-summary {
  display: grid;
  gap: 12px;
}
.follow-up-summary > button {
  display: grid;
  grid-template-columns: 42px 1fr 20px;
  gap: 12px;
  align-items: center;
  padding: 13px;
  border: 1px solid var(--analytics-ui-border, var(--btf-border));
  border-radius: 10px;
  color: var(--analytics-ui-text, var(--btf-teal));
  background: var(--analytics-ui-surface, white);
  text-align: left;
  cursor: pointer;
}
.follow-up-summary > button:hover,
.follow-up-summary > button.active {
  border-color: var(--analytics-ui-control-border, var(--btf-mint-green));
  background: color-mix(in srgb, var(--analytics-ui-selected, var(--btf-light-green)) 22%, var(--analytics-ui-surface, white));
}
.follow-up-summary > button > span:nth-child(2) {
  display: grid;
  gap: 2px;
}
.follow-up-summary > button strong {
  font-size: 22px;
}
.follow-up-summary > button small {
  color: var(--analytics-ui-muted, var(--btf-muted));
}
.summary-icon {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 10px;
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  background: color-mix(in srgb, var(--analytics-ui-selected, var(--btf-light-green)) 55%, var(--analytics-ui-surface, white));
}
.summary-icon.warning {
  background: color-mix(in srgb, var(--analytics-ui-warning-bg, var(--btf-yellow)) 60%, var(--analytics-ui-surface, white));
}
.table-card {
  padding: 0;
}
.table-heading {
  padding: 20px;
}
.table-search {
  display: flex;
  min-width: 280px;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  border: 1px solid var(--analytics-ui-border, var(--btf-border));
  border-radius: 9px;
  color: var(--analytics-ui-muted, var(--btf-muted));
}
.table-search input {
  width: 100%;
  height: 38px;
  border: 0;
  outline: 0;
  color: var(--analytics-ui-text, var(--btf-teal));
  background: transparent;
}
.table-tabs {
  display: flex;
  gap: 4px;
  padding: 0 20px;
  border-bottom: 1px solid var(--analytics-ui-border, var(--btf-border));
}
.table-tabs button {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 11px 12px;
  border: 0;
  border-bottom: 3px solid transparent;
  color: var(--analytics-ui-muted, var(--btf-muted));
  background: transparent;
  cursor: pointer;
  font-weight: 700;
}
.table-tabs button.active {
  border-bottom-color: var(--btf-dark-green);
  color: var(--analytics-ui-accent, var(--btf-dark-green));
}
.table-tabs button span {
  padding: 2px 6px;
  border-radius: 999px;
  background: var(--analytics-ui-soft, var(--btf-track));
  font-size: 10px;
}
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
th,
td {
  padding: 13px 15px;
  border-bottom: 1px solid var(--analytics-ui-border, var(--btf-border));
  text-align: left;
  white-space: nowrap;
}
th {
  color: var(--analytics-ui-muted, var(--btf-muted));
  background: var(--btf-surface-muted);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
td:first-child {
  min-width: 190px;
}
td:first-child strong,
td:first-child small {
  display: block;
}
td:first-child small {
  margin-top: 3px;
  color: var(--analytics-ui-muted, var(--btf-muted));
}
.registration-follow-up-row--clickable {
  cursor: pointer;
}
.registration-follow-up-row--clickable:hover td,
.registration-follow-up-row--clickable:focus-visible td {
  background: color-mix(in srgb, var(--analytics-ui-selected, var(--btf-light-green)) 35%, var(--analytics-ui-surface, white));
}
.registration-follow-up-row--clickable:focus-visible {
  outline: 2px solid var(--analytics-ui-accent, var(--btf-dark-green));
  outline-offset: -2px;
}
.sort-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  border: 0;
  color: inherit;
  background: transparent;
  cursor: pointer;
  font: inherit;
  text-transform: inherit;
}
.source-badge,
.status-badge {
  display: inline-flex;
  padding: 4px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
}
.source-badge {
  color: var(--analytics-ui-secondary, var(--btf-air-force-blue));
  background: color-mix(in srgb, var(--btf-air-force-blue) 11%, var(--analytics-ui-surface, white));
}
.source-badge.unavailable {
  color: var(--analytics-ui-muted, var(--btf-muted));
  background: var(--btf-surface-muted);
}
.status-badge {
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  background: color-mix(in srgb, var(--analytics-ui-selected, var(--btf-light-green)) 43%, var(--analytics-ui-surface, white));
}
.status-badge.missing_guardian {
  color: var(--analytics-ui-text, var(--btf-teal));
  background: color-mix(in srgb, var(--analytics-ui-warning-bg, var(--btf-yellow)) 58%, var(--analytics-ui-surface, white));
}
.overdue {
  color: var(--analytics-ui-danger, #9b3a2e);
}
.view-link {
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  font-weight: 700;
  text-decoration: none;
}
.view-link:hover {
  text-decoration: underline;
}
.table-footer {
  justify-content: space-between;
  gap: 12px;
  padding: 13px 20px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 11px;
}
.table-footer > div {
  gap: 10px;
}
.table-footer button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 9px;
  border: 1px solid var(--analytics-ui-border, var(--btf-border));
  border-radius: 7px;
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  background: var(--analytics-ui-surface, white);
  cursor: pointer;
}
.table-footer button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 1180px) {
  .filter-card {
    grid-template-columns: repeat(3, minmax(160px, 1fr));
  }
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .primary-grid,
  .secondary-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 900px) {
  .registration-analytics-page {
    padding: 18px 14px;
  }
  .page-heading,
  .table-heading,
  .table-footer {
    align-items: stretch;
    flex-direction: column;
  }
  .page-actions,
  .export-button,
  .table-search {
    width: 100%;
  }
  .filter-card,
  .kpi-grid,
  .status-grid {
    grid-template-columns: 1fr;
  }
  .series-controls {
    flex-wrap: wrap;
  }
  .source-row {
    grid-template-columns: 95px minmax(80px, 1fr) 30px 32px;
  }
  .table-footer > div {
    justify-content: space-between;
  }
}


/* =========================================================
   Match the Groups Analytics page header.
   Keeps this page's existing controls/content, but aligns
   spacing, typography, badge and action sizing.
   ========================================================= */
.page-heading {
  display: grid !important;
  grid-template-columns: minmax(0, 1fr) auto !important;
  align-items: start !important;
  gap: 24px !important;
  margin-bottom: 22px !important;
}

.breadcrumb {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  margin-bottom: 18px !important;
  color: var(--analytics-ui-muted, #59706e) !important;
  font-size: 14px !important;
}

.breadcrumb a {
  color: var(--analytics-ui-muted, #59706e) !important;
  text-decoration: none !important;
}

.breadcrumb a:hover {
  color: var(--analytics-ui-accent, #08765d) !important;
  text-decoration: underline !important;
}

.title-line {
  display: flex !important;
  align-items: center !important;
  gap: 12px !important;
  flex-wrap: wrap !important;
}

.title-line h1,
.heading-copy h1 {
  margin: 0 !important;
  color: var(--analytics-ui-text, #163f3c) !important;
  font-size: 36px !important;
  line-height: 1.15 !important;
  font-weight: 800 !important;
  letter-spacing: normal !important;
}

.page-heading .heading-copy > p,
.page-heading p {
  margin: 8px 0 0 !important;
  color: var(--analytics-ui-muted, #617572) !important;
  font-size: 16px !important;
}

.demo-badge {
  display: inline-flex !important;
  align-items: center !important;
  min-height: 30px !important;
  padding: 0 10px !important;
  border: 1px solid var(--analytics-ui-control-border, #f0d487) !important;
  border-radius: 999px !important;
  background: var(--analytics-ui-soft, #fff7df) !important;
  color: var(--analytics-ui-warning, #916700) !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  white-space: nowrap !important;
}

.page-actions {
  display: flex !important;
  align-items: center !important;
  gap: 12px !important;
  align-self: start !important;
  flex-wrap: nowrap !important;
}

.export-button {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 8px !important;
  width: 142px !important;
  height: 46px !important;
  min-height: 46px !important;
  padding: 0 16px !important;
  border: 1px solid var(--analytics-ui-control-border, #9fd8c7) !important;
  border-radius: 12px !important;
  background: var(--analytics-ui-surface, #fff) !important;
  color: var(--analytics-ui-accent, #017151) !important;
  font-size: 14px !important;
  font-weight: 700 !important;
  cursor: pointer !important;
}

.export-button:hover {
  background: var(--analytics-ui-selected, #ecf8f4) !important;
}

@media (max-width: 780px) {
  .page-heading {
    grid-template-columns: 1fr !important;
  }

  .page-actions {
    width: 100% !important;
    flex-wrap: wrap !important;
  }

  .export-button {
    width: auto !important;
    flex: 1 1 142px !important;
  }
}

.registration-analytics-page {
  padding: 28px 32px 40px !important;
}


/* Sticky registration filters */
.registration-analytics-page {
  overflow: visible !important;
}

.sticky-filter-card {
  position: -webkit-sticky !important;
  position: sticky !important;
  top: 0 !important;
  z-index: 100 !important;
  isolation: isolate;
  background: var(--analytics-ui-surface, #ffffff) !important;
  box-shadow: 0 8px 18px rgba(23, 66, 67, 0.10) !important;
}



/* =========================================================
   Groups-style Registration top-right action
   ========================================================= */
.registration-analytics-page .page-actions {
  display: flex !important;
  align-items: center !important;
  gap: 12px !important;
  align-self: start !important;
  flex-wrap: nowrap !important;
}

.registration-analytics-page .export-button {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 8px !important;
  width: 142px !important;
  height: 46px !important;
  min-height: 46px !important;
  padding: 0 16px !important;
  border: 1px solid var(--analytics-ui-control-border, #9fd8c7) !important;
  border-radius: 12px !important;
  color: var(--analytics-ui-accent, #017151) !important;
  background: var(--analytics-ui-page, #ffffff) !important;
  font-size: 14px !important;
  font-weight: 700 !important;
}

.registration-analytics-page .export-button:hover {
  background: var(--analytics-ui-selected, #ecf8f4) !important;
}

@media (max-width: 760px) {
  .registration-analytics-page .page-actions {
    width: 100% !important;
  }

  .registration-analytics-page .export-button {
    width: 100% !important;
  }
}


.registration-analytics-page .export-button,
.registration-analytics-page .export-button i {
  color: var(--analytics-ui-accent, #017151) !important;
}

.registration-analytics-page .export-button {
  border-color: var(--analytics-ui-control-border, #9fd8c7) !important;
  background: var(--analytics-ui-page, #ffffff) !important;
}

.registration-analytics-page .export-button:hover {
  color: var(--analytics-ui-accent, #017151) !important;
  background: var(--analytics-ui-selected, #ecf8f4) !important;
}

.registration-analytics-page .export-button i {
  font-size: 16px !important;
}


#registration-follow-up {
  scroll-margin-top: 170px;
}

#registration-follow-up:target {
  border-color: var(--analytics-ui-control-border, #9fd8c7);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.08), 0 8px 22px rgba(16, 32, 27, 0.05);
}

/* Match the Activity and Messages filter layout. */
.registration-analytics-page .sticky-filter-card {
  display: grid !important;
  grid-template-columns:
    minmax(165px, 1.1fr)
    minmax(165px, 1.1fr)
    minmax(125px, .8fr)
    minmax(220px, 1.3fr)
    132px !important;
  gap: 10px !important;
  align-items: end !important;
  padding: 16px !important;
  border: 1px solid var(--analytics-ui-border, #d7e3df) !important;
  border-radius: 14px !important;
  background: var(--analytics-ui-page, #fff) !important;
}

.registration-analytics-page .sticky-filter-card label {
  width: auto !important;
  min-width: 0 !important;
  max-width: none !important;
  gap: 6px !important;
  color: var(--analytics-ui-muted, #425e59) !important;
  font-size: 12px !important;
  font-weight: 700 !important;
}

.registration-analytics-page .sticky-filter-card select {
  width: 100% !important;
  height: 42px !important;
  box-sizing: border-box;
  padding: 0 12px !important;
  border: 1px solid var(--analytics-ui-control-border, #79bdb4) !important;
  border-radius: 10px !important;
  background: var(--analytics-ui-page, #fff) !important;
  color: var(--analytics-ui-accent, #017151) !important;
  font: inherit;
  font-size: 13px !important;
}

.registration-analytics-page .sticky-filter-card .reset-button {
  width: 132px !important;
  min-width: 132px !important;
  height: 42px !important;
  min-height: 42px !important;
  margin: 0 !important;
  padding: 0 12px !important;
  border: 1px solid var(--analytics-ui-control-border, #79bdb4) !important;
  border-radius: 10px !important;
  background: var(--analytics-ui-page, #fff) !important;
  color: var(--analytics-ui-accent, #017151) !important;
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .registration-analytics-page .sticky-filter-card {
    grid-template-columns: repeat(3, minmax(170px, 1fr)) !important;
  }

  .registration-analytics-page .sticky-filter-card .reset-button {
    width: 100% !important;
  }
}

@media (max-width: 720px) {
  .registration-analytics-page .sticky-filter-card {
    grid-template-columns: minmax(0, 1fr) !important;
  }
}

</style>
