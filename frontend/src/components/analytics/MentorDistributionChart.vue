<template>
  <div class="distribution" :class="kind">
    <p v-if="!total" class="empty">No mentors in this snapshot.</p>
    <template v-else>
      <div v-if="kind === 'donut'" class="ring">
        <svg viewBox="0 0 160 160" role="group" :aria-label="summary">
          <circle cx="80" cy="80" r="62" fill="none" stroke="var(--analytics-ui-soft, var(--btf-track))" stroke-width="22" />
          <circle
            v-for="(item, index) in segments"
            :key="item.label"
            class="donut-segment"
            :tabindex="item.value > 0 ? 0 : -1"
            role="img"
            :aria-label="`${item.label}: ${item.value} mentors, ${percent(item.value, total)}%`"
            @mouseenter="show($event, item)"
            @mousemove="show($event, item)"
            @mouseleave="hide"
            @focus="show($event, item)"
            @blur="hide"
            @keydown.esc="hide"
            @click="show($event, item)"
            cx="80"
            cy="80"
            r="62"
            fill="none"
            :stroke="color(index)"
            stroke-width="22"
            pathLength="100"
            :stroke-dasharray="`${item.share} ${100 - item.share}`"
            :stroke-dashoffset="-item.offset"
            transform="rotate(-90 80 80)"
          />
        </svg>
        <div class="ring-center">
          <strong>{{ total }}</strong
          ><span>Total mentors</span>
        </div>
      </div>
      <div class="marks" :class="{ vertical: kind === 'vertical' }" :aria-label="summary">
        <button
          v-for="(item, index) in items"
          :key="item.label"
          type="button"
          class="mark"
          :aria-label="`${item.label}: ${item.value} mentors, ${percent(item.value, total)}%`"
          @mouseenter="show($event, item)"
          @mousemove="show($event, item)"
          @mouseleave="hide"
          @focus="show($event, item)"
          @blur="hide"
          @keydown.esc="hide"
          @click="show($event, item)"
        >
          <template v-if="kind === 'vertical'">
            <strong>{{ item.value }}</strong>
            <span class="column-track"
              ><span
                :style="{ height: `${(item.value / maximum) * 100}%`, background: color(0) }"
              ></span
            ></span>
            <span class="label">{{ item.label }}</span>
          </template>
          <template v-else>
            <span class="label"
              ><i v-if="kind === 'donut'" :style="{ background: color(index) }"></i
              >{{ item.label }}</span
            >
            <span v-if="kind === 'horizontal'" class="track"
              ><span
                :style="{ width: `${(item.value / maximum) * 100}%`, background: color(index) }"
              ></span
            ></span>
            <strong
              >{{ item.value }} <small>({{ percent(item.value, total) }}%)</small></strong
            >
          </template>
        </button>
      </div>
      <p v-if="kind !== 'donut'" class="caption">
        {{ kind === 'vertical' ? 'Number of mentors by ' + axis : 'Number of mentors' }}
      </p>
    </template>
    <ChartTooltip v-bind="tooltip" />
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import { BTF_CHART_SERIES } from '@/constants/btfTheme'
import { percent, type MetricBucket } from '@/utils/mentorsAnalytics'
const props = defineProps<{
  items: MetricBucket[]
  kind: 'donut' | 'horizontal' | 'vertical'
  axis?: string
}>()
const palette = BTF_CHART_SERIES
const color = (index: number) => palette[index % palette.length]
const total = computed(() => props.items.reduce((sum, item) => sum + item.value, 0))
const maximum = computed(() => Math.max(1, ...props.items.map((item) => item.value)))
const summary = computed(() =>
  props.items.map((item) => `${item.label}: ${item.value} mentors`).join('; '),
)
const segments = computed(() => {
  let offset = 0
  return props.items.map((item, index) => {
    const share = total.value
      ? (index === props.items.length - 1 ? Math.max(0, 100 - offset) : (item.value / total.value) * 100)
      : 0
    const segment = { ...item, share, offset }
    offset += share
    return segment
  })
})
const tooltip = ref({ visible: false, x: 0, y: 0, title: '', value: '', detail: '' })
function show(event: Event, item: MetricBucket) {
  const rect = (event.currentTarget as HTMLElement | SVGElement).getBoundingClientRect()
  const mouse = event instanceof MouseEvent ? event : null
  tooltip.value = {
    visible: true,
    x: mouse?.clientX ?? rect.left + rect.width / 2,
    y: mouse?.clientY ?? rect.top + rect.height / 2,
    title: item.label,
    value: `${item.value} mentors`,
    detail: `${percent(item.value, total.value)}% of the snapshot`,
  }
}
function hide() {
  tooltip.value.visible = false
}
watch(() => props.items, hide)
onMounted(() => {
  window.addEventListener('scroll', hide, true)
  window.addEventListener('resize', hide)
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', hide, true)
  window.removeEventListener('resize', hide)
})
</script>
<style scoped>
.distribution {
  min-width: 0;
}
.donut {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 16px;
  min-height: 200px;
}
.ring {
  position: relative;
  isolation: isolate;
  width: 150px;
  flex: 0 0 150px;
}
.ring svg {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
}
.donut-segment {
  pointer-events: visiblePainted;
  cursor: default;
}
.donut-segment:focus-visible {
  outline: 2px solid var(--btf-dark-green);
  outline-offset: 3px;
}
.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  pointer-events: none;
  z-index: 2;
  margin: auto;
  width: 104px;
  height: 104px;
  border-radius: 50%;
  background: var(--analytics-ui-surface, #fff);
}
.ring-center strong {
  font-size: 26px;
  color: var(--analytics-ui-text, var(--btf-teal));
}
.ring-center span,
.caption {
  font-size: 11px;
  color: var(--analytics-ui-muted, var(--btf-muted));
}
.marks {
  display: grid;
  gap: 10px;
  flex: 1;
  min-width: 155px;
}
.mark {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 0;
  padding: 5px 2px;
  background: transparent;
  color: var(--analytics-ui-text, var(--btf-teal));
  font: inherit;
  font-size: 12px;
  text-align: left;
  border-radius: 4px;
  cursor: default;
  min-width: 0;
}
.mark:focus-visible {
  outline: 2px solid var(--btf-dark-green);
  outline-offset: 3px;
}
.mark:hover {
  background: var(--analytics-ui-page, var(--btf-surface));
}
.label {
  display: flex;
  gap: 7px;
  align-items: center;
}
.label i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}
.mark strong {
  white-space: nowrap;
  font-size: 12px;
}
.mark small {
  font-size: 10px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  font-weight: normal;
}
.horizontal .mark {
  display: grid;
  grid-template-columns: 100px minmax(25px, 1fr) 72px;
}
.horizontal {
  padding-top: 12px;
}
.track {
  height: 12px;
  background: var(--analytics-ui-soft, var(--btf-track));
  border-radius: 3px;
  overflow: hidden;
}
.track span {
  display: block;
  height: 100%;
}
.marks.vertical {
  display: flex;
  gap: 8px;
  align-items: stretch;
}
.marks.vertical .mark {
  flex: 1;
  display: grid;
  grid-template-rows: 20px 128px 32px;
  text-align: center;
  gap: 6px;
}
.column-track {
  height: 128px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  border-bottom: 1px solid var(--analytics-ui-border, var(--btf-border));
}
.column-track span {
  width: 65%;
  max-width: 42px;
  border-radius: 3px 3px 0 0;
}
.marks.vertical .label {
  justify-content: center;
  font-size: 10px;
}
.caption {
  text-align: center;
  margin: 10px 0 0;
}
.empty {
  padding: 48px 8px;
  color: var(--analytics-ui-muted, var(--btf-muted));
  text-align: center;
}
</style>
