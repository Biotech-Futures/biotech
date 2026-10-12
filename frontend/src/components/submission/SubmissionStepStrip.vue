<template>
  <nav class="submission-steps" aria-label="Submission sections">
    <button
      v-for="step in steps"
      :key="step.key"
      type="button"
      class="submission-step"
      :class="{ 'is-active': active === step.key }"
      :aria-current="active === step.key ? 'step' : undefined"
      @click="emit('select', step.key)"
    >
      <span class="submission-step__label">{{ step.label }}</span>
      <span class="submission-step__state">{{ summary(step.key) }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
/** The step strip shared by the submission portal and its Finalist step. */
defineProps<{
  steps: { key: string; label: string }[]
  active: string
  summary: (key: string) => string
}>()

const emit = defineEmits<{ select: [key: string] }>()
</script>

<style scoped>
.submission-steps {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--panel-border);
}

.submission-step {
  flex: 1 1 180px;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.7rem 0.9rem;
  border: 0;
  border-bottom: 3px solid transparent;
  background: none;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: var(--body-text);
  margin-bottom: -1px;
}

.submission-step:hover {
  color: var(--accent);
}

.submission-step.is-active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.submission-step__label {
  font-weight: 700;
  font-size: 1rem;
  flex: 1;
}

.submission-step__state {
  font-size: 0.875rem;
  color: var(--muted);
  white-space: nowrap;
}
</style>
