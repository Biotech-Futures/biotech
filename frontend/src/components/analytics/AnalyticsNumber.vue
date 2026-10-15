<template>
  <span
    class="analytics-number"
    :title="isCompact ? exactValue : undefined"
    :aria-label="isCompact ? exactValue : undefined"
  >{{ displayValue }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  value: number | string | null | undefined
}>()

const numericValue = computed(() => {
  if (typeof props.value === 'number') return Number.isFinite(props.value) ? props.value : null
  if (typeof props.value !== 'string') return null
  const normalized = props.value.trim().replace(/,/g, '')
  if (!/^-?\d+(?:\.\d+)?$/.test(normalized)) return null
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
})

const exactValue = computed(() => {
  if (numericValue.value === null) return String(props.value ?? '—')
  return numericValue.value.toLocaleString('en-AU', { maximumFractionDigits: 2 })
})

const isCompact = computed(() => numericValue.value !== null && Math.abs(numericValue.value) >= 10_000)

const displayValue = computed(() => {
  const value = numericValue.value
  if (value === null) return String(props.value ?? '—')
  if (!isCompact.value) return exactValue.value

  const absolute = Math.abs(value)
  const divisor = absolute >= 1_000_000_000 ? 1_000_000_000 : absolute >= 1_000_000 ? 1_000_000 : 1_000
  const suffix = divisor === 1_000_000_000 ? 'b' : divisor === 1_000_000 ? 'm' : 'k'
  const compact = value / divisor
  const rounded = Math.abs(compact) >= 100 || Number.isInteger(compact)
    ? compact.toFixed(0)
    : compact.toFixed(1)
  return `${rounded}${suffix}`
})
</script>

<style scoped>
.analytics-number {
  color: inherit !important;
  font-family: inherit !important;
  font-size: inherit !important;
  font-weight: inherit !important;
  line-height: inherit !important;
  letter-spacing: inherit !important;
}
</style>
