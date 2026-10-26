<template>
  <section class="mentors-analytics-page">
    <header class="page-heading">
      <div class="heading-copy">
        <nav class="breadcrumb" aria-label="Breadcrumb">
          <RouterLink to="/dashboard">Home</RouterLink><span aria-hidden="true">›</span
          ><RouterLink to="/analytics">Analytics</RouterLink><span aria-hidden="true">›</span
          ><span aria-current="page">Mentors</span>
        </nav>
        <div class="title-line">
          <h1>Mentors Analytics</h1>
          
        </div>
        <p>Understand mentor allocation, utilisation and engagement.</p>
      </div>
      <div class="page-actions">
        <label class="range-control"
          ><i class="fas fa-calendar" aria-hidden="true"></i><span class="sr-only">Select analytics year</span
          ><select v-model.number="selectedYear" aria-label="Select analytics year">
            <option v-for="year in availableYears" :key="year" :value="year">{{ year }}</option>
          </select></label
        >
        <div class="analytics-export-stack">
          <AnalyticsExportMenu :options="exportOptions" :disabled="loading || !!loadError || !!rangeError" @select="exportCsv" />
          <div class="analytics-update-status">
            <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />
          </div>
        </div>
      </div>
    </header>
    <AnalyticsPartialNotice :sources="unavailableSources" @retry="initializeMentors(true)" />

    <div v-if="loadError" class="range-error" role="alert">
      <span>Mentor analytics could not be loaded. {{ loadError }}</span>
      <button type="button" @click="initializeMentors(true)">Retry</button>
    </div>
    <p v-else-if="loading" role="status">Loading mentor analytics…</p>
    <template v-else>
    <p v-if="rangeError" class="range-error" role="alert">{{ rangeError }}</p>
    <p v-if="exportError" class="export-status" role="alert">{{ exportError }}</p>

    <section class="kpi-grid" aria-label="Mentor snapshot summary">
      <article v-for="item in kpis" :key="item.label" class="kpi-card">
        <span class="kpi-icon"><BtfIcon :name="item.icon" :size="24" /></span>
        <div class="kpi-copy">
          <span
            class="kpi-label"
            :class="{ 'kpi-label--compact': item.label === 'Avg. Students per Mentor' }"
          >{{ item.label }}</span>
          <div class="analytics-value-row">
            <strong class="kpi-value"><AnalyticsNumber :value="item.value" /></strong>
            <AnalyticsYearChange
              v-if="item.comparison"
              :current="item.comparison.current"
              :previous="item.comparison.previous"
              :label="`vs ${item.comparison.previousYear}`"
            />
          </div>
          <div v-if="item.label === 'Mentor Utilisation' && sourceAvailable('groups')" class="progress-track" aria-hidden="true">
            <span :style="{ width: snapshot.utilisation + '%' }"></span>
          </div>
          <small>{{ item.detail }}</small>
        </div>
      </article>
    </section>

    <section class="chart-grid" aria-label="Mentor snapshot distributions">
      <article v-for="chart in charts" :key="chart.title" class="analytics-card">
        <h2>{{ chart.title }}</h2>
        <template v-if="chart.kind === 'donut'">
          <div
            class="interactive-mentor-donut-layout"
            @mouseleave="clearMentorDonutSelection(chart.title)"
          >
            <div class="interactive-mentor-donut-wrap">
              <svg
                class="interactive-mentor-donut-svg"
                viewBox="0 0 180 180"
                role="img"
                :aria-label="chart.title"
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
                  v-for="segment in mentorDonutArcs(chart)"
                  :key="segment.label"
                  cx="90"
                  cy="90"
                  r="64"
                  pathLength="100"
                  fill="none"
                  :stroke="segment.color"
                  stroke-width="24"
                  :stroke-dasharray="segment.dasharray"
                  :stroke-dashoffset="-segment.start"
                  stroke-linecap="butt"
                  class="interactive-mentor-donut-segment"
                  :class="{
                    selected:
                      selectedMentorDonut?.chartTitle === chart.title &&
                      selectedMentorDonut?.label === segment.label,
                  }"
                  transform="rotate(-90 90 90)"
                  tabindex="0"
                  @mouseenter="selectMentorDonut(chart.title, segment)"
                  @focus="selectMentorDonut(chart.title, segment)"
                  @blur="clearMentorDonutSelection(chart.title)"
                  @keydown.escape="clearMentorDonutSelection(chart.title)"
                />
              </svg>

              <div class="interactive-mentor-donut-centre">
                <template v-if="selectedMentorDonut?.chartTitle === chart.title">
                  <span class="interactive-donut-selection-label">
                    {{ selectedMentorDonut.label }}
                  </span>
                  <strong>{{ selectedMentorDonut.value }}</strong>
                  <span>{{ selectedMentorDonut.percent }}% of mentors</span>
                </template>
                <template v-else>
                  <strong>{{ mentorDonutTotal(chart) }}</strong>
                  <span>{{ chart.centreLabel ?? 'Total mentors' }}</span>
                </template>
              </div>
            </div>

            <div class="interactive-mentor-donut-legend">
              <div
                v-for="segment in mentorDonutSegments(chart)"
                :key="`legend-${segment.label}`"
                class="interactive-mentor-donut-legend-row"
                :class="{
                  selected:
                    selectedMentorDonut?.chartTitle === chart.title &&
                    selectedMentorDonut?.label === segment.label,
                }"
                tabindex="0"
                @mouseenter="selectMentorDonut(chart.title, segment)"
                @focus="selectMentorDonut(chart.title, segment)"
                @mouseleave="clearMentorDonutSelection(chart.title)"
                @blur="clearMentorDonutSelection(chart.title)"
                @keydown.escape="clearMentorDonutSelection(chart.title)"
              >
                <span>
                  <i class="interactive-donut-dot" :style="{ background: segment.color }"></i>
                  {{ segment.label }}
                </span>
                <strong>{{ segment.value }} <small>({{ segment.percent }}%)</small></strong>
              </div>
              <div
                v-if="chart.title === 'Mentor Capacity Split'"
                class="capacity-pool"
                aria-label="Activated mentor pool capacity"
              >
                <span>Pool capacity</span>
                <strong>{{ snapshot.capacityPool.usedSlots }} / {{ snapshot.capacityPool.totalSlots }} groups</strong>
                <div class="capacity-pool-track" role="presentation">
                  <span :style="{ width: `${Math.min(snapshot.capacityPool.utilisation, 100)}%` }"></span>
                </div>
                <small>{{ snapshot.capacityPool.utilisation }}% used · {{ snapshot.capacityPool.openSlots }} open slots</small>
                <button type="button" class="capacity-table-shortcut" @click="openCapacityTable">
                  View mentors with capacity <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>
          </div>
        </template>

        <MentorDistributionChart
          v-else
          :items="chart.items"
          :kind="chart.kind"
          :axis="chart.axis"
        />
      </article>
    </section>

    <MentorCapacityTable
      v-if="sourceAvailable('groups')"
      id="mentors-with-capacity"
      ref="capacityTable"
      :mentors="liveMentors"
      @select="openAdminMentor"
    />

    <section v-if="sourceAvailable('groupActivity')" class="activity-grid" aria-label="Mentor activity in the selected range">
      <article class="analytics-card activity-card">
        <h2>Mentor Activity by Month</h2>
        <p class="card-note">Unique mentors with a login or message · {{ rangeLabel }}</p>
        <p v-if="rangeError" class="empty-state">Choose a valid date range to view activity.</p>
        <p v-else-if="!activity.eventCount" class="empty-state">
          No mentor activity was recorded in this date range.
        </p>
        <template v-else>
          <div class="series-key"><i></i>Active mentors (login or messages)</div>
          <svg
            class="activity-chart"
            viewBox="0 0 600 230"
            role="group"
            aria-label="Monthly active mentors. Focus a data point for its count."
          >
            <g v-for="tick in [0, 1, 2, 3, 4]" :key="tick">
              <line
                x1="36"
                x2="578"
                :y1="190 - tick * 40"
                :y2="190 - tick * 40"
                class="grid-line"
              />
              <text x="28" :y="194 - tick * 40" text-anchor="end">
                {{ Math.round((activityMax * tick) / 4) }}
              </text>
            </g>
            <polyline
              :points="points.map((p) => `${p.x},${p.y}`).join(' ')"
              fill="none"
              :stroke="BTF_COLORS.darkGreen"
              stroke-width="3"
            />
            <g v-for="point in points" :key="point.month">
              <text
                class="activity-value-label"
                :x="point.x"
                :y="point.y - 12"
                text-anchor="middle"
                aria-hidden="true"
              >
                {{ point.active }}
              </text>
              <circle
                :cx="point.x"
                :cy="point.y"
                r="5"
                :fill="BTF_COLORS.darkGreen"
                tabindex="0"
                role="img"
                :aria-label="`${point.month}: ${point.active} active mentors`"
                @mouseenter="showActivity($event, point)"
                @mousemove="showActivity($event, point)"
                @mouseleave="hideTooltip"
                @focus="showActivity($event, point)"
                @blur="hideTooltip"
                @keydown.esc="hideTooltip"
                @click="showActivity($event, point)"
              />
              <text
                v-if="points.length <= 12 || point.index % 2 === 0"
                :x="point.x"
                y="214"
                text-anchor="middle"
              >
                {{ monthLabel(point.month) }}
              </text>
            </g>
          </svg>
        </template>
      </article>
      <article class="analytics-card mentor-activity-card">
        <div class="mentor-activity-heading">
          <h2>Mentor Activity</h2>
          <button
            type="button"
            class="mentor-activity-sort"
            :title="mentorActivitySort === 'desc' ? 'Highest to lowest' : 'Lowest to highest'"
            :aria-label="mentorActivitySort === 'desc' ? 'Sort lowest to highest' : 'Sort highest to lowest'"
            @click="mentorActivitySort = mentorActivitySort === 'desc' ? 'asc' : 'desc'"
          >
            <i
              class="fas"
              :class="mentorActivitySort === 'desc' ? 'fa-caret-down' : 'fa-caret-up'"
              aria-hidden="true"
            ></i>
          </button>
        </div>
        <p class="card-note">Activated mentors by messages sent · {{ rangeLabel }}</p>
        <p v-if="rangeError" class="empty-state">Choose a valid date range to view mentor activity.</p>
        <p v-else-if="!sortedMentorActivity.length" class="empty-state">
          No activated mentor accounts.
        </p>
        <ol v-else class="ranking mentor-activity-list">
          <li v-for="(mentor, index) in sortedMentorActivity" :key="mentor.id">
            <span class="rank-number">{{ index + 1 }}</span>
            <div class="rank-copy">
              <span>{{ mentor.name }}</span>
              <div class="rank-track">
                <span :style="{ width: `${(mentor.messages / mentorActivityMax) * 100}%` }"></span>
              </div>
            </div>
            <strong>{{ mentor.messages }}<small>{{ mentor.messages === 1 ? 'message' : 'messages' }}</small></strong>
          </li>
        </ol>
      </article>
    </section>
    <section class="bottom-grid">
      <article v-if="sourceAvailable('groups')" class="analytics-card">
        <h2>Mentor Coverage</h2>
        <p class="card-note">Current group support across all {{ snapshot.total }} mentors.</p>
        <div
          class="interactive-mentor-donut-layout"
          @mouseleave="clearMentorDonutSelection(coverageChart.title)"
        >
          <div class="interactive-mentor-donut-wrap">
            <svg
              class="interactive-mentor-donut-svg"
              viewBox="0 0 180 180"
              role="img"
              aria-label="Mentor Coverage"
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
                v-for="segment in mentorDonutArcs(coverageChart)"
                :key="segment.label"
                cx="90"
                cy="90"
                r="64"
                pathLength="100"
                fill="none"
                :stroke="segment.color"
                stroke-width="24"
                :stroke-dasharray="segment.dasharray"
                :stroke-dashoffset="-segment.start"
                stroke-linecap="butt"
                class="interactive-mentor-donut-segment"
                :class="{
                  selected:
                    selectedMentorDonut?.chartTitle === coverageChart.title &&
                    selectedMentorDonut?.label === segment.label,
                }"
                transform="rotate(-90 90 90)"
                tabindex="0"
                @mouseenter="selectMentorDonut(coverageChart.title, segment)"
                @focus="selectMentorDonut(coverageChart.title, segment)"
                @blur="clearMentorDonutSelection(coverageChart.title)"
                @keydown.escape="clearMentorDonutSelection(coverageChart.title)"
              />
            </svg>

            <div class="interactive-mentor-donut-centre">
              <template v-if="selectedMentorDonut?.chartTitle === coverageChart.title">
                <span class="interactive-donut-selection-label">{{ selectedMentorDonut.label }}</span>
                <strong>{{ selectedMentorDonut.value }}</strong>
                <span>{{ selectedMentorDonut.percent }}% of mentors</span>
              </template>
              <template v-else>
                <strong>{{ mentorDonutTotal(coverageChart) }}</strong>
                <span>Total mentors</span>
              </template>
            </div>
          </div>

          <div class="interactive-mentor-donut-legend">
            <div
              v-for="segment in mentorDonutSegments(coverageChart)"
              :key="`coverage-legend-${segment.label}`"
              class="interactive-mentor-donut-legend-row"
              :class="{
                selected:
                  selectedMentorDonut?.chartTitle === coverageChart.title &&
                  selectedMentorDonut?.label === segment.label,
              }"
              tabindex="0"
              @mouseenter="selectMentorDonut(coverageChart.title, segment)"
              @focus="selectMentorDonut(coverageChart.title, segment)"
              @mouseleave="clearMentorDonutSelection(coverageChart.title)"
              @blur="clearMentorDonutSelection(coverageChart.title)"
              @keydown.escape="clearMentorDonutSelection(coverageChart.title)"
            >
              <span>
                <i class="interactive-donut-dot" :style="{ background: segment.color }"></i>
                {{ segment.label }}
              </span>
              <strong>{{ segment.value }} <small>({{ segment.percent }}%)</small></strong>
            </div>
          </div>
        </div>
      </article>
      <article class="analytics-card mentor-insights-card">
        <AnalyticsKeyInsights
          :items="mentorInsightItems"
          :columns="2"
          description="Summarises mentor availability, engagement, and allocation signals that may need attention."
        />
      </article>
    </section>
    </template>
    <ChartTooltip v-bind="tooltip" />
  </section>
</template>

<script setup lang="ts">
import AnalyticsPartialNotice from '@/components/analytics/AnalyticsPartialNotice.vue'
import type { AnalyticsSource } from '@/utils/liveAnalyticsData'
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { useAnalyticsRefreshState } from '@/composables/useAnalyticsRefreshState'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import BtfIcon from '@/components/BtfIcon.vue'
import AnalyticsKeyInsights from '@/components/analytics/AnalyticsKeyInsights.vue'
import AnalyticsYearChange from '@/components/analytics/AnalyticsYearChange.vue'
import AnalyticsNumber from '@/components/analytics/AnalyticsNumber.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import MentorDistributionChart from '@/components/analytics/MentorDistributionChart.vue'
import MentorCapacityTable from '@/components/analytics/MentorCapacityTable.vue'
import { useRouter } from 'vue-router'
import { BTF_COLORS } from '@/constants/btfTheme'
import type { DemoMentor, MentorEvent } from '@/types/analytics'
import { buildMentorData, loadMentorsAnalyticsBundle } from '@/utils/liveAnalyticsData'
import {
  mentorSnapshot,
  mentorActivity,
  mentorsSummaryRows,
  percent,
  validRange,
  type MetricBucket,
} from '@/utils/mentorsAnalytics'
import AnalyticsExportMenu from '@/components/analytics/AnalyticsExportMenu.vue'
import {
  ACTIVE_WINDOW_DAYS,
  DETAILS_OPTION,
  SUMMARY_OPTION,
  accountStatusLabel,
  activityStatusLabel,
  detailsCsv,
  exportFileName,
  isoUtc,
  runExport,
  sourceLabels,
  summaryCsv,
  type ExportKind,
  type ExportOption,
} from '@/utils/analyticsExport'

const liveMentors = ref<DemoMentor[]>([])
const capacityTable = ref<{ open: () => void } | null>(null)
const router = useRouter()
const liveEvents = ref<MentorEvent[]>([])
const unavailableSources = ref<AnalyticsSource[]>([])
const sourceAvailable = (source: AnalyticsSource) => !unavailableSources.value.includes(source)
const loadError = ref('')
const loading = ref(true)
const mentorsSnapshotDate = ref(new Date().toISOString().slice(0, 10))
const snapshotYear = computed(() => Number(mentorsSnapshotDate.value.slice(0, 4)))
const selectedYear = ref(snapshotYear.value)

useAnalyticsRefreshState('mentors', {
  selectedYear,
}, () => !loading.value && !loadError.value)
const availableYears = computed(() => {
  const years = new Set<number>([snapshotYear.value])
  liveEvents.value.forEach((event) => years.add(Number(event.date.slice(0, 4))))
  return [...years].filter(Number.isFinite).sort((a, b) => b - a)
})
const snapshot = computed(() =>
  mentorSnapshot(liveMentors.value, liveEvents.value, mentorsSnapshotDate.value),
)
const mentorInsightItems = computed(() =>
  snapshot.value.insights.filter((item) => {
    if (['Unassigned mentors', 'Near capacity', 'Over capacity'].includes(item.label)) return sourceAvailable('groups')
    return true
  }).map((item) => ({
    key: item.label,
    value: item.value,
    text: item.label,
    detail: item.detail,
  })),
)

async function openCapacityTable() {
  capacityTable.value?.open()
  await nextTick()
  document.getElementById('mentors-with-capacity')?.scrollIntoView?.({
    behavior: 'smooth',
    block: 'start',
  })
}

function openAdminMentor(mentor: DemoMentor) {
  void router.push({
    path: '/admin/users',
    query: {
      tab: 'mentors',
      capacity: 'available',
      search: mentor.name,
    },
    hash: '#admin-mentors-table',
  })
}
const range = computed(() => {
  const year = selectedYear.value
  return {
    start: `${year}-01-01`,
    end: year === snapshotYear.value ? mentorsSnapshotDate.value : `${year}-12-31`,
  }
})
const rangeError = computed(() => {
  if (!validRange(range.value))
    return 'Choose valid start and end dates, with the end on or after the start.'
  const start = new Date(range.value.start)
  const end = new Date(range.value.end)
  if (
    (end.getUTCFullYear() - start.getUTCFullYear()) * 12 +
      end.getUTCMonth() -
      start.getUTCMonth() >=
    24
  )
    return 'Choose a range spanning no more than 24 calendar months.'
  return ''
})
const activity = computed(() => mentorActivity(liveMentors.value, liveEvents.value, range.value))
const mentorActivitySort = ref<'desc' | 'asc'>('desc')
const sortedMentorActivity = computed(() =>
  mentorActivitySort.value === 'desc'
    ? activity.value.ranking
    : [...activity.value.ranking].sort((a, b) =>
        a.messages - b.messages || a.name.localeCompare(b.name) || a.id.localeCompare(b.id)),
)
const mentorActivityMax = computed(() =>
  Math.max(...activity.value.ranking.map((mentor) => mentor.messages), 1),
)
const rangeLabel = computed(() => `${range.value.start} – ${range.value.end} (UTC)`)
const activeMentorsForYear = (year: number) => new Set(
  liveEvents.value
    .filter((event) => Number(event.date.slice(0, 4)) === year && (event.logins > 0 || event.messages > 0))
    .map((event) => event.mentorId),
).size
const activeMentorComparison = computed(() => ({
  current: activeMentorsForYear(selectedYear.value),
  previous: activeMentorsForYear(selectedYear.value - 1),
  previousYear: selectedYear.value - 1,
}))
const kpis = computed(() => [
  {
    label: 'Total Mentors',
    value: snapshot.value.total,
    icon: 'users',
    detail: 'All mentor accounts',
  },
  {
    label: 'Active Mentors',
    value: activeMentorComparison.value.current,
    icon: 'activity',
    detail: 'Mentors with a recorded login or message',
    comparison: activeMentorComparison.value,
  },
  {
    label: 'Mentor Utilisation',
    value: `${snapshot.value.utilisation}%`,
    icon: 'mentor',
    detail: `${snapshot.value.assigned} of ${snapshot.value.total} mentors assigned`,
  },
  {
    label: 'Assigned Mentors',
    value: snapshot.value.assigned,
    icon: 'user-plus',
    detail: `${snapshot.value.utilisation}% have at least one group`,
  },
  {
    label: 'Unassigned Mentors',
    value: snapshot.value.unassigned,
    icon: 'user',
    detail: `${percent(snapshot.value.unassigned, snapshot.value.total)}% have no groups`,
  },
  {
    label: 'Avg. Students per Mentor',
    value: snapshot.value.averageStudents,
    icon: 'scale',
    detail: 'Unique students per assigned mentor',
  },
].map((item) => {
  if (item.label.startsWith('Active Mentors') && !sourceAvailable('groupActivity')) {
    return { ...item, value: '—', comparison: undefined, detail: 'Mentor activity data is unavailable.' }
  }
  if (!sourceAvailable('groups') && !['Total Mentors'].includes(item.label) && !item.label.startsWith('Active Mentors')) {
    return { ...item, value: '—', comparison: undefined, detail: 'Group allocation data is unavailable.' }
  }
  return item
}))

type MentorChart = {
  title: string
  note: string
  items: MetricBucket[]
  kind: 'donut' | 'horizontal' | 'vertical'
  axis?: string
  centreLabel?: string
}

const charts = computed(() => ([
  {
    title: 'Mentor Status',
    note: 'Account state; onboarding includes invited / pending.',
    items: snapshot.value.status,
    kind: 'donut',
  },
  {
    title: 'Mentor Capacity Split',
    note: 'Activated mentors only: assigned groups vs configured capacity; 0 of 0 is at capacity.',
    items: snapshot.value.capacity,
    kind: 'donut',
    centreLabel: 'Activated mentors',
  },
  {
    title: 'Mentor Background',
    note: 'Mentor profile backgrounds in the current database.',
    items: snapshot.value.background,
    kind: 'horizontal',
  },
  {
    title: 'Groups per Mentor',
    note: 'Distinct current group assignments, including zero; a mentor supports at most 5 groups.',
    items: snapshot.value.groups,
    kind: 'vertical',
    axis: 'group count',
  },
  {
    title: 'Students per Mentor',
    note: 'Unique students supported by each mentor; at most 25 (5 groups of up to 5 students).',
    items: snapshot.value.students,
    kind: 'vertical',
    axis: 'student count',
  },
  {
    title: 'Last Login Distribution',
    note: 'Days since each mentor account last logged in, as of today; 90+ means more than 90 days.',
    items: snapshot.value.lastLogin,
    kind: 'vertical',
    axis: 'last login',
  },
] as MentorChart[]).filter((chart) => {
  if (chart.title === 'Mentor Background') return sourceAvailable('users')
  if (['Mentor Capacity Split', 'Groups per Mentor', 'Students per Mentor'].includes(chart.title)) return sourceAvailable('groups')
  return true
}))

const coverageChart = computed<MentorChart>(() => ({
  title: 'Mentor Coverage',
  note: 'Supporting groups means at least one assignment.',
  items: snapshot.value.coverage,
  kind: 'donut',
}))


type MentorDonutSegment = {
  label: string
  value: number
  percent: number
  arc: number
  start: number
  color: string
}

const mentorDonutPalette = ['#007b5b', '#3b7185', '#60aba2', '#b9d9b8']

const selectedMentorDonut = ref<
  (MentorDonutSegment & { chartTitle: string }) | null
>(null)

function mentorDonutTotal(chart: MentorChart) {
  return chart.items.reduce((total, item) => total + item.value, 0)
}

function mentorDonutSegments(chart: MentorChart): MentorDonutSegment[] {
  const total = mentorDonutTotal(chart)
  let start = 0

  return chart.items.map((item, index) => {
    // Geometry uses the exact share; the rounded percent is only for labels,
    // so the arcs always close the ring without gaps or overlaps.
    const arc = total
      ? (index === chart.items.length - 1 ? Math.max(0, 100 - start) : (item.value / total) * 100)
      : 0
    const segment = {
      label: item.label,
      value: item.value,
      percent: percent(item.value, total),
      arc,
      start,
      color: mentorDonutPalette[index % mentorDonutPalette.length]!,
    }

    start += arc
    return segment
  })
}

// Arcs actually drawn on the ring. Empty categories stay in the legend but are
// not drawn (a zero-length dash can still paint a sliver in some browsers),
// and each arc runs slightly into the next to hide anti-aliasing seams.
const DONUT_ARC_OVERLAP = 0.4

function mentorDonutArcs(chart: MentorChart) {
  const drawn = mentorDonutSegments(chart).filter((segment) => segment.value > 0)
  return drawn.map((segment, index) => {
    // The last arc meets the first at 12 o'clock, so it gets no overlap.
    const overlap = index < drawn.length - 1 ? DONUT_ARC_OVERLAP : 0
    const length = drawn.length > 1 ? Math.min(segment.arc + overlap, 100) : 100
    return { ...segment, dasharray: `${length} ${100 - length}` }
  })
}

function selectMentorDonut(chartTitle: string, segment: MentorDonutSegment) {
  selectedMentorDonut.value = { chartTitle, ...segment }
}

function clearMentorDonutSelection(chartTitle: string) {
  if (selectedMentorDonut.value?.chartTitle === chartTitle) {
    selectedMentorDonut.value = null
  }
}

const activityMax = computed(() =>
  Math.max(4, Math.ceil(Math.max(0, ...activity.value.monthly.map((p) => p.active)) / 4) * 4),
)
const points = computed(() =>
  activity.value.monthly.map((p, index, all) => ({
    ...p,
    index,
    x: all.length === 1 ? 307 : 36 + (index / (all.length - 1)) * 542,
    y: 190 - (p.active / activityMax.value) * 160,
  })),
)
const monthLabel = (month: string) =>
  new Date(`${month}-01T00:00:00Z`).toLocaleDateString('en-AU', {
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  })
const tooltip = ref({ visible: false, x: 0, y: 0, title: '', value: '', detail: '' })
function hideTooltip() {
  tooltip.value.visible = false
}
function showActivity(event: Event, point: (typeof points.value)[number]) {
  const rect = (event.currentTarget as SVGElement).getBoundingClientRect()
  const mouse = event instanceof MouseEvent ? event : null
  tooltip.value = {
    visible: true,
    x: mouse?.clientX ?? rect.left + rect.width / 2,
    y: mouse?.clientY ?? rect.top + rect.height / 2,
    title: monthLabel(point.month),
    value: `${point.active} active mentors`,
    detail: `${point.messages} messages · ${point.logins} logins`,
  }
}
const exportError = ref('')
watch(range, () => {
  hideTooltip()
  exportError.value = ''
})
const exportOptions: ExportOption[] = [
  SUMMARY_OPTION,
  { ...DETAILS_OPTION, description: 'One row per mentor: status, capacity, groups and messages' },
]

function mentorsSummary() {
  const { start, end } = range.value
  return {
    fileName: exportFileName('mentors', 'summary', `${start} to ${end}`),
    csv: summaryCsv({
      page: 'Mentors',
      covers: `Current mentors; activity ${start} to ${end} (UTC)`,
      dataAsOf: mentorsSnapshotDate.value,
      unavailable: sourceLabels(unavailableSources.value),
    }, mentorsSummaryRows(snapshot.value, activity.value, {
      groups: sourceAvailable('groups'),
      background: sourceAvailable('users'),
      activity: sourceAvailable('groupActivity'),
    })),
  }
}

const backgroundLabel = (value: string) =>
  value === 'unknown' ? '' : value === 'hdr' ? 'HDR' : value.charAt(0).toUpperCase() + value.slice(1)

function mentorsDetails() {
  const { start, end } = range.value
  const messages = new Map<string, number>()
  for (const event of liveEvents.value) {
    if (event.date >= start && event.date <= end) messages.set(event.mentorId, (messages.get(event.mentorId) ?? 0) + event.messages)
  }
  // Snapshot rows keep only the login date; the account timestamp is on the mentor.
  const lastLogins = new Map(liveMentors.value.map((mentor) => [mentor.id, mentor.lastLogin]))
  const rows = [...snapshot.value.rows]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((mentor) => [
      mentor.id,
      mentor.name,
      mentor.email,
      accountStatusLabel(mentor.accountStatus, mentor.accountActive),
      activityStatusLabel(mentor.daysSinceLogin),
      isoUtc(lastLogins.get(mentor.id)),
      mentor.daysSinceLogin,
      mentor.capacity,
      mentor.groups,
      Math.max(mentor.capacity - mentor.groups, 0),
      mentor.students,
      messages.get(mentor.id) ?? 0,
      backgroundLabel(mentor.background),
    ])
  return {
    fileName: exportFileName('mentors', 'details', `${start} to ${end}`),
    csv: detailsCsv([
      'Mentor ID', 'Mentor', 'Email', 'Account Status', `Activity Status (${ACTIVE_WINDOW_DAYS} days)`, 'Last Login (UTC)',
      'Days Since Last Login', 'Capacity (Groups)', 'Groups', 'Open Slots', 'Students', 'Messages in Range', 'Background',
    ], rows),
  }
}

function exportCsv(kind: ExportKind) {
  if (rangeError.value) return
  exportError.value = runExport(kind === 'summary' ? mentorsSummary : mentorsDetails)
}

const analyticsRefreshBusy = ref(false)
const { lastUpdated, refreshFailed, markUpdated, markRefreshFailed } = useAnalyticsRefresh(async () => { if (!analyticsRefreshBusy.value) await initializeMentors(true, true) })

async function initializeMentors(force = false, preserveFilters = false) {
  if (analyticsRefreshBusy.value) return
  analyticsRefreshBusy.value = true
  if (!preserveFilters || !lastUpdated.value) loading.value = true
  loadError.value = ''
  try {
    const bundle = await loadMentorsAnalyticsBundle(force)
    unavailableSources.value = bundle.unavailableSources ?? []
    const live = buildMentorData(bundle)
    liveMentors.value = live.mentors
    liveEvents.value = live.events
    mentorsSnapshotDate.value = live.snapshotDate
    if (!preserveFilters) selectedYear.value = Number(live.snapshotDate.slice(0, 4))
    markUpdated()
  } catch (error) {
    if (preserveFilters && lastUpdated.value) { markRefreshFailed(); return }
    loadError.value = error instanceof Error ? error.message : 'Mentor analytics could not be loaded.'
  } finally {
    analyticsRefreshBusy.value = false
    loading.value = false
  }
}

onMounted(() => {
  void initializeMentors()
  window.addEventListener('scroll', hideTooltip, true)
  window.addEventListener('resize', hideTooltip)
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', hideTooltip, true)
  window.removeEventListener('resize', hideTooltip)
})
</script>

<style src="@/assets/analytics-theme.css"></style>

<style scoped>
.mentors-analytics-page {
  container-type: inline-size;
  color: var(--analytics-ui-text, var(--btf-teal));
  background: var(--analytics-ui-page, var(--btf-surface));
  font-family: Arial, sans-serif;
  padding: 22px;
  min-width: 0;
}
.mentors-analytics-page * {
  box-sizing: border-box;
}
button,
input,
select {
  font: inherit;
}
.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 18px;
  margin-bottom: 16px;
}
.breadcrumb {
  display: flex;
  gap: 10px;
  font-size: 12px;
  margin-bottom: 15px;
}
.breadcrumb a {
  color: var(--analytics-ui-muted, var(--btf-muted));
  text-decoration: none;
}
.breadcrumb a:hover {
  color: var(--analytics-ui-accent, var(--btf-dark-green));
}
.title-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
h1 {
  margin: 0;
  font-size: 28px;
  letter-spacing: -0.6px;
}
.heading-copy p {
  font-size: 13px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  margin: 8px 0 0;
}
.demo-badge {
  font-size: 10px;
  padding: 5px 9px;
  border-radius: 5px;
  border: 1px solid var(--analytics-ui-border, var(--btf-light-green));
  background: var(--analytics-ui-soft, var(--btf-track));
  white-space: nowrap;
}
.page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.range-control,
.export-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  border: 1px solid var(--analytics-ui-control-border, var(--btf-mint-green));
  background: var(--analytics-ui-surface, white);
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  border-radius: 7px;
  padding: 9px 12px;
  font-size: 12px;
}
.range-control select {
  border: none;
  color: inherit;
  background: transparent;
  max-width: 100%;
}
.export-button {
  cursor: pointer;
}
.export-button:hover {
  background: var(--analytics-ui-soft, var(--btf-track));
}
.export-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button:focus-visible,
input:focus-visible,
select:focus-visible,
a:focus-visible,
circle:focus-visible {
  outline: 2px solid var(--btf-dark-green);
  outline-offset: 3px;
}
.scope-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  margin: 0 0 18px;
  line-height: 1.6;
}
.scope-note svg {
  flex-shrink: 0;
  margin-top: 2px;
}
.custom-range {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}
.custom-range label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.custom-range input {
  border: 1px solid var(--analytics-ui-border, var(--btf-border));
  border-radius: 5px;
  padding: 7px;
  background: var(--analytics-ui-surface, white);
  color: var(--analytics-ui-text, var(--btf-teal));
}
.range-error,
.export-status {
  padding: 12px;
  border: 1px solid var(--analytics-ui-border, var(--btf-border));
  border-radius: 6px;
  font-size: 12px;
  background: var(--analytics-ui-soft, var(--btf-track));
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}
.kpi-card,
.analytics-card {
  border: 1px solid var(--analytics-ui-border, var(--btf-border));
  border-radius: 10px;
  background: var(--analytics-ui-surface, white);
  box-shadow: 0 2px 6px rgb(23 66 67 / 3%);
  min-width: 0;
}
.kpi-card {
  display: flex;
  align-items: center;
  gap: 18px;
  min-height: 118px;
  padding: 20px;
}
.kpi-icon {
  display: grid;
  place-items: center;
  background: var(--analytics-ui-soft, var(--btf-track));
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  border-radius: 13px;
  width: 58px;
  height: 58px;
  flex-shrink: 0;
}
.kpi-copy {
  min-width: 0;
}
.kpi-label {
  display: block;
  font-size: 14px;
  line-height: 1.4;
  margin-bottom: 5px;
  color: var(--analytics-ui-muted, var(--btf-muted));
}
.kpi-value {
  display: block;
  font-size: 32px;
  line-height: 1;
  margin: 6px 0;
}
.kpi-copy small {
  font-size: 12px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  line-height: 1.5;
  display: block;
}
.progress-track,
.rank-track {
  background: var(--analytics-ui-soft, var(--btf-track));
  height: 7px;
  border-radius: 3px;
  overflow: hidden;
}
.progress-track {
  margin-bottom: 6px;
}
.progress-track span,
.rank-track span {
  display: block;
  height: 100%;
  background: var(--btf-dark-green);
}
.chart-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.analytics-card {
  padding: 20px;
}
h2 {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 18px;
  margin: 0 0 16px;
}
.info-button {
  display: inline-flex;
  flex-shrink: 0;
  padding: 3px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--analytics-ui-muted, var(--btf-muted));
  cursor: help;
}
.card-note {
  font-size: 12px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  line-height: 1.5;
  margin: 0 0 14px;
}
.activity-grid,
.bottom-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.mentor-insights-card :deep(.key-insights-list) {
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  column-gap: 24px;
}

@media (max-width: 700px) {
  .mentor-insights-card :deep(.key-insights-list) {
    grid-template-columns: 1fr !important;
  }
}
.bottom-grid {
  grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.4fr);
}
.activity-chart {
  display: block;
  width: 100%;
  overflow: visible;
}
.activity-chart text {
  fill: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 10px;
  font-family: Arial, sans-serif;
}
.activity-chart .activity-value-label {
  fill: var(--analytics-ui-text, var(--btf-teal));
  font-size: 10px;
  pointer-events: none;
}
.grid-line {
  stroke: var(--analytics-ui-border, var(--btf-border));
  stroke-width: 1;
}
.series-key {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  margin: 10px 0;
  color: var(--analytics-ui-muted, var(--btf-muted));
}
.series-key i {
  width: 18px;
  height: 3px;
  background: var(--btf-dark-green);
}
.ranking {
  list-style: none;
  padding: 0;
  margin: 20px 0;
  display: grid;
  gap: 18px;
}

/* Mentor Activity: full list scrolls inside the card. */
.mentor-activity-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.mentor-activity-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.mentor-activity-heading h2 {
  margin: 0;
}
.mentor-activity-sort {
  display: inline-flex;
  flex: 0 0 40px;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: 1px solid var(--analytics-ui-border, #bad7b8);
  border-radius: 10px;
  background: var(--analytics-ui-surface, #fff);
  color: var(--analytics-ui-accent, #017151);
  font-size: 16px;
  cursor: pointer;
}
.mentor-activity-sort:hover {
  background: var(--analytics-ui-selected, #f3f8f5);
}
.mentor-activity-list {
  flex: 1 1 0;
  min-height: 220px;
  max-height: 320px;
  margin: 12px 0 0;
  padding-right: 8px;
  overflow-y: scroll;
  align-content: start;
}
.mentor-activity-list::-webkit-scrollbar {
  width: 6px;
}
.mentor-activity-list::-webkit-scrollbar-track {
  border-radius: 3px;
  background: var(--analytics-ui-soft, #eef3f1);
}
.mentor-activity-list::-webkit-scrollbar-thumb {
  border-radius: 3px;
  background: #9fbfb9;
}

/* Activated mentor pool capacity, under the capacity split legend. */
.capacity-pool {
  display: grid;
  gap: 4px;
  margin-top: 6px;
  padding-top: 10px;
  border-top: 1px solid var(--analytics-ui-border, #e7eeeb);
}
.capacity-pool > span {
  color: var(--analytics-ui-muted, #60726f);
  font-size: 11px;
  font-weight: 700;
}
.capacity-pool strong {
  color: var(--analytics-ui-text, #174243);
  font-size: 15px;
}
.capacity-pool small {
  color: var(--analytics-ui-muted, #60726f);
  font-size: 11px;
}
.capacity-pool-track {
  height: 8px;
  overflow: hidden;
  border-radius: 4px;
  background: var(--analytics-ui-soft, var(--btf-track, #eef3f1));
}
.capacity-pool-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--btf-dark-green, #017151);
}
.capacity-table-shortcut {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  margin-top: 5px;
  padding: 6px 0 0;
  border: 0;
  border-top: 1px solid var(--analytics-ui-border, #e7eeeb);
  background: transparent;
  color: var(--analytics-ui-accent, #017151);
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.capacity-table-shortcut:hover,
.capacity-table-shortcut:focus-visible {
  color: var(--analytics-ui-text, #174243);
}
.ranking li {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}
.rank-number {
  background: var(--analytics-ui-soft, var(--btf-track));
  border-radius: 4px;
  padding: 4px 7px;
}
.rank-copy {
  flex: 1;
  min-width: 0;
}
.rank-copy > span {
  display: block;
  overflow-wrap: anywhere;
  margin-bottom: 7px;
}
.ranking strong {
  text-align: right;
}
.ranking small {
  display: block;
  font-weight: normal;
  font-size: 10px;
  color: var(--analytics-ui-muted, var(--btf-muted));
}
.insights {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 15px;
  margin-top: 20px;
}
.insight {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 0;
  border-top: 1px solid var(--analytics-ui-border, var(--btf-border));
}
.insight > strong {
  background: var(--analytics-ui-soft, var(--btf-track));
  color: var(--analytics-ui-accent, var(--btf-dark-green));
  border-radius: 7px;
  padding: 9px;
  min-width: 38px;
  text-align: center;
  font-size: 24px;
}
.insight span {
  display: block;
  font-weight: 600;
  font-size: 14px;
  margin: 3px 0 5px;
}
.insight small {
  display: block;
  font-size: 12px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  line-height: 1.5;
}
.empty-state {
  text-align: center;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-size: 13px;
  padding: 55px 12px;
  line-height: 1.6;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
@media (min-width: 1001px) {
  .mentors-analytics-page {
    zoom: var(--analytics-page-scale, 0.9);
  }
}
@media (max-width: 1200px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .chart-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 850px) {
  .activity-grid,
  .bottom-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 600px) {
  .mentors-analytics-page {
    padding: 12px;
  }
  h1 {
    font-size: 25px;
  }
  .kpi-grid,
  .chart-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .kpi-label {
    min-height: auto;
  }
  .page-actions,
  .range-control {
    width: 100%;
  }
  .insights {
    grid-template-columns: minmax(0, 1fr);
  }
  .analytics-card {
    padding: 15px;
  }
}
@container (max-width: 1250px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .chart-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@container (max-width: 720px) {
  .activity-grid,
  .bottom-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@container (max-width: 520px) {
  .kpi-grid,
  .chart-grid,
  .insights {
    grid-template-columns: minmax(0, 1fr);
  }
  .kpi-label {
    min-height: auto;
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


/* Match the year selector used by the other analytics pages. */
.range-control {
  display: inline-flex !important;
  align-items: center !important;
  gap: 9px !important;
  height: 46px !important;
  min-height: 46px !important;
  padding: 0 13px !important;
  border: 1px solid var(--analytics-ui-border, #d7e3e0) !important;
  border-radius: 12px !important;
  background: var(--analytics-ui-surface, #fff) !important;
  color: var(--analytics-ui-text, #174844) !important;
  font-size: 14px !important;
  font-weight: 700 !important;
}

.range-control select {
  min-width: 0 !important;
  border: 0 !important;
  outline: 0 !important;
  background: transparent !important;
  color: inherit !important;
  font: inherit !important;
  cursor: pointer !important;
}

@media (max-width: 780px) {
  .range-control {
    flex: 1 1 210px !important;
  }
}

.mentors-analytics-page {
  padding: 28px 32px 40px !important;
}



/* =========================================================
   Compact Mentors summary + Groups-style top actions
   ========================================================= */
.mentors-analytics-page .page-actions {
  display: flex !important;
  align-items: center !important;
  gap: 12px !important;
  align-self: start !important;
  flex-wrap: nowrap !important;
}

.mentors-analytics-page .range-control,
.mentors-analytics-page .export-button {
  height: 46px !important;
  min-height: 46px !important;
  border-radius: 12px !important;
  font-size: 14px !important;
  font-weight: 700 !important;
}

.mentors-analytics-page .range-control {
  width: 120px !important;
  padding: 0 13px !important;
  border: 1px solid var(--analytics-ui-control-border, #9fd8c7) !important;
  color: var(--analytics-ui-accent, #017151) !important;
  background: var(--analytics-ui-page, #ffffff) !important;
  gap: 9px !important;
}

.mentors-analytics-page .range-control select {
  flex: 1 !important;
  min-width: 0 !important;
  border: 0 !important;
  outline: 0 !important;
  background: transparent !important;
  color: inherit !important;
  font: inherit !important;
  cursor: pointer !important;
}

.mentors-analytics-page .export-button {
  width: 142px !important;
  padding: 0 16px !important;
  border: 1px solid var(--analytics-ui-control-border, #9fd8c7) !important;
  color: var(--analytics-ui-accent, #017151) !important;
  background: var(--analytics-ui-page, #ffffff) !important;
}

.mentors-analytics-page .export-button:hover {
  background: var(--analytics-ui-selected, #ecf8f4) !important;
}

/* Keep all six mentor KPI cards on one desktop row. */
.mentors-analytics-page .kpi-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
  gap: 12px !important;
}

.mentors-analytics-page .kpi-card {
  min-width: 0 !important;
  min-height: 96px !important;
  padding: 10px 12px !important;
  gap: 10px !important;
}

.mentors-analytics-page .kpi-icon {
  width: 42px !important;
  height: 42px !important;
  flex: 0 0 42px !important;
  border-radius: 11px !important;
}

.mentors-analytics-page .kpi-copy {
  min-width: 0 !important;
  flex: 1 1 auto;
  grid-template-rows: auto 34px 6px minmax(24px, auto) !important;
}

.mentors-analytics-page .kpi-copy > .analytics-value-row {
  width: 100%;
  justify-content: flex-start;
}

.mentors-analytics-page .kpi-label {
  font-size: 11px !important;
  line-height: 1.2 !important;
}

.mentors-analytics-page .kpi-label--compact {
  font-size: 10px !important;
  white-space: nowrap;
}

.mentors-analytics-page .kpi-value {
  font-size: 25px !important;
  line-height: 1.05 !important;
}

.mentors-analytics-page .kpi-card small {
  font-size: 10px !important;
  line-height: 1.25 !important;
}

.mentors-analytics-page .progress-track {
  max-width: 130px !important;
}

@media (max-width: 1279px) {
  .mentors-analytics-page .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  }
}

@media (max-width: 760px) {
  .mentors-analytics-page .kpi-grid {
    grid-template-columns: 1fr !important;
  }

  .mentors-analytics-page .page-actions {
    width: 100% !important;
    flex-wrap: wrap !important;
  }

  .mentors-analytics-page .range-control,
  .mentors-analytics-page .export-button {
    width: auto !important;
    flex: 1 1 140px !important;
  }
}


.mentors-analytics-page .range-control svg,
.mentors-analytics-page .range-control i {
  color: var(--analytics-ui-accent, #017151) !important;
  stroke: #017151 !important;
}



/* =========================================================
   Final mentor distribution layout
   Row 1: Status | Capacity Split | Background
   Row 2: Groups | Students | Last Login
   ========================================================= */
.mentors-analytics-page .chart-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 16px !important;
  align-items: stretch !important;
}

.mentors-analytics-page .chart-grid > .analytics-card {
  width: 100% !important;
  min-width: 0 !important;
  height: 300px !important;
}

/* Keep donut cards visually close to the Users by Role style:
   chart on the left, legend/details on the right. */
.mentors-analytics-page .chart-grid > .analytics-card:nth-child(1),
.mentors-analytics-page .chart-grid > .analytics-card:nth-child(2) {
  overflow: hidden !important;
}

/* Groups-style green icons in the top-right controls. */
.mentors-analytics-page .range-control > i,
.mentors-analytics-page .export-button > i {
  color: var(--analytics-ui-accent, #017151) !important;
  font-size: 16px !important;
  line-height: 1 !important;
}

.mentors-analytics-page .range-control,
.mentors-analytics-page .range-control select,
.mentors-analytics-page .export-button {
  color: var(--analytics-ui-accent, #017151) !important;
}

@media (max-width: 1200px) {
  .mentors-analytics-page .chart-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }
}

@media (max-width: 700px) {
  .mentors-analytics-page .chart-grid {
    grid-template-columns: 1fr !important;
  }

  .mentors-analytics-page .chart-grid > .analytics-card {
    height: auto !important;
    min-height: 280px !important;
  }
}



/* =========================================================
   Interactive Mentor Status / Mentor Capacity Split donuts
   Matches the Users by Role interaction:
   segment hover/focus <-> legend highlight + centre details.
   ========================================================= */
.interactive-mentor-donut-layout {
  display: grid;
  grid-template-columns: minmax(150px, 0.9fr) minmax(180px, 1.1fr);
  align-items: start;
  gap: 14px;
  min-height: 220px;
  padding-top: 8px;
}

.interactive-mentor-donut-wrap {
  position: relative;
  isolation: isolate;
  width: 180px;
  height: 180px;
  margin: 0 auto;
}

.interactive-mentor-donut-svg {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.interactive-mentor-donut-segment {
  cursor: pointer;
  outline: none;
  transition:
    stroke-width 0.16s ease,
    filter 0.16s ease,
    opacity 0.16s ease;
}

.interactive-mentor-donut-segment:hover,
.interactive-mentor-donut-segment:focus-visible,
.interactive-mentor-donut-segment.selected {
  stroke-width: 28;
  filter: brightness(0.98);
}

.interactive-mentor-donut-centre {
  position: absolute;
  top: 50%;
  left: 50%;
  display: flex;
  width: 104px;
  height: 104px;
  padding: 8px;
  border-radius: 50%;
  background: var(--analytics-ui-surface, #fff);
  box-sizing: border-box;
  transform: translate(-50%, -50%);
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  text-align: center;
  z-index: 2;
}

.interactive-mentor-donut-centre strong {
  color: var(--analytics-ui-text, #163f3c);
  font-size: 28px;
  line-height: 1;
}

.interactive-mentor-donut-centre > span:last-child {
  margin-top: 8px;
  color: var(--analytics-ui-muted, #667b77);
  font-size: 11px;
  line-height: 1.25;
}

.interactive-donut-selection-label {
  max-width: 88px;
  margin-bottom: 7px;
  color: var(--analytics-ui-muted, #506965) !important;
  font-size: 10px !important;
  line-height: 1.15 !important;
  font-weight: 700;
  text-align: center;
  white-space: normal;
  overflow-wrap: anywhere;
}

.interactive-mentor-donut-legend {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.interactive-mentor-donut-legend-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  min-height: 36px;
  padding: 6px 8px;
  border-radius: 9px;
  cursor: pointer;
  outline: none;
  transition:
    background-color 0.15s ease,
    transform 0.15s ease;
}

.interactive-mentor-donut-legend-row:hover,
.interactive-mentor-donut-legend-row:focus,
.interactive-mentor-donut-legend-row.selected {
  background: var(--analytics-ui-selected, #e5f0e2);
}

.interactive-mentor-donut-legend-row > span {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
  color: var(--analytics-ui-text, #174243);
  font-size: 12px;
  white-space: nowrap;
}

.interactive-mentor-donut-legend-row > strong {
  color: var(--analytics-ui-text, #123f3c);
  font-size: 12px;
  white-space: nowrap;
}

.interactive-mentor-donut-legend-row > strong small {
  color: var(--analytics-ui-muted, #667b77);
  font-size: 10px;
  font-weight: 500;
}

.interactive-donut-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  flex: 0 0 10px;
  border-radius: 50%;
}

@media (max-width: 1350px) {
  .interactive-mentor-donut-layout {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .interactive-mentor-donut-wrap {
    width: 160px;
    height: 160px;
  }

  .interactive-mentor-donut-legend {
    width: 100%;
  }
}

@media (max-width: 700px) {
  .interactive-mentor-donut-layout {
    grid-template-columns: minmax(140px, 0.9fr) minmax(160px, 1.1fr);
  }
}

</style>
