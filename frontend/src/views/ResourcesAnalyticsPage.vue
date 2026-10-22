<template>
  <section class="resources-analytics-page">
    <div class="page-heading">
      <div class="heading-copy">
        <div class="breadcrumb">
          <RouterLink to="/dashboard">Home</RouterLink><span>›</span>
          <RouterLink to="/analytics">Analytics</RouterLink><span>›</span>
          <span>Resources Analytics</span>
        </div>
        <div class="title-line">
          <h1>Resources Analytics</h1>
          
        </div>
        <p>Monitor resource access and engagement across the program.</p>
      </div>
      <div class="page-actions">
        <div class="analytics-export-stack">
          <AnalyticsExportMenu :options="exportOptions" :disabled="exportDisabled" @select="exportCsv" />
          <div class="analytics-update-status">
            <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />
          </div>
        </div>
      </div>
    </div>

    <p v-if="exportError" role="alert">{{ exportError }}</p>

    <AnalyticsPartialNotice :sources="unavailableSources" @retry="loadAnalytics(true)" />

    <AnalyticsDataState
      :loading="isLoading"
      :error="loadError"
      :empty="isEmpty"
      empty-message="No resources are available in the current database. Generate or load a dataset, then refresh this page."
      @retry="refreshAnalytics"
    >
    <section class="kpi-grid">
      <article class="kpi-card"><div class="kpi-icon"><i class="fas fa-arrow-pointer"></i></div><div><span class="kpi-label">Resource Clicks</span><strong><AnalyticsNumber :value="sourceAvailable('resourceAnalytics') ? data.totalClicks : '—'" /></strong><small>Total recorded clicks</small></div></article>
      <article v-if="sourceAvailable('resourceAnalytics')" class="kpi-card"><div class="kpi-icon"><i class="fas fa-chart-line"></i></div><div><span class="kpi-label">Clicks</span><div class="analytics-value-row"><strong><AnalyticsNumber :value="resourceYearComparison.current" /></strong><AnalyticsYearChange :current="resourceYearComparison.current" :previous="resourceYearComparison.previous" :label="`vs ${resourceYearComparison.previousYear}`" /></div><small>Recorded clicks during the year</small></div></article>
      <article class="kpi-card"><div class="kpi-icon"><i class="fas fa-users"></i></div><div><span class="kpi-label">Unique Users</span><strong><AnalyticsNumber :value="sourceAvailable('resourceAnalytics') ? data.uniqueUsers : '—'" /></strong><small>Users who accessed resources</small></div></article>
      <article class="kpi-card"><div class="kpi-icon"><i class="fas fa-book"></i></div><div><span class="kpi-label">Active Resources</span><strong><AnalyticsNumber :value="sourceAvailable('resourceAnalytics') ? data.activeResources : '—'" /></strong><small>Resources with recorded access</small></div></article>
      <article class="kpi-card"><div class="kpi-icon"><i class="fas fa-book-open"></i></div><div><span class="kpi-label">Most Used Resource</span><strong class="resource-name">{{ data.mostUsedResource }}</strong><small>Highest click count</small></div></article>
    </section>

    <section v-if="sourceAvailable('resourceAnalytics')" class="analytics-grid top-grid">
      <article class="analytics-card">
        <div class="chart-title-row">
          <h2>Resource Clicks Over Time</h2>
          <label class="chart-range-control">
            <span class="sr-only">Search resource clicks by date</span>
            <i class="fas fa-magnifying-glass" aria-hidden="true"></i>
            <input
              v-model="clicksDateQuery"
              type="search"
              inputmode="search"
              aria-label="Search resource clicks by year, month, or date"
              placeholder="YY, MM, YYMM or MMDD"
            />
          </label>
        </div>
        <p class="card-subtitle">Daily clicks recorded in the current database period.</p>
        <div class="chart-with-y-axis">
          <div class="y-axis"><span v-for="tick in yTicks" :key="tick">{{ tick }}</span></div>
          <div class="resource-chart">
            <div class="grid-lines"><span v-for="n in 5" :key="n"></span></div>
            <div v-if="filteredDailyClicks.length" ref="clicksBars" class="bars">
              <div v-for="point in filteredDailyClicks" :key="point.label" class="bar-column">
                <strong>{{ point.clicks }}</strong>
                <div class="bar-track"><div class="bar-fill" :style="{ height: `${(point.clicks / dailyAxisMax) * 100}%` }" @mouseenter="showTooltip($event, point.label, `${point.clicks} clicks`, 'Resource activity')" @mousemove="moveTooltip" @mouseleave="hideTooltip"></div></div>
                <span>{{ point.label }}</span>
              </div>
            </div>
            <div v-else class="chart-empty">No records match this date.</div>
          </div>
        </div>
        <div class="axis-title">Number of Clicks</div>
      </article>

      <article class="analytics-card">
        <h2>Usage by Resource Type</h2>
        <p class="card-subtitle">Total clicks grouped by resource type.</p>
        <div class="type-list">
          <div v-for="item in data.byType" :key="item.label" class="type-row">
            <span>{{ item.label }}</span>
            <div class="type-track"><i :style="{ width: `${(item.value / maxTypeValue) * 100}%`, background: item.color }"></i></div>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section v-if="sourceAvailable('resourceAnalytics')" class="analytics-card resource-trend-card">
      <h2>Clicks and Unique Users by Resource</h2>
      <p class="card-subtitle">Daily usage of each resource. Switch resources on or off to compare them.</p>
      <ResourceUsageTrendChart v-if="data.resourceDaily" :rows="data.resourceDaily" />
      <p v-else class="card-subtitle">Per-resource daily usage is not available from the server yet.</p>
    </section>

    <section class="analytics-card table-card">
      <div class="table-heading">
        <div>
          <h2>Resource Usage Details</h2>
          <p class="card-subtitle">
            Clicks and unique users for each resource. Audience filters describe who the resource
            is available to, not the role of the visitors who clicked it.
          </p>
        </div>
        <div class="resource-table-filters">
          <select :disabled="!sourceAvailable('resources')" v-model="selectedAudienceRole" aria-label="Filter resources by configured audience">
            <option value="all">All audiences</option>
            <option value="Student">Students</option>
            <option value="Mentor">Mentors</option>
            <option value="Supervisor">Supervisors</option>
          </select>
          <input v-model="search" type="search" placeholder="Search resources" />
        </div>
      </div>
      <div class="table-wrap">
        <table class="resource-usage-table">
          <colgroup>
            <col class="col-resource" />
            <col class="col-type" />
            <col class="col-clicks" />
            <col class="col-unique-users" />
          </colgroup>
          <thead>
            <tr>
              <th>Resource</th>
              <th>Type</th>
              <th>
                <button :disabled="!sourceAvailable('resourceAnalytics')" type="button" class="sort-header-button" @click="toggleSort('clicks')">
                  Clicks
                  <i :class="sortIcon('clicks')" aria-hidden="true"></i>
                </button>
              </th>
              <th>
                <button :disabled="!sourceAvailable('resourceAnalytics')" type="button" class="sort-header-button" @click="toggleSort('uniqueUsers')">
                  Unique Users
                  <i :class="sortIcon('uniqueUsers')" aria-hidden="true"></i>
                </button>
              </th>

            </tr>
          </thead>
          <tbody>
            <tr v-for="item in sortedResources" :key="item.id">
              <td><strong>{{ item.name }}</strong></td>
              <td>{{ item.type }}</td>
              <td>{{ sourceAvailable('resourceAnalytics') ? item.clicks : '—' }}</td>
              <td>{{ sourceAvailable('resourceAnalytics') ? item.uniqueUsers : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <ChartTooltip :visible="tooltip.visible" :x="tooltip.x" :y="tooltip.y" :title="tooltip.title" :value="tooltip.value" :detail="tooltip.detail" />
    </AnalyticsDataState>
  </section>
</template>

<script setup lang="ts">
import AnalyticsPartialNotice from '@/components/analytics/AnalyticsPartialNotice.vue'
import type { AnalyticsSource } from '@/utils/liveAnalyticsData'
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { useAnalyticsRefreshState } from '@/composables/useAnalyticsRefreshState'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import AnalyticsDataState from '@/components/analytics/AnalyticsDataState.vue'
import AnalyticsYearChange from '@/components/analytics/AnalyticsYearChange.vue'
import AnalyticsNumber from '@/components/analytics/AnalyticsNumber.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import ResourceUsageTrendChart from '@/components/analytics/ResourceUsageTrendChart.vue'
import type { ResourceDailyUsage } from '@/types/analytics'
import {
  buildResourcesAnalytics,
  loadResourcesAnalyticsBundle,
  type ResourceAnalyticsBundle,
} from '@/utils/liveAnalyticsData'
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

const data = reactive({
  totalClicks: 0, uniqueUsers: 0, activeResources: 0, mostUsedResource: '—',
  dailyClicks: [] as Array<{ label: string; clicks: number }>,
  resourceDaily: [] as ResourceDailyUsage[] | null,
  resources: [] as Array<{ id: number; name: string; clicks: number; uniqueUsers: number; type: string; roles: Array<'Student' | 'Mentor' | 'Supervisor'> }>,
  byType: [] as Array<{ label: string; value: number; color: string }>,
})
const resourceYearComparison = computed(() => {
  const years = data.dailyClicks
    .map((point) => Number(point.label.slice(0, 4)))
    .filter(Number.isFinite)
  const year = years.length ? Math.max(...years) : new Date().getUTCFullYear()
  const clicksForYear = (target: number) => data.dailyClicks
    .filter((point) => Number(point.label.slice(0, 4)) === target)
    .reduce((sum, point) => sum + point.clicks, 0)
  return {
    year,
    previousYear: year - 1,
    current: clicksForYear(year),
    previous: clicksForYear(year - 1),
  }
})
const unavailableSources = ref<AnalyticsSource[]>([])
const sourceAvailable = (source: AnalyticsSource) => !unavailableSources.value.includes(source)
const loadError = ref('')
const isLoading = ref(true)
const isEmpty = ref(false)
const hasLoaded = ref(false)
const exportDisabled = computed(() => isLoading.value || !!loadError.value || isEmpty.value || !hasLoaded.value)

function resourceBundleIsEmpty(bundle: ResourceAnalyticsBundle) {
  return bundle.resources.length === 0
    && bundle.resourceAnalytics.total_clicks === 0
    && bundle.resourceAnalytics.unique_users === 0
    && bundle.resourceAnalytics.active_resources === 0
    && bundle.resourceAnalytics.top_resources.length === 0
    && bundle.resourceAnalytics.clicks_by_day.length === 0
}

const analyticsRefreshBusy = ref(false)
const { lastUpdated, refreshFailed, markUpdated, markRefreshFailed } = useAnalyticsRefresh(async () => { if (!analyticsRefreshBusy.value) await loadAnalytics(true, true) })

async function loadAnalytics(force = false, preserveFilters = false) {
  if (analyticsRefreshBusy.value) return
  analyticsRefreshBusy.value = true
  if (!preserveFilters || !lastUpdated.value) isLoading.value = true
  loadError.value = ''
  try {
    const bundle = await loadResourcesAnalyticsBundle(force)
    unavailableSources.value = bundle.unavailableSources ?? []
    Object.assign(data, buildResourcesAnalytics(bundle))
    if (!sourceAvailable('resources')) selectedAudienceRole.value = 'all'
    isEmpty.value = unavailableSources.value.length === 0 && resourceBundleIsEmpty(bundle)
    hasLoaded.value = true
    markUpdated()
  } catch (error) {
    if (preserveFilters && lastUpdated.value) { markRefreshFailed(); return }
    console.error('Failed to load resource analytics from the backend.', error)
    loadError.value = 'Resource analytics could not be loaded from the backend. Check the API and try again.'
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
const search = ref('')
const selectedAudienceRole = ref<'all' | 'Student' | 'Mentor' | 'Supervisor'>('all')
const clicksDateQuery = ref('')
type ResourceSortKey = 'clicks' | 'uniqueUsers'
const resourceSortKey = ref<ResourceSortKey | null>(null)
const resourceSortDirection = ref<'asc' | 'desc'>('desc')

useAnalyticsRefreshState('resources', {
  search,
  selectedAudienceRole,
  clicksDateQuery,
  resourceSortKey,
  resourceSortDirection,
}, () => !isLoading.value && hasLoaded.value)
const tooltip = ref({ visible:false,x:0,y:0,title:'',value:'',detail:'' })
const monthNames = [
  'january', 'february', 'march', 'april', 'may', 'june',
  'july', 'august', 'september', 'october', 'november', 'december',
]
const filteredDailyClicks = computed(() => {
  const points = [...data.dailyClicks].sort((a, b) => a.label.localeCompare(b.label))
  const query = clicksDateQuery.value.trim()
  if (!query) return points

  const monthNameQuery = query.toLowerCase()
  if (/^[a-z]+$/.test(monthNameQuery) && monthNameQuery.length >= 3) {
    const monthIndex = monthNames.findIndex((month) => month.startsWith(monthNameQuery))
    if (monthIndex >= 0) {
      const paddedMonth = String(monthIndex + 1).padStart(2, '0')
      return points.filter((point) => point.label.slice(5, 7) === paddedMonth)
    }
    return []
  }

  const digits = query.replace(/\D/g, '')
  if (!digits) return []

  // One or two digits can be a month; exactly two digits can also be a
  // two-digit year. Keep every matching interpretation present in the data.
  if (/^\d{1,2}$/.test(digits)) {
    const month = Number(digits)
    const paddedMonth = String(month).padStart(2, '0')
    return points.filter((point) => {
      const compactDate = point.label.replace(/\D/g, '')
      const matchesMonth = month >= 1 && month <= 12
        && compactDate.slice(4, 6) === paddedMonth
      const matchesYear = digits.length === 2
        && compactDate.slice(2, 4) === digits
      return matchesMonth || matchesYear
    })
  }

  // Four digits can mean a full year, YYMM, or MMDD. Match every valid
  // interpretation present in the loaded data instead of guessing one.
  if (/^\d{4}$/.test(digits)) {
    return points.filter((point) => {
      const compactDate = point.label.replace(/\D/g, '')
      return compactDate.slice(0, 4) === digits
        || compactDate.slice(2, 6) === digits
        || compactDate.slice(4, 8) === digits
    })
  }

  // Dates arrive as YYYY-MM-DD. Comparing the compact value supports YYYY,
  // YYYYMM and YYYYMMDD as well as the same values typed with separators.
  return points.filter((point) => point.label.replace(/\D/g, '').startsWith(digits))
})
const clicksBars = ref<HTMLElement | null>(null)

watch(filteredDailyClicks, async () => {
  await nextTick()
  window.requestAnimationFrame(() => {
    if (clicksBars.value) clicksBars.value.scrollLeft = clicksBars.value.scrollWidth
  })
}, { flush: 'post' })

const maxDailyClicks = computed(() => Math.max(...filteredDailyClicks.value.map(p => p.clicks),1))
const dailyAxisMax = computed(() => Math.max(4, Math.ceil(maxDailyClicks.value / 4) * 4))
const maxTypeValue = computed(() => Math.max(...data.byType.map(p => p.value),1))
const yTicks = computed(() => Array.from({ length: 5 }, (_, index) => dailyAxisMax.value * (4 - index) / 4))
const filteredResources = computed(() => {
  const q = search.value.trim().toLowerCase()

  return data.resources.filter((item) => {
    const matchesSearch =
      !q ||
      item.name.toLowerCase().includes(q) ||
      item.type.toLowerCase().includes(q)

    const matchesRole =
      selectedAudienceRole.value === 'all' ||
      item.roles.includes(selectedAudienceRole.value)

    return matchesSearch && matchesRole
  })
})

const sortedResources = computed(() => {
  const items = [...filteredResources.value]
  if (!resourceSortKey.value) return items

  const key = resourceSortKey.value
  const direction = resourceSortDirection.value === 'asc' ? 1 : -1
  return items.sort((a, b) => (a[key] - b[key]) * direction)
})

function toggleSort(key: ResourceSortKey) {
  if (resourceSortKey.value === key) {
    resourceSortDirection.value = resourceSortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    resourceSortKey.value = key
    resourceSortDirection.value = 'desc'
  }
}

function sortIcon(key: ResourceSortKey) {
  if (resourceSortKey.value !== key) return 'fas fa-sort'
  return resourceSortDirection.value === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'
}
function showTooltip(e:MouseEvent,title:string,value:string,detail=''){tooltip.value={visible:true,x:e.clientX,y:e.clientY,title,value,detail}}
function moveTooltip(e:MouseEvent){tooltip.value.x=e.clientX;tooltip.value.y=e.clientY}
function hideTooltip(){tooltip.value.visible=false}
const exportError = ref('')
const exportOptions = computed<ExportOption[]>(() => [
  SUMMARY_OPTION,
  { ...DETAILS_OPTION, description: 'One row per resource in the table, with its filters' },
  {
    kind: 'daily',
    label: 'Daily usage by resource',
    description: 'Clicks and unique users per resource per day',
    disabled: !data.resourceDaily,
  },
])
const latestClickDay = computed(() =>
  data.dailyClicks.reduce((latest, point) => (point.label > latest ? point.label : latest), ''),
)

function resourcesSummary() {
  const comparison = resourceYearComparison.value
  const rows: SummaryRow[] = [
    figure('Resources', 'Total clicks', data.totalClicks, 'clicks'),
    figure('Resources', 'Unique users', data.uniqueUsers, 'users'),
    figure('Resources', 'Resources used', data.activeResources, 'resources'),
    figure('Resources', 'Most used resource', data.mostUsedResource),
    figure('Resources', `Clicks in ${comparison.year}`, comparison.current, 'clicks'),
    figure('Resources', `Clicks in ${comparison.previousYear}`, comparison.previous, 'clicks'),
    ...data.byType.map((item) => figure('Clicks by resource type', item.label, item.value, 'clicks')),
    ...filteredDailyClicks.value.map((point) => figure('Clicks per day', point.label, point.clicks, 'clicks')),
    ...sortedResources.value.flatMap((resource) => [
      figure('Clicks by resource', resource.name, resource.clicks, 'clicks'),
      figure('Unique users by resource', resource.name, resource.uniqueUsers, 'users'),
    ]),
  ]
  return {
    fileName: exportFileName('resources', 'summary', latestClickDay.value || 'all dates'),
    csv: summaryCsv({
      page: 'Resources',
      covers: 'All recorded resource clicks',
      filters: [
        ['Search', search.value.trim()],
        ['Audience', selectedAudienceRole.value],
        ['Clicks per day date filter', clicksDateQuery.value.trim()],
      ].filter(([, value]) => value && value !== 'all') as Array<[string, string]>,
      dataAsOf: latestClickDay.value || null,
      unavailable: sourceLabels(unavailableSources.value),
    }, rows),
  }
}

function resourcesDetails() {
  const usage = sourceAvailable('resourceAnalytics')
  return {
    fileName: exportFileName('resources', 'details', latestClickDay.value || 'all dates'),
    csv: detailsCsv(
      ['Resource ID', 'Resource', 'Type', 'Audiences', 'Clicks', 'Unique Users'],
      sortedResources.value.map((resource) => [
        resource.id,
        resource.name,
        resource.type,
        resource.roles.join('; '),
        usage ? resource.clicks : null,
        usage ? resource.uniqueUsers : null,
      ]),
    ),
  }
}

function resourcesDaily() {
  const rows = [...(data.resourceDaily ?? [])]
    .sort((a, b) => a.date.localeCompare(b.date) || a.name.localeCompare(b.name))
    .map((row) => [row.date, row.resourceId, row.name, row.clicks, row.uniqueUsers])
  return {
    fileName: exportFileName('resources', 'daily-usage', latestClickDay.value || 'all dates'),
    // Unique users are counted per day, so they do not add up across days.
    csv: detailsCsv(['Date (UTC)', 'Resource ID', 'Resource', 'Clicks', 'Unique Users That Day'], rows),
  }
}

function exportCsv(kind: ExportKind) {
  const build = kind === 'summary' ? resourcesSummary : kind === 'daily' ? resourcesDaily : resourcesDetails
  exportError.value = runExport(build)
}
</script>

<style scoped>
.resources-analytics-page {
  min-width: 0;
  padding: 32px 40px 44px;
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
  gap: 8px;
  margin-bottom: 18px;
  color: #59706e;
  font-size: 14px;
}

.breadcrumb a {
  color: inherit;
  text-decoration: none;
}

.title-line {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

h1 {
  margin: 0;
  color: #163f3c;
  font-size: 36px;
  line-height: 1.15;
  font-weight: 800;
}

.heading-copy > p {
  margin: 8px 0 0;
  color: #617572;
  font-size: 16px;
}

.demo-badge {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  padding: 0 10px;
  border: 1px solid #bad7b8;
  border-radius: 999px;
  background: #f1e5a6;
  font-size: 12px;
  font-weight: 700;
}

.export-button {
  display: inline-flex;
  width: 142px;
  height: 46px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid #9fd8c7;
  border-radius: 12px;
  background: #fff;
  color: #017151;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.kpi-card,
.analytics-card {
  border: 1px solid #d7e3df;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 20px rgba(23, 66, 67, 0.04);
}

.kpi-card {
  display: flex;
  min-height: 132px;
  align-items: flex-start;
  gap: 16px;
  padding: 18px;
}

.kpi-icon {
  display: grid;
  width: 52px;
  height: 52px;
  flex: 0 0 52px;
  place-items: center;
  border-radius: 14px;
  background: #e4f0e2;
  color: #017151;
  font-size: 20px;
}

.kpi-label {
  display: block;
  color: #465b57;
  font-size: 13px;
  font-weight: 700;
}

.kpi-card strong {
  display: block;
  margin-top: 5px;
  color: #123f3c;
  font-size: 28px;
  line-height: 1.05;
}

.kpi-card small {
  display: block;
  margin-top: 8px;
  color: #6c7c78;
  font-size: 12px;
}

.kpi-card .resource-name {
  font-size: 20px;
}

.analytics-grid {
  display: grid;
  gap: 18px;
  margin-bottom: 18px;
}

.top-grid {
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.75fr);
}

.analytics-card {
  padding: 20px;
}

.analytics-card h2 {
  margin: 0;
  font-size: 20px;
  color: #174243;
}

.chart-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.chart-range-control {
  position: relative;
  flex: 0 0 auto;
}

.chart-range-control i {
  position: absolute;
  top: 50%;
  left: 13px;
  color: #59706e;
  font-size: 12px;
  pointer-events: none;
  transform: translateY(-50%);
}

.chart-range-control input {
  width: 220px;
  height: 40px;
  padding: 0 12px 0 34px;
  border: 1px solid #bad7b8;
  border-radius: 10px;
  background: #ffffff;
  color: #174243;
  font-size: 13px;
  font-weight: 600;
}

.chart-range-control input::placeholder {
  color: #72837f;
  font-weight: 500;
}

.card-subtitle {
  margin: 5px 0 16px;
  color: #6c7c78;
  font-size: 13px;
}

.chart-with-y-axis {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 8px;
}

.y-axis {
  display: flex;
  height: 180px;
  margin-top: 18px;
  flex-direction: column;
  justify-content: space-between;
  padding: 0;
  color: #6c7c78;
  font-size: 11px;
  text-align: right;
}

.y-axis span {
  line-height: 0;
}

.resource-chart {
  position: relative;
  height: 230px;
}

.chart-empty {
  position: absolute;
  inset: 18px 0 32px;
  display: grid;
  place-items: center;
  color: #6c7c78;
  font-size: 13px;
}

.grid-lines {
  position: absolute;
  inset: 18px 0 32px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  pointer-events: none;
}

.grid-lines span {
  border-top: 1px solid #e3ebe8;
}

.bars {
  position: absolute;
  inset: 0;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(76px, 1fr);
  grid-template-rows: 214px;
  align-items: start;
  gap: 14px;
  padding: 0 12px 16px;
  box-sizing: border-box;
  overflow-x: auto;
  overflow-y: hidden;
}

.bar-column {
  display: grid;
  height: 214px;
  grid-template-rows: 18px 180px 16px;
  align-items: end;
  text-align: center;
  color: #5f716d;
  font-size: 10px;
}

.bar-column strong {
  font-size: 10px;
  font-weight: 600;
}

.bar-column > span {
  white-space: nowrap;
}

.bar-track {
  display: flex;
  width: 100%;
  height: 180px;
  align-items: flex-end;
  justify-content: center;
}

.bar-fill {
  width: 24px;
  border-radius: 5px 5px 0 0;
  background: #5ea99e;
  cursor: pointer;
}

.axis-title {
  margin-top: 6px;
  color: #667873;
  font-size: 11px;
  text-align: center;
}

.type-list {
  display: grid;
  gap: 18px;
  margin-top: 28px;

  max-height: 220px;
  overflow-y: auto;
  padding-right: 8px;
}

.type-row{
    display:grid;
    grid-template-columns:92px 1fr 54px;
    gap:12px;
    align-items:center;
    font-size:12px
}

.type-track {
  height: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: #e8efec;
}

.type-track i {
  display: block;
  height: 100%;
  border-radius: 999px;
}

.type-row strong {
  text-align: right;
}

.table-card {
  margin-bottom: 18px;
}

.table-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 12px;
}

.table-heading input {
  width: 260px;
  height: 40px;
  padding: 0 12px;
  border: 1px solid #bad7b8;
  border-radius: 10px;
  color: #174243;
}

.table-wrap {
  overflow: auto;
  border: 1px solid #e0e8e5;
  border-radius: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th {
  padding: 12px;
  background: #f0f4f2;
  color: #174243;
  text-align: left;
}

td {
  padding: 12px;
  border-top: 1px solid #e4ebe8;
  color: #536762;
}

tbody tr:hover td {
  background: rgba(186, 215, 184, 0.35);
}

@media (max-width: 1000px) {
  .kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .top-grid {
    grid-template-columns: 1fr;
  }

  .page-heading {
    grid-template-columns: 1fr;
  }
}

/* Keep Resource Usage Details column widths fixed */
.resources-analytics-page .resource-usage-table {
  width: 100%;
  table-layout: fixed;
}

.resources-analytics-page .resource-usage-table .col-resource {
  width: 32%;
}

.resources-analytics-page .resource-usage-table .col-type {
  width: 14%;
}

.resources-analytics-page .resource-usage-table .col-clicks {
  width: 14%;
}

.resources-analytics-page .resource-usage-table .col-unique-users {
  width: 20%;
}

.resources-analytics-page .resource-usage-table th,
.resources-analytics-page .resource-usage-table td {
  box-sizing: border-box;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Requested table hover colour */
.table-wrap tbody tr:hover,
.table-wrap tbody tr:hover td {
  background: rgba(186, 215, 184, 0.35) !important;
}

.sort-header-button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #174243;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.sort-header-button i {
  min-width: 12px;
  color: #5EA99E;
  font-size: 11px;
}

.sort-header-button:hover {
  color: #017151;
}

/* Match Email Monitoring page header and card rhythm */
.resources-analytics-page {
  min-width: 0;
  padding: 32px 40px 44px;
  background: #f7faf9;
  color: #174243;
}

.resources-analytics-page .page-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  margin-bottom: 22px;
}

.resources-analytics-page .breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
  color: #59706e;
  font-size: 14px;
}

.resources-analytics-page .title-line {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.resources-analytics-page h1 {
  margin: 0;
  color: #163f3c;
  font-size: 36px;
  line-height: 1.15;
  font-weight: 800;
}

.resources-analytics-page .heading-copy > p {
  margin: 8px 0 0;
  color: #617572;
  font-size: 16px;
}

.resources-analytics-page .demo-badge {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  padding: 0 10px;
  border: 1px solid #BAD7B8;
  border-radius: 999px;
  background: #F1E5A6;
  color: #174243;
  font-size: 12px;
  font-weight: 700;
}

.resources-analytics-page .page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  align-self: start;
  margin: 0;
}

.resources-analytics-page .export-button {
  display: inline-flex;
  width: 142px;
  height: 46px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  border: 1px solid #9fd8c7;
  border-radius: 12px;
  background: #ffffff;
  color: #017151;
  font-size: 14px;
  font-weight: 700;
}

/* Exact header/layout alignment copied from Email Monitoring */
.resources-analytics-page {
  min-height: 100%;
  min-width: 0;
  padding: 28px 32px 40px !important;
  background: #f7faf9;
  color: #174243;
}

.resources-analytics-page .page-heading {
  display: grid !important;
  grid-template-columns: minmax(0, 1fr) auto !important;
  align-items: start !important;
  gap: 24px !important;
  margin-bottom: 22px !important;
}

.resources-analytics-page .heading-copy {
  min-width: 0;
}

.resources-analytics-page .breadcrumb {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  margin-bottom: 18px !important;
  color: #59706e !important;
  font-size: 14px !important;
}

.resources-analytics-page .breadcrumb a {
  color: #59706e !important;
  text-decoration: none !important;
}

.resources-analytics-page .title-line {
  display: flex !important;
  align-items: center !important;
  gap: 12px !important;
  flex-wrap: wrap;
}

.resources-analytics-page .title-line h1,
.resources-analytics-page .page-heading h1 {
  margin: 0 !important;
  color: #163f3c !important;
  font-size: 36px !important;
  line-height: 1.15 !important;
  font-weight: 800 !important;
}

.resources-analytics-page .heading-copy > p {
  margin: 8px 0 0 !important;
  color: #617572 !important;
  font-size: 16px !important;
}

.resources-analytics-page .demo-badge {
  display: inline-flex !important;
  align-items: center !important;
  min-height: 30px !important;
  padding: 0 10px !important;
  border: 1px solid #BAD7B8 !important;
  border-radius: 999px !important;
  background: #F1E5A6 !important;
  color: #174243 !important;
  font-size: 12px !important;
  font-weight: 700 !important;
}

.resources-analytics-page .page-actions {
  display: flex !important;
  align-items: center !important;
  gap: 12px !important;
  align-self: start !important;
  margin: 0 !important;
}

.resources-analytics-page .export-button {
  display: inline-flex !important;
  width: 142px !important;
  height: 46px !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 8px !important;
  padding: 0 16px !important;
  border: 1px solid #9fd8c7 !important;
  border-radius: 12px !important;
  background: #ffffff !important;
  color: #017151 !important;
  font-size: 14px !important;
  font-weight: 700 !important;
  cursor: pointer;
}

.resources-analytics-page .resource-table-filters {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: nowrap;
}

.resources-analytics-page .resource-table-filters select,
.resources-analytics-page .resource-table-filters input {
  height: 44px;
  border: 1px solid #bad7b8;
  border-radius: 12px;
  background: #ffffff;
  color: #174243;
  font-size: 14px;
}

.resources-analytics-page .resource-table-filters select {
  width: 190px;
  padding: 0 38px 0 14px;
  font-weight: 600;
  cursor: pointer;
}

.resources-analytics-page .resource-table-filters input {
  width: 260px;
  padding: 0 14px;
}

@media (max-width: 900px) {
  .resources-analytics-page .table-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .resources-analytics-page .resource-table-filters {
    width: 100%;
  }

  .resources-analytics-page .resource-table-filters select,
  .resources-analytics-page .resource-table-filters input {
    flex: 1 1 0;
    width: auto;
  }
}

/* Large resource datasets stay inside a fixed-height table card */
.resources-analytics-page .table-card .table-wrap {
  max-height: 430px;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}

.resources-analytics-page .table-card thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f0f4f2;
}

.resources-analytics-page .breadcrumb a:hover {
  color: #017151 !important;
  text-decoration: underline !important;
}

/* The resource summary has five cards; keep them in one fixed desktop row. */
.resources-analytics-page .kpi-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr)) !important;
  gap: 12px !important;
}

.resources-analytics-page .kpi-card {
  min-width: 0;
  min-height: 0;
  padding: 16px 14px;
  gap: 12px;
}

.resources-analytics-page .kpi-card > div:not(.kpi-icon) {
  flex: 1 1 auto;
  min-width: 0;
}

.resources-analytics-page .kpi-card > div:not(.kpi-icon) > strong:not(.resource-name) {
  width: 100%;
  text-align: left;
}

.resources-analytics-page .kpi-card .analytics-value-row {
  width: 100%;
  justify-content: flex-start;
}

/* Use identical title/value/helper tracks across every resource KPI, including
   the longer resource-name card. */
.resources-analytics-page .kpi-grid .kpi-card > div:not(.kpi-icon) {
  display: grid !important;
  min-width: 0 !important;
  flex: 1 1 0% !important;
  align-self: stretch;
  grid-template-rows: 34px auto 34px !important;
  align-content: start;
}

.resources-analytics-page .kpi-grid .kpi-card .kpi-label {
  display: flex !important;
  grid-row: 1;
  align-items: flex-start;
  margin: 0 !important;
}

.resources-analytics-page .kpi-grid .kpi-card > div:not(.kpi-icon) > :is(strong, .analytics-value-row) {
  grid-row: 2;
  align-self: center;
}

.resources-analytics-page .kpi-grid .kpi-card > div:not(.kpi-icon) > small {
  grid-row: 3;
  align-self: start;
  margin: 0 !important;
}

.resources-analytics-page .kpi-card .resource-name {
  font-size: 14px !important;
  line-height: 16px !important;
  overflow-wrap: anywhere;
}

@media (max-width: 1279px) {
  .resources-analytics-page .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  }
}

@media (max-width: 720px) {
  .resources-analytics-page .kpi-grid {
    grid-template-columns: minmax(0, 1fr) !important;
  }
}

</style>
