<template>
  <div
    class="bulk-actions-bar"
    role="toolbar"
    aria-label="Bulk actions"
  >
    <div class="bulk-actions-bar__summary">
      <p class="bulk-actions-bar__count" aria-live="polite">
        {{ count }} {{ count === 1 ? noun : `${noun}s` }} selected
      </p>
      <button
        type="button"
        class="bulk-actions-bar__clear"
        :disabled="disabled"
        @click="$emit('clear')"
      >
        <i class="fas fa-times" aria-hidden="true"></i>
        <span>{{ clearLabel }}</span>
      </button>
    </div>

    <div class="bulk-actions-bar__actions">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    count: number
    noun: string
    clearLabel?: string
    disabled?: boolean
  }>(),
  {
    clearLabel: 'Clear',
    disabled: false
  }
)

defineEmits<{
  (e: 'clear'): void
}>()
</script>

<style scoped>
.bulk-actions-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  margin-bottom: 1rem;
  border: 1px solid var(--border-light);
  border-left: 3px solid var(--dark-green);
  border-radius: 8px;
  background-color: var(--light-green);
}

.bulk-actions-bar__summary {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.bulk-actions-bar__count {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--charcoal);
}

.bulk-actions-bar__clear {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.6rem;
  border: none;
  border-radius: 6px;
  background-color: transparent;
  color: var(--dark-green);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.18s ease;
}

.bulk-actions-bar__clear:hover:not(:disabled) {
  background-color: rgba(1, 113, 81, 0.1);
}

.bulk-actions-bar__clear:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.bulk-actions-bar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
</style>
