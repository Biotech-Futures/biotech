<template>
  <section class="groups-analytics-page">
    <div class="page-heading">
      <div class="heading-copy">
        <div class="breadcrumb">
          <RouterLink to="/dashboard">Home</RouterLink>
          <span class="breadcrumb-separator">›</span>
          <RouterLink to="/analytics">Analytics</RouterLink>
          <span class="breadcrumb-separator">›</span>
          <span>Groups Analytics</span>
        </div>

        <div class="title-line">
          <h1>Groups Analytics</h1>
          
        </div>
        <p>Understand group structure, mentor allocation and group health.</p>
      </div>

      <div class="page-actions">
        <label class="year-control">
          <i class="fas fa-calendar" aria-hidden="true"></i>
          <select v-model.number="selectedYear" aria-label="Select analytics year">
            <option v-for="year in availableYears" :key="year" :value="year">
              {{ year }}
            </option>
          </select>
        </label>

        <button type="button" class="export-button" :disabled="loading || !!loadError || exporting" @click="exportCsv">
          <i class="fas fa-download" aria-hidden="true"></i>
          Export CSV
        </button>
      </div>
    </div>

    <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />

    <p v-if="exportError" role="alert">{{ exportError }}</p>

    <div v-if="loadError" class="range-error" role="alert">
      <span>Groups analytics could not be loaded. {{ loadError }}</span>
      <button type="button" @click="initializeGroups(true)">Retry</button>
    </div>
    <p v-else-if="loading" role="status">Loading groups analytics…</p>
    <template v-if="!loading && !loadError">

    <section class="kpi-grid" aria-label="Groups analytics summary">
      <article class="kpi-card">
        <div class="kpi-icon purple"><i class="fas fa-users"></i></div>
        <div>
          <span class="kpi-label">Total Groups</span>
          <div class="kpi-value-row">
            <strong>{{ data.totalGroups }}</strong>
            <span class="trend-up">{{ data.groupGrowth === null ? 'N/A' : `↑ ${data.groupGrowth}%` }}</span>
          </div>
          <small>{{ data.groupGrowth === null ? 'No historical snapshot available' : 'vs. last period' }}</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon teal"><i class="fas fa-people-group"></i></div>
        <div>
          <span class="kpi-label">Average Group Size</span>
          <div class="kpi-value-row">
            <strong>{{ data.averageGroupSize }}</strong>
            <span class="trend-down">{{ data.avgSizeChange === null ? 'N/A' : `↓ ${data.avgSizeChange}%` }}</span>
          </div>
          <small>{{ data.avgSizeChange === null ? 'No historical snapshot available' : 'vs. last period' }}</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon blue"><i class="fas fa-shield-halved"></i></div>
        <div>
          <span class="kpi-label">Groups with Mentor</span>
          <strong class="kpi-value">{{ data.groupsWithMentor }}</strong>
          <small>{{ percent(data.groupsWithMentor, data.totalGroups) }}%</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon red"><i class="fas fa-user-group"></i></div>
        <div>
          <span class="kpi-label">Groups without Mentor</span>
          <strong class="kpi-value">{{ data.groupsWithoutMentor }}</strong>
          <small>{{ percent(data.groupsWithoutMentor, data.totalGroups) }}%</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon orange"><i class="fas fa-scale-balanced"></i></div>
        <div>
          <span class="kpi-label">Mentor-to-Student Ratio</span>
          <strong class="kpi-value">{{ data.mentorStudentRatio === null ? 'N/A' : `1 : ${data.mentorStudentRatio}` }}</strong>
          <small>Target 1 : 8</small>
        </div>
      </article>
    </section>

    <section class="analytics-grid groups-custom-grid">

<article class="analytics-card group-status-card">
        <h2>Group Status</h2>
        <div class="donut-layout">
          <div class="group-donut-wrap" @mouseleave="clearStatusSelection">
            <svg
              class="group-donut-svg"
              viewBox="0 0 180 180"
              role="img"
              aria-label="Group status"
            >
              <circle
                cx="90"
                cy="90"
                r="64"
                pathLength="100"
                fill="none"
                stroke="#e7ebef"
                stroke-width="24"
              />
              <circle
                v-for="segment in statusSegments"
                :key="segment.label"
                cx="90"
                cy="90"
                r="64"
                pathLength="100"
                fill="none"
                :stroke="segment.color"
                stroke-width="24"
                :stroke-dasharray="`${segment.percent} ${100 - segment.percent}`"
                :stroke-dashoffset="-segment.start"
                stroke-linecap="butt"
                class="group-donut-segment"
                :class="{ selected: selectedStatus?.label === segment.label }"
                transform="rotate(-90 90 90)"
                tabindex="0"
                @mouseenter="selectStatus(segment)"
                @focus="selectStatus(segment)"
                @blur="clearStatusSelection"
              />
            </svg>

            <div class="donut-centre group-donut-centre">
              <template v-if="selectedStatus">
                <span class="donut-selection-label">{{ selectedStatus.label }}</span>
                <strong>{{ selectedStatus.value }}</strong>
                <span>{{ selectedStatus.percent }}% of groups</span>
              </template>
              <template v-else>
                <strong>{{ data.totalGroups }}</strong>
                <span>Total Groups</span>
              </template>
            </div>
          </div>

          <div class="legend-list">
            <div
              v-for="segment in statusSegments"
              :key="segment.label"
              class="legend-row donut-legend-row"
              :class="{ selected: selectedStatus?.label === segment.label }"
              @mouseenter="selectStatus(segment)"
              @mouseleave="clearStatusSelection"
            >
              <span>
                <i class="dot" :style="{ background: segment.color }"></i>
                {{ segment.label }}
              </span>
              <strong>{{ segment.value }} ({{ segment.percent }}%)</strong>
            </div>
          </div>
        </div>
      </article>

<article class="analytics-card mentor-coverage-card">
        <h2>Mentor Coverage</h2>
        <div class="donut-layout">
          <div class="group-donut-wrap" @mouseleave="clearCoverageSelection">
            <svg
              class="group-donut-svg"
              viewBox="0 0 180 180"
              role="img"
              aria-label="Mentor coverage"
            >
              <circle
                cx="90"
                cy="90"
                r="64"
                pathLength="100"
                fill="none"
                stroke="#e7ebef"
                stroke-width="24"
              />
              <circle
                v-for="segment in coverageSegments"
                :key="segment.label"
                cx="90"
                cy="90"
                r="64"
                pathLength="100"
                fill="none"
                :stroke="segment.color"
                stroke-width="24"
                :stroke-dasharray="`${segment.percent} ${100 - segment.percent}`"
                :stroke-dashoffset="-segment.start"
                stroke-linecap="butt"
                class="group-donut-segment"
                :class="{ selected: selectedCoverage?.label === segment.label }"
                transform="rotate(-90 90 90)"
                tabindex="0"
                @mouseenter="selectCoverage(segment)"
                @focus="selectCoverage(segment)"
                @blur="clearCoverageSelection"
              />
            </svg>

            <div class="donut-centre group-donut-centre">
              <template v-if="selectedCoverage">
                <span class="donut-selection-label">{{ selectedCoverage.label }}</span>
                <strong>{{ selectedCoverage.value }}</strong>
                <span>{{ selectedCoverage.percent }}% of groups</span>
              </template>
              <template v-else>
                <strong>{{ data.totalGroups }}</strong>
                <span>Total Groups</span>
              </template>
            </div>
          </div>

          <div class="legend-list">
            <div
              v-for="segment in coverageSegments"
              :key="segment.label"
              class="legend-row donut-legend-row"
              :class="{ selected: selectedCoverage?.label === segment.label }"
              @mouseenter="selectCoverage(segment)"
              @mouseleave="clearCoverageSelection"
            >
              <span>
                <i class="dot" :style="{ background: segment.color }"></i>
                {{ segment.label }}
              </span>
              <strong>{{ segment.value }} ({{ segment.percent }}%)</strong>
            </div>
          </div>
        </div>
      </article>

<article class="analytics-card wide-distribution-card group-size-card">
        <h2>Group Size Distribution</h2>
        <div class="chart-with-y-axis">
          <div class="y-axis">
            <span v-for="tick in axisTicks(maxGroupSizeCount)" :key="tick">{{ tick }}</span>
          </div>
          <div class="y-axis-line">
            <div class="vertical-chart">
          <div
            v-for="item in groupSizeDistributionForChart"
            :key="item.label"
            class="vertical-bar-item"
          >
            <span class="bar-value">{{ item.value }}</span>
            <div class="vertical-track">
              <div
                class="vertical-fill purple-bar interactive-chart-mark"
                :style="{ height: `${barHeight(item.value, maxGroupSizeCount)}%` }"
                @mouseenter="showTooltip($event, `${item.label} students`, `${item.value} groups`, 'Group size distribution')"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              ></div>
            </div>
            <span class="bar-label">{{ item.label }}</span>
          </div>
        </div>
          </div>
        </div>
        <div class="y-axis-title">Number of Groups</div>
        <div class="axis-caption">Number of Students per Group</div>
      </article>

<article class="analytics-card wide-distribution-card ratio-card">
        <h2>Mentor-to-Student Ratio by Group</h2>
        <div class="chart-with-y-axis">
          <div class="y-axis">
            <span v-for="tick in axisTicks(maxRatioCount)" :key="tick">{{ tick }}</span>
          </div>
          <div class="y-axis-line">
            <div class="vertical-chart">
          <div
            v-for="item in data.ratioDistribution"
            :key="item.label"
            class="vertical-bar-item"
          >
            <span class="bar-value">{{ item.value }}</span>
            <div class="vertical-track">
              <div
                class="vertical-fill blue-bar interactive-chart-mark"
                :style="{ height: `${barHeight(item.value, maxRatioCount)}%` }"
                @mouseenter="showTooltip($event, `Ratio ${item.label}`, `${item.value} groups`, 'Mentor-to-student ratio')"
                @mousemove="moveTooltip"
                @mouseleave="hideTooltip"
              ></div>
            </div>
            <span class="bar-label">{{ item.label }}</span>
          </div>
        </div>
          </div>
        </div>
        <div class="y-axis-title">Number of Groups</div>
        <div class="axis-caption">Mentor-to-Student Ratio</div>
      </article>

      <article class="analytics-card compact-insights-card insights-card">
        <AnalyticsKeyInsights
          :items="groupInsightItems"
          description="Highlights group allocation, recent inactivity, and capacity conditions that may require follow-up."
        />
      </article>
    </section>


    <section class="group-issue-detail-grid" aria-label="Group allocation issues">
      <article id="students-not-assigned" class="group-issue-detail-card">
        <div class="group-issue-detail-heading">
          <div>
            <h2>Students not assigned to groups</h2>
            <p>Current students without a group assignment.</p>
          </div>
          <strong>{{ studentsNotAssignedCount }}</strong>
        </div>

        <div class="group-issue-table-wrap">
          <table class="group-issue-table">
            <thead>
              <tr>
                <th>Student</th>
                <th>Email</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="student in studentsNotAssignedRows" :key="student.id">
                <td>{{ student.name }}</td>
                <td>{{ student.email }}</td>
                <td><span class="issue-status-chip unassigned">{{ student.status }}</span></td>
              </tr>
              <tr v-if="studentsNotAssignedRows.length === 0">
                <td colspan="3" class="group-empty-state">No unassigned students.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article id="groups-without-mentors" class="group-issue-detail-card">
        <div class="group-issue-detail-heading">
          <div>
            <h2>Groups without mentors</h2>
            <p>Groups that currently require a mentor assignment.</p>
          </div>
          <strong>{{ data.groupsWithoutMentor }}</strong>
        </div>

        <div class="group-issue-table-wrap">
          <table class="group-issue-table">
            <thead>
              <tr>
                <th>Group</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="group in groupsWithoutMentorRows" :key="group.id">
                <td>{{ group.name }}</td>
                <td><span class="issue-status-chip no-mentor">{{ group.status }}</span></td>
              </tr>
              <tr v-if="groupsWithoutMentorRows.length === 0">
                <td colspan="2" class="group-empty-state">All groups have mentors assigned.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    </template>

    <ChartTooltip
      :visible="tooltip.visible"
      :x="tooltip.x"
      :y="tooltip.y"
      :title="tooltip.title"
      :value="tooltip.value"
      :detail="tooltip.detail"
    />
  </section>
</template>

<script setup lang="ts">
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import AnalyticsKeyInsights from '@/components/analytics/AnalyticsKeyInsights.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import { useRoute } from 'vue-router'
import type { GroupsAnalyticsYear } from '@/types/analytics'
import {
  analyticsYears,
  buildGroupsAnalytics,
  loadGroupsAnalyticsBundle,
  type CoreAnalyticsBundle,
} from '@/utils/liveAnalyticsData'
import type { AdminGroup, AdminUser } from '@/utils/liveAnalyticsApi'
import { downloadReportCsv } from '@/utils/reportExport'

const route = useRoute()
const availableYears = ref<number[]>([new Date().getFullYear()])
const selectedYear = ref(availableYears.value[0]!)
const liveData = ref<GroupsAnalyticsYear>({
  totalGroups: 0,
  groupGrowth: null,
  averageGroupSize: 0,
  avgSizeChange: null,
  groupsWithMentor: 0,
  groupsWithoutMentor: 0,
  mentorStudentRatio: 0,
  smallGroups: 0,
  inactiveRecent: 0,
  nearCapacity: 0,
  groupSizeDistribution: [],
  groupStatus: [],
  ratioDistribution: [],
  groupActivity: [],
})
const liveUsers = ref<AdminUser[]>([])
const liveGroups = ref<AdminGroup[]>([])
const loadError = ref('')
const loading = ref(true)
const exporting = ref(false)
const exportError = ref('')
const groupBundle = ref<CoreAnalyticsBundle | null>(null)

const analyticsRefreshBusy = ref(false)
const { lastUpdated, refreshFailed, markUpdated, markRefreshFailed } = useAnalyticsRefresh(async () => { if (!analyticsRefreshBusy.value) await initializeGroups(true, true) })

async function initializeGroups(force = false, preserveFilters = false) {
  if (analyticsRefreshBusy.value) return
  analyticsRefreshBusy.value = true
  if (!preserveFilters || !lastUpdated.value) loading.value = true
  loadError.value = ''
  try {
    const bundle = await loadGroupsAnalyticsBundle(force)
    // User records are needed for current allocation only. Keep the existing
    // group charts and year range anchored to group message activity.
    const activityBundle = { ...bundle, users: [] }
    groupBundle.value = activityBundle
    availableYears.value = analyticsYears(activityBundle)
    if (!preserveFilters || !availableYears.value.includes(selectedYear.value)) selectedYear.value = availableYears.value[0]!
    liveUsers.value = bundle.users
    liveGroups.value = bundle.groups
    liveData.value = buildGroupsAnalytics(activityBundle, selectedYear.value)
    markUpdated()
  } catch (error) {
    if (preserveFilters && lastUpdated.value) { markRefreshFailed(); return }
    loadError.value = error instanceof Error ? error.message : 'Groups analytics could not be loaded.'
  } finally {
    analyticsRefreshBusy.value = false
    loading.value = false
  }
}

onMounted(() => initializeGroups())
watch(selectedYear, (year) => {
  if (groupBundle.value) liveData.value = buildGroupsAnalytics(groupBundle.value, year)
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



const data = computed(() => liveData.value)
const groupInsightItems = computed(() => [
  {
    key: 'without-mentor',
    value: data.value.groupsWithoutMentor,
    text: `groups (${percent(data.value.groupsWithoutMentor, data.value.totalGroups)}%) do not have a mentor assigned.`,
  },
  { key: 'small', value: data.value.smallGroups, text: 'groups have fewer than 3 students.' },
  { key: 'inactive', value: data.value.inactiveRecent, text: 'groups have had no activity in the past 7 days.' },
  { key: 'capacity', value: data.value.nearCapacity, text: 'groups are nearing capacity (10+ students).' },
])

const studentsNotAssignedRows = computed(() =>
  liveUsers.value
    .filter((user) => (user.role ?? '').toLowerCase() === 'student' && !user.groupId)
    .map((user) => ({
      id: user.id,
      name: `${user.firstName} ${user.lastName}`.trim() || user.email,
      email: user.email,
      status: 'Unassigned',
    })),
)
const studentsNotAssignedCount = computed(() => studentsNotAssignedRows.value.length)

const groupsWithoutMentorRows = computed(() =>
  liveGroups.value
    .filter((group) => !group.mentor)
    .map((group) => ({ id: group.id, name: group.name, status: 'No mentor' })),
)



const groupSizeDistributionForChart = computed(() => {
  const items = [...data.value.groupSizeDistribution]

  if (!items.some((item) => item.label === '20+')) {
    items.push({
      label: '20+',
      value: 0,
    })
  }

  return items
})

const maxGroupSizeCount = computed(() =>
  Math.max(...groupSizeDistributionForChart.value.map((item) => item.value), 1),
)

const maxRatioCount = computed(() =>
  Math.max(...data.value.ratioDistribution.map((item) => item.value), 1),
)



type DonutSegment = {
  label: string
  value: number
  percent: number
  start: number
  color: string
}

const selectedStatus = ref<DonutSegment | null>(null)
const selectedCoverage = ref<DonutSegment | null>(null)

const statusSegments = computed<DonutSegment[]>(() => {
  const statusColors: Record<string, string> = {
    Active: '#017151',
    Inactive: '#39687B',
    'Not started': '#5EA99E',
  }

  let start = 0

  return data.value.groupStatus.map((item) => {
    const segment = {
      label: item.label,
      value: item.value,
      percent: percent(item.value, data.value.totalGroups),
      start,
      color: statusColors[item.label] ?? item.color,
    }

    start += segment.percent
    return segment
  })
})

const coverageSegments = computed<DonutSegment[]>(() => {
  const raw = [
    {
      label: 'With mentor',
      value: data.value.groupsWithMentor,
      color: '#017151',
    },
    {
      label: 'Without mentor',
      value: data.value.groupsWithoutMentor,
      color: '#BAD7B8',
    },
  ]

  let start = 0

  return raw.map((item) => {
    const segment = {
      ...item,
      percent: percent(item.value, data.value.totalGroups),
      start,
    }

    start += segment.percent
    return segment
  })
})

function selectStatus(segment: DonutSegment) {
  selectedStatus.value = segment
  hideTooltip()
}

function clearStatusSelection() {
  selectedStatus.value = null
}

function selectCoverage(segment: DonutSegment) {
  selectedCoverage.value = segment
  hideTooltip()
}

function clearCoverageSelection() {
  selectedCoverage.value = null
}



function axisTicks(maxValue: number, steps = 4) {
  const safeMax = Math.max(maxValue, 1)
  const rawStep = safeMax / steps
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep || 1)))
  const normalized = rawStep / magnitude
  const nice = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  const step = nice * magnitude
  const top = Math.ceil(safeMax / step) * step
  return Array.from({ length: steps + 1 }, (_, index) => Math.round(top - index * (top / steps)))
}

function percent(value: number, total: number) {
  if (!total) return 0
  return Math.round((value / total) * 100)
}

function barHeight(value: number, max: number) {
  return Math.max((value / max) * 100, value > 0 ? 4 : 0)
}





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

async function exportCsv() {
  exporting.value = true
  exportError.value = ''
  try {
    await downloadReportCsv(new URLSearchParams({ report: 'groups', year: String(selectedYear.value) }), 'groups')
  } catch (error) {
    exportError.value = error instanceof Error ? error.message : 'The report could not be downloaded.'
  } finally {
    exporting.value = false
  }
}
</script>

<style src="@/assets/analytics-theme.css"></style>

<style scoped>
.groups-analytics-page {
  padding: 28px 32px 40px;
  min-height: 100%;
  background: #f7faf9;
  color: #153f3c;
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
  color: #59706e;
  font-size: 14px;
}

.breadcrumb a {
  color: #59706e;
  text-decoration: none;
}

.breadcrumb a:hover {
  color: #08765d;
  text-decoration: underline;
}

.breadcrumb-separator {
  color: #9aaaa7;
}

.title-line {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.title-line h1 {
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

.demo-badge {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid #f0d487;
  border-radius: 999px;
  background: #fff7df;
  color: #916700;
  font-size: 12px;
  font-weight: 700;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  align-self: start;
}

.year-control,
.export-button {
  height: 46px;
  border-radius: 12px;
  background: #fff;
  font-size: 14px;
  font-weight: 700;
}

.year-control {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  width: 120px;
  padding: 0 13px;
  border: 1px solid #d7e3e0;
  color: #174844;
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
  border: 1px solid #9fd8c7;
  color: #017151;
  cursor: pointer;
}

.export-button:hover {
  background: #ecf8f4;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.kpi-card,
.analytics-card {
  border: 1px solid #e0e9e7;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 3px 12px rgba(20, 64, 60, 0.04);
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 112px;
  padding: 17px;
}

.kpi-icon {
  display: grid;
  flex: 0 0 54px;
  width: 54px;
  height: 54px;
  place-items: center;
  border-radius: 13px;
  font-size: 22px;
}

.kpi-icon.purple { color: #5EA99E; background: color-mix(in srgb, #5EA99E 14%, white); }
.kpi-icon.teal { color: #017151; background: color-mix(in srgb, #BAD7B8 55%, white); }
.kpi-icon.blue { color: #39687B; background: color-mix(in srgb, #39687B 14%, white); }
.kpi-icon.red { color: #174243; background: color-mix(in srgb, #BAD7B8 45%, white); }
.kpi-icon.orange { color: #017151; background: color-mix(in srgb, #F1E5A6 50%, white); }

.kpi-label {
  display: block;
  margin-bottom: 5px;
  color: #4e6662;
  font-size: 12px;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.kpi-value-row strong,
.kpi-value {
  display: block;
  color: #163f3c;
  font-size: 27px;
  line-height: 1.05;
}

.trend-up { color: #017151; font-weight: 700; }

.trend-down { color: #39687B; font-weight: 700; }

.kpi-card small {
  display: block;
  margin-top: 4px;
  color: #7c8d89;
  font-size: 10px;
}

.analytics-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.analytics-card {
  height: 270px;
  min-width: 0;
  overflow: hidden;
  padding: 16px;
}

.analytics-card h2 {
  margin: 0 0 12px;
  color: #163f3c;
  font-size: 16px;
  line-height: 1.2;
}

.analytics-card h2 small {
  font-size: 10px;
  font-weight: 500;
  color: #60726f;
}

.vertical-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 190px;
  padding: 5px 12px 0;
}

.vertical-bar-item {
  display: grid;
  grid-template-rows: 18px 142px 24px;
  justify-items: center;
  width: 17%;
}

.bar-value {
  color: #355953;
  font-size: 10px;
  font-weight: 700;
}

.vertical-track {
  display: flex;
  align-items: flex-end;
  width: 35px;
  height: 138px;
  border-bottom: 1px solid #dce5e2;
}

.vertical-fill {
  width: 100%;
  min-height: 4px;
  border-radius: 5px 5px 0 0;
}

.purple-bar { background: #5EA99E; }

.blue-bar { background: #39687B; }

.bar-label {
  margin-top: 5px;
  color: #647875;
  font-size: 9px;
  text-align: center;
}

.axis-caption {
  margin-top: -2px;
  color: #5f7470;
  font-size: 9px;
  text-align: center;
}

.donut-layout {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  height: 210px;
}

.donut {
  display: grid;
  flex: 0 0 150px;
  width: 150px;
  height: 150px;
  place-items: center;
  border-radius: 50%;
}

.donut-centre {
  display: grid;
  width: 92px;
  height: 92px;
  place-items: center;
  align-content: center;
  border-radius: 50%;
  background: #fff;
  text-align: center;
}

.donut-centre strong {
  color: #163f3c;
  font-size: 25px;
}

.donut-centre span {
  margin-top: 2px;
  color: #687b77;
  font-size: 10px;
}

.legend-list {
  min-width: 155px;
}

.legend-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 16px 0;
  color: #3f5b57;
  font-size: 11px;
}

.legend-row span {
  display: flex;
  align-items: center;
  gap: 7px;
}

.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.blue-dot { background: #017151; }
.grey-dot { background: #BAD7B8; }
.active-dot { background: #017151; }
.inactive-dot { background: #BAD7B8; }

.horizontal-bars {
  display: grid;
  gap: 8px;
  padding: 1px 3px 0;
}

.horizontal-row {
  display: grid;
  grid-template-columns: 62px minmax(80px, 1fr) 36px;
  align-items: center;
  gap: 8px;
  color: #3d5b57;
  font-size: 10px;
}

.row-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.horizontal-track,
.rank-track {
  overflow: hidden;
  height: 11px;
  border-radius: 4px;
  background: #edf1f0;
}

.horizontal-fill,
.rank-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.purple-fill { background: #5EA99E; }

.line-chart svg {
  display: block;
  width: 100%;
  height: 204px;
}

.grid-line {
  stroke: #edf1f0;
  stroke-width: 1;
}

.message-area {
  fill: rgba(129, 88, 238, 0.12);
}

.message-line {
  fill: none;
  stroke: #7f5af0;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.message-dot {
  fill: #7f5af0;
}

.month-labels {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  margin-top: -10px;
  padding: 0 7px 0 22px;
  color: #6f807d;
  font-size: 8px;
  text-align: center;
}

.stacked-legend {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 6px;
  color: #617571;
  font-size: 10px;
}

.stacked-legend span {
  display: flex;
  align-items: center;
  gap: 5px;
}

.stacked-bars {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  align-items: end;
  column-gap: 10px;
  height: 174px;
  padding: 0 10px;
}

.stacked-item {
  display: grid;
  grid-template-rows: 148px 18px;
  justify-items: center;
  width: 100%;
  min-width: 0;
}


.stacked-bar-wrap {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  width: 48px;
  height: 144px;
}

.stacked-value-labels {
  position: absolute;
  right: calc(50% + 12px);
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: flex-end;
  gap: 2px;
  width: 24px;
  height: 100%;
  pointer-events: none;
  font-size: 8px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.stacked-value-labels .active-value {
  color: #017151;
}

.stacked-value-labels .inactive-value {
  color: #7aa777;
}

.stacked-track {
  display: flex;
  align-items: flex-end;
  width: 16px;
  height: 144px;
  border-bottom: 1px solid #dce5e2;
}

.stacked-inactive {
  position: relative;
  width: 100%;
  border-radius: 3px 3px 0 0;
  background: #BAD7B8;
}

.stacked-active {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  border-radius: 0 0 0 0;
  background: #017151;
}

.stacked-item span {
  margin-top: 4px;
  color: #697c78;
  font-size: 8px;
}

.ranking-list {
  display: grid;
  gap: 15px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.ranking-list li {
  display: grid;
  grid-template-columns: 26px 62px minmax(90px, 1fr) 36px;
  align-items: center;
  gap: 8px;
}

.rank-number {
  display: grid;
  width: 24px;
  height: 24px;
  place-items: center;
  border-radius: 7px;
  background: #f2f5f8;
  color: #445f5b;
  font-size: 10px;
  font-weight: 800;
}

.rank-name {
  color: #415d59;
  font-size: 10px;
}

.rank-track span {
  background: #017151;
}

.ranking-list strong {
  color: #2e534d;
  font-size: 10px;
  text-align: right;
}

.insights-card h2 i {
  margin-right: 7px;
  color: #5279a5;
}

.insights-list {
  display: grid;
  gap: 10px;
  padding-top: 5px;
}

.insight-row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-height: 39px;
  border-radius: 9px;
  font-size: 10px;
}

.insight-row strong {
  display: grid;
  width: 40px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  font-size: 12px;
}

.insight-red strong { background: #BAD7B8; color: #174243; }
.insight-orange strong { background: #F1E5A6; color: #174243; }
.insight-purple strong { background: #5EA99E; color: #FFFFFF; }
.insight-blue strong { background: #39687B; color: #FFFFFF; }

.insight-row span {
  color: #425e59;
}


.interactive-chart-mark,
.interactive-chart-row,
.interactive-svg-point {
  cursor: pointer;
}

.interactive-chart-mark {
  transition: filter 0.15s ease, opacity 0.15s ease;
}

.interactive-chart-mark:hover {
  filter: brightness(0.95) saturate(1.08);
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

  .analytics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 780px) {
  .groups-analytics-page {
    padding: 20px 16px;
  }

  .page-heading {
    grid-template-columns: 1fr;
  }

  .page-actions {
    width: 100%;
  }

  .year-control,
  .export-button {
    flex: 1;
    width: auto;
  }

  .kpi-grid,
  .analytics-grid {
    grid-template-columns: 1fr;
  }

  .analytics-card {
    height: auto;
    min-height: 270px;
  }
}

.group-donut-wrap {
  position: relative;
  isolation: isolate;
  flex: 0 0 180px;
  width: 180px;
  height: 180px;
}

.group-donut-svg {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.group-donut-segment {
  cursor: pointer;
  outline: none;
  transition:
    stroke-width 0.16s ease,
    filter 0.16s ease;
}

.group-donut-segment:hover,
.group-donut-segment:focus,
.group-donut-segment.selected {
  stroke-width: 28;
  filter: brightness(0.98);
}

.group-donut-centre {
  position: absolute;
  inset: 50% auto auto 50%;
  transform: translate(-50%, -50%);
  width: 102px;
  height: 102px;
  pointer-events: none;
  z-index: 2;
}

.donut-selection-label {
  max-width: 88px;
  margin-bottom: 2px;
  color: #506965 !important;
  font-size: 10px !important;
  font-weight: 700;
  text-align: center;
  line-height: 1.15;
  overflow-wrap: anywhere;
}

.donut-legend-row {
  cursor: pointer;
  border-radius: 7px;
  padding: 5px 6px;
  transition: background-color 0.15s ease;
}

.donut-legend-row:hover,
.donut-legend-row.selected {
  background: #f2f7f5;
}


.chart-with-y-axis {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 8px;
  align-items: stretch;
}

.y-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 2px 0 24px;
  color: #7a8984;
  font-size: 10px;
  line-height: 1;
  text-align: right;
}

.y-axis-line {
  border-left: 1px solid #d9e2df;
  padding-left: 8px;
}

.y-axis-title {
  margin-top: 6px;
  padding-bottom: 2px;
  color: #52615c;
  font-size: 10px;
  line-height: 14px;
  font-weight: 700;
  text-align: center;
}


/* BTF chart series */
.purple-bar { background: #5EA99E !important; }
.blue-bar { background: #39687B !important; }
.active-dot { background: #017151 !important; }
.inactive-dot { background: #BAD7B8 !important; }
.stacked-active { background: #017151 !important; }
.stacked-inactive { background: #BAD7B8 !important; }

/* Group Activity spacing refinement */
.analytics-card:has(> h2:first-child) {
  min-width: 0;
}

.stacked-chart {
  padding-bottom: 8px;
}

/* Dense distributions keep readable spacing instead of compressing bars */
.analytics-card .y-axis-line {
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
}

.analytics-card .vertical-chart {
  min-width: 720px;
  justify-content: flex-start;
  gap: 20px;
  padding-right: 18px;
  padding-left: 18px;
}

.analytics-card .vertical-bar-item {
  flex: 0 0 42px;
  width: 42px;
}

.analytics-card .vertical-track {
  width: 30px;
}

/* Requested large-data layout */
.groups-custom-grid {
  display: grid !important;
  grid-template-columns: minmax(0, 1.45fr) minmax(0, 1.45fr) minmax(220px, 0.7fr) !important;
  gap: 14px !important;
  align-items: stretch;
}

.group-activity-card {
  grid-column: 1 / 2;
}

.group-status-card {
  grid-column: 2 / 3;
}

.mentor-coverage-card {
  grid-column: 3 / 4;
}

.group-size-card {
  grid-column: 1 / 2;
}

.ratio-card {
  grid-column: 2 / 3;
}

.compact-insights-card {
  grid-column: 3 / 4;
}

.groups-custom-grid .analytics-card {
  height: 270px;
}

/* Use the extra width instead of forcing horizontal scrolling where possible */
.groups-custom-grid .wide-distribution-card .y-axis-line {
  overflow-x: hidden;
}

.groups-custom-grid .wide-distribution-card .vertical-chart {
  min-width: 0;
  width: 100%;
  justify-content: space-between;
  gap: 8px;
  padding: 5px 10px 0;
}

.groups-custom-grid .wide-distribution-card .vertical-bar-item {
  flex: 1 1 0;
  width: auto;
  min-width: 34px;
  max-width: 58px;
}

.groups-custom-grid .wide-distribution-card .vertical-track {
  width: 28px;
}

.compact-insights-card {
  padding: 14px !important;
}

.compact-insights-card .insights-list {
  gap: 7px;
}

.compact-insights-card .insight-row {
  grid-template-columns: 44px 1fr;
  gap: 8px;
  padding: 7px 8px;
}

.compact-insights-card .insight-row strong {
  font-size: 14px;
}

.compact-insights-card .insight-row span {
  font-size: 16px;
  line-height: 1.45;
  font-weight: 500;
}

@media (max-width: 1279px) {
  .groups-custom-grid {
    grid-template-columns: minmax(0, 1fr) !important;
  }

  .groups-custom-grid .analytics-card {
    height: auto;
    min-height: 270px;
  }

  .group-activity-card,
  .group-status-card,
  .mentor-coverage-card,
  .group-size-card,
  .ratio-card,
  .compact-insights-card {
    grid-column: auto;
  }
}

.activity-definition { margin:5px 0 10px; color:#687a76; font-size:11px; line-height:1.4; }
.activity-definition strong { color:#174243; }

/* Restore the original donut-card proportions: Group Status is wide, Mentor Coverage keeps its own card width. */
@media (min-width: 1280px) {
  .groups-custom-grid {
    grid-template-columns: repeat(84, minmax(0, 1fr)) !important;
    gap: 14px !important;
  }

  /* Row 1: Group Status and Mentor Coverage use matching widths; Key Insights stays one narrow card. */
  .group-status-card {
    grid-column: 1 / 34 !important;
    grid-row: 1;
  }

  .mentor-coverage-card {
    grid-column: 34 / 67 !important;
    grid-row: 1;
  }

  .compact-insights-card {
    grid-column: 67 / 85 !important;
    grid-row: 1;
  }

  /* Row 2: give the denser group-size distribution more room. */
  .group-size-card {
    grid-column: 1 / 50 !important;
    grid-row: 2;
  }

  .ratio-card {
    grid-column: 50 / 85 !important;
    grid-row: 2;
  }

  /* Row 3: Group Activity is full width. */
  .group-activity-card {
    grid-column: 1 / 85 !important;
    grid-row: 3;
  }

  .group-status-card .donut-layout,
  .mentor-coverage-card .donut-layout {
    display: flex !important;
    align-items: center;
    justify-content: center;
    gap: 18px;
    min-width: 0;
  }

  .group-status-card .group-donut-wrap,
  .mentor-coverage-card .group-donut-wrap {
    flex: 0 0 172px;
    width: 172px;
    height: 172px;
    aspect-ratio: 1 / 1;
  }

  .group-status-card .group-donut-svg,
  .mentor-coverage-card .group-donut-svg {
    display: block;
    width: 172px !important;
    height: 172px !important;
    aspect-ratio: 1 / 1;
    flex: none;
  }

  .group-status-card .legend-list,
  .mentor-coverage-card .legend-list {
    min-width: 150px;
  }

  .group-size-card .vertical-chart,
  .ratio-card .vertical-chart {
    min-width: 0 !important;
    width: 100%;
    justify-content: space-between;
    gap: 12px;
    padding-inline: 10px;
  }

  .group-size-card .vertical-chart {
    gap: 8px;
    padding-inline: 6px;
  }

  .ratio-card .vertical-chart {
    gap: 14px;
    padding-inline: 12px;
  }

  .group-size-card .vertical-bar-item,
  .ratio-card .vertical-bar-item {
    flex: 1 1 0;
    width: auto;
    min-width: 30px;
    max-width: 64px;
  }

  .group-size-card .vertical-track,
  .ratio-card .vertical-track {
    width: 30px;
  }

  .compact-insights-card {
    padding: 12px !important;
  }

  .compact-insights-card h2 {
    font-size: 16px;
  }

  .compact-insights-card .insights-list {
    gap: 6px;
  }

  .compact-insights-card .insight-row {
    grid-template-columns: 36px 1fr;
    gap: 5px;
    padding: 6px 4px;
  }

  .compact-insights-card .insight-row strong {
    font-size: 13px;
  }

  .compact-insights-card .insight-row span {
    font-size: 11px;
    line-height: 1.45;
    font-weight: 500;
  }
}



/* Active / inactive group directory */
.group-directory-card {
  margin-top: 14px;
  border: 1px solid #e0e9e7;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 3px 12px rgba(20, 64, 60, 0.04);
  padding: 18px;
}

.group-directory-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 10px;
}

.group-directory-header h2 {
  margin: 0 0 5px;
  color: #163f3c;
  font-size: 18px;
}

.group-directory-header p {
  margin: 0;
  color: #667a76;
  font-size: 12px;
}

.group-directory-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.group-search-control,
.group-status-control,
.group-clear-button {
  height: 40px;
  border: 1px solid #cfe0dc;
  border-radius: 10px;
  background: #fff;
  color: #174844;
}

.group-search-control {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 220px;
  padding: 0 12px;
}

.group-search-control i {
  color: #6d827e;
}

.group-search-control input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #174844;
  font: inherit;
  font-size: 12px;
}

.group-status-control {
  display: flex;
  align-items: center;
  width: 150px;
  padding: 0 9px;
}

.group-status-control select {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.group-clear-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 12px;
  color: #017151;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.group-clear-button:hover {
  background: #eef8f5;
}

.group-directory-summary {
  margin: 0 0 9px;
  color: #667a76;
  font-size: 11px;
}

.group-directory-summary strong {
  color: #174243;
}

.group-table-wrap {
  max-height: 430px;
  overflow-y: auto;
  overflow-x: hidden;
  border: 1px solid #e4ecea;
  border-radius: 11px;
}

.group-activity-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  color: #425e59;
  font-size: 12px;
}

.group-col-name { width: 27%; }
.group-col-status { width: 18%; }
.group-col-last-active { width: 32%; }
.group-col-days { width: 23%; }

.group-activity-table thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  height: 46px;
  padding: 0 14px;
  border-bottom: 1px solid #dce6e3;
  background: #f1f6f4;
  color: #174243;
  text-align: left;
}

.group-activity-table tbody td {
  height: 46px;
  padding: 0 14px;
  border-bottom: 1px solid #edf2f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}

.group-activity-table tbody tr:last-child td {
  border-bottom: 0;
}

.group-activity-table tbody tr:hover td {
  background: rgba(186, 215, 184, 0.22);
}

.table-sort-button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
}

.table-sort-button i {
  color: #5EA99E;
  font-size: 10px;
}

.group-name-cell {
  color: #174243;
  font-weight: 700;
}

.group-status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 76px;
  height: 28px;
  padding: 0 11px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.group-status-chip.active {
  background: rgba(186, 215, 184, 0.55);
  color: #017151;
}

.group-status-chip.inactive {
  background: rgba(241, 229, 166, 0.7);
  color: #6b5b12;
}

.days-since-value {
  color: #174243;
}

.days-since-unit {
  color: #71837f;
}

.group-empty-state {
  height: 76px !important;
  color: #71837f;
  text-align: center;
}

@media (max-width: 900px) {
  .group-directory-header {
    flex-direction: column;
  }

  .group-directory-controls {
    width: 100%;
    justify-content: flex-start;
  }

  .group-search-control {
    flex: 1 1 220px;
  }

  .group-status-control {
    flex: 0 0 150px;
  }
}


.group-issue-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.group-issue-detail-card {
  min-width: 0;
  padding: 16px;
  border: 1px solid #e0e9e7;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 3px 12px rgba(20, 64, 60, 0.04);
  scroll-margin-top: 120px;
}

.group-issue-detail-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.group-issue-detail-heading h2 {
  margin: 0 0 4px;
  color: #163f3c;
  font-size: 17px;
}

.group-issue-detail-heading p {
  margin: 0;
  color: #667a76;
  font-size: 11px;
}

.group-issue-detail-heading > strong {
  display: grid;
  min-width: 42px;
  height: 34px;
  place-items: center;
  border-radius: 9px;
  background: rgba(186, 215, 184, 0.55);
  color: #017151;
  font-size: 17px;
}

.group-issue-table-wrap {
  max-height: 265px;
  overflow-y: auto;
  border: 1px solid #e4ecea;
  border-radius: 10px;
}

.group-issue-table {
  width: 100%;
  border-collapse: collapse;
  color: #425e59;
  font-size: 11px;
}

.group-issue-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 10px 12px;
  background: #f1f6f4;
  color: #174243;
  text-align: left;
}

.group-issue-table td {
  padding: 10px 12px;
  border-top: 1px solid #edf2f0;
}

.issue-status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
}

.issue-status-chip.unassigned {
  background: rgba(241, 229, 166, 0.65);
  color: #6b5b12;
}

.issue-status-chip.no-mentor {
  background: rgba(186, 215, 184, 0.55);
  color: #017151;
}

@media (max-width: 900px) {
  .group-issue-detail-grid {
    grid-template-columns: 1fr;
  }
}

</style>
