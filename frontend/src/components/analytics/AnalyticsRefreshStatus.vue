<template>
  <p class="analytics-refresh-status" role="status" aria-live="polite">
    <span v-if="updatedAt">Last updated: {{ formattedTime }}.</span>
    Automatically refreshes every 5 minutes. Reloading this page fetches fresh data.
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
.analytics-refresh-status { margin: 12px 0; color: #536763; font-size: 13px; }
</style>
