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
          <button type="button" class="export-button" :disabled="loading || !!loadError || !!rangeError" @click="exportCsv">
            <i class="fas fa-download" aria-hidden="true"></i>Export CSV
          </button>
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
    <p v-if="exportStatus" class="export-status" role="status">{{ exportStatus }}</p>

    <section class="kpi-grid" aria-label="Mentor snapshot summary">
      <article v-for="item in kpis" :key="item.label" class="kpi-card">
        <span class="kpi-icon"><BtfIcon :name="item.icon" :size="24" /></span>
        <div class="kpi-copy">
          <span class="kpi-label">{{ item.label }}</span
          ><strong class="kpi-value">{{ item.value }}</strong>
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
                  stroke="#e7ebef"
                  stroke-width="24"
                />

                <circle
                  v-for="segment in mentorDonutSegments(chart)"
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
                  <span>Total mentors</span>
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
      <article class="analytics-card">
        <h2>Top 5 Most Active Mentors</h2>
        <p class="card-note">Ranked by messages · {{ rangeLabel }}</p>
        <p v-if="rangeError" class="empty-state">Choose a valid date range to view rankings.</p>
        <p v-else-if="!activity.ranking.length" class="empty-state">
          No mentor messages in this date range.
        </p>
        <ol v-else class="ranking">
          <li v-for="(mentor, index) in activity.ranking" :key="mentor.id">
            <span class="rank-number">{{ index + 1 }}</span>
            <div class="rank-copy">
              <span>{{ mentor.name }}</span>
              <div class="rank-track">
                <span
                  :style="{
                    width: `${(mentor.messages / (activity.ranking[0]?.messages || 1)) * 100}%`,
                  }"
                ></span>
              </div>
            </div>
            <strong>{{ mentor.messages }}<small>messages</small></strong>
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
                stroke="#e7ebef"
                stroke-width="24"
              />
              <circle
                v-for="segment in mentorDonutSegments(coverageChart)"
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import BtfIcon from '@/components/BtfIcon.vue'
import AnalyticsKeyInsights from '@/components/analytics/AnalyticsKeyInsights.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import MentorDistributionChart from '@/components/analytics/MentorDistributionChart.vue'
import { BTF_COLORS } from '@/constants/btfTheme'
import type { DemoMentor, MentorEvent } from '@/types/analytics'
import { buildMentorData, loadMentorsAnalyticsBundle } from '@/utils/liveAnalyticsData'
import {
  mentorSnapshot,
  mentorActivity,
  mentorsCsv,
  percent,
  validRange,
  type MetricBucket,
} from '@/utils/mentorsAnalytics'

const liveMentors = ref<DemoMentor[]>([])
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
    if (['No login for more than 30 days', 'No recorded login'].includes(item.label)) return sourceAvailable('groupActivity')
    return true
  }).map((item) => ({
    key: item.label,
    value: item.value,
    text: item.label,
    detail: item.detail,
  })),
)
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
const rangeLabel = computed(() => `${range.value.start} – ${range.value.end} (UTC)`)
const kpis = computed(() => [
  {
    label: 'Total Mentors',
    value: snapshot.value.total,
    icon: 'users',
    detail: 'All mentor accounts',
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
    label: 'Average Students per Mentor',
    value: snapshot.value.averageStudents,
    icon: 'scale',
    detail: 'Unique students per assigned mentor',
  },
].map((item) => !sourceAvailable('groups') && item.label !== 'Total Mentors'
  ? { ...item, value: '—', detail: 'Group allocation data is unavailable.' }
  : item))

type MentorChart = {
  title: string
  note: string
  items: MetricBucket[]
  kind: 'donut' | 'horizontal' | 'vertical'
  axis?: string
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
    note: 'Assigned groups vs configured capacity; 0 of 0 is at capacity.',
    items: snapshot.value.capacity,
    kind: 'donut',
  },
  {
    title: 'Mentor Background',
    note: 'Mentor profile backgrounds in the current database.',
    items: snapshot.value.background,
    kind: 'horizontal',
  },
  {
    title: 'Groups per Mentor',
    note: 'Distinct current group assignments, including zero.',
    items: snapshot.value.groups,
    kind: 'vertical',
    axis: 'group count',
  },
  {
    title: 'Students per Mentor',
    note: 'Unique students supported by each mentor; the 0–5 bucket includes zero students.',
    items: snapshot.value.students,
    kind: 'vertical',
    axis: 'student count',
  },
  {
    title: 'Last Login Distribution',
    note: 'Days before the snapshot; 90+ means more than 90 days.',
    items: snapshot.value.lastLogin,
    kind: 'vertical',
    axis: 'last login',
  },
] as MentorChart[]).filter((chart) => {
  if (chart.title === 'Mentor Background') return sourceAvailable('users')
  if (chart.title === 'Last Login Distribution') return sourceAvailable('groupActivity')
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
  const total = mentorDonutTotal(chart) || 1
  let start = 0

  return chart.items.map((item, index) => {
    const itemPercent = percent(item.value, total)
    const segment = {
      label: item.label,
      value: item.value,
      percent: itemPercent,
      start,
      color: mentorDonutPalette[index % mentorDonutPalette.length],
    }

    start += itemPercent
    return segment
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
const exportStatus = ref('')
watch(range, () => {
  hideTooltip()
  exportStatus.value = ''
})
function exportCsv() {
  if (rangeError.value) return
  try {
    const url = URL.createObjectURL(
      new Blob([mentorsCsv(snapshot.value, activity.value, range.value, mentorsSnapshotDate.value, {
        groups: sourceAvailable('groups'),
        background: sourceAvailable('users'),
        activity: sourceAvailable('groupActivity'),
      })], {
        type: 'text/csv;charset=utf-8;',
      }),
    )
    const anchor = document.createElement('a')
    try {
      anchor.href = url
      anchor.download = `mentors-analytics-${range.value.start}-${range.value.end}.csv`
      document.body.appendChild(anchor)
      anchor.click()
      exportStatus.value =
        'CSV download started. Includes snapshot metrics and selected activity dates.'
    } finally {
      anchor.remove()
      URL.revokeObjectURL(url)
    }
  } catch {
    exportStatus.value = 'The CSV could not be downloaded. Please try again.'
  }
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
  color: var(--btf-teal);
  background: var(--btf-surface);
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
  color: var(--btf-muted);
  text-decoration: none;
}
.breadcrumb a:hover {
  color: var(--btf-dark-green);
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
  color: var(--btf-muted);
  margin: 8px 0 0;
}
.demo-badge {
  font-size: 10px;
  padding: 5px 9px;
  border-radius: 5px;
  border: 1px solid var(--btf-light-green);
  background: var(--btf-track);
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
  border: 1px solid var(--btf-mint-green);
  background: white;
  color: var(--btf-dark-green);
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
  background: var(--btf-track);
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
  color: var(--btf-muted);
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
  border: 1px solid var(--btf-border);
  border-radius: 5px;
  padding: 7px;
  background: white;
  color: var(--btf-teal);
}
.range-error,
.export-status {
  padding: 12px;
  border: 1px solid var(--btf-border);
  border-radius: 6px;
  font-size: 12px;
  background: var(--btf-track);
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}
.kpi-card,
.analytics-card {
  border: 1px solid var(--btf-border);
  border-radius: 10px;
  background: white;
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
  background: var(--btf-track);
  color: var(--btf-dark-green);
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
  color: var(--btf-muted);
}
.kpi-value {
  display: block;
  font-size: 32px;
  line-height: 1;
  margin: 6px 0;
}
.kpi-copy small {
  font-size: 12px;
  color: var(--btf-muted);
  line-height: 1.5;
  display: block;
}
.progress-track,
.rank-track {
  background: var(--btf-track);
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
  color: var(--btf-muted);
  cursor: help;
}
.card-note {
  font-size: 12px;
  color: var(--btf-muted);
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
  fill: var(--btf-muted);
  font-size: 10px;
  font-family: Arial, sans-serif;
}
.activity-chart .activity-value-label {
  fill: var(--btf-teal);
  font-size: 10px;
  pointer-events: none;
}
.grid-line {
  stroke: var(--btf-border);
  stroke-width: 1;
}
.series-key {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  margin: 10px 0;
  color: var(--btf-muted);
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
.ranking li {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}
.rank-number {
  background: var(--btf-track);
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
  color: var(--btf-muted);
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
  border-top: 1px solid var(--btf-border);
}
.insight > strong {
  background: var(--btf-track);
  color: var(--btf-dark-green);
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
  color: var(--btf-muted);
  line-height: 1.5;
}
.empty-state {
  text-align: center;
  color: var(--btf-muted);
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
  color: #59706e !important;
  font-size: 14px !important;
}

.breadcrumb a {
  color: #59706e !important;
  text-decoration: none !important;
}

.breadcrumb a:hover {
  color: #08765d !important;
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
  color: #163f3c !important;
  font-size: 36px !important;
  line-height: 1.15 !important;
  font-weight: 800 !important;
  letter-spacing: normal !important;
}

.page-heading .heading-copy > p,
.page-heading p {
  margin: 8px 0 0 !important;
  color: #617572 !important;
  font-size: 16px !important;
}

.demo-badge {
  display: inline-flex !important;
  align-items: center !important;
  min-height: 30px !important;
  padding: 0 10px !important;
  border: 1px solid #f0d487 !important;
  border-radius: 999px !important;
  background: #fff7df !important;
  color: #916700 !important;
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
  border: 1px solid #9fd8c7 !important;
  border-radius: 12px !important;
  background: #fff !important;
  color: #017151 !important;
  font-size: 14px !important;
  font-weight: 700 !important;
  cursor: pointer !important;
}

.export-button:hover {
  background: #ecf8f4 !important;
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
  border: 1px solid #d7e3e0 !important;
  border-radius: 12px !important;
  background: #fff !important;
  color: #174844 !important;
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
  border: 1px solid #9fd8c7 !important;
  color: #017151 !important;
  background: #ffffff !important;
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
  border: 1px solid #9fd8c7 !important;
  color: #017151 !important;
  background: #ffffff !important;
}

.mentors-analytics-page .export-button:hover {
  background: #ecf8f4 !important;
}

/* Put all five mentor KPI cards on one desktop row. */
.mentors-analytics-page .kpi-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr)) !important;
  gap: 12px !important;
}

.mentors-analytics-page .kpi-card {
  min-width: 0 !important;
  min-height: 108px !important;
  padding: 14px 13px !important;
  gap: 11px !important;
}

.mentors-analytics-page .kpi-icon {
  width: 46px !important;
  height: 46px !important;
  flex: 0 0 46px !important;
  border-radius: 12px !important;
}

.mentors-analytics-page .kpi-copy {
  min-width: 0 !important;
}

.mentors-analytics-page .kpi-label {
  font-size: 11px !important;
  line-height: 1.2 !important;
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

@media (max-width: 1180px) {
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
  color: #017151 !important;
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
  color: #017151 !important;
  font-size: 16px !important;
  line-height: 1 !important;
}

.mentors-analytics-page .range-control,
.mentors-analytics-page .range-control select,
.mentors-analytics-page .export-button {
  color: #017151 !important;
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
  align-items: center;
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
.interactive-mentor-donut-segment:focus,
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
  background: #fff;
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
  color: #163f3c;
  font-size: 28px;
  line-height: 1;
}

.interactive-mentor-donut-centre > span:last-child {
  margin-top: 8px;
  color: #667b77;
  font-size: 11px;
  line-height: 1.25;
}

.interactive-donut-selection-label {
  max-width: 88px;
  margin-bottom: 7px;
  color: #506965 !important;
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
  background: #e5f0e2;
}

.interactive-mentor-donut-legend-row > span {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
  color: #174243;
  font-size: 12px;
  white-space: nowrap;
}

.interactive-mentor-donut-legend-row > strong {
  color: #123f3c;
  font-size: 12px;
  white-space: nowrap;
}

.interactive-mentor-donut-legend-row > strong small {
  color: #667b77;
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
