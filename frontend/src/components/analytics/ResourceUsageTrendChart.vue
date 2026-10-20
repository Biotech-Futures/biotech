<template>
  <div class="resource-trend">
    <div class="resource-trend-controls">
      <div class="resource-trend-metric" role="group" aria-label="Chart metric">
        <button
          v-for="option in metricOptions"
          :key="option.value"
          type="button"
          :class="{ active: metric === option.value }"
          :aria-pressed="metric === option.value"
          @click="metric = option.value"
        >
          {{ option.label }}
        </button>
      </div>
      <div class="resource-trend-view-controls">
        <span class="resource-trend-series-actions">
          <button type="button" @click="showTop">Top {{ DEFAULT_VISIBLE }}</button>
          <button type="button" @click="visibleIds = new Set(seriesResources.map((resource) => resource.id))">All</button>
          <button type="button" @click="visibleIds = new Set()">None</button>
        </span>
        <select v-model.number="windowDays" aria-label="Resource trend period">
          <option v-for="option in windowOptions" :key="option" :value="option">Last {{ option }} days</option>
        </select>
      </div>
    </div>

    <div class="resource-trend-series" aria-label="Resources shown in the chart">
      <button
        v-for="resource in seriesResources"
        :key="resource.id"
        type="button"
        class="resource-trend-chip"
        :class="{ active: visibleIds.has(resource.id) }"
        :aria-pressed="visibleIds.has(resource.id)"
        :title="`${resource.name} — ${styleFor(resource.id).label} line`"
        @click="toggleSeries(resource.id)"
      >
        <svg class="resource-trend-swatch" viewBox="0 0 26 8" aria-hidden="true">
          <line
            x1="1"
            x2="25"
            y1="4"
            y2="4"
            :stroke="styleFor(resource.id).color"
            :stroke-dasharray="styleFor(resource.id).dash || undefined"
          />
        </svg>
        <span>{{ resource.name }}</span>
      </button>
    </div>

    <p v-if="!seriesResources.length" class="resource-trend-empty">No resource clicks have been recorded yet.</p>
    <div v-else ref="plot" class="resource-trend-plot" @mouseleave="hoverIndex = null">
      <svg
        :viewBox="`0 0 ${size.width} ${size.height}`"
        :width="size.width"
        :height="size.height"
        role="img"
        :aria-label="`${metricLabel} per day by resource`"
        @mousemove="onHover"
      >
        <g v-for="tick in ticks" :key="`tick-${tick}`">
          <line :x1="PAD.left" :x2="size.width - PAD.right" :y1="y(tick)" :y2="y(tick)" class="resource-trend-grid" />
          <text :x="PAD.left - 8" :y="y(tick)" text-anchor="end" class="resource-trend-axis">{{ tick }}</text>
        </g>
        <text
          v-for="label in xLabels"
          :key="`x-${label.index}`"
          :x="x(label.index)"
          :y="size.height - 8"
          text-anchor="middle"
          class="resource-trend-axis resource-trend-x-axis"
        >{{ label.text }}</text>

        <line
          v-if="hoverIndex !== null"
          :x1="x(hoverIndex)"
          :x2="x(hoverIndex)"
          :y1="PAD.top"
          :y2="baseline"
          class="resource-trend-hover-line"
        />
        <polyline
          v-for="series in visibleSeries"
          :key="series.id"
          :points="series.values.map((value, index) => `${x(index)},${y(value)}`).join(' ')"
          :stroke="series.color"
          :stroke-dasharray="series.dash || undefined"
          class="resource-trend-line"
        />
        <template v-if="hoverIndex !== null">
          <circle
            v-for="series in visibleSeries"
            :key="`dot-${series.id}`"
            :cx="x(hoverIndex)"
            :cy="y(series.values[hoverIndex] ?? 0)"
            r="4"
            :fill="series.color"
          />
        </template>
      </svg>

      <div
        v-if="hoverIndex !== null && visibleSeries.length"
        class="resource-trend-readout"
        :style="readoutStyle"
        role="status"
      >
        <div class="resource-trend-readout-header">
          <strong>{{ formatDay(days[hoverIndex]!) }}</strong>
          <small>{{ metricLabel }}</small>
        </div>
        <div class="resource-trend-readout-body">
          <div v-for="series in hoverRows" :key="series.id" class="resource-trend-readout-row" :title="series.name">
            <span class="resource-trend-readout-name">{{ series.name }}</span>
            <span class="resource-trend-readout-value">
              <b>{{ series.value }}</b>
              <svg class="resource-trend-swatch" viewBox="0 0 30 8" aria-hidden="true">
                <line
                  x1="1"
                  x2="29"
                  y1="4"
                  y2="4"
                  :stroke="series.color"
                  :stroke-dasharray="series.dash || undefined"
                />
              </svg>
            </span>
          </div>
        </div>
      </div>
    </div>
    <p class="resource-trend-note">
      {{ metric === 'clicks' ? 'Clicks per day for each selected resource.' : 'Distinct users per day for each selected resource; daily counts are not added together because the same person can return on several days.' }}
      {{ periodLabel }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ResourceDailyUsage } from '@/types/analytics'
import { BTF_COLORS } from '@/constants/btfTheme'

const props = defineProps<{ rows: ResourceDailyUsage[] }>()

const DEFAULT_VISIBLE = 6
const PAD = { top: 18, right: 16, bottom: 30, left: 42 }
const BTF_PALETTE = [
  BTF_COLORS.darkGreen,
  BTF_COLORS.teal,
  BTF_COLORS.airForceBlue,
  BTF_COLORS.mintGreen,
  BTF_COLORS.lightGreen,
  BTF_COLORS.yellow,
]
const FALLBACK_PALETTE = ['#8a5a9e', '#d9734e', '#2e86ab', '#7a9e3e', '#b0476a', '#5c6b73']
const LINE_STYLES = [
  { label: 'Solid', dash: '' },
  { label: 'Dashed', dash: '10 6' },
  { label: 'Dotted', dash: '2 6' },
  { label: 'Dash-dot', dash: '10 5 2 5' },
  { label: 'Long dashed', dash: '16 6' },
  { label: 'Dash-dot-dot', dash: '14 5 2 5 2 5' },
] as const
const DAY = 86_400_000

const metricOptions = [
  { value: 'clicks', label: 'Clicks' },
  { value: 'uniqueUsers', label: 'Unique users' },
] as const
const windowOptions = [30, 90, 365]

const metric = ref<'clicks' | 'uniqueUsers'>('clicks')
const windowDays = ref(30)
const visibleIds = ref(new Set<number>())
const hoverIndex = ref<number | null>(null)
const hoverY = ref(PAD.top)

// The window ends on the latest recorded day so older datasets still show data.
const endDay = computed(() => props.rows.reduce((latest, row) => (row.date > latest ? row.date : latest), ''))
const days = computed(() => {
  if (!endDay.value) return []
  const end = Date.parse(`${endDay.value}T00:00:00Z`)
  return Array.from({ length: windowDays.value }, (_, index) =>
    new Date(end - (windowDays.value - 1 - index) * DAY).toISOString().slice(0, 10))
})
const periodLabel = computed(() => {
  const list = days.value
  return list.length ? `${formatDay(list[0]!)} – ${formatDay(list[list.length - 1]!)} (UTC).` : ''
})

// Resources ordered by clicks in the selected period, busiest first.
const seriesResources = computed(() => {
  const start = days.value[0] ?? ''
  const totals = new Map<number, { id: number; name: string; clicks: number }>()
  for (const row of props.rows) {
    const entry = totals.get(row.resourceId) ?? { id: row.resourceId, name: row.name, clicks: 0 }
    if (row.date >= start) entry.clicks += row.clicks
    totals.set(row.resourceId, entry)
  }
  return [...totals.values()].sort((a, b) => b.clicks - a.clicks || a.name.localeCompare(b.name))
})

// Stable colour-and-line combinations follow overall busiest order. The
// diagonal sequence makes adjacent resources differ by both colour and line
// style while still exhausting every BTF combination before any fallback.
const styleById = computed(() => {
  const overall = new Map<number, number>()
  for (const row of props.rows) overall.set(row.resourceId, (overall.get(row.resourceId) ?? 0) + row.clicks)
  const ordered = [...overall.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0])
  const btfCombinations = BTF_PALETTE.length * LINE_STYLES.length
  return new Map(ordered.map(([id], index) => {
    if (index < btfCombinations) {
      const group = Math.floor(index / LINE_STYLES.length)
      const styleIndex = index % LINE_STYLES.length
      const colorIndex = (group + styleIndex) % BTF_PALETTE.length
      return [id, { color: BTF_PALETTE[colorIndex]!, ...LINE_STYLES[styleIndex]! }]
    }

    const fallbackIndex = index - btfCombinations
    const lineStyle = LINE_STYLES[Math.floor(fallbackIndex / FALLBACK_PALETTE.length) % LINE_STYLES.length]!
    return [id, { color: FALLBACK_PALETTE[fallbackIndex % FALLBACK_PALETTE.length]!, ...lineStyle }]
  }))
})
const styleFor = (id: number) => styleById.value.get(id) ?? { color: BTF_PALETTE[0]!, ...LINE_STYLES[0]! }

function showTop() {
  visibleIds.value = new Set(seriesResources.value.slice(0, DEFAULT_VISIBLE).map((resource) => resource.id))
}
function toggleSeries(id: number) {
  const next = new Set(visibleIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  visibleIds.value = next
}

// Start with the busiest resources selected; keep the user's choice afterwards.
let initialised = false
watch(seriesResources, (resources) => {
  if (initialised || !resources.length) return
  initialised = true
  showTop()
}, { immediate: true })

const visibleSeries = computed(() => {
  const index = new Map(days.value.map((day, position) => [day, position]))
  return seriesResources.value
    .filter((resource) => visibleIds.value.has(resource.id))
    .map((resource) => {
      const values = days.value.map(() => 0)
      for (const row of props.rows) {
        const position = row.resourceId === resource.id ? index.get(row.date) : undefined
        if (position !== undefined) values[position] = metric.value === 'clicks' ? row.clicks : row.uniqueUsers
      }
      return { id: resource.id, name: resource.name, ...styleFor(resource.id), values }
    })
})

const metricLabel = computed(() => (metric.value === 'clicks' ? 'Clicks' : 'Unique users'))
const maxValue = computed(() => Math.max(1, ...visibleSeries.value.flatMap((series) => series.values)))
const ticks = computed(() => {
  const step = Math.max(1, Math.ceil(maxValue.value / 4))
  return [4, 3, 2, 1, 0].map((multiple) => multiple * step)
})

// Drawn at the plot's real pixel size so text stays readable at any width.
const plot = ref<HTMLElement | null>(null)
const size = ref({ width: 800, height: 260 })
watch(plot, (element, _previous, onCleanup) => {
  if (!element || typeof ResizeObserver === 'undefined') return
  const observer = new ResizeObserver(([entry]) => {
    const width = Math.round(entry?.contentRect.width ?? 0)
    const height = Math.round(entry?.contentRect.height ?? 0)
    if (width > 0 && height > 0) size.value = { width, height }
  })
  observer.observe(element)
  onCleanup(() => observer.disconnect())
})
const baseline = computed(() => size.value.height - PAD.bottom)
function x(index: number) {
  const count = days.value.length
  const span = size.value.width - PAD.left - PAD.right
  return count <= 1 ? PAD.left + span / 2 : PAD.left + (index / (count - 1)) * span
}
function y(value: number) {
  const top = ticks.value[0] ?? 1
  return baseline.value - (value / top) * (baseline.value - PAD.top)
}
const xLabels = computed(() => {
  const count = days.value.length
  const latestIndex = count - 1
  return days.value
    .map((day, index) => ({ index, text: formatDay(day, false) }))
    .filter((label) => (latestIndex - label.index) % 7 === 0)
})

function onHover(event: MouseEvent) {
  const svg = event.currentTarget as SVGSVGElement
  const rect = svg.getBoundingClientRect()
  const scaleX = rect.width ? size.value.width / rect.width : 1
  const scaleY = rect.height ? size.value.height / rect.height : 1
  const pointer = (event.clientX - rect.left) * scaleX
  hoverY.value = (event.clientY - rect.top) * scaleY
  const count = days.value.length
  if (!count) return
  const span = size.value.width - PAD.left - PAD.right
  const position = Math.round(((pointer - PAD.left) / span) * (count - 1))
  hoverIndex.value = Math.min(count - 1, Math.max(0, position))
}
const hoverRows = computed(() => {
  const index = hoverIndex.value
  if (index === null) return []
  return visibleSeries.value
    .map((series) => ({
      id: series.id,
      name: series.name,
      color: series.color,
      dash: series.dash,
      value: series.values[index] ?? 0,
    }))
    .sort((a, b) => b.value - a.value)
})
const readoutStyle = computed(() => {
  const index = hoverIndex.value ?? 0
  const pointX = x(index)
  const tooltipWidth = Math.min(380, Math.max(0, size.value.width - 24))
  return {
    left: `${pointX - tooltipWidth / 2}px`,
    top: `${hoverY.value + 12}px`,
  }
})

function formatDay(day: string, withYear = true) {
  const date = new Date(`${day}T00:00:00Z`)
  return date.toLocaleDateString('en-AU', {
    day: 'numeric', month: 'short', ...(withYear ? { year: 'numeric' } : {}), timeZone: 'UTC',
  })
}
</script>

<style scoped>
.resource-trend {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.resource-trend-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.resource-trend-metric {
  display: inline-flex;
  padding: 3px;
  border: 1px solid #bad7b8;
  border-radius: 10px;
  background: #fff;
}

.resource-trend-metric button {
  padding: 6px 12px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #39687b;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.resource-trend-metric button.active {
  background: #017151;
  color: #fff;
}

.resource-trend-controls select {
  height: 36px;
  padding: 0 12px;
  border: 1px solid #bad7b8;
  border-radius: 9px;
  background-color: #fff;
  color: #017151;
  font-size: 13px;
  font-weight: 700;
}

.resource-trend-view-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.resource-trend-series {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  max-height: 84px;
  overflow-y: auto;
}

.resource-trend-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 220px;
  padding: 5px 10px;
  border: 1px solid #dbe6e3;
  border-radius: 999px;
  background: #f6f8f8;
  color: #7a8c88;
  font-size: 12px;
  cursor: pointer;
}

.resource-trend-swatch {
  flex: 0 0 auto;
  width: 26px;
  height: 8px;
  opacity: 0.35;
}

.resource-trend-swatch line {
  stroke-width: 3;
  stroke-linecap: round;
}

.resource-trend-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-trend-chip.active {
  border-color: #bad7b8;
  background: #fff;
  color: #174243;
  font-weight: 700;
}

.resource-trend-chip.active .resource-trend-swatch {
  opacity: 1;
}

.resource-trend-series-actions {
  display: inline-flex;
  gap: 4px;
}

.resource-trend-series-actions button {
  padding: 4px 8px;
  border: 0;
  background: transparent;
  color: #017151;
  font-size: 12px;
  font-weight: 700;
  text-decoration: underline;
  cursor: pointer;
}

.resource-trend-plot {
  position: relative;
  height: 280px;
}

.resource-trend-plot > svg {
  position: absolute;
  inset: 0;
  display: block;
  overflow: visible;
}

.resource-trend-grid {
  stroke: #edf1f0;
}

.resource-trend-axis {
  fill: #748683;
  font-size: 11px;
  dominant-baseline: middle;
}

.resource-trend-line {
  fill: none;
  stroke-width: 2.4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.resource-trend-hover-line {
  stroke: #9fbfb9;
  stroke-dasharray: 3 3;
}

.resource-trend-readout {
  position: absolute;
  z-index: 4;
  width: 380px;
  max-width: calc(100% - 24px);
  overflow: hidden;
  border: 1px solid #bad7bb;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(23, 66, 67, 0.18);
  color: #174243;
  font-size: 12px;
  pointer-events: none;
}

.resource-trend-readout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 14px;
  border-bottom: 1px solid #dbe6e3;
  background: #eef4f1;
}

.resource-trend-readout-header strong {
  color: #174243;
  font-size: 14px;
}

.resource-trend-readout-header small {
  color: #60726f;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.resource-trend-readout-body {
  display: grid;
  padding: 4px 0;
}

.resource-trend-readout-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 48px;
  align-items: center;
  gap: 14px;
  min-height: 42px;
  padding: 7px 14px;
}

.resource-trend-readout-row + .resource-trend-readout-row {
  border-top: 1px solid #edf1f0;
}

.resource-trend-readout-name {
  overflow: hidden;
  color: #314f4d;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-trend-readout-value {
  display: grid;
  justify-items: center;
  gap: 2px;
  width: 48px;
}

.resource-trend-readout-value b {
  color: #017151;
  font-size: 14px;
  text-align: center;
}

.resource-trend-readout-value .resource-trend-swatch {
  width: 30px;
  opacity: 1;
}

.resource-trend-note,
.resource-trend-empty {
  margin: 0;
  color: #60726f;
  font-size: 12px;
  line-height: 1.5;
}
</style>
