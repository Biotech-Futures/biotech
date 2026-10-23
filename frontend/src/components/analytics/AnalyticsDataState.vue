<template>
  <div
    v-if="loading"
    class="analytics-data-state analytics-data-state-loading"
    role="status"
    aria-live="polite"
    data-testid="analytics-loading-state"
  >
    <span class="analytics-state-icon analytics-state-spinner" aria-hidden="true">
      <i class="fas fa-spinner"></i>
    </span>
    <div>
      <h2>Loading analytics</h2>
      <p>{{ loadingMessage }}</p>
    </div>
  </div>

  <div
    v-else-if="error"
    class="analytics-data-state analytics-data-state-error"
    role="alert"
    data-testid="analytics-error-state"
  >
    <span class="analytics-state-icon" aria-hidden="true">
      <i class="fas fa-triangle-exclamation"></i>
    </span>
    <div>
      <h2>Analytics unavailable</h2>
      <p>{{ error }}</p>
      <button type="button" class="analytics-state-action" @click="$emit('retry')">
        <i class="fas fa-rotate-right" aria-hidden="true"></i>
        Try again
      </button>
    </div>
  </div>

  <div
    v-else-if="empty"
    class="analytics-data-state analytics-data-state-empty"
    role="status"
    data-testid="analytics-empty-state"
  >
    <span class="analytics-state-icon" aria-hidden="true">
      <i class="fas fa-database"></i>
    </span>
    <div>
      <h2>No analytics data</h2>
      <p>{{ emptyMessage }}</p>
      <button type="button" class="analytics-state-action" @click="$emit('retry')">
        <i class="fas fa-rotate-right" aria-hidden="true"></i>
        Refresh data
      </button>
    </div>
  </div>

  <slot v-else />
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  loading: boolean
  error?: string
  empty: boolean
  loadingMessage?: string
  emptyMessage?: string
}>(), {
  error: '',
  loadingMessage: 'Reading the latest values from the analytics API.',
  emptyMessage: 'The current database does not contain records for this analytics view.',
})

defineEmits<{ retry: [] }>()
</script>

<style scoped>
.analytics-data-state {
  min-height: 250px;
  margin: 22px 0;
  padding: 42px 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  text-align: left;
  color: var(--analytics-ui-text, var(--btf-teal, #174243));
  background: var(--analytics-ui-surface, var(--btf-white, #fff));
  border: 1px solid var(--analytics-ui-border, var(--btf-border, #d7e2de));
  border-radius: 16px;
}

.analytics-state-icon {
  width: 48px;
  height: 48px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: var(--analytics-ui-accent, var(--btf-dark-green, #017151));
  background: color-mix(in srgb, var(--analytics-ui-selected, var(--btf-light-green, #bad7b8)) 55%, var(--analytics-ui-surface, white));
  font-size: 20px;
}

.analytics-data-state-error .analytics-state-icon {
  color: var(--analytics-ui-danger, #a7372a);
  background: var(--analytics-ui-danger-bg, #fff0ed);
}

.analytics-state-spinner i {
  animation: analytics-state-spin 0.9s linear infinite;
}

.analytics-data-state h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.analytics-data-state p {
  max-width: 620px;
  margin: 0;
  color: var(--analytics-ui-muted, var(--btf-muted, #667873));
  line-height: 1.5;
}

.analytics-state-action {
  margin-top: 16px;
  padding: 9px 15px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  background: var(--btf-dark-green, #017151);
  border: 1px solid var(--btf-dark-green, #017151);
  border-radius: 8px;
  font-weight: 700;
  cursor: pointer;
}

.analytics-state-action:hover {
  background: var(--btf-teal, #174243);
}

@keyframes analytics-state-spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 640px) {
  .analytics-data-state {
    min-height: 210px;
    padding: 30px 20px;
    align-items: flex-start;
  }
}
</style>
