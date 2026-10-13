<template>
  <div class="key-insights-content" :class="{ 'key-insights-content--two-columns': columns === 2 }">
    <div class="key-insights-heading">
      <button type="button" class="key-insights-info" aria-label="About these key insights">
        <BtfIcon name="info" :size="18" />
        <span class="key-insights-tooltip" role="tooltip">{{ description }}</span>
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
  </div>
</template>

<script setup lang="ts">
import BtfIcon from '@/components/BtfIcon.vue'

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
</script>

<style scoped>
.key-insights-content {
  container-type: inline-size;
  min-width: 0;
}

.key-insights-heading {
  display: flex;
  align-items: center;
  gap: 10px;
}

:global(.analytics-card:has(.key-insights-content)) {
  overflow: visible !important;
  height: auto !important;
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

.key-insights-tooltip {
  position: absolute;
  z-index: 30;
  top: calc(100% + 9px);
  left: 0;
  width: 220px !important;
  max-width: min(220px, calc(100vw - 40px)) !important;
  min-width: 0 !important;
  height: auto !important;
  min-height: 0 !important;
  box-sizing: border-box;
  padding: 8px 10px;
  border-radius: 7px;
  border: 0 !important;
  background: #173f3c !important;
  color: #fff !important;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
  text-align: left;
  white-space: normal !important;
  overflow-wrap: break-word;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-3px);
  transition: opacity 0.15s ease, transform 0.15s ease;
  box-shadow: 0 6px 18px rgba(16, 32, 27, 0.18);
}

.key-insights-info:hover .key-insights-tooltip,
.key-insights-info:focus .key-insights-tooltip {
  opacity: 1;
  transform: translateY(0);
}

.key-insights-list {
  display: grid;
  grid-template-columns: 1fr;
  min-width: 0;
  margin-top: 10px;
}

.key-insights-row {
  display: grid;
  grid-template-columns: minmax(64px, 38%) minmax(0, 1fr);
  column-gap: clamp(12px, 3cqi, 28px);
  align-items: start;
  min-width: 0;
  padding: 9px 0;
  border-top: 1px solid #e7eeeb;
}

.key-insights-content--two-columns .key-insights-list {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: clamp(24px, 5cqi, 56px);
}

.key-insights-row strong {
  min-width: 44px;
  color: #017151;
  font-size: 18px;
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
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.key-insights-copy small {
  margin-top: 3px;
  color: #71817d;
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
