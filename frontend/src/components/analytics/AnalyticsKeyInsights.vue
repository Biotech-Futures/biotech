<template>
  <div class="key-insights-content" :class="{ 'key-insights-content--two-columns': columns === 2 }">
    <div class="key-insights-heading">
      <button
        type="button"
        class="key-insights-info"
        aria-label="About these key insights"
        @mouseenter="showInfoTooltip"
        @mousemove="moveInfoTooltip"
        @mouseleave="hideInfoTooltip"
        @focus="showFocusedInfoTooltip"
        @blur="hideInfoTooltip"
      >
        <BtfIcon name="info" :size="18" />
      </button>
      <h2>{{ title }}</h2>
    </div>

    <div class="key-insights-list">
      <div v-for="(item, index) in items" :key="item.key ?? index" class="key-insights-row">
        <strong>{{ item.value }}</strong>
        <div class="key-insights-copy">
          <span>{{ item.text }}</span>
          <small v-if="item.detail">{{ item.detail }}</small>
        </div>
      </div>
    </div>

    <ChartTooltip
      :visible="infoTooltip.visible"
      :x="infoTooltip.x"
      :y="infoTooltip.y"
      :detail="description"
    />
  </div>
</template>

<script setup lang="ts">
import BtfIcon from '@/components/BtfIcon.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import { ref } from 'vue'

interface AnalyticsInsightItem {
  key?: string | number
  value: string | number
  text: string
  detail?: string
}

withDefaults(defineProps<{
  items: AnalyticsInsightItem[]
  description: string
  title?: string
  columns?: 1 | 2
}>(), {
  title: 'Key Insights',
  columns: 1,
})

const infoTooltip = ref({ visible: false, x: 0, y: 0 })

function showInfoTooltip(event: MouseEvent) {
  infoTooltip.value = { visible: true, x: event.clientX, y: event.clientY }
}

function moveInfoTooltip(event: MouseEvent) {
  infoTooltip.value.x = event.clientX
  infoTooltip.value.y = event.clientY
}

function showFocusedInfoTooltip(event: FocusEvent) {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  infoTooltip.value = {
    visible: true,
    x: rect.left + rect.width / 2,
    y: rect.top + rect.height / 2,
  }
}

function hideInfoTooltip() {
  infoTooltip.value.visible = false
}
</script>

<style scoped>
.key-insights-content {
  container-type: inline-size;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
}

.key-insights-heading {
  display: flex;
  align-items: center;
  gap: 10px;
}

:global(.analytics-card:has(.key-insights-content)) {
  overflow: visible !important;
}

.key-insights-heading h2 {
  margin: 0;
  color: #174243;
  font-size: 18px;
}

.key-insights-info {
  position: relative;
  display: inline-flex;
  flex: 0 0 auto;
  color: #39687b;
  padding: 0;
  border: 0;
  background: transparent;
  font: inherit;
  cursor: help;
  outline: none;
}

.key-insights-info:focus-visible {
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.18);
}

.key-insights-list {
  display: grid;
  grid-template-columns: 1fr;
  /* Equal-height rows spread the insights across tall cards without leaving
     uneven gaps; each row then centres its own number and text. */
  grid-auto-rows: 1fr;
  flex: 1;
  min-height: 0;
  min-width: 0;
  margin-top: 10px;
}

.key-insights-row {
  display: grid;
  grid-template-columns: minmax(64px, 38%) minmax(0, 1fr);
  column-gap: clamp(12px, 3cqi, 28px);
  align-items: center;
  min-width: 0;
  padding: 10px 0;
  border-top: 1px solid #e7eeeb;
}

.key-insights-content--two-columns .key-insights-list {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: clamp(24px, 5cqi, 56px);
}

.key-insights-row strong {
  min-width: 44px;
  padding-left: 8px;
  color: #017151;
  font-size: 20px;
  line-height: 1.2;
  overflow-wrap: anywhere;
}

.key-insights-copy {
  min-width: 0;
}

.key-insights-copy span,
.key-insights-copy small {
  display: block;
  color: #536762;
  font-size: 14px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.key-insights-copy small {
  margin-top: 3px;
  color: #71817d;
  font-size: 13px;
}

@media (max-width: 520px) {
  .key-insights-content--two-columns .key-insights-list {
    grid-template-columns: 1fr;
  }

  .key-insights-row {
    grid-template-columns: 1fr;
    gap: 5px;
  }
}
</style>
