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
        <button
          type="button"
          class="analytics-refresh-button"
          :disabled="isLoading"
          @click="refreshAnalytics"
        >
          <i class="fas fa-rotate-right"></i>
          Refresh
        </button>
        <button type="button" class="export-button" :disabled="exportDisabled" @click="exportCsv"><i class="fas fa-download"></i> Export CSV</button>
      </div>
    </div>

    <AnalyticsRefreshStatus :updated-at="lastUpdated" :refresh-failed="refreshFailed" />

    <AnalyticsDataState
      :loading="isLoading"
      :error="loadError"
      :empty="isEmpty"
      empty-message="No resources are available in the current database. Generate or load a dataset, then refresh this page."
      @retry="refreshAnalytics"
    >
    <section class="kpi-grid">
      <article class="kpi-card"><div class="kpi-icon"><i class="fas fa-arrow-pointer"></i></div><div><span class="kpi-label">Resource Clicks</span><strong>{{ data.totalClicks.toLocaleString() }}</strong><small>Total recorded clicks</small></div></article>
      <article class="kpi-card"><div class="kpi-icon"><i class="fas fa-users"></i></div><div><span class="kpi-label">Unique Users</span><strong>{{ data.uniqueUsers }}</strong><small>Users who accessed resources</small></div></article>
      <article class="kpi-card"><div class="kpi-icon"><i class="fas fa-book"></i></div><div><span class="kpi-label">Active Resources</span><strong>{{ data.activeResources }}</strong><small>Resources with recorded access</small></div></article>
      <article class="kpi-card"><div class="kpi-icon"><i class="fas fa-book-open"></i></div><div><span class="kpi-label">Most Used Resource</span><strong class="resource-name">{{ data.mostUsedResource }}</strong><small>Highest click count</small></div></article>
    </section>

    <section class="analytics-grid top-grid">
      <article class="analytics-card">
        <h2>Resource Clicks Over Time</h2>
        <p class="card-subtitle">Daily clicks recorded in the current database period.</p>
        <div class="chart-with-y-axis">
          <div class="y-axis"><span v-for="tick in yTicks" :key="tick">{{ tick }}</span></div>
          <div class="resource-chart">
            <div class="grid-lines"><span v-for="n in 5" :key="n"></span></div>
            <div class="bars">
              <div v-for="point in data.dailyClicks" :key="point.label" class="bar-column">
                <strong>{{ point.clicks }}</strong>
                <div class="bar-track"><div class="bar-fill" :style="{ height: `${(point.clicks / dailyAxisMax) * 100}%` }" @mouseenter="showTooltip($event, point.label, `${point.clicks} clicks`, 'Resource activity')" @mousemove="moveTooltip" @mouseleave="hideTooltip"></div></div>
                <span>{{ point.label }}</span>
              </div>
            </div>
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
          <select v-model="selectedAudienceRole" aria-label="Filter resources by configured audience">
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
                <button type="button" class="sort-header-button" @click="toggleSort('clicks')">
                  Clicks
                  <i :class="sortIcon('clicks')" aria-hidden="true"></i>
                </button>
              </th>
              <th>
                <button type="button" class="sort-header-button" @click="toggleSort('uniqueUsers')">
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
              <td>{{ item.clicks }}</td>
              <td>{{ item.uniqueUsers }}</td>
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
import AnalyticsRefreshStatus from '@/components/analytics/AnalyticsRefreshStatus.vue'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { computed, onMounted, reactive, ref } from 'vue'
import AnalyticsDataState from '@/components/analytics/AnalyticsDataState.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import {
  buildResourcesAnalytics,
  loadResourcesAnalyticsBundle,
  type ResourceAnalyticsBundle,
} from '@/utils/liveAnalyticsData'

const data = reactive({
  totalClicks: 0, uniqueUsers: 0, activeResources: 0, mostUsedResource: '—',
  dailyClicks: [] as Array<{ label: string; clicks: number }>,
  resources: [] as Array<{ id: number; name: string; clicks: number; uniqueUsers: number; type: string; roles: Array<'Student' | 'Mentor' | 'Supervisor'> }>,
  byType: [] as Array<{ label: string; value: number; color: string }>,
})
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
    Object.assign(data, buildResourcesAnalytics(bundle))
    isEmpty.value = resourceBundleIsEmpty(bundle)
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
type ResourceSortKey = 'clicks' | 'uniqueUsers'
const resourceSortKey = ref<ResourceSortKey | null>(null)
const resourceSortDirection = ref<'asc' | 'desc'>('desc')
const tooltip = ref({ visible:false,x:0,y:0,title:'',value:'',detail:'' })
const maxDailyClicks = computed(() => Math.max(...data.dailyClicks.map(p => p.clicks),1))
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
function exportCsv() {
  const rows = [
    ['Resource', 'Type', 'Clicks', 'Unique Users'],
    ...sortedResources.value.map((resource) => [
      resource.name, resource.type, resource.clicks, resource.uniqueUsers,
    ]),
  ]
  const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'resource-analytics.csv'
  anchor.click()
  URL.revokeObjectURL(url)
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

</style>
