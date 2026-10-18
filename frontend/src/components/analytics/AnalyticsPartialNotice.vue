<template>
  <div v-if="sources.length" class="analytics-partial-notice" role="status">
    <p>
      Some data could not be loaded: {{ sourceLabels(sources).join(', ') }}.
      Available statistics remain visible. A dash or an unavailable section does not mean zero.
    </p>
    <button type="button" @click="$emit('retry')">Retry unavailable data</button>
  </div>
</template>

<script setup lang="ts">
import type { AnalyticsSource } from '@/utils/liveAnalyticsData'
import { sourceLabels } from '@/utils/analyticsExport'

defineProps<{ sources: AnalyticsSource[] }>()
defineEmits<{ retry: [] }>()
</script>

<style scoped>
.analytics-partial-notice {
  margin: 16px 0;
  padding: 16px 20px;
  border: 1px solid var(--btf-border, #d7e2de);
  border-radius: 12px;
  background: var(--btf-surface, #f7faf9);
  color: var(--btf-teal, #174243);
}
.analytics-partial-notice p { margin: 0 0 10px; line-height: 1.5; }
.analytics-partial-notice button {
  padding: 7px 12px;
  border: 1px solid currentColor;
  border-radius: 8px;
  color: inherit;
  background: transparent;
  cursor: pointer;
}
</style>
