<template>
  <div
    v-if="hasPreviousData"
    class="analytics-year-change"
    :class="`analytics-year-change--${direction}`"
    :aria-label="accessibleLabel"
  >
    <span class="analytics-year-change__indicator" aria-hidden="true">{{ symbol }}</span>
    <span class="analytics-year-change__percent">{{ percentageLabel }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  current: number
  previous: number
  label?: string
}>(), {
  label: 'vs last year',
})

const difference = computed(() => props.current - props.previous)
const hasPreviousData = computed(() => Number.isFinite(props.previous) && props.previous > 0)
const direction = computed(() => difference.value > 0 ? 'increase' : difference.value < 0 ? 'decrease' : 'unchanged')
const symbol = computed(() => difference.value > 0 ? '↑' : difference.value < 0 ? '↓' : '—')
const percentageLabel = computed(() => {
  if (difference.value === 0) return '0%'
  if (props.previous === 0) return '100%'
  const value = Math.abs((difference.value / props.previous) * 100)
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`
})
const accessibleLabel = computed(() => difference.value === 0
  ? `No change ${props.label}`
  : `${difference.value > 0 ? 'Increased' : 'Decreased'} by ${percentageLabel.value} ${props.label}`)
</script>

<style scoped>
.analytics-year-change {
  display: inline-flex;
  align-items: baseline;
  flex: 0 0 auto;
  gap: 2px;
  margin: 0;
  white-space: nowrap;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
}
.analytics-year-change--increase .analytics-year-change__indicator,
.analytics-year-change--increase .analytics-year-change__percent {
  color: var(--analytics-ui-accent, var(--btf-dark-green, #007b5b));
}
.analytics-year-change--decrease .analytics-year-change__indicator,
.analytics-year-change--decrease .analytics-year-change__percent {
  color: var(--analytics-ui-danger, #b43a3a);
}
.analytics-year-change--unchanged {
  color: var(--analytics-ui-muted, var(--btf-muted, #687a76));
}
</style>
