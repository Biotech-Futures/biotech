<script setup lang="ts">
// TEMP (skeleton Part 5): raw smoke test of the shared client against
// GET /api/v1/admin/summary/. Part 6 replaces this with vue-query + real cards.
import { onMounted, ref } from 'vue'
import { adminApi } from '@/admin/api/client'
import { apiErrorFromUnknown } from '@/utils/apiError'

const summary = ref<unknown>(null)
const errorMessage = ref('')
const isLoading = ref(true)

onMounted(async () => {
  try {
    summary.value = await adminApi.get('/summary')
  } catch (error) {
    errorMessage.value = apiErrorFromUnknown(error).message
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="mb-4">Overview</h1>
    <v-progress-circular v-if="isLoading" indeterminate color="primary" />
    <v-alert v-else-if="errorMessage" type="error" variant="tonal" :text="errorMessage" />
    <pre v-else class="summary-json">{{ JSON.stringify(summary, null, 2) }}</pre>
  </div>
</template>

<style scoped>
.summary-json {
  background-color: var(--accent-green-soft);
  border-radius: 8px;
  padding: 1rem;
  overflow-x: auto;
  font-size: 0.9rem;
  color: var(--charcoal);
}
</style>
