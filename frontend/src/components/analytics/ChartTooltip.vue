<template>
  <Transition name="chart-tooltip-fade">
    <div
      v-if="visible"
      class="chart-tooltip"
      :style="{ left: `${x}px`, top: `${y}px` }"
      role="status"
      aria-live="polite"
    >
      <strong>{{ title }}</strong>
      <span>{{ value }}</span>
      <small v-if="detail">{{ detail }}</small>
    </div>
  </Transition>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  x: number
  y: number
  title: string
  value: string
  detail?: string
}>()
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
  transform: translate(10px, 10px);
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
