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

        <div class="analytics-export-stack">
          <AnalyticsExportMenu :options="exportOptions" :disabled="loading || !!loadError" @select="exportCsv" />
          <div class="analytics-update-status">
            <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />
          </div>
        </div>
      </div>
    </div>

    <p v-if="exportError" role="alert">{{ exportError }}</p>

    <AnalyticsPartialNotice :sources="unavailableSources" @retry="initializeGroups(true)" />

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
          <div class="kpi-value-row analytics-value-row">
            <strong><AnalyticsNumber :value="data.totalGroups" /></strong>
            <AnalyticsYearChange :current="groupComparison.current" :previous="groupComparison.previous" :label="`vs ${groupComparison.previousYear}`" />
          </div>
          <small>Current groups</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon teal"><i class="fas fa-people-group"></i></div>
        <div>
          <span class="kpi-label">Average Group Size</span>
          <div class="kpi-value-row analytics-value-row">
            <strong><AnalyticsNumber :value="data.averageGroupSize" /></strong>
            <AnalyticsYearChange
              v-if="data.averageGroupSizePrevious !== null"
              :current="data.averageGroupSize"
              :previous="data.averageGroupSizePrevious"
              :label="`vs ${data.averageGroupSizePreviousYear}`"
            />
          </div>
          <small>Students per group</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon blue"><i class="fas fa-shield-halved"></i></div>
        <div>
          <span class="kpi-label">Groups with Mentor</span>
          <div class="kpi-value-row analytics-value-row">
            <strong><AnalyticsNumber :value="data.groupsWithMentor" /></strong>
            <AnalyticsYearChange
              v-if="data.groupsWithMentorPrevious !== null"
              :current="data.groupsWithMentor"
              :previous="data.groupsWithMentorPrevious"
              :label="`vs ${data.comparisonPreviousYear}`"
            />
          </div>
          <small>{{ percent(data.groupsWithMentor, data.totalGroups) }}% of groups assigned</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon red"><i class="fas fa-user-group"></i></div>
        <div>
          <span class="kpi-label">Groups without Mentor</span>
          <div class="kpi-value-row analytics-value-row">
            <strong><AnalyticsNumber :value="data.groupsWithoutMentor" /></strong>
            <AnalyticsYearChange
              v-if="data.groupsWithoutMentorPrevious !== null"
              :current="data.groupsWithoutMentor"
              :previous="data.groupsWithoutMentorPrevious"
              :label="`vs ${data.comparisonPreviousYear}`"
            />
          </div>
          <small>{{ percent(data.groupsWithoutMentor, data.totalGroups) }}% of groups unassigned</small>
        </div>
      </article>

      <article class="kpi-card">
        <div class="kpi-icon orange"><i class="fas fa-scale-balanced"></i></div>
        <div>
          <span class="kpi-label ratio-kpi-label">Mentor-to-Student Ratio</span>
          <div class="kpi-value-row analytics-value-row">
            <strong class="ratio-kpi-value"><AnalyticsNumber :value="data.mentorStudentRatio === null ? 'N/A' : `1 : ${data.mentorStudentRatio}`" /></strong>
            <AnalyticsYearChange
              v-if="data.mentorStudentRatio !== null && data.mentorStudentRatioPrevious !== null"
              :current="data.mentorStudentRatio"
              :previous="data.mentorStudentRatioPrevious"
              :label="`vs ${data.comparisonPreviousYear}`"
            />
          </div>
          <small class="ratio-kpi-helper">{{ data.mentorStudentRatio === null ? 'No ratio available' : 'Students per assigned mentor' }}</small>
        </div>
      </article>
    </section>

    <section class="analytics-grid groups-custom-grid">

<article v-if="sourceAvailable('groupActivity')" class="analytics-card group-status-card">
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
                stroke="var(--analytics-ui-border, #e7ebef)"
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
                :stroke-dasharray="`${segment.drawPercent} ${100 - segment.drawPercent}`"
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
                stroke="var(--analytics-ui-border, #e7ebef)"
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
                :stroke-dasharray="`${segment.drawPercent} ${100 - segment.drawPercent}`"
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

      <article class="analytics-card student-assignment-card">
        <h2>Student Assignment Coverage</h2>
        <div v-if="studentAssignmentCoverage" class="donut-layout">
          <div class="group-donut-wrap" @mouseleave="clearStudentCoverageSelection">
            <svg
              class="group-donut-svg"
              viewBox="0 0 180 180"
              role="img"
              aria-label="Student assignment coverage"
            >
              <circle
                cx="90"
                cy="90"
                r="64"
                pathLength="100"
                fill="none"
                stroke="var(--analytics-ui-border, #e7ebef)"
                stroke-width="24"
              />
              <circle
                v-for="segment in studentCoverageSegments"
                :key="segment.label"
                cx="90"
                cy="90"
                r="64"
                pathLength="100"
                fill="none"
                :stroke="segment.color"
                stroke-width="24"
                :stroke-dasharray="`${segment.drawPercent} ${100 - segment.drawPercent}`"
                :stroke-dashoffset="-segment.start"
                stroke-linecap="butt"
                class="group-donut-segment"
                :class="{ selected: selectedStudentCoverage?.label === segment.label }"
                transform="rotate(-90 90 90)"
                tabindex="0"
                @mouseenter="selectStudentCoverage(segment)"
                @focus="selectStudentCoverage(segment)"
                @blur="clearStudentCoverageSelection"
              />
            </svg>

            <div class="donut-centre group-donut-centre">
              <template v-if="selectedStudentCoverage">
                <span class="donut-selection-label">{{ selectedStudentCoverage.label }}</span>
                <strong>{{ selectedStudentCoverage.value }}</strong>
                <span>{{ selectedStudentCoverage.percent }}% of students</span>
              </template>
              <template v-else>
                <strong>{{ studentAssignmentCoverage.total }}</strong>
                <span>Total Students</span>
              </template>
            </div>
          </div>

          <div class="legend-list">
            <div
              v-for="segment in studentCoverageSegments"
              :key="segment.label"
              class="legend-row donut-legend-row"
              :class="{ selected: selectedStudentCoverage?.label === segment.label }"
              @mouseenter="selectStudentCoverage(segment)"
              @mouseleave="clearStudentCoverageSelection"
            >
              <span>
                <i class="dot" :style="{ background: segment.color }"></i>
                {{ segment.label }}
              </span>
              <strong>{{ segment.value }} ({{ segment.percent }}%)</strong>
            </div>
          </div>
        </div>
        <p v-else class="student-assignment-unavailable">Student assignment data is unavailable.</p>
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
          <strong>{{ sourceAvailable('users') ? studentsNotAssignedCount : '—' }}</strong>
        </div>

        <p v-if="!sourceAvailable('users')" role="status">Student allocation details are unavailable.</p>
        <div v-else class="group-issue-table-wrap">
          <table class="group-issue-table">
            <thead>
              <tr>
                <th>Student</th>
                <th>Email</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="student in studentsNotAssignedRows"
                :key="student.id"
                class="group-issue-table-row--clickable"
                role="link"
                tabindex="0"
                @click="openUnassignedStudent(student.email)"
                @keydown.enter="openUnassignedStudent(student.email)"
                @keydown.space.prevent="openUnassignedStudent(student.email)"
              >
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
              <tr
                v-for="group in groupsWithoutMentorRows"
                :key="group.id"
                class="group-issue-table-row--clickable"
                role="link"
                tabindex="0"
                @click="openUnmentoredGroup(group.name)"
                @keydown.enter="openUnmentoredGroup(group.name)"
                @keydown.space.prevent="openUnmentoredGroup(group.name)"
              >
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
import AnalyticsPartialNotice from '@/components/analytics/AnalyticsPartialNotice.vue'
import type { AnalyticsSource } from '@/utils/liveAnalyticsData'
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { useAnalyticsRefreshState } from '@/composables/useAnalyticsRefreshState'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import AnalyticsKeyInsights from '@/components/analytics/AnalyticsKeyInsights.vue'
import AnalyticsYearChange from '@/components/analytics/AnalyticsYearChange.vue'
import AnalyticsNumber from '@/components/analytics/AnalyticsNumber.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import { useRoute, useRouter } from 'vue-router'
import type { GroupsAnalyticsYear } from '@/types/analytics'
import {
  buildGroupsAnalytics,
  groupAnalyticsYears,
  groupYearComparison,
  liveAnalyticsAsOf,
  loadGroupsAnalyticsBundle,
  participantYearComparison,
  type CoreAnalyticsBundle,
} from '@/utils/liveAnalyticsData'
import type { AdminGroup, AdminUser } from '@/utils/liveAnalyticsApi'
import AnalyticsExportMenu from '@/components/analytics/AnalyticsExportMenu.vue'
import {
  DETAILS_OPTION,
  SUMMARY_OPTION,
  detailsCsv,
  exportFileName,
  figure,
  isoDay,
  isoUtc,
  runExport,
  sourceLabels,
  summaryCsv,
  type ExportKind,
  type ExportOption,
  type SummaryRow,
} from '@/utils/analyticsExport'

const route = useRoute()
const router = useRouter()

const openUnassignedStudent = (email: string) => router.push({
  path: '/admin/users',
  query: { tab: 'students', inGroup: 'no', search: email },
  hash: '#admin-users-table',
})

const openUnmentoredGroup = (name: string) => router.push({
  path: '/admin/groups',
  query: { mentorStatus: 'unmatched', search: name },
  hash: '#admin-groups-table',
})
const availableYears = ref<number[]>([new Date().getFullYear()])
const selectedYear = ref(availableYears.value[0]!)
const groupComparison = ref(groupYearComparison([], selectedYear.value))
const liveData = ref<GroupsAnalyticsYear>({
  totalGroups: 0,
  groupGrowth: null,
  averageGroupSize: 0,
  averageGroupSizePrevious: null,
  averageGroupSizePreviousYear: selectedYear.value - 1,
  avgSizeChange: null,
  groupsWithMentor: 0,
  groupsWithoutMentor: 0,
  mentorStudentRatio: 0,
  comparisonPreviousYear: selectedYear.value - 1,
  groupsWithMentorPrevious: null,
  groupsWithoutMentorPrevious: null,
  mentorStudentRatioPrevious: null,
  smallGroups: 0,
  inactiveRecent: 0,
  nearCapacity: 0,
  overCapacity: 0,
  groupSizeDistribution: [],
  groupStatus: [],
  groupActivity: [],
})
const liveUsers = ref<AdminUser[]>([])
const liveGroups = ref<AdminGroup[]>([])
const unavailableSources = ref<AnalyticsSource[]>([])
const sourceAvailable = (source: AnalyticsSource) => !unavailableSources.value.includes(source)
const loadError = ref('')
const loading = ref(true)
const exportError = ref('')
const groupBundle = ref<CoreAnalyticsBundle | null>(null)

useAnalyticsRefreshState('groups', {
  selectedYear,
}, () => !loading.value && !loadError.value)

const analyticsRefreshBusy = ref(false)
const { lastUpdated, refreshFailed, markUpdated, markRefreshFailed } = useAnalyticsRefresh(async () => { if (!analyticsRefreshBusy.value) await initializeGroups(true, true) })

function applySelectedYear(year: number) {
  if (!groupBundle.value) return
  liveData.value = buildGroupsAnalytics(groupBundle.value, year)
  const previousSummary = groupBundle.value.groupActivity.group_summary_by_year
    ?.find((row) => row.year === year - 1)
  groupComparison.value = {
    year,
    previousYear: year - 1,
    current: liveData.value.totalGroups,
    previous: previousSummary?.group_count ?? groupYearComparison(groupBundle.value.groups, year).previous,
  }
}

async function initializeGroups(force = false, preserveFilters = false) {
  if (analyticsRefreshBusy.value) return
  analyticsRefreshBusy.value = true
  if (!preserveFilters || !lastUpdated.value) loading.value = true
  loadError.value = ''
  try {
    const bundle = await loadGroupsAnalyticsBundle(force)
    unavailableSources.value = bundle.unavailableSources ?? []
    // User records are needed for current allocation only. Group years come
    // from group creation, membership summaries and recorded group activity.
    const activityBundle = { ...bundle, users: [] }
    groupBundle.value = activityBundle
    availableYears.value = groupAnalyticsYears(activityBundle)
    const currentYear = new Date().getUTCFullYear()
    if (!preserveFilters || !availableYears.value.includes(selectedYear.value)) selectedYear.value = currentYear
    liveUsers.value = bundle.users
    liveGroups.value = bundle.groups
    applySelectedYear(selectedYear.value)
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
watch(selectedYear, applySelectedYear)

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
  { key: 'small', value: data.value.smallGroups, text: 'groups have fewer than 3 students.' },
  ...(sourceAvailable('groupActivity') ? [{ key: 'inactive', value: data.value.inactiveRecent, text: 'groups have had no activity in the past 7 days.' }] : []),
  { key: 'capacity', value: data.value.nearCapacity, text: 'groups are full (5 students, the maximum).' },
  ...(data.value.overCapacity
    ? [{ key: 'over-capacity', value: data.value.overCapacity, text: 'groups have more than 5 students, above the limit.' }]
    : []),
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

const studentAssignmentCoverage = computed(() => {
  if (!sourceAvailable('users')) return null

  const participantStudents = participantYearComparison(liveUsers.value, selectedYear.value).current.students
  const historicalSummary = groupBundle.value?.groupActivity.group_summary_by_year
    ?.find((row) => row.year === selectedYear.value)
  const assignedFallback = new Set(
    liveGroups.value
      .filter((group) => new Date(group.createdAt).getUTCFullYear() <= selectedYear.value)
      .flatMap((group) => group.members)
      .filter((member) => member.role.toLowerCase() === 'student')
      .map((member) => String(member.id)),
  ).size
  const assigned = historicalSummary?.student_count ?? assignedFallback
  const total = Math.max(participantStudents, assigned)

  return {
    total,
    assigned,
    unassigned: Math.max(total - assigned, 0),
  }
})

const groupsWithoutMentorRows = computed(() =>
  liveGroups.value
    .filter((group) => !group.mentor)
    .map((group) => ({ id: group.id, name: group.name, status: 'No mentor' })),
)



const groupSizeDistributionForChart = computed(() => data.value.groupSizeDistribution)

const maxGroupSizeCount = computed(() =>
  Math.max(...groupSizeDistributionForChart.value.map((item) => item.value), 1),
)



type DonutSegment = {
  label: string
  value: number
  percent: number
  drawPercent: number
  start: number
  color: string
}

const selectedStatus = ref<DonutSegment | null>(null)
const selectedCoverage = ref<DonutSegment | null>(null)
const selectedStudentCoverage = ref<DonutSegment | null>(null)

function buildDonutSegments(
  items: Array<{ label: string; value: number; color: string }>,
  total: number,
): DonutSegment[] {
  let start = 0

  return items.map((item, index) => {
    const drawPercent = total
      ? (index === items.length - 1 ? Math.max(0, 100 - start) : (item.value / total) * 100)
      : 0
    const segment = {
      ...item,
      percent: percent(item.value, total),
      drawPercent,
      start,
    }
    start += drawPercent
    return segment
  })
}

const statusSegments = computed<DonutSegment[]>(() => {
  const statusColors: Record<string, string> = {
    Active: '#017151',
    Inactive: '#39687B',
    'Not started': '#5EA99E',
  }

  return buildDonutSegments(
    data.value.groupStatus.map((item) => ({
      label: item.label,
      value: item.value,
      color: statusColors[item.label] ?? item.color,
    })),
    data.value.totalGroups,
  )
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

  return buildDonutSegments(raw, data.value.totalGroups)
})

const studentCoverageSegments = computed<DonutSegment[]>(() => {
  const coverage = studentAssignmentCoverage.value
  if (!coverage) return []

  const raw = [
    { label: 'Assigned', value: coverage.assigned, color: '#017151' },
    { label: 'Unassigned', value: coverage.unassigned, color: '#F1E5A6' },
  ]
  return buildDonutSegments(raw, coverage.total)
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

function selectStudentCoverage(segment: DonutSegment) {
  selectedStudentCoverage.value = segment
  hideTooltip()
}

function clearStudentCoverageSelection() {
  selectedStudentCoverage.value = null
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

const exportOptions = computed<ExportOption[]>(() => [
  SUMMARY_OPTION,
  { ...DETAILS_OPTION, description: 'One row per group: members, mentors and messages' },
  {
    kind: 'unassigned',
    label: 'Students without a group',
    description: 'Every student not yet placed in a group',
    disabled: !sourceAvailable('users'),
  },
])

function groupsSummary() {
  const current = data.value
  const year = selectedYear.value
  const previous = current.comparisonPreviousYear
  const rows: SummaryRow[] = [
    figure('Groups', 'Total groups', current.totalGroups, 'groups'),
    figure('Groups', 'Average group size', current.averageGroupSize, 'students', 'Students per group'),
    figure('Groups', `Average group size (${current.averageGroupSizePreviousYear})`, current.averageGroupSizePrevious, 'students'),
    figure('Groups', 'Groups with mentor', current.groupsWithMentor, 'groups'),
    figure('Groups', `Groups with mentor (${previous})`, current.groupsWithMentorPrevious, 'groups'),
    figure('Groups', 'Groups without mentor', current.groupsWithoutMentor, 'groups'),
    figure('Groups', `Groups without mentor (${previous})`, current.groupsWithoutMentorPrevious, 'groups'),
    figure('Groups', 'Students per mentor', current.mentorStudentRatio, 'students', 'Mentor-to-student ratio 1 : value'),
    figure('Groups', `Students per mentor (${previous})`, current.mentorStudentRatioPrevious, 'students'),
    ...(studentAssignmentCoverage.value
      ? [
          figure('Student assignment', 'Assigned to a group', studentAssignmentCoverage.value.assigned, 'students'),
          figure('Student assignment', 'Not assigned to a group', studentAssignmentCoverage.value.unassigned, 'students'),
        ]
      : []),
    ...groupInsightItems.value.map((item) => figure('Key insights', item.text, item.value, 'groups')),
    ...current.groupStatus.map((item) => figure('Group status', item.label, item.value, 'groups')),
    ...current.groupSizeDistribution.map((item) => figure('Group size (students)', item.label, item.value, 'groups')),
    ...current.groupActivity.flatMap((month) => [
      figure('Group activity by month', `${month.month}: active`, month.active, 'groups'),
      figure('Group activity by month', `${month.month}: inactive`, month.inactive, 'groups'),
    ]),
  ]
  return {
    fileName: exportFileName('groups', 'summary', String(year)),
    csv: summaryCsv({
      page: 'Groups',
      covers: `Current groups; comparisons and monthly activity for ${year}`,
      dataAsOf: groupBundle.value ? liveAnalyticsAsOf(groupBundle.value) : null,
      unavailable: sourceLabels(unavailableSources.value),
    }, rows),
  }
}

function groupsDetails() {
  const activity = groupBundle.value?.groupActivity
  const asOf = groupBundle.value ? liveAnalyticsAsOf(groupBundle.value) : isoDay(new Date())
  const recentStart = new Date(`${asOf}T00:00:00Z`)
  recentStart.setUTCDate(recentStart.getUTCDate() - 6)
  const recentFrom = isoDay(recentStart)
  const totals = new Map((activity?.messages_by_group ?? []).map((row) => [String(row.group_id), row.message_count]))
  const recent = new Map<string, number>()
  const lastDay = new Map<string, string>()
  for (const row of activity?.messages_by_group_by_day ?? []) {
    const id = String(row.group_id)
    if (row.message_count > 0 && row.date > (lastDay.get(id) ?? '')) lastDay.set(id, row.date)
    if (row.date >= recentFrom && row.date <= asOf) recent.set(id, (recent.get(id) ?? 0) + row.message_count)
  }
  const rows = [...liveGroups.value]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((group) => {
      const id = String(group.id)
      const byRole = (role: string) => group.members.filter((member) => member.role.toLowerCase() === role)
      const mentors = group.mentors ?? (group.mentor ? [group.mentor] : [])
      const messages = totals.get(id) ?? 0
      const lastWeek = recent.get(id) ?? 0
      const status = lastWeek > 0 ? 'Active' : messages === 0 && group.members.length === 0 ? 'Not started' : 'Inactive'
      return [
        group.id,
        group.name,
        isoUtc(group.createdAt),
        byRole('student').length,
        mentors.length,
        byRole('supervisor').length,
        mentors.map((mentor) => mentor.name).join('; '),
        messages,
        lastWeek,
        lastDay.get(id) ?? '',
        status,
      ]
    })
  return {
    // Membership is current, so the file is named for the day it was exported.
    fileName: exportFileName('groups', 'details', isoDay(new Date())),
    csv: detailsCsv([
      'Group ID', 'Group', 'Created (UTC)', 'Students', 'Mentors', 'Supervisors', 'Mentor Names',
      'Messages (All Time)', `Messages (7 Days to ${asOf})`, 'Last Message Day (UTC)', 'Status',
    ], rows),
  }
}

function unassignedStudents() {
  const rows = liveUsers.value
    .filter((user) => (user.role ?? '').toLowerCase() === 'student' && !user.groupId)
    .sort((a, b) => `${a.lastName} ${a.firstName}`.localeCompare(`${b.lastName} ${b.firstName}`))
    .map((user) => [
      user.id,
      `${user.firstName} ${user.lastName}`.trim(),
      user.email,
      user.schoolName,
      user.supervisorName,
      isoUtc(user.createdAt ?? user.invitedAt ?? user.activatedAt),
    ])
  return {
    fileName: exportFileName('groups', 'students-without-group', isoDay(new Date())),
    csv: detailsCsv(['Student ID', 'Student', 'Email', 'School', 'Supervisor', 'Registered (UTC)'], rows),
  }
}

function exportCsv(kind: ExportKind) {
  const build = kind === 'summary' ? groupsSummary : kind === 'unassigned' ? unassignedStudents : groupsDetails
  exportError.value = runExport(build)
}
</script>

<style src="@/assets/analytics-theme.css"></style>

<style scoped>
.groups-analytics-page {
  padding: 28px 32px 40px;
  min-height: 100%;
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

.page-heading p {
  margin: 8px 0 0;
  color: var(--analytics-ui-muted, #617572);
  font-size: 16px;
}

.demo-badge {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
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
  align-self: start;
}

.year-control,
.export-button {
  height: 46px;
  border-radius: 12px;
  background: var(--analytics-ui-surface, #fff);
  font-size: 14px;
  font-weight: 700;
}

.year-control {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  width: 120px;
  padding: 0 13px;
  border: 1px solid var(--analytics-ui-border, #d7e3e0);
  color: var(--analytics-ui-text, #174844);
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
}

.export-button:hover {
  background: var(--analytics-ui-selected, #ecf8f4);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.kpi-card,
.analytics-card {
  border: 1px solid var(--analytics-ui-border, #e0e9e7);
  border-radius: 14px;
  background: var(--analytics-ui-surface, #fff);
  box-shadow: 0 3px 12px rgba(20, 64, 60, 0.04);
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 0;
  padding: 10px 18px;
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

.kpi-icon.purple { color: var(--analytics-ui-muted, #5EA99E); background: color-mix(in srgb, #5EA99E 14%, var(--analytics-ui-surface, white)); }
.kpi-icon.teal { color: var(--analytics-ui-accent, #017151); background: color-mix(in srgb, var(--analytics-ui-soft, #BAD7B8) 55%, var(--analytics-ui-surface, white)); }
.kpi-icon.blue { color: var(--analytics-ui-secondary, #39687B); background: color-mix(in srgb, #39687B 14%, var(--analytics-ui-surface, white)); }
.kpi-icon.red { color: var(--analytics-ui-text, #174243); background: color-mix(in srgb, var(--analytics-ui-soft, #BAD7B8) 45%, var(--analytics-ui-surface, white)); }
.kpi-icon.orange { color: var(--analytics-ui-accent, #017151); background: color-mix(in srgb, var(--analytics-ui-warning-bg, #F1E5A6) 50%, var(--analytics-ui-surface, white)); }

.kpi-label {
  display: block;
  margin-bottom: 5px;
  color: var(--analytics-ui-muted, #4e6662);
  font-size: 12px;
}

.ratio-kpi-label {
  align-items: center;
  height: 15px;
  font-size: 10.5px;
  line-height: 15px;
  white-space: nowrap;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.kpi-value-row strong,
.kpi-value {
  display: block;
  color: var(--analytics-ui-text, #163f3c);
  font-size: 27px;
  line-height: 1.05;
}

.kpi-value-row .ratio-kpi-value {
  font-size: 24px;
  line-height: 28.35px;
  white-space: nowrap;
}

.trend-up { color: var(--analytics-ui-accent, #017151); font-weight: 700; }

.trend-down { color: var(--analytics-ui-secondary, #39687B); font-weight: 700; }

.kpi-card small {
  display: block;
  margin-top: 4px;
  color: var(--analytics-ui-muted, #7c8d89);
  font-size: 10px;
}

.kpi-card .ratio-kpi-helper {
  font-size: 10px;
  white-space: nowrap;
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
  color: var(--analytics-ui-text, #163f3c);
  font-size: 16px;
  line-height: 1.2;
}

.analytics-card h2 small {
  font-size: 10px;
  font-weight: 500;
  color: var(--analytics-ui-muted, #60726f);
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
  color: var(--analytics-ui-text, #355953);
  font-size: 10px;
  font-weight: 700;
}

.vertical-track {
  display: flex;
  align-items: flex-end;
  width: 35px;
  height: 138px;
  border-bottom: 1px solid var(--analytics-ui-border, #dce5e2);
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
  color: var(--analytics-ui-muted, #647875);
  font-size: 9px;
  text-align: center;
}

.axis-caption {
  margin-top: -2px;
  color: var(--analytics-ui-muted, #5f7470);
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
  background: var(--analytics-ui-surface, #fff);
  text-align: center;
}

.donut-centre strong {
  color: var(--analytics-ui-text, #163f3c);
  font-size: 25px;
}

.donut-centre span {
  margin-top: 2px;
  color: var(--analytics-ui-muted, #687b77);
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
  color: var(--analytics-ui-muted, #3f5b57);
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
.grey-dot { background: var(--analytics-ui-soft, #BAD7B8); }
.active-dot { background: #017151; }
.inactive-dot { background: var(--analytics-ui-selected, #BAD7B8); }

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
  color: var(--analytics-ui-text, #3d5b57);
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
  background: var(--analytics-ui-soft, #edf1f0);
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
  stroke: var(--analytics-ui-border, #edf1f0);
  stroke-width: 1;
}

.message-area {
  fill: rgba(129, 88, 238, 0.12);
}

.message-line {
  fill: none;
  stroke: var(--analytics-ui-control-border, #7f5af0);
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
  color: var(--analytics-ui-muted, #6f807d);
  font-size: 8px;
  text-align: center;
}

.stacked-legend {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 6px;
  color: var(--analytics-ui-muted, #617571);
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
  color: var(--analytics-ui-accent, #017151);
}

.stacked-value-labels .inactive-value {
  color: var(--analytics-ui-muted, #7aa777);
}

.stacked-track {
  display: flex;
  align-items: flex-end;
  width: 16px;
  height: 144px;
  border-bottom: 1px solid var(--analytics-ui-border, #dce5e2);
}

.stacked-inactive {
  position: relative;
  width: 100%;
  border-radius: 3px 3px 0 0;
  background: var(--analytics-ui-selected, #BAD7B8);
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
  color: var(--analytics-ui-muted, #697c78);
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
  background: var(--analytics-ui-soft, #f2f5f8);
  color: var(--analytics-ui-muted, #445f5b);
  font-size: 10px;
  font-weight: 800;
}

.rank-name {
  color: var(--analytics-ui-muted, #415d59);
  font-size: 10px;
}

.rank-track span {
  background: #017151;
}

.ranking-list strong {
  color: var(--analytics-ui-text, #2e534d);
  font-size: 10px;
  text-align: right;
}

.insights-card h2 i {
  margin-right: 7px;
  color: var(--analytics-ui-secondary, #5279a5);
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

.insight-red strong { background: var(--analytics-ui-soft, #BAD7B8); color: var(--analytics-ui-text, #174243); }
.insight-orange strong { background: var(--analytics-ui-warning-bg, #F1E5A6); color: var(--analytics-ui-text, #174243); }
.insight-purple strong { background: #5EA99E; color: #FFFFFF; }
.insight-blue strong { background: #39687B; color: #FFFFFF; }

.insight-row span {
  color: var(--analytics-ui-muted, #425e59);
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
  color: var(--analytics-ui-muted, #506965) !important;
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
  background: var(--analytics-ui-selected, #f2f7f5);
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
  margin-top: 6px;
  padding-bottom: 2px;
  color: var(--analytics-ui-muted, #52615c);
  font-size: 10px;
  line-height: 14px;
  font-weight: 700;
  text-align: center;
}


/* BTF chart series */
.purple-bar { background: #5EA99E !important; }
.blue-bar { background: #39687B !important; }
.active-dot { background: #017151 !important; }
.inactive-dot { background: var(--analytics-ui-selected, #BAD7B8) !important; }
.stacked-active { background: #017151 !important; }
.stacked-inactive { background: var(--analytics-ui-selected, #BAD7B8) !important; }

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
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
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
  grid-column: 2 / 3;
}

.student-assignment-card {
  grid-column: 3 / 4;
}

.student-assignment-unavailable {
  display: grid;
  height: calc(100% - 30px);
  margin: 0;
  place-items: center;
  color: var(--analytics-ui-muted, #687a76);
  font-size: 12px;
  text-align: center;
}

.group-size-card {
  grid-column: 1 / 2;
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
  .student-assignment-card,
  .group-size-card,
  .compact-insights-card {
    grid-column: auto;
  }
}

.activity-definition { margin:5px 0 10px; color:var(--analytics-ui-muted, #687a76); font-size:11px; line-height:1.4; }
.activity-definition strong { color:var(--analytics-ui-text, #174243); }

/* Restore the original donut-card proportions: Group Status is wide, Mentor Coverage keeps its own card width. */
@media (min-width: 1280px) {
  .groups-custom-grid {
    grid-template-columns: repeat(84, minmax(0, 1fr)) !important;
    gap: 14px !important;
  }

  /* Row 1: group status, mentor coverage and student assignment align. */
  .group-status-card {
    grid-column: 1 / 29 !important;
    grid-row: 1;
  }

  .mentor-coverage-card {
    grid-column: 29 / 57 !important;
    grid-row: 1;
  }

  .student-assignment-card {
    grid-column: 57 / 85 !important;
    grid-row: 1;
  }

  /* Row 2: Key Insights matches the Group Size Distribution height. */
  .group-size-card {
    grid-column: 1 / 57 !important;
    grid-row: 2;
  }

  .compact-insights-card {
    grid-column: 57 / 85 !important;
    grid-row: 2;
    height: 270px !important;
  }

  /* Row 3: Group Activity is full width. */
  .group-activity-card {
    grid-column: 1 / 85 !important;
    grid-row: 3;
  }

  .group-status-card .donut-layout,
  .mentor-coverage-card .donut-layout,
  .student-assignment-card .donut-layout {
    display: flex !important;
    align-items: center;
    justify-content: center;
    gap: 18px;
    min-width: 0;
  }

  .group-status-card .group-donut-wrap,
  .mentor-coverage-card .group-donut-wrap,
  .student-assignment-card .group-donut-wrap {
    flex: 0 0 172px;
    width: 172px;
    height: 172px;
    aspect-ratio: 1 / 1;
  }

  .group-status-card .group-donut-svg,
  .mentor-coverage-card .group-donut-svg,
  .student-assignment-card .group-donut-svg {
    display: block;
    width: 172px !important;
    height: 172px !important;
    aspect-ratio: 1 / 1;
    flex: none;
  }

  .group-status-card .legend-list,
  .mentor-coverage-card .legend-list,
  .student-assignment-card .legend-list {
    min-width: 128px;
  }

  .group-size-card .vertical-chart {
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

  .group-size-card .vertical-bar-item {
    flex: 1 1 0;
    width: auto;
    min-width: 30px;
    max-width: 64px;
  }

  .group-size-card .vertical-track {
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

/* Compact KPI cards avoid the reserved two-line slots that previously
   created excess vertical space. */
.groups-analytics-page .kpi-grid .kpi-card {
  align-items: center !important;
}

.groups-analytics-page .kpi-grid .kpi-card > .kpi-icon {
  align-self: center !important;
}

.groups-analytics-page .kpi-card > div:not(.kpi-icon) {
  align-self: center !important;
}

.groups-analytics-page .kpi-card > div:not(.kpi-icon) > .kpi-label,
.groups-analytics-page .kpi-card > div:not(.kpi-icon) > small,
.groups-analytics-page .kpi-card .analytics-value-row {
  min-height: 0 !important;
}



/* Active / inactive group directory */
.group-directory-card {
  margin-top: 14px;
  border: 1px solid var(--analytics-ui-border, #e0e9e7);
  border-radius: 14px;
  background: var(--analytics-ui-surface, #fff);
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
  color: var(--analytics-ui-text, #163f3c);
  font-size: 18px;
}

.group-directory-header p {
  margin: 0;
  color: var(--analytics-ui-muted, #667a76);
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
  border: 1px solid var(--analytics-ui-border, #cfe0dc);
  border-radius: 10px;
  background: var(--analytics-ui-surface, #fff);
  color: var(--analytics-ui-text, #174844);
}

.group-search-control {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 220px;
  padding: 0 12px;
}

.group-search-control i {
  color: var(--analytics-ui-muted, #6d827e);
}

.group-search-control input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--analytics-ui-text, #174844);
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
  color: var(--analytics-ui-accent, #017151);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.group-clear-button:hover {
  background: var(--analytics-ui-selected, #eef8f5);
}

.group-directory-summary {
  margin: 0 0 9px;
  color: var(--analytics-ui-muted, #667a76);
  font-size: 11px;
}

.group-directory-summary strong {
  color: var(--analytics-ui-text, #174243);
}

.group-table-wrap {
  max-height: 430px;
  overflow-y: auto;
  overflow-x: hidden;
  border: 1px solid var(--analytics-ui-border, #e4ecea);
  border-radius: 11px;
}

.group-activity-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  color: var(--analytics-ui-muted, #425e59);
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
  border-bottom: 1px solid var(--analytics-ui-border, #dce6e3);
  background: var(--analytics-ui-soft, #f1f6f4);
  color: var(--analytics-ui-text, #174243);
  text-align: left;
}

.group-activity-table tbody td {
  height: 46px;
  padding: 0 14px;
  border-bottom: 1px solid var(--analytics-ui-border, #edf2f0);
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
  color: var(--analytics-ui-muted, #5EA99E);
  font-size: 10px;
}

.group-name-cell {
  color: var(--analytics-ui-text, #174243);
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
  color: var(--analytics-ui-accent, #017151);
}

.group-status-chip.inactive {
  background: rgba(241, 229, 166, 0.7);
  color: var(--analytics-ui-text, #6b5b12);
}

.days-since-value {
  color: var(--analytics-ui-text, #174243);
}

.days-since-unit {
  color: var(--analytics-ui-muted, #71837f);
}

.group-empty-state {
  height: 76px !important;
  color: var(--analytics-ui-muted, #71837f);
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
  border: 1px solid var(--analytics-ui-border, #e0e9e7);
  border-radius: 14px;
  background: var(--analytics-ui-surface, #ffffff);
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
  color: var(--analytics-ui-text, #163f3c);
  font-size: 17px;
}

.group-issue-detail-heading p {
  margin: 0;
  color: var(--analytics-ui-muted, #667a76);
  font-size: 11px;
}

.group-issue-detail-heading > strong {
  display: grid;
  min-width: 42px;
  height: 34px;
  place-items: center;
  border-radius: 9px;
  background: rgba(186, 215, 184, 0.55);
  color: var(--analytics-ui-accent, #017151);
  font-size: 17px;
}

.group-issue-table-wrap {
  max-height: 265px;
  overflow-y: auto;
  border: 1px solid var(--analytics-ui-border, #e4ecea);
  border-radius: 10px;
}

.group-issue-table {
  width: 100%;
  border-collapse: collapse;
  color: var(--analytics-ui-muted, #425e59);
  font-size: 11px;
}

.group-issue-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 10px 12px;
  background: var(--analytics-ui-soft, #f1f6f4);
  color: var(--analytics-ui-text, #174243);
  text-align: left;
}

.group-issue-table td {
  padding: 10px 12px;
  border-top: 1px solid var(--analytics-ui-border, #edf2f0);
}

.group-issue-table-row--clickable {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.group-issue-table-row--clickable:hover,
.group-issue-table-row--clickable:focus-visible {
  background: var(--analytics-ui-selected, #f1f8f5);
}

.group-issue-table-row--clickable:focus-visible {
  outline: 2px solid #00866a;
  outline-offset: -2px;
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
  color: var(--analytics-ui-text, #6b5b12);
}

.issue-status-chip.no-mentor {
  background: rgba(186, 215, 184, 0.55);
  color: var(--analytics-ui-accent, #017151);
}

@media (max-width: 900px) {
  .group-issue-detail-grid {
    grid-template-columns: 1fr;
  }
}

</style>
