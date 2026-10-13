<template>
  <Transition name="chart-tooltip-fade">
    <div
      v-if="visible"
      ref="tooltipElement"
      class="chart-tooltip"
      :style="tooltipStyle"
      role="status"
      aria-live="polite"
    >
      <strong v-if="title">{{ title }}</strong>
      <span v-if="value">{{ value }}</span>
      <small v-if="detail">{{ detail }}</small>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onUpdated, reactive, ref } from 'vue'

const props = defineProps<{
  visible: boolean
  x: number
  y: number
  title?: string
  value?: string
  detail?: string
}>()

const tooltipElement = ref<HTMLElement | null>(null)
const tooltipSize = reactive({ width: 180, height: 68 })
const cursorGap = -20
const viewportPadding = 8

onUpdated(() => {
  const rect = tooltipElement.value?.getBoundingClientRect()
  if (!rect) return
  if (Math.abs(tooltipSize.width - rect.width) > 0.5) tooltipSize.width = rect.width
  if (Math.abs(tooltipSize.height - rect.height) > 0.5) tooltipSize.height = rect.height
})

const tooltipStyle = computed(() => {
  const viewportWidth = typeof window === 'undefined' ? 1920 : window.innerWidth
  const viewportHeight = typeof window === 'undefined' ? 1080 : window.innerHeight
  const maximumLeft = Math.max(viewportPadding, viewportWidth - tooltipSize.width - viewportPadding)
  const preferredTop = props.y - cursorGap - tooltipSize.height

  const leftAbove = props.x - cursorGap - tooltipSize.width
  const centreAbove = props.x - tooltipSize.width / 2
  const rightAbove = props.x + cursorGap
  const left = leftAbove >= viewportPadding
    ? leftAbove
    : centreAbove >= viewportPadding && centreAbove <= maximumLeft
      ? centreAbove
      : Math.min(Math.max(rightAbove, viewportPadding), maximumLeft)

  return {
    left: `${Math.round(left)}px`,
    top: `${Math.round(Math.min(Math.max(preferredTop, viewportPadding), viewportHeight - tooltipSize.height - viewportPadding))}px`,
  }
})
</script>

<style scoped>
.chart-tooltip {
  font-family: Arial, sans-serif;
  position: fixed;
  z-index: 9999;
  display: flex;
  min-width: 118px;
  max-width: 220px;
  flex-direction: column;
  gap: 3px;
  padding: 9px 11px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 9px;
  background: var(--btf-teal);
  color: var(--btf-white);
  pointer-events: none;
  box-shadow: 0 8px 24px rgba(16, 45, 42, 0.18);
}

.chart-tooltip strong {
  font-size: 12px;
  line-height: 1.25;
}

.chart-tooltip span {
  color: var(--btf-white);
  font-size: 11px;
  font-weight: 600;
}

.chart-tooltip small {
  color: #dce3e0;
  font-size: 10px;
  line-height: 1.3;
}

.chart-tooltip-fade-enter-active,
.chart-tooltip-fade-leave-active {
  transition: opacity 0.12s ease;
}

.chart-tooltip-fade-enter-from,
.chart-tooltip-fade-leave-to {
  opacity: 0;
}
</style>
