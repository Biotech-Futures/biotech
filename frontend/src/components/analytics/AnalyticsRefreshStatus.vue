<template>
  <p v-if="updatedAt || refreshFailed" class="analytics-refresh-status" role="status" aria-live="polite">
    <span v-if="updatedAt">Last updated: {{ formattedTime }}.</span>
    <span v-if="refreshFailed">Latest refresh failed; showing the last successfully loaded data.</span>
  </p>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ updatedAt: string | null; refreshFailed?: boolean }>()
const formattedTime = computed(() => props.updatedAt
  ? new Date(props.updatedAt).toLocaleString('en-AU', { dateStyle: 'medium', timeStyle: 'short' })
  : '')
</script>

<style scoped>
.analytics-refresh-status {
  margin: 8px 0 0;
  color: var(--analytics-ui-muted, #536763);
  font-size: 13px;
  line-height: 1.3;
  text-align: right;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .analytics-refresh-status {
    white-space: normal;
  }
}
</style>
