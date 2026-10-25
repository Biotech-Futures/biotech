<template>
  <section class="messages-analytics-page">
    <div class="page-heading">
      <div class="heading-copy">
        <div class="breadcrumb">
          <RouterLink to="/dashboard">Home</RouterLink>
          <span class="breadcrumb-separator">›</span>
          <RouterLink to="/analytics">Analytics</RouterLink>
          <span class="breadcrumb-separator">›</span>
          <span>Messages Analytics</span>
        </div>

        <div class="title-line">
          <h1>Messages Analytics</h1>
          
        </div>
        <p>Understand how groups and users are communicating across the program.</p>
      </div>

      <div class="page-actions">
        <div class="analytics-export-stack">
          <AnalyticsExportMenu
            :options="exportOptions"
            :disabled="loading || !!loadError || !availableYears.length || !periodDateRange().start"
            @select="exportCsv"
          />
          <div class="analytics-update-status">
            <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />
          </div>
        </div>
      </div>
    </div>

    <p v-if="exportError" role="alert">{{ exportError }}</p>

    <AnalyticsPartialNotice :sources="unavailableSources" @retry="initializeMessages(true)" />

    <div v-if="loadError" role="alert" class="filter-card">
      <p>Message analytics could not be loaded. {{ loadError }}</p>
      <button type="button" @click="initializeMessages(true)">Retry</button>
    </div>
    <p v-else-if="loading" role="status">Loading message analytics…</p>
    <p v-else-if="!availableYears.length" role="status" class="filter-card">
      No recorded message dates are available.
    </p>
    <template v-else>
    <section class="kpi-grid" aria-label="Messages analytics summary">
      <article class="kpi-card">
        <span class="kpi-icon blue"><i class="fas fa-message"></i></span>
        <div>
          <span class="kpi-label">Total Messages</span>
          <strong><AnalyticsNumber :value="totalMessages" /></strong>
          <small>All recorded messages</small>
        </div>
      </article>

      <article class="kpi-card">
        <span class="kpi-icon purple"><i class="fas fa-chart-simple"></i></span>
        <div>
          <span class="kpi-label">Messages This Period</span>
          <div class="analytics-value-row">
            <strong><AnalyticsNumber :value="periodTotal" /></strong>
            <AnalyticsYearChange :current="periodTotal" :previous="previousPeriodMetrics.messages" label="vs same period last year" />
          </div>
          <small>{{ periodLabel }}</small>
        </div>
      </article>

      <article class="kpi-card">
        <span class="kpi-icon blue"><i class="fas fa-people-group"></i></span>
        <div>
          <span class="kpi-label">Average per Group</span>
          <div class="analytics-value-row">
            <strong><AnalyticsNumber :value="averagePerGroup" /></strong>
            <AnalyticsYearChange :current="Number(averagePerGroup)" :previous="previousPeriodMetrics.averagePerGroup" label="vs same period last year" />
          </div>
          <small>Across groups with messages</small>
        </div>
      </article>

      <article class="kpi-card">
        <span class="kpi-icon teal"><i class="fas fa-users"></i></span>
        <div>
          <span class="kpi-label">Groups with Messages</span>
          <div class="analytics-value-row">
            <strong><AnalyticsNumber :value="groupsWithMessages" /></strong>
            <AnalyticsYearChange :current="groupsWithMessages" :previous="previousPeriodMetrics.groupsWithMessages" label="vs same period last year" />
          </div>
          <small>{{ groupCoverage }}% of total groups</small>
        </div>
      </article>

      <article class="kpi-card group-name-kpi">
        <span class="kpi-icon orange"><i class="fas fa-trophy"></i></span>
        <div>
          <span class="kpi-label">Most Active Group</span>
          <strong
            class="text-value"
            :class="{ 'is-compact': mostActiveGroup.name.length > 18 }"
          >{{ mostActiveGroup.name }}</strong>
          <small class="group-message-count">
            <strong><AnalyticsNumber :value="mostActiveGroup.value" /></strong>
            <span>messages</span>
          </small>
        </div>
      </article>

      <article class="kpi-card group-name-kpi">
        <span class="kpi-icon red"><i class="fas fa-arrow-down"></i></span>
        <div>
          <span class="kpi-label">Lowest Message Group</span>
          <strong
            class="text-value"
            :class="{ 'is-compact': leastActiveGroup.name.length > 18 }"
          >{{ leastActiveGroup.name }}</strong>
          <small class="group-message-count">
            <strong><AnalyticsNumber :value="leastActiveGroup.value" /></strong>
            <span>messages</span>
          </small>
        </div>
      </article>
    </section>

    <section
      class="filter-card sticky-filter-card"
      :class="{ 'is-user-view': contentMode === 'users' }"
      aria-label="Message analytics filters"
    >
      <label>
        <span>View</span>
        <select v-model="contentMode" aria-label="Select message analytics view">
          <option value="groups">Groups</option>
          <option value="users">Users</option>
        </select>
      </label>

      <label>
        <span>Trend start date</span>
        <AnalyticsDatePicker
          :model-value="startDate"
          :min="dataStartDate"
          :max="endDate || dataEndDate"
          :available-years="availableYears"
          label="Trend start date"
          @update:model-value="updateTrendStart"
        />
      </label>

      <label>
        <span>Trend end date</span>
        <AnalyticsDatePicker
          :model-value="endDate"
          :min="startDate || dataStartDate"
          :max="dataEndDate"
          :available-years="availableYears"
          label="Trend end date"
          @update:model-value="updateTrendEnd"
        />
      </label>

      <label>
        <span>Trend interval</span>
        <select v-model="interval" aria-label="Trend interval">
          <option value="day">Day</option>
          <option value="week">Week</option>
          <option value="month">Month</option>
        </select>
      </label>

      <label>
        <span>Group</span>
        <select v-model="selectedGroupId" aria-label="Filter messages by group">
          <option value="all">All Groups</option>
          <option
            v-for="group in selectableGroups"
            :key="group.id"
            :value="group.id"
          >
            {{ groupDisplayLabel(group) }}
          </option>
        </select>
      </label>

      <label v-if="contentMode === 'users'">
        <span>Role</span>
        <select v-model="selectedUserRole" aria-label="Filter messages by user role">
          <option value="all">All Roles</option>
          <option v-for="role in userRoleOptions" :key="role" :value="role">
            {{ role }}
          </option>
        </select>
      </label>

      <button type="button" class="reset-button" @click="resetFilters">
        <i class="fas fa-rotate-left"></i>
        Reset filters
      </button>
    </section>

    <p
      v-if="contentMode === 'users' && (userGroupCountsUnavailable || userRecentGroupCountsUnavailable)"
      class="filter-scope-note"
    >
      <span v-if="userGroupCountsUnavailable">
        User message counts for the selected group are unavailable from the current API response.
      </span>
      <span v-if="userRecentGroupCountsUnavailable">
        Past-seven-day user counts for the selected group are unavailable from the current API response.
      </span>
    </p>

    <section class="analytics-grid top-grid">
      <article class="analytics-card wide-card">
        <div class="card-heading">
          <div>
            <h2>Messages Over Time</h2>
            <p>Messages grouped {{ chartPeriodName.toLowerCase() }} for the selected group(s).</p>
          </div>

          <div class="chart-range-summary">
            <span>{{ chartPeriodName }}</span>
            <strong>{{ chartRangeLabel }}</strong>
          </div>
        </div>

        <div class="chart-with-y-axis">
          <div class="y-axis-line">
            <div class="line-chart">
          <svg viewBox="0 0 720 280" role="img" aria-label="Messages over time">
            <line
              v-for="y in [34, 88, 142, 196, 250]"
              :key="y"
              x1="48"
              x2="700"
              :y1="y"
              :y2="y"
              class="grid-line"
            />
            <text v-for="(tick, index) in messageAxisTicks" :key="tick"
              class="message-axis-tick" x="44" :y="34 + index * 54"
              text-anchor="end" dominant-baseline="middle" font-size="10" fill="currentColor">{{ tick }}</text>
            <polygon :points="areaPoints" class="message-area" />
            <polyline :points="linePoints" class="message-line" />
            <circle
              v-for="point in lineDots"
              :key="point.label"
              :cx="point.x"
              :cy="point.y"
              r="5"
              class="message-dot interactive-svg-point"
              @mouseenter="showTooltip($event, point.label, `${point.value.toLocaleString()} messages`, selectedGroupLabel)"
              @mousemove="moveTooltip"
              @mouseleave="hideTooltip"
            />
            <text
              v-for="point in lineDots"
              :key="`value-${point.label}`"
              :x="point.x"
              :y="Math.max(point.y - 12, 18)"
              text-anchor="middle"
              class="message-value-label"
            >
              {{ point.value.toLocaleString() }}
            </text>
          </svg>

          <div
            class="chart-labels"
            :style="{ gridTemplateColumns: `repeat(${timeSeries.labels.length}, minmax(0, 1fr))` }"
          >
            <span v-for="(label, index) in timeSeriesAxisLabels" :key="`${label}-${index}`">{{ label }}</span>
          </div>
        </div>
          </div>
        </div>
        <div class="y-axis-title">Number of Messages</div>
      </article>

      <article class="analytics-card breakdown-card">
        <div class="card-heading breakdown-heading">
          <div>
            <h2>{{ contentMode === 'groups' ? 'Messages by Group' : 'Messages by User' }}</h2>
            <p>
              Total number of messages across all recorded dates.
            </p>
          </div>

          <div class="breakdown-actions">
            <button
              type="button"
              class="message-sort-button"
              @click="toggleBreakdownSort"
              :title="breakdownSortDirection === 'desc' ? 'Largest to smallest' : 'Smallest to largest'"
              aria-label="Sort message breakdown"
            >
              <i :class="breakdownSortDirection === 'desc' ? 'fas fa-sort-down' : 'fas fa-sort-up'"></i>
            </button>

          </div>
        </div>

        <div class="horizontal-bars breakdown-scroll">
          <div
            v-for="(item, index) in breakdownItems"
            :key="item.id ?? `${contentMode}-${item.name}`"
            class="horizontal-row interactive-chart-row"
            @mouseenter="showTooltip(
              $event,
              item.name,
              `${item.value.toLocaleString()} messages`,
              contentMode === 'groups'
                ? `Rank #${index + 1}`
                : `${item.role || 'User'} · ${userGroupName(item.id)} · Rank #${index + 1}`,
            )"
            @mousemove="moveTooltip"
            @mouseleave="hideTooltip"
          >
            <span class="rank">{{ index + 1 }}</span>
            <span class="row-name user-row-name">
              <span class="user-name-line">
                <span>{{ item.name }}</span>
                <span
                  v-if="contentMode === 'users'"
                  class="role-circle"
                  :class="`role-circle-${roleClass(roleForItem(item))}`"
                  :title="roleForItem(item)"
                >
                  {{ roleBadgeText(roleForItem(item)) }}
                </span>
              </span>
              <small v-if="contentMode === 'users'">{{ userGroupName(item.id) }}</small>
            </span>
            <div class="horizontal-track">
              <span
                class="horizontal-fill purple-fill interactive-chart-mark"
                :style="{ width: `${barWidth(item.value, maxBreakdownMessages)}%` }"
              ></span>
            </div>
            <strong>{{ item.value.toLocaleString() }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="analytics-grid lower-grid">
      <article class="analytics-card details-card">
        <div class="card-heading details-heading">
          <div>
            <h2>{{ contentMode === 'groups' ? 'Message Details by Group' : 'Message Details by User' }}</h2>
            <p>Detailed message statistics for the selected filters {{ showAllMessageDetails ? 'across all recorded dates' : 'in the selected period' }}.</p>
          </div>

          <div class="details-actions">
            <label class="show-all-control">
              <input
                v-model="showAllMessageDetails"
                type="checkbox"
                aria-label="Show all message details"
              />
              <span>All recorded dates</span>
            </label>
            <label class="details-search">
              <i class="fas fa-search" aria-hidden="true"></i>
              <span class="sr-only">Search {{ contentMode === 'groups' ? 'group' : 'user' }}</span>
              <input
                v-model="detailsSearch"
                type="search"
                :placeholder="contentMode === 'groups' ? 'Search group' : 'Search user'"
              />
            </label>


          </div>
        </div>

        <div class="table-wrap details-table-scroll">
          <table v-if="contentMode === 'groups'" class="message-details-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Group</th>
                <th>
                  <button type="button" class="table-sort-button" @click="setDetailsSort('value')">
                    Total Messages <i :class="detailsSortIcon('value')"></i>
                  </button>
                </th>
                <th>
                  <button type="button" class="table-sort-button" @click="setDetailsSort('avgPerDay')">
                    Avg per Day <i :class="detailsSortIcon('avgPerDay')"></i>
                  </button>
                </th>
                <th>
                  <button type="button" class="table-sort-button" @click="setDetailsSort('last7Days')">
                    Messages in the past 7 days (UTC, including today) <i :class="detailsSortIcon('last7Days')"></i>
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(group, index) in filteredSortedTableGroups"
                :key="group.id ?? group.name"
                class="interactive-chart-row"
                @mouseenter="showTooltip(
                  $event,
                  group.name,
                  `${group.value.toLocaleString()} messages`,
                  `Avg ${group.avgPerDay} per day · ${group.last7Days.toLocaleString()} in past 7 days · Rank #${index + 1}`,
                )"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              >
                <td>{{ index + 1 }}</td>
                <td>{{ group.name }}</td>
                <td>{{ group.value.toLocaleString() }}</td>
                <td>{{ group.avgPerDay }}</td>
                <td>{{ group.last7Days.toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>

          <table v-else class="message-details-table">
            <thead>
              <tr>
                <th>#</th>
                <th>User</th>
                <th>Role</th>
                <th>
                  <button type="button" class="table-sort-button" @click="setDetailsSort('value')">
                    Total Messages <i :class="detailsSortIcon('value')"></i>
                  </button>
                </th>
                <th>
                  <button type="button" class="table-sort-button" @click="setDetailsSort('last7Days')">
                    Messages in the past 7 days (UTC, including today) <i :class="detailsSortIcon('last7Days')"></i>
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(user, index) in filteredSortedTableUsers"
                :key="user.id ?? user.name"
                class="interactive-chart-row"
                @mouseenter="showTooltip(
                  $event,
                  user.name,
                  `${user.value.toLocaleString()} messages`,
                  `${user.role} · ${userGroupName(user.id)} · ${formatRecentMessages(user.last7Days)} in past 7 days · Rank #${index + 1}`,
                )"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              >
                <td>{{ index + 1 }}</td>
                <td>
                  <span class="details-user-cell">
                    <strong>{{ user.name }}</strong>
                    <small>{{ userGroupName(user.id) }}</small>
                  </span>
                </td>
                <td>
                  <span class="role-pill" :class="`role-${user.role.toLowerCase()}`">{{ user.role }}</span>
                </td>
                <td>{{ user.value.toLocaleString() }}</td>
                <td>{{ formatRecentMessages(user.last7Days) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <div class="right-stack">
        <article class="analytics-card insights-card">
          <AnalyticsKeyInsights
            :items="messageInsightItems"
            description="Summarises message coverage and the most active groups and users for the selected filters."
          />
        </article>
      </div>
    </section>

    <ChartTooltip
      :visible="tooltip.visible"
      :x="tooltip.x"
      :y="tooltip.y"
      :title="tooltip.title"
      :value="tooltip.value"
      :detail="tooltip.detail"
    />
    </template>
  </section>
</template>

<script setup lang="ts">
import AnalyticsPartialNotice from '@/components/analytics/AnalyticsPartialNotice.vue'
import type { AnalyticsSource } from '@/utils/liveAnalyticsData'
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { useAnalyticsRefreshState } from '@/composables/useAnalyticsRefreshState'
import { computed, onMounted, ref, watch } from 'vue'
import AnalyticsKeyInsights from '@/components/analytics/AnalyticsKeyInsights.vue'
import AnalyticsYearChange from '@/components/analytics/AnalyticsYearChange.vue'
import AnalyticsNumber from '@/components/analytics/AnalyticsNumber.vue'
import AnalyticsDatePicker from '@/components/analytics/AnalyticsDatePicker.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import type { MessagesAnalyticsYear } from '@/types/analytics'
import {
  buildMessagesAnalytics,
  groupActivityForRange,
  loadMessagesAnalyticsBundle,
  type CoreAnalyticsBundle,
} from '@/utils/liveAnalyticsData'
import type { GroupActivityResponse } from '@/utils/liveAnalyticsApi'
import AnalyticsExportMenu from '@/components/analytics/AnalyticsExportMenu.vue'
import {
  DETAILS_OPTION,
  SUMMARY_OPTION,
  detailsCsv,
  exportFileName,
  figure,
  runExport,
  sourceLabels,
  summaryCsv,
  type ExportKind,
  type ExportOption,
  type SummaryRow,
} from '@/utils/analyticsExport'

const availableYears = ref<number[]>([])
const selectedYear = ref(0)
const datasetAnchorDay = ref<string | null>(null)
const liveData = ref<MessagesAnalyticsYear>({
  totalMessages: 0,
  totalGroups: 0,
  groupsWithMessages: 0,
  groups: [],
  users: [],
  monthly: Array.from({ length: 12 }, () => 0),
  weekly: [],
  monthWeeks: [],
})
const unavailableSources = ref<AnalyticsSource[]>([])
const sourceAvailable = (source: AnalyticsSource) => !unavailableSources.value.includes(source)
const loadError = ref('')
const baseBundle = ref<CoreAnalyticsBundle | null>(null)
const currentActivity = ref<GroupActivityResponse | null>(null)
const recentActivity = ref<GroupActivityResponse | null>(null)
const loading = ref(true)
const exportError = ref('')
let initializing = false

function utcDay(value: string | null | undefined) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString().slice(0, 10)
}

function messageYears(activity: GroupActivityResponse) {
  return [...new Set(activity.messages_by_day
    .map((row) => utcDay(row.date))
    .filter((day): day is string => day !== null)
    .map((day) => Number(day.slice(0, 4))))]
    .sort((a, b) => b - a)
}

function observedDatasetAnchor(bundle: CoreAnalyticsBundle) {
  const explicitEnd = utcDay(bundle.groupActivity.query_range.end)
  if (explicitEnd) return explicitEnd

  const observedDays = [
    ...bundle.groupActivity.messages_by_day.map((row) => utcDay(row.date)),
  ].filter((day): day is string => day !== null)

  observedDays.sort()
  return observedDays[observedDays.length - 1] ?? null
}

const analyticsRefreshBusy = ref(false)
const { lastUpdated, refreshFailed, markUpdated, markRefreshFailed } = useAnalyticsRefresh(async () => { if (!analyticsRefreshBusy.value) await initializeMessages(true, true) })

async function initializeMessages(force = false, preserveFilters = false) {
  if (analyticsRefreshBusy.value) return
  analyticsRefreshBusy.value = true
  initializing = true
  if (!preserveFilters || !lastUpdated.value) loading.value = true
  loadError.value = ''
  const preservedState = preserveFilters && lastUpdated.value
    ? {
        baseBundle: baseBundle.value,
        datasetAnchorDay: datasetAnchorDay.value,
        availableYears: [...availableYears.value],
        selectedYear: selectedYear.value,
        startDate: startDate.value,
        endDate: endDate.value,
        dataStartDate: dataStartDate.value,
        dataEndDate: dataEndDate.value,
        interval: interval.value,
        currentActivity: currentActivity.value,
        recentActivity: recentActivity.value,
      }
    : null
  try {
    const bundle = await loadMessagesAnalyticsBundle(force)
    unavailableSources.value = bundle.unavailableSources ?? []
    baseBundle.value = bundle
    datasetAnchorDay.value = observedDatasetAnchor(bundle)
    availableYears.value = messageYears(bundle.groupActivity)

    if (!availableYears.value.length) {
      currentActivity.value = bundle.groupActivity
      liveData.value = buildMessagesAnalytics(bundle)
      markUpdated()
      return
    }

    if (!preserveFilters) {
      selectedYear.value = availableYears.value[0]!
      applyObservedDateRange()
    } else {
      updateObservedDateBounds()
      normaliseTrendDates('end')
    }

    if (datasetAnchorDay.value) {
      const end = new Date(`${datasetAnchorDay.value}T00:00:00Z`)
      const start = new Date(end)
      start.setUTCDate(start.getUTCDate() - 6)
      recentActivity.value = await groupActivityForRange(
        bundle.groupActivity,
        start.toISOString().slice(0, 10),
        datasetAnchorDay.value,
      )
    }
    await refreshMessageData(preserveFilters && !!lastUpdated.value)
    markUpdated()
  } catch (error) {
    if (preservedState) {
      baseBundle.value = preservedState.baseBundle
      datasetAnchorDay.value = preservedState.datasetAnchorDay
      availableYears.value = preservedState.availableYears
      selectedYear.value = preservedState.selectedYear
      startDate.value = preservedState.startDate
      endDate.value = preservedState.endDate
      dataStartDate.value = preservedState.dataStartDate
      dataEndDate.value = preservedState.dataEndDate
      interval.value = preservedState.interval
      currentActivity.value = preservedState.currentActivity
      recentActivity.value = preservedState.recentActivity
      markRefreshFailed()
      return
    }
    loadError.value = error instanceof Error ? error.message : 'Message analytics could not be loaded.'
  } finally {
    analyticsRefreshBusy.value = false
    initializing = false
    loading.value = false
  }
}
onMounted(initializeMessages)
type Interval = 'day' | 'week' | 'month'
const startDate = ref('')
const endDate = ref('')
const dataStartDate = ref('')
const dataEndDate = ref('')
const interval = ref<Interval>('day')
const selectedGroupId = ref<number | 'all'>('all')

const monthNames = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

const contentMode = ref<'groups' | 'users'>('groups')
const userRoleOptions = ['Student', 'Mentor', 'Supervisor', 'Unavailable'] as const
type UserRoleFilter = (typeof userRoleOptions)[number] | 'all'
const selectedUserRole = ref<UserRoleFilter>('all')
const breakdownSortDirection = ref<'asc' | 'desc'>('desc')
const detailsSearch = ref('')
const showAllMessageDetails = ref(false)
type DetailsSortKey = 'value' | 'avgPerDay' | 'last7Days' | 'share'
const detailsSortKey = ref<DetailsSortKey>('value')
const detailsSortDirection = ref<'asc' | 'desc'>('desc')

useAnalyticsRefreshState('messages', {
  selectedYear,
  startDate,
  endDate,
  interval,
  selectedGroupId,
  contentMode,
  selectedUserRole,
  breakdownSortDirection,
  detailsSearch,
  showAllMessageDetails,
  detailsSortKey,
  detailsSortDirection,
}, () => !loading.value && !!baseBundle.value)
const effectiveDetailsSortKey = computed<DetailsSortKey>(() =>
  contentMode.value === 'users' && !['value', 'last7Days'].includes(detailsSortKey.value)
    ? 'value'
    : detailsSortKey.value,
)


const data = computed(() => liveData.value)
const allMessagesData = computed(() =>
  baseBundle.value ? buildMessagesAnalytics(baseBundle.value) : data.value,
)

function periodDateRange() {
  const start = parseInputDate(startDate.value)
  const end = parseInputDate(endDate.value)
  return start && end && start <= end
    ? { start: startDate.value, end: endDate.value }
    : { start: undefined, end: undefined }
}

function parseInputDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

function recommendedInterval(start: Date, end: Date): Interval {
  const days = Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1
  if (days <= 45) return 'day'
  if (days <= 240) return 'week'
  return 'month'
}

function observedDateBounds() {
  const activity = baseBundle.value?.groupActivity
  const days = activity?.messages_by_day
    .map((row) => utcDay(row.date))
    .filter((day): day is string => day !== null)
    .sort() ?? []
  const fallback = datasetAnchorDay.value ?? new Date().toISOString().slice(0, 10)
  return {
    start: days[0] ?? fallback,
    end: datasetAnchorDay.value ?? days[days.length - 1] ?? fallback,
  }
}

function defaultObservedStart(start: string, end: string) {
  const defaultStart = new Date(`${end}T00:00:00Z`)
  defaultStart.setUTCDate(defaultStart.getUTCDate() - 7)
  return defaultStart.toISOString().slice(0, 10) < start
    ? start
    : defaultStart.toISOString().slice(0, 10)
}

function updateObservedDateBounds() {
  const bounds = observedDateBounds()
  dataStartDate.value = bounds.start
  dataEndDate.value = bounds.end
}

function applyObservedDateRange() {
  updateObservedDateBounds()
  startDate.value = defaultObservedStart(dataStartDate.value, dataEndDate.value)
  endDate.value = dataEndDate.value
  selectedYear.value = Number(endDate.value.slice(0, 4))
  const range = periodDateRange()
  interval.value = range.start && range.end
    ? recommendedInterval(new Date(`${range.start}T00:00:00Z`), new Date(`${range.end}T00:00:00Z`))
    : 'day'
}

function normaliseTrendDates(changed: 'start' | 'end') {
  if (dataStartDate.value && startDate.value < dataStartDate.value) startDate.value = dataStartDate.value
  if (dataEndDate.value && startDate.value > dataEndDate.value) startDate.value = dataEndDate.value
  if (dataStartDate.value && endDate.value < dataStartDate.value) endDate.value = dataStartDate.value
  if (dataEndDate.value && endDate.value > dataEndDate.value) endDate.value = dataEndDate.value
  if (startDate.value > endDate.value) {
    if (changed === 'start') endDate.value = startDate.value
    else startDate.value = endDate.value
  }
}

function updateTrendStart(value: string) {
  startDate.value = value
  normaliseTrendDates('start')
}

function updateTrendEnd(value: string) {
  endDate.value = value
  normaliseTrendDates('end')
}

let refreshVersion = 0
async function refreshMessageData(preserveData = false) {
  if (!baseBundle.value) return
  const version = ++refreshVersion
  const { start, end } = periodDateRange()
  if (!preserveData) loading.value = true
  try {
  // Derived from the loaded full-range data, so changing dates needs no request.
  const activity = await groupActivityForRange(baseBundle.value.groupActivity, start, end)
  if (version !== refreshVersion) return
  currentActivity.value = activity
  loadError.value = ''
  liveData.value = buildMessagesAnalytics({ ...baseBundle.value, groupActivity: activity })
  } catch (error) {
    if (version === refreshVersion) {
      if (preserveData) throw error
      loadError.value = error instanceof Error ? error.message : 'Message analytics could not be loaded.'
    }
  } finally {
    if (version === refreshVersion) loading.value = false
  }
}

watch([startDate, endDate], () => {
  const range = periodDateRange()
  if (range.start && range.end) {
    selectedYear.value = Number(range.end.slice(0, 4))
    interval.value = recommendedInterval(
      new Date(`${range.start}T00:00:00Z`),
      new Date(`${range.end}T00:00:00Z`),
    )
  }
  if (!initializing) void refreshMessageData()
})

const periodLabel = computed(() => {
  const { start, end } = periodDateRange()
  if (!start || !end) return 'Invalid date range'

  const startValue = new Date(`${start}T00:00:00Z`)
  const endValue = new Date(`${end}T00:00:00Z`)
  return `${startValue.getUTCDate()} ${monthNames[startValue.getUTCMonth()].slice(0, 3)} ${startValue.getUTCFullYear()}–${endValue.getUTCDate()} ${monthNames[endValue.getUTCMonth()].slice(0, 3)} ${endValue.getUTCFullYear()} (UTC)`
})

const chartRangeLabel = computed(() => periodLabel.value)
const chartPeriodName = computed(() => interval.value === 'day' ? 'Daily' : interval.value === 'week' ? 'Weekly' : 'Monthly')
const selectedGroupLabel = computed(() =>
  selectedGroupId.value === 'all'
    ? 'All groups'
    : groupDisplayLabel(data.value.groups.find((group) => group.id === selectedGroupId.value)),
)

function groupDisplayLabel(group: { id?: number; name: string } | undefined) {
  if (!group) return selectedGroupId.value === 'all' ? 'All groups' : `Group ${selectedGroupId.value}`
  const duplicateName = data.value.groups.some((candidate) =>
    candidate.id !== group.id && candidate.name === group.name,
  )
  return duplicateName ? `${group.name} (ID ${group.id ?? 'Unavailable'})` : group.name
}

const selectableGroups = computed(() =>
  data.value.groups.filter((group): group is typeof group & { id: number } => group.id !== undefined),
)

const visibleGroups = computed(() => {
  const rows = data.value.groups
  if (selectedGroupId.value === 'all') return rows
  return rows.filter((group) => group.id === selectedGroupId.value)
})
const allTimeVisibleGroups = computed(() => {
  const rows = allMessagesData.value.groups
  if (selectedGroupId.value === 'all') return rows
  return rows.filter((group) => group.id === selectedGroupId.value)
})
function usersForGroup(
  users: typeof data.value.users,
  activity: GroupActivityResponse | null | undefined,
) {
  if (selectedGroupId.value === 'all') return users
  const rows = activity?.messages_by_user_by_group_by_day
  if (!rows) return []
  const totals = new Map<number, number>()
  for (const row of rows) {
    if (row.group_id !== selectedGroupId.value) continue
    totals.set(row.user_id, (totals.get(row.user_id) ?? 0) + row.message_count)
  }
  return users
    .filter((user) => user.id !== undefined && totals.has(user.id))
    .map((user) => ({ ...user, value: totals.get(user.id!) ?? 0 }))
    .sort((a, b) => b.value - a.value)
}

const visibleUsers = computed(() => {
  const rows = usersForGroup(data.value.users, currentActivity.value)
  return selectedUserRole.value === 'all'
    ? rows
    : rows.filter((user) => user.role === selectedUserRole.value)
})
const allTimeVisibleUsers = computed(() => {
  const rows = usersForGroup(allMessagesData.value.users, baseBundle.value?.groupActivity)
  return selectedUserRole.value === 'all'
    ? rows
    : rows.filter((user) => user.role === selectedUserRole.value)
})
const userGroupCountsUnavailable = computed(() =>
  contentMode.value === 'users' && selectedGroupId.value !== 'all'
  && (!currentActivity.value?.messages_by_user_by_group_by_day
    || !baseBundle.value?.groupActivity.messages_by_user_by_group_by_day),
)
const userRecentGroupCountsUnavailable = computed(() =>
  contentMode.value === 'users' && selectedGroupId.value !== 'all'
  && !recentActivity.value?.messages_by_user_by_group_by_day,
)
const detailGroups = computed(() =>
  showAllMessageDetails.value ? allTimeVisibleGroups.value : visibleGroups.value,
)
const detailUsers = computed(() =>
  showAllMessageDetails.value ? allTimeVisibleUsers.value : visibleUsers.value,
)
const totalMessages = computed(() => {
  const activity = baseBundle.value?.groupActivity
  if (!activity) return 0
  if (selectedGroupId.value === 'all') {
    return activity.messages_by_day
      .reduce((sum, row) => sum + row.message_count, 0)
  }
  return activity.messages_by_group_by_day
    .filter((row) => row.group_id === selectedGroupId.value)
    .reduce((sum, row) => sum + row.message_count, 0)
})
const periodTotal = computed(() =>
  selectedGroupId.value === 'all'
    ? data.value.totalMessages
    : visibleGroups.value.reduce((sum, group) => sum + group.value, 0),
)
function previousYearDate(value: string) {
  const date = new Date(`${value}T00:00:00Z`)
  date.setUTCFullYear(date.getUTCFullYear() - 1)
  return date.toISOString().slice(0, 10)
}
const previousPeriodMetrics = computed(() => {
  const activity = baseBundle.value?.groupActivity
  const range = periodDateRange()
  if (!activity || !range.start || !range.end) {
    return { messages: 0, groupsWithMessages: 0, averagePerGroup: 0 }
  }
  const start = previousYearDate(range.start)
  const end = previousYearDate(range.end)
  const totals = new Map<number, number>()
  for (const row of activity.messages_by_group_by_day) {
    if (row.date < start || row.date > end) continue
    if (selectedGroupId.value !== 'all' && row.group_id !== selectedGroupId.value) continue
    totals.set(row.group_id, (totals.get(row.group_id) ?? 0) + row.message_count)
  }
  const messages = [...totals.values()].reduce((sum, value) => sum + value, 0)
  const groupsWithMessages = [...totals.values()].filter((value) => value > 0).length
  return {
    messages,
    groupsWithMessages,
    averagePerGroup: groupsWithMessages ? Number((messages / groupsWithMessages).toFixed(1)) : 0,
  }
})
const groupsWithMessages = computed(() =>
  selectedGroupId.value === 'all' ? data.value.groupsWithMessages : visibleGroups.value.filter((group) => group.value > 0).length,
)
const groupCoverage = computed(() => {
  if (selectedGroupId.value !== 'all') return visibleGroups.value.some((group) => group.value > 0) ? 100 : 0
  return data.value.totalGroups ? Math.round((data.value.groupsWithMessages / data.value.totalGroups) * 100) : 0
})

const mostActiveGroup = computed(() => visibleGroups.value[0] ?? { name: '—', value: 0 })
const leastActiveGroups = computed(() =>
  [...visibleGroups.value].sort((a, b) => a.value - b.value).slice(0, 5),
)
function roleClass(role: string | undefined) {
  return (role || 'Unavailable').toLowerCase().replace(/[^a-z0-9]+/g, '-')
}

function roleForItem(item: { name: string; value: number; role?: string }) {
  return item.role || 'Unavailable'
}

function roleBadgeText(role: string) {
  if (role === 'Mentor') return 'M'
  if (role === 'Student') return 'S'
  if (role === 'Supervisor') return 'SV'
  return 'U'
}

function userGroupName(userId: number | undefined) {
  if (!sourceAvailable('groups')) return 'Group unavailable'
  if (userId === undefined || !baseBundle.value) return 'Group —'
  const id = String(userId)
  const names = baseBundle.value.groups
    .filter((group) =>
      group.members.some((member) => member.id === id)
      || (group.mentors ?? (group.mentor ? [group.mentor] : [])).some((mentor) => mentor.id === id),
    )
    .map((group) => group.name)
  return names.length ? names.join(', ') : 'Group —'
}
const leastActiveGroup = computed(() => leastActiveGroups.value[0] ?? { name: '—', value: 0 })

const mostActiveUser = computed(() => visibleUsers.value[0] ?? { name: '—', value: 0, role: '' })
const messageInsightItems = computed(() => [
  {
    key: 'groups',
    value: groupsWithMessages.value,
    text: `of ${data.value.totalGroups} groups exchanged messages (${groupCoverage.value}%).`,
  },
  { key: 'messages', value: periodTotal.value.toLocaleString(), text: 'messages were sent in the selected period.' },
  {
    key: 'group',
    value: mostActiveGroup.value.name,
    text: `is the most active group with ${mostActiveGroup.value.value.toLocaleString()} messages.`,
  },
  selectedGroupId.value !== 'all' && !currentActivity.value?.messages_by_user_by_group_by_day
    ? {
      key: 'user',
      value: 'Unavailable',
      text: 'The most active user for the selected group cannot be determined from the current API response.',
    }
    : {
      key: 'user',
      value: mostActiveUser.value.name,
      text: `is the most active user with ${mostActiveUser.value.value.toLocaleString()} messages.`,
    },
])

const averagePerGroup = computed(() => {
  if (!groupsWithMessages.value) return '0.0'
  return (periodTotal.value / groupsWithMessages.value).toFixed(1)
})

type BreakdownItem = {
  id?: number
  name: string
  value: number
  role?: string
}

const breakdownItems = computed<BreakdownItem[]>(() => {
  const source = contentMode.value === 'groups'
    ? allTimeVisibleGroups.value
    : allTimeVisibleUsers.value

  return [...source].sort((a, b) =>
    breakdownSortDirection.value === 'desc' ? b.value - a.value : a.value - b.value,
  )
})

const maxBreakdownMessages = computed(() =>
  Math.max(...breakdownItems.value.map((item) => item.value), 1),
)

const timeSeries = computed(() => {
  const activity = currentActivity.value
  const range = periodDateRange()
  if (!activity || !range.start || !range.end) return { keys: [] as string[], labels: [] as string[], values: [] as number[] }

  const rows = selectedGroupId.value === 'all'
    ? activity.messages_by_day.map((row) => ({ date: row.date, value: row.message_count }))
    : activity.messages_by_group_by_day
        .filter((row) => row.group_id === selectedGroupId.value)
        .map((row) => ({ date: row.date, value: row.message_count }))

  function bucketFor(date: Date) {
    if (interval.value === 'week') {
      const monday = new Date(date)
      const weekday = monday.getUTCDay() || 7
      monday.setUTCDate(monday.getUTCDate() - weekday + 1)
      return {
        key: monday.toISOString().slice(0, 10),
        label: `${monday.getUTCDate()} ${monthNames[monday.getUTCMonth()].slice(0, 3)}`,
      }
    }
    if (interval.value === 'month') {
      return {
        key: date.toISOString().slice(0, 7),
        label: `${monthNames[date.getUTCMonth()].slice(0, 3)} ${date.getUTCFullYear()}`,
      }
    }
    return {
      key: date.toISOString().slice(0, 10),
      label: `${date.getUTCDate()} ${monthNames[date.getUTCMonth()].slice(0, 3)}`,
    }
  }

  const buckets = new Map<string, { label: string; value: number }>()
  const start = new Date(`${range.start}T00:00:00Z`)
  const end = new Date(`${range.end}T00:00:00Z`)
  for (const cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    const bucket = bucketFor(cursor)
    if (!buckets.has(bucket.key)) buckets.set(bucket.key, { label: bucket.label, value: 0 })
  }
  for (const row of rows) {
    const day = utcDay(row.date)
    if (!day || day < range.start || day > range.end) continue
    const date = new Date(`${day}T00:00:00Z`)
    const key = bucketFor(date).key
    const bucket = buckets.get(key)
    if (bucket) bucket.value += row.value
  }
  return {
    keys: [...buckets.keys()],
    labels: [...buckets.values()].map((bucket) => bucket.label),
    values: [...buckets.values()].map((bucket) => bucket.value),
  }
})

const messageAxisTicks = computed(() => {
  const values = timeSeries.value.values
  const maxValue = Math.max(...values, 0)
  let top = 4
  if (maxValue > 4 && maxValue <= 20) top = Math.ceil(maxValue / 4) * 4
  else if (maxValue > 20 && maxValue <= 100) top = Math.ceil(maxValue / 20) * 20
  else if (maxValue > 100) top = Math.ceil(maxValue / 50) * 50
  return Array.from({ length: 5 }, (_, index) => Math.round((top * (4 - index)) / 4))
})

const timeSeriesAxisLabels = computed(() => {
  const labels = timeSeries.value.labels
  if (labels.length <= 10) return labels
  const step = Math.ceil((labels.length - 1) / 9)
  return labels.map((label, index) =>
    index === 0 || index === labels.length - 1 || index % step === 0 ? label : '',
  )
})

const lineDots = computed(() => {
  const values = timeSeries.value.values
  const range = messageAxisTicks.value[0]!
  const left = 52
  const right = 690
  const top = 34
  const bottom = 250

  return values.map((value, index) => ({
    label: timeSeries.value.labels[index],
    value,
    x: values.length === 1 ? (left + right) / 2 : left + (index / (values.length - 1)) * (right - left),
    y: bottom - (value / range) * (bottom - top),
  }))
})

const linePoints = computed(() =>
  lineDots.value.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' '),
)

const areaPoints = computed(() => {
  if (!lineDots.value.length) return ''
  const first = lineDots.value[0]
  const last = lineDots.value[lineDots.value.length - 1]
  return [
    `${first.x.toFixed(1)},250`,
    ...lineDots.value.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`),
    `${last.x.toFixed(1)},250`,
  ].join(' ')
})

const tableGroups = computed(() => {
  const total = Math.max(detailGroups.value.reduce((sum, group) => sum + group.value, 0), 1)
  const range = showAllMessageDetails.value
    ? { start: dataStartDate.value || undefined, end: dataEndDate.value || undefined }
    : periodDateRange()
  const days = range.start && range.end ? (Date.parse(range.end) - Date.parse(range.start)) / 86400000 + 1 : 1
  const recent = new Map((recentActivity.value?.messages_by_group ?? []).map((row) => [row.group_id, row.message_count]))

  return detailGroups.value.map((group) => ({
    ...group,
    avgPerDay: Number((group.value / days).toFixed(2)),
    last7Days: recent.get(group.id!) ?? 0,
    share: Number(((group.value / total) * 100).toFixed(1)),
  }))
})

const tableUsers = computed(() => {
  const recent = new Map<number, number>()
  const groupRows = recentActivity.value?.messages_by_user_by_group_by_day
  const recentUnavailable = selectedGroupId.value !== 'all' && !groupRows
  if (selectedGroupId.value === 'all') {
    for (const row of recentActivity.value?.messages_by_user ?? []) {
      recent.set(row.user_id, row.message_count)
    }
  } else {
    for (const row of groupRows ?? []) {
      if (row.group_id !== selectedGroupId.value) continue
      recent.set(row.user_id, (recent.get(row.user_id) ?? 0) + row.message_count)
    }
  }
  return detailUsers.value.map((user) => ({
    ...user,
    last7Days: recentUnavailable ? null : recent.get(user.id!) ?? 0,
  }))
})

function formatRecentMessages(value: number | null) {
  return value === null ? 'Unavailable' : value.toLocaleString()
}

const filteredSortedTableGroups = computed(() => {
  const q = detailsSearch.value.trim().toLowerCase()
  const rows = tableGroups.value.filter((group) => !q || group.name.toLowerCase().includes(q))
  const key = effectiveDetailsSortKey.value
  return [...rows].sort((a, b) => {
    const av = key === 'avgPerDay' ? a.avgPerDay : key === 'last7Days' ? a.last7Days : key === 'share' ? a.share : a.value
    const bv = key === 'avgPerDay' ? b.avgPerDay : key === 'last7Days' ? b.last7Days : key === 'share' ? b.share : b.value
    return detailsSortDirection.value === 'desc' ? bv - av : av - bv
  })
})

const filteredSortedTableUsers = computed(() => {
  const q = detailsSearch.value.trim().toLowerCase()
  const rows = tableUsers.value.filter((user) => !q || user.name.toLowerCase().includes(q))
  const key = effectiveDetailsSortKey.value === 'last7Days' ? 'last7Days' : 'value'
  return [...rows].sort((a, b) => {
    const av = key === 'last7Days' ? a.last7Days : a.value
    const bv = key === 'last7Days' ? b.last7Days : b.value
    if (av === null) return bv === null ? 0 : 1
    if (bv === null) return -1
    return detailsSortDirection.value === 'desc' ? bv - av : av - bv
  })
})

function toggleBreakdownSort() {
  breakdownSortDirection.value = breakdownSortDirection.value === 'desc' ? 'asc' : 'desc'
}

function setDetailsSort(key: DetailsSortKey) {
  if (detailsSortKey.value === key) {
    detailsSortDirection.value = detailsSortDirection.value === 'desc' ? 'asc' : 'desc'
  } else {
    detailsSortKey.value = key
    detailsSortDirection.value = 'desc'
  }
}

function detailsSortIcon(key: DetailsSortKey) {
  if (effectiveDetailsSortKey.value !== key) return 'fas fa-sort'
  return detailsSortDirection.value === 'desc' ? 'fas fa-sort-down' : 'fas fa-sort-up'
}

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
  if (!tooltip.value.visible) return
  tooltip.value.x = event.clientX
  tooltip.value.y = event.clientY
}

function hideTooltip() {
  tooltip.value.visible = false
}

function barWidth(value: number, max: number) {
  return Math.max((value / max) * 100, value > 0 ? 3 : 0)
}

function resetFilters() {
  applyObservedDateRange()
  selectedGroupId.value = 'all'
  selectedUserRole.value = 'all'
  contentMode.value = 'groups'
  detailsSearch.value = ''
  showAllMessageDetails.value = false
  detailsSortKey.value = 'value'
  detailsSortDirection.value = 'desc'
}

const exportOptions = computed<ExportOption[]>(() => [
  SUMMARY_OPTION,
  {
    ...DETAILS_OPTION,
    description: contentMode.value === 'groups'
      ? 'One row per group in the details table, with its filters'
      : 'One row per user in the details table, with its filters',
    disabled: contentMode.value === 'users' && (!sourceAvailable('users') || !sourceAvailable('groups')),
  },
])

function messagesSummary() {
  const { start, end } = periodDateRange()
  const previous = previousPeriodMetrics.value
  const rows: SummaryRow[] = [
    figure('Messages', 'Messages (all time)', totalMessages.value, 'messages'),
    figure('Messages', 'Messages in the period', periodTotal.value, 'messages'),
    figure('Messages', 'Messages in the same period last year', previous.messages, 'messages'),
    figure('Messages', 'Groups with messages', groupsWithMessages.value, 'groups'),
    figure('Messages', 'Groups with messages last year', previous.groupsWithMessages, 'groups'),
    figure('Messages', 'Group coverage', groupCoverage.value, '%', `Of ${data.value.totalGroups} groups`),
    figure('Messages', 'Average per group', averagePerGroup.value, 'messages', 'Groups with messages'),
    figure('Messages', 'Average per group last year', previous.averagePerGroup, 'messages'),
    figure('Messages', 'Most active group', mostActiveGroup.value.name, '', `${mostActiveGroup.value.value} messages`),
    figure('Messages', 'Least active group', leastActiveGroup.value.name, '', `${leastActiveGroup.value.value} messages`),
    ...messageInsightItems.value.map((item) => figure('Key insights', item.text, item.value)),
    ...timeSeries.value.keys.map((key, index) =>
      figure(`Messages over time (${chartPeriodName.value})`, key, timeSeries.value.values[index] ?? 0, 'messages'),
    ),
    ...breakdownItems.value.map((item) =>
      figure(contentMode.value === 'groups' ? 'Messages by group' : 'Messages by user', item.name, item.value, 'messages'),
    ),
  ]
  return {
    fileName: exportFileName('messages', 'summary', `${start} to ${end}`),
    csv: summaryCsv({
      page: 'Messages',
      covers: `${start} to ${end} (UTC)`,
      filters: [
        ['View', contentMode.value],
        ['Group', selectedGroupLabel.value],
        ['Trend interval', interval.value],
        ...(contentMode.value === 'users' ? [['Role', selectedUserRole.value] as [string, string]] : []),
      ],
      dataAsOf: datasetAnchorDay.value,
      unavailable: sourceLabels(unavailableSources.value),
    }, rows),
  }
}

function messagesDetails() {
  const { start, end } = periodDateRange()
  const scope = showAllMessageDetails.value ? 'all dates' : `${start} to ${end}`
  if (contentMode.value === 'groups') {
    return {
      fileName: exportFileName('messages', 'details', `groups ${scope}`),
      csv: detailsCsv(
        ['Group ID', 'Group', 'Messages', 'Average per Day', 'Messages (Last 7 Days)', 'Share of Messages (%)'],
        filteredSortedTableGroups.value.map((group) => [group.id, group.name, group.value, group.avgPerDay, group.last7Days, group.share]),
      ),
    }
  }
  return {
    fileName: exportFileName('messages', 'details', `users ${scope}`),
    csv: detailsCsv(
      ['User ID', 'User', 'Role', 'Groups', 'Messages', 'Messages (Last 7 Days)'],
      filteredSortedTableUsers.value.map((user) => [
        user.id,
        user.name,
        roleForItem(user),
        userGroupName(user.id).replace(/^Group (—|unavailable)$/, ''),
        user.value,
        user.last7Days,
      ]),
    ),
  }
}

function exportCsv(kind: ExportKind) {
  exportError.value = runExport(kind === 'summary' ? messagesSummary : messagesDetails)
}
</script>

<style src="@/assets/analytics-theme.css">
.messages-analytics-page .filter-card > label:first-child {
  min-width: 210px;
}


.message-value-label {
  fill: var(--analytics-ui-text, #174243);
  font-size: 11px;
  font-weight: 700;
  pointer-events: none;
}

.messages-analytics-page .filter-card {
  flex-wrap: wrap;
}

.messages-analytics-page .filter-card label {
  min-width: 170px;
}

.messages-analytics-page .filter-card > label:first-child {
  width: 135px;
  min-width: 135px;
  max-width: 135px;
  flex: 0 0 135px;
}

.messages-analytics-page .filter-card .reset-button {
  align-self: end;
}

</style>

<style scoped>
.filter-scope-note {
  margin: -6px 0 18px;
  color: var(--analytics-ui-muted, #5b6f69);
  font-size: 0.875rem;
  line-height: 1.45;
}

.messages-analytics-page {
  min-height: 100%;
  padding: 28px 32px 40px;
  background: var(--analytics-ui-page, #f7faf9);
  color: var(--analytics-ui-text, #153f3c);
}

.page-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 24px;
  margin-bottom: 22px;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
  color: var(--analytics-ui-muted, #59706e);
  font-size: 14px;
}

.breadcrumb a {
  color: var(--analytics-ui-muted, #59706e);
  text-decoration: none;
}

.breadcrumb a:hover {
  color: var(--analytics-ui-accent, #08765d);
  text-decoration: underline;
}

.breadcrumb-separator {
  color: var(--analytics-ui-muted, #9aaaa7);
}


.title-line {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.title-line h1 {
  margin: 0;
  color: var(--analytics-ui-text, #163f3c);
  font-size: 36px;
  line-height: 1.15;
  font-weight: 800;
}

.heading-copy p {
  margin: 7px 0 0;
  color: var(--analytics-ui-muted, #617572);
  font-size: 16px;
}

.demo-badge {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  padding: 0 10px;
  border: 1px solid var(--analytics-ui-control-border, #f0d487);
  border-radius: 999px;
  background: var(--analytics-ui-soft, #fff7df);
  color: var(--analytics-ui-warning, #916700);
  font-size: 12px;
  font-weight: 700;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 0;
  flex-shrink: 0;
}

.year-control,
.export-button {
  height: 46px;
  border-radius: 12px;
  background: var(--analytics-ui-surface, #ffffff);
  font-size: 14px;
  font-weight: 700;
}

.year-control {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  width: 120px;
  padding: 0 13px;
  border: 1px solid var(--analytics-ui-control-border, #9fd8c7);
  color: var(--analytics-ui-accent, #017151);
}

.year-control i {
  color: var(--analytics-ui-accent, #017151);
}

.year-control select {
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
  padding: 0 16px;
  border: 1px solid var(--analytics-ui-control-border, #9fd8c7);
  color: var(--analytics-ui-accent, #017151);
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;
}

.export-button:hover {
  background: var(--analytics-ui-selected, #ecf8f4);
  border-color: var(--analytics-ui-control-border, #74c9b3);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.kpi-card,
.filter-card,
.analytics-card {
  border: 1px solid var(--analytics-ui-border, #e1e9e6);
  border-radius: 12px;
  background: var(--analytics-ui-surface, #fff);
  box-shadow: 0 8px 22px rgba(16, 32, 27, 0.035);
}

.kpi-card {
  min-height: 120px;
  display: flex;
  align-items: flex-start;
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
}

.kpi-icon.blue { background: color-mix(in srgb, #39687B 14%, var(--analytics-ui-surface, white)); color: var(--analytics-ui-secondary, #39687B); }
.kpi-icon.purple { background: color-mix(in srgb, #5EA99E 14%, var(--analytics-ui-surface, white)); color: var(--analytics-ui-muted, #5EA99E); }
.kpi-icon.teal { background: color-mix(in srgb, var(--analytics-ui-soft, #BAD7B8) 55%, var(--analytics-ui-surface, white)); color: var(--analytics-ui-accent, #017151); }
.kpi-icon.orange { background: color-mix(in srgb, var(--analytics-ui-warning-bg, #F1E5A6) 55%, var(--analytics-ui-surface, white)); color: var(--analytics-ui-text, #174243); }
.kpi-icon.red { background: color-mix(in srgb, var(--analytics-ui-soft, #BAD7B8) 45%, var(--analytics-ui-surface, white)); color: var(--analytics-ui-muted, #5EA99E); }

.kpi-card > div {
  min-width: 0;
  display: grid;
  grid-template-rows: 34px 38px 34px;
  align-content: start;
}

.kpi-label {
  display: flex;
  align-items: flex-start;
  color: var(--analytics-ui-muted, #516966);
  font-size: 12px;
  font-weight: 700;
  line-height: 17px;
}

.kpi-card strong {
  display: flex;
  align-items: center;
  margin: 0;
  color: var(--analytics-ui-accent, #12261f);
  font-size: 30px;
  line-height: 38px;
  white-space: nowrap;
}

.kpi-card strong.text-value {
  align-items: flex-start;
  font-size: 30px;
  line-height: 38px;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.kpi-card strong.text-value.is-compact {
  font-size: 18px;
  line-height: 19px;
}

.group-name-kpi {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  grid-template-rows: auto auto;
  align-items: start;
  column-gap: 12px;
  row-gap: 8px;
}

.group-name-kpi > .kpi-icon {
  grid-column: 1;
  grid-row: 1;
}

.group-name-kpi > div {
  grid-column: 2;
  grid-row: 1;
  min-width: 0;
  display: block;
}

.group-name-kpi .kpi-label {
  display: block;
  margin-bottom: 8px;
}

.group-name-kpi strong.text-value {
  display: block;
  line-height: 1.05;
}

.group-name-kpi > small {
  grid-column: 1;
  grid-row: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding-top: 0;
  color: var(--analytics-ui-muted, #748783);
  line-height: 1.05;
}

.group-name-kpi > small.group-message-count strong {
  display: block;
  margin: 0;
  color: var(--analytics-ui-accent, #12261f);
  font-size: 18px;
  line-height: 20px;
  white-space: nowrap;
}

.group-name-kpi > small.group-message-count span {
  display: block;
  margin-top: 1px;
  font-size: 10px;
  line-height: 12px;
}
.kpi-card small {
  display: flex;
  align-items: flex-start;
  margin: 0;
  padding-top: 5px;
  color: var(--analytics-ui-muted, #748783);
  font-size: 11px;
  line-height: 15px;
}

.filter-card {
  display: flex;
  align-items: end;
  gap: 22px;
  margin-bottom: 16px;
  padding: 12px 16px;
}

.filter-card label {
  min-width: 210px;
  display: grid;
  gap: 6px;
}

.filter-card label span {
  color: var(--analytics-ui-muted, #425e59);
  font-size: 12px;
  font-weight: 700;
}

.filter-card select,
.filter-card input {
  height: 38px;
  box-sizing: border-box;
  width: 100%;
  padding: 0 34px 0 11px;
  border: 1px solid var(--analytics-ui-border, #dbe5e2);
  border-radius: 8px;
  background: var(--analytics-ui-surface, #fff);
  color: var(--analytics-ui-text, #234844);
  font-size: 13px;
}

.reset-button {
  height: 38px;
  margin-left: auto;
  padding: 0 13px;
  border: 1px solid var(--analytics-ui-border, #d7dff2);
  border-radius: 8px;
  background: var(--analytics-ui-surface, #fff);
  color: var(--analytics-ui-secondary, #39687B);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.analytics-grid {
  display: grid;
  gap: 14px;
  margin-bottom: 14px;
}

.top-grid {
  grid-template-columns: minmax(0, 1.9fr) minmax(285px, 0.7fr);
}

.lower-grid {
  grid-template-columns: minmax(0, 1.9fr) minmax(285px, 0.7fr);
  align-items: stretch;
}

.right-stack {
  min-width: 0;
  display: grid;
  grid-template-rows: auto auto;
  gap: 14px;
}

.details-card,
.breakdown-card {
  min-height: 0;
}

.insights-card {
  min-height: 0;
}

.analytics-card {
  min-width: 0;
  padding: 16px;
}

.card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.card-heading h2 {
  margin: 0;
  color: var(--analytics-ui-text, #163f3c);
  font-size: 18px;
  font-weight: 800;
}

.card-heading p {
  margin: 4px 0 0;
  color: var(--analytics-ui-muted, #71827f);
  font-size: 12px;
}

.period-pill {
  padding: 6px 9px;
  border: 1px solid var(--analytics-ui-border, #e0e7e5);
  border-radius: 8px;
  color: var(--analytics-ui-muted, #526864);
  font-size: 11px;
  font-weight: 700;
}

.line-chart {
  min-height: 300px;
}

.line-chart svg {
  display: block;
  width: 100%;
  height: 260px;
  overflow: visible;
}

.grid-line {
  stroke: var(--analytics-ui-border, #e7eeec);
  stroke-width: 1;
}

.message-area {
  fill: rgba(186, 215, 184, 0.28);
}

.message-line {
  fill: none;
  stroke: #39687B;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.message-dot {
  fill: #39687B;
  stroke: var(--analytics-ui-surface, #fff);
  stroke-width: 2;
}

.chart-labels {
  display: grid;
  gap: 3px;
  padding: 2px 6px 0 44px;
}

.chart-labels span {
  min-width: 0;
  color: var(--analytics-ui-muted, #71827f);
  font-size: 10px;
  text-align: center;
}

.horizontal-bars {
  display: grid;
  gap: 11px;
}

.horizontal-row {
  display: grid;
  grid-template-columns: 28px minmax(74px, 0.8fr) minmax(72px, 1.35fr) 46px;
  align-items: center;
  gap: 9px;
  min-width: 0;
  padding: 5px;
}

.rank {
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  border-radius: 50%;
  background: var(--analytics-ui-soft, #f2f4f8);
  color: var(--analytics-ui-muted, #647270);
  font-size: 10px;
  font-weight: 800;
}

.row-name {
  overflow: hidden;
  color: var(--analytics-ui-muted, #425e59);
  font-size: 12px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.horizontal-track {
  height: 12px;
  overflow: hidden;
  border-radius: 3px;
  background: var(--analytics-ui-soft, #f0f2f4);
}

.horizontal-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.purple-fill { background: #5EA99E; }

.teal-fill { background: #017151; }

.horizontal-row strong {
  color: var(--analytics-ui-text, #314e49);
  font-size: 11px;
  text-align: right;
}

.user-bars {
  padding-top: 3px;
}

.table-card {
  overflow: hidden;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 580px;
  border-collapse: collapse;
}

th,
td {
  padding: 9px 10px;
  border-bottom: 1px solid var(--analytics-ui-border, #edf1ef);
  color: var(--analytics-ui-muted, #425e59);
  font-size: 12px;
  text-align: left;
}

th {
  background: var(--analytics-ui-soft, #edf6fa);
  color: var(--analytics-ui-text, #174243);
  font-size: 11px;
  font-weight: 800;
}

tbody tr:hover {
  background: var(--analytics-ui-surface, #f7fbfa);
}

.insight-list {
  display: grid;
  gap: 9px;
}

.insight-row {
  display: grid;
  grid-template-columns: 34px 80px 1fr;
  align-items: center;
  gap: 9px;
  padding: 9px 10px;
  border-radius: 8px;
}

.insight-icon {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 8px;
}

.insight-row strong {
  font-size: 17px;
}

.insight-row p {
  margin: 0;
  color: var(--analytics-ui-muted, #60736f);
  font-size: 11px;
}

.blue-insight { background: color-mix(in srgb, #39687B 10%, var(--analytics-ui-surface, white)); }
.blue-insight .insight-icon, .blue-insight strong { color: var(--analytics-ui-secondary, #39687B); }
.purple-insight { background: color-mix(in srgb, #5EA99E 12%, var(--analytics-ui-surface, white)); }
.purple-insight .insight-icon, .purple-insight strong { color: var(--analytics-ui-muted, #5EA99E); }
.orange-insight { background: color-mix(in srgb, var(--analytics-ui-warning-bg, #F1E5A6) 55%, var(--analytics-ui-surface, white)); }
.orange-insight .insight-icon, .orange-insight strong { color: var(--analytics-ui-text, #174243); }
.teal-insight { background: color-mix(in srgb, var(--analytics-ui-soft, #BAD7B8) 35%, var(--analytics-ui-surface, white)); }
.teal-insight .insight-icon, .teal-insight strong { color: var(--analytics-ui-accent, #017151); }

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
  background: rgba(236, 248, 244, 0.65);
}

.interactive-svg-point {
  transition: r 0.12s ease;
}

.interactive-svg-point:hover {
  r: 7px;
}

@media (max-width: 1250px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .top-grid,
  .lower-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 780px) {
  .messages-analytics-page {
    padding: 20px 16px;
  }

  .page-heading {
    grid-template-columns: 1fr;
  }

  .page-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .year-control,
  .export-button {
    flex: 1;
    width: auto;
  }

  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .filter-card {
    align-items: stretch;
    flex-direction: column;
    gap: 12px;
  }

  .filter-card label {
    min-width: 0;
  }

  .reset-button {
    width: 100%;
    margin-left: 0;
  }

  .horizontal-row {
    grid-template-columns: 24px 70px minmax(70px, 1fr) 46px;
  }

  .title-line h1 {
    font-size: 30px;
  }
}

.breakdown-heading,
.details-heading {
  align-items: center;
}

.breakdown-toggle {
  display: inline-flex;
  flex: 0 0 auto;
  gap: 3px;
  padding: 3px;
  border: 1px solid var(--analytics-ui-border, #e0e8e5);
  border-radius: 8px;
  background: var(--analytics-ui-surface, #f7faf9);
}

.breakdown-toggle button {
  height: 28px;
  padding: 0 9px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--analytics-ui-muted, #627572);
  font-size: 10px;
  font-weight: 800;
  cursor: pointer;
}

.breakdown-toggle button.active {
  background: var(--analytics-ui-surface, #ffffff);
  color: var(--analytics-ui-accent, #017151);
  box-shadow: 0 1px 3px rgba(30, 55, 50, 0.09);
}

.mini-period-control select {
  height: 34px;
  padding: 0 28px 0 10px;
  border: 1px solid var(--analytics-ui-border, #dfe7e4);
  border-radius: 8px;
  background: var(--analytics-ui-surface, #fff);
  color: var(--analytics-ui-muted, #475f5a);
  font-size: 11px;
  font-weight: 700;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

.details-card .table-wrap {
  min-height: 355px;
}

.breakdown-card .horizontal-bars {
  gap: 9px;
}

.insights-card .card-heading {
  margin-bottom: 9px;
}

.insight-row {
  min-height: 48px;
}

.chart-with-y-axis {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: stretch;
}

.y-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 2px 0 24px;
  color: var(--analytics-ui-muted, #7a8984);
  font-size: 10px;
  line-height: 1;
  text-align: right;
}

.y-axis-line {
  border-left: 1px solid var(--analytics-ui-border, #d9e2df);
  padding-left: 8px;
}

.y-axis-title {
  color: var(--analytics-ui-muted, #667975);
  font-size: 10px;
  font-weight: 700;
  text-align: center;
}


.breakdown-card .horizontal-bars {
  max-height: 430px;
  overflow-y: auto;
  padding-right: 6px;
  scrollbar-gutter: stable;
}

.breakdown-card .horizontal-bars::-webkit-scrollbar {
  width: 8px;
}

.breakdown-card .horizontal-bars::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: var(--analytics-ui-soft, #d5deda);
}

.breakdown-card .horizontal-bars::-webkit-scrollbar-track {
  background: transparent;
}


/* BTF message chart series */
.message-line { stroke: #39687B !important; }
.message-dot { fill: #39687B !important; }
.purple-fill { background: #5EA99E !important; }
.teal-fill { background: #017151 !important; }

/* Visual refinements */
.messages-analytics-page .message-area {
  fill: rgba(186, 215, 184, 0.28) !important;
}

.chart-range-summary {
  display: flex;
  min-width: 155px;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 2px;
  padding: 8px 12px;
  border: 1px solid var(--analytics-ui-control-border, #9fd8c7);
  border-radius: 10px;
  background: var(--analytics-ui-surface, #ffffff);
  color: var(--analytics-ui-text, #174243);
}

.chart-range-summary span {
  color: var(--analytics-ui-accent, #017151);
  font-size: 11px;
  font-weight: 700;
}

.chart-range-summary strong {
  font-size: 11px;
  font-weight: 600;
}

.chart-labels span {
  white-space: normal;
  line-height: 1.2;
}

/* Keep Messages by Group/User the same height regardless of dataset size */
.breakdown-card {
  height: 390px !important;
  min-height: 390px !important;
  overflow: hidden;
}

.breakdown-scroll {
  max-height: 292px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 5px;
}

.breakdown-actions,
.details-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.show-all-control {
  display: inline-flex;
  height: 34px;
  align-items: center;
  gap: 7px;
  padding: 0 10px;
  border: 1px solid var(--analytics-ui-border, #bad7b8);
  border-radius: 9px;
  background: var(--analytics-ui-surface, #fff);
  color: var(--analytics-ui-muted, #425e59);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
}

.show-all-control input {
  width: 15px;
  height: 15px;
  margin: 0;
  accent-color: #007f5f;
}

.message-sort-button {
  display: inline-grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid var(--analytics-ui-border, #d7e3e0);
  border-radius: 9px;
  background: var(--analytics-ui-surface, #ffffff);
  color: var(--analytics-ui-accent, #017151);
  cursor: pointer;
}

.message-sort-button:hover {
  background: var(--analytics-ui-selected, #ecf8f4);
}

.details-search {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.details-search i {
  position: absolute;
  left: 10px;
  color: var(--analytics-ui-muted, #5EA99E);
  font-size: 11px;
  pointer-events: none;
}

.details-search input {
  width: 170px;
  height: 34px;
  padding: 0 10px 0 29px;
  border: 1px solid var(--analytics-ui-border, #bad7b8);
  border-radius: 9px;
  background: var(--analytics-ui-surface, #ffffff);
  color: var(--analytics-ui-text, #174243);
  font-size: 11px;
}

.details-card {
  height: 500px;
  min-height: 500px;
  overflow: hidden;
}

.message-details-table {
  width: 100%;
  min-width: 100%;
  table-layout: fixed;
}

.message-details-table th:nth-child(1),
.message-details-table td:nth-child(1) {
  width: 6%;
}

.message-details-table th:nth-child(2),
.message-details-table td:nth-child(2) {
  width: 22%;
}

.message-details-table th:nth-child(3),
.message-details-table td:nth-child(3) {
  width: 22%;
}

.message-details-table th:nth-child(4),
.message-details-table td:nth-child(4) {
  width: 19%;
}

.message-details-table th:nth-child(5),
.message-details-table td:nth-child(5) {
  width: 31%;
}

.message-details-table th,
.message-details-table td {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-details-table th {
  overflow: visible;
  text-overflow: clip;
  white-space: normal;
  line-height: 1.2;
}

.details-table-scroll {
  max-height: 390px;
  overflow-y: auto !important;
  overflow-x: auto !important;
}

.details-table-scroll thead th {
  position: sticky;
  top: 0;
  z-index: 2;
}

.table-sort-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--analytics-ui-text, #174243);
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.table-sort-button i {
  color: var(--analytics-ui-muted, #5EA99E);
  font-size: 10px;
}

.message-details-table th:nth-child(3) .table-sort-button {
  white-space: nowrap;
}

/* Align the two top cards exactly */
.top-grid {
  align-items: stretch !important;
}

.top-grid > .analytics-card {
  height: 410px !important;
  min-height: 410px !important;
}

.breakdown-card {
  display: flex;
  flex-direction: column;
  overflow: hidden !important;
}

.breakdown-card .card-heading {
  flex: 0 0 auto;
}

.breakdown-scroll {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none !important;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 6px;
  padding-bottom: 24px; /* white breathing space so the last row is never cut */
  scroll-padding-bottom: 24px;
}

/*
 * The details card sets this row's height. Size containment stops a long user
 * table from making the grid row grow; the table then scrolls inside the card
 * and Key Insights stretches to match it.
 */
.lower-grid {
  align-items: stretch !important;
}

.details-card {
  display: flex;
  height: 100% !important;
  min-height: 480px !important;
  flex-direction: column;
  overflow: hidden !important;
  contain: size;
}

.details-card .card-heading {
  flex: 0 0 auto;
}

.details-table-scroll {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none !important;
  overflow-y: auto !important;
  overflow-x: auto !important;
  padding-bottom: 22px;
  scroll-padding-bottom: 22px;
}

.right-stack {
  align-self: stretch;
  grid-template-rows: minmax(0, 1fr) !important;
}


/* User group context in message views */
.user-name-line {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.user-name-line > span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-circle {
  display: inline-grid;
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
  place-items: center;
  border-radius: 50%;
  font-size: 8px;
  font-weight: 800;
  line-height: 1;
}

.role-circle-mentor {
  background: var(--analytics-ui-soft, #dff1e6);
  color: var(--analytics-ui-accent, #017151);
}

.role-circle-student {
  background: var(--analytics-ui-soft, #e3edf2);
  color: var(--analytics-ui-secondary, #39687b);
}

.role-circle-supervisor {
  background: var(--analytics-ui-soft, #eee8f8);
  color: var(--analytics-ui-secondary, #6848a8);
}

.role-circle-user {
  background: var(--analytics-ui-soft, #eef3f3);
  color: var(--analytics-ui-muted, #52615c);
}

.user-row-name {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 1px;
}

.user-row-name > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-row-name small,
.details-user-cell small {
  color: var(--analytics-ui-muted, #7a8f8b);
  font-size: 9px;
  font-weight: 600;
  line-height: 1.15;
  white-space: nowrap;
}

.details-user-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.details-user-cell strong {
  color: var(--analytics-ui-muted, #425e59);
  font-weight: 600;
}

.role-pill {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.role-pill.role-student {
  background: rgba(57, 104, 123, 0.14);
  color: var(--analytics-ui-secondary, #39687B);
}

.role-pill.role-mentor {
  background: rgba(94, 169, 158, 0.18);
  color: var(--analytics-ui-accent, #017151);
}

.role-pill.role-supervisor {
  background: rgba(94, 169, 158, 0.16);
  color: var(--analytics-ui-muted, #2f7f76);
}


/* Sticky message analytics filters — same behaviour as Activity Analytics. */
.messages-analytics-page {
  overflow: visible !important;
}

.messages-analytics-page .sticky-filter-card {
  position: -webkit-sticky !important;
  position: sticky !important;
  top: 0 !important;
  z-index: 100 !important;
  isolation: isolate;
  background: var(--analytics-ui-page, #ffffff) !important;
  box-shadow: 0 8px 18px rgba(23, 66, 67, 0.10) !important;
}

.messages-analytics-page .sticky-filter-card::before {
  content: "";
  position: absolute;
  inset: -2px 0 auto;
  height: 2px;
  background: var(--analytics-ui-page, #f7faf9);
  pointer-events: none;
}


/* Final Messages Analytics layout refinements */
.messages-analytics-page .filter-card > label:first-child {
  width: 120px !important;
  min-width: 120px !important;
  max-width: 120px !important;
  flex: 0 0 120px !important;
}

.messages-analytics-page .filter-card > label:first-child select {
  width: 120px;
}

.messages-analytics-page .user-name-line {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: minmax(0, 1fr) 20px;
  align-items: center;
  column-gap: 6px;
}

.messages-analytics-page .user-name-line > span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.messages-analytics-page .role-circle {
  justify-self: center;
  align-self: center;
}

.messages-analytics-page .role-circle-student {
  background: rgba(57, 104, 123, 0.14);
  color: var(--analytics-ui-secondary, #39687B);
}

.messages-analytics-page .role-circle-mentor {
  background: rgba(94, 169, 158, 0.18);
  color: var(--analytics-ui-accent, #017151);
}

.messages-analytics-page .role-circle-supervisor {
  background: rgba(94, 169, 158, 0.16);
  color: var(--analytics-ui-muted, #2f7f76);
}


.messages-analytics-page .filter-card > label:nth-child(2) {
  width: 150px !important;
  min-width: 150px !important;
  max-width: 150px !important;
  flex: 0 0 150px !important;
}

.messages-analytics-page .filter-card > label:nth-child(2) select,
.messages-analytics-page .filter-card > label:nth-child(2) input {
  width: 150px;
}


.messages-analytics-page .horizontal-row.interactive-chart-row,
.messages-analytics-page .message-details-table tbody tr.interactive-chart-row {
  cursor: default;
}

/* Shared analytics filter appearance (matches Registration and Activity). */
.messages-analytics-page .sticky-filter-card {
  display: grid !important;
  grid-template-columns:
    minmax(100px, 0.7fr)
    repeat(2, minmax(140px, 1.2fr))
    minmax(110px, 0.85fr)
    minmax(140px, 1.15fr)
    minmax(132px, 0.9fr) !important;
  gap: 12px !important;
  align-items: end !important;
  padding: 16px !important;
  border: 1px solid var(--analytics-ui-border, #d7e3df) !important;
  border-radius: 14px !important;
  background: var(--analytics-ui-page, #fff) !important;
}

.messages-analytics-page .sticky-filter-card.is-user-view {
  grid-template-columns:
    minmax(90px, 0.65fr)
    repeat(2, minmax(130px, 1.15fr))
    minmax(100px, 0.8fr)
    minmax(130px, 1.1fr)
    minmax(100px, 0.75fr)
    minmax(132px, 0.9fr) !important;
}

.messages-analytics-page .sticky-filter-card label,
.messages-analytics-page .sticky-filter-card > label:first-child,
.messages-analytics-page .sticky-filter-card > label:nth-child(2) {
  width: auto !important;
  min-width: 0 !important;
  max-width: none !important;
  flex: none !important;
  gap: 6px !important;
}

.messages-analytics-page .sticky-filter-card label > span {
  color: var(--analytics-ui-muted, #425e59) !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  line-height: 1.2;
}

.messages-analytics-page .sticky-filter-card select,
.messages-analytics-page .sticky-filter-card input[type='date'] {
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

.messages-analytics-page .sticky-filter-card .reset-button {
  width: auto !important;
  min-width: 132px !important;
  height: 42px !important;
  margin: 0 !important;
  border: 1px solid var(--analytics-ui-control-border, #79bdb4) !important;
  border-radius: 10px !important;
  background: var(--analytics-ui-page, #fff) !important;
  color: var(--analytics-ui-accent, #017151) !important;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .messages-analytics-page .sticky-filter-card {
    grid-template-columns: repeat(3, minmax(170px, 1fr)) !important;
  }

  .messages-analytics-page .sticky-filter-card .reset-button {
    width: 100% !important;
  }
}

@media (max-width: 720px) {
  .messages-analytics-page .sticky-filter-card {
    grid-template-columns: minmax(0, 1fr) !important;
  }
}

/* All six summary cards share the same title, value and helper tracks. */
.messages-analytics-page .kpi-grid .kpi-card {
  display: flex !important;
  align-items: flex-start !important;
  min-height: 0 !important;
}

.messages-analytics-page .kpi-grid .kpi-card > div:not(.kpi-icon) {
  display: grid !important;
  min-width: 0 !important;
  flex: 1 1 0% !important;
  align-self: stretch;
  grid-template-rows: 34px auto 34px !important;
  align-content: start;
}

.messages-analytics-page .kpi-grid .kpi-card .kpi-label {
  display: flex !important;
  grid-row: 1;
  align-items: flex-start;
  margin: 0 !important;
}

.messages-analytics-page .kpi-grid .kpi-card > div:not(.kpi-icon) > :is(strong, .analytics-value-row) {
  grid-row: 2;
  align-self: center;
}

.messages-analytics-page .kpi-grid .kpi-card > div:not(.kpi-icon) > small {
  grid-row: 3;
  align-self: start;
  margin: 0 !important;
}

.messages-analytics-page .kpi-grid .group-name-kpi .text-value {
  display: -webkit-box !important;
  font-size: 30px !important;
  line-height: 38px !important;
  max-height: 76px;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.messages-analytics-page .kpi-grid .group-name-kpi .text-value.is-compact {
  font-size: 18px !important;
  line-height: 19px !important;
  max-height: 76px;
  -webkit-line-clamp: 4;
}

.messages-analytics-page .kpi-grid .group-message-count {
  display: flex !important;
  align-items: baseline !important;
  gap: 4px;
  padding: 0 !important;
}

.messages-analytics-page .kpi-grid .group-message-count strong,
.messages-analytics-page .kpi-grid .group-message-count span {
  display: inline !important;
  margin: 0 !important;
}

.messages-analytics-page .kpi-grid .group-message-count strong {
  font-size: 18px !important;
  line-height: 20px !important;
}

.messages-analytics-page .kpi-grid .group-message-count span {
  font-size: 10px !important;
  line-height: 12px !important;
}

</style>
