<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="admin-sheet"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
      :aria-describedby="description ? descriptionId : undefined"
      @keydown.esc="onDismiss"
    >
      <div class="admin-sheet__backdrop" aria-hidden="true" @mousedown.self="onDismiss"></div>

      <div class="admin-sheet__panel" :style="{ width }">
        <header class="admin-sheet__header">
          <div class="admin-sheet__heading">
            <h2 :id="titleId" class="admin-sheet__title">{{ title }}</h2>
            <p v-if="description" :id="descriptionId" class="admin-sheet__description">
              {{ description }}
            </p>
          </div>
          <button
            type="button"
            class="admin-sheet__close"
            :aria-label="closeLabel"
            @click="onDismiss"
          >
            <i class="fas fa-times" aria-hidden="true"></i>
          </button>
        </header>

        <div class="admin-sheet__body" :class="{ 'admin-sheet__body--flush': flushBody }">
          <slot />
        </div>

        <footer v-if="$slots.footer" class="admin-sheet__footer">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    description?: string
    width?: string
    closeLabel?: string
    flushBody?: boolean
  }>(),
  {
    description: '',
    width: 'min(100vw, 560px)',
    closeLabel: 'Close',
    flushBody: false
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
}>()

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})

const instanceId = `form-sheet-${Math.random().toString(36).slice(2, 8)}`
const titleId = `form-sheet-title-${instanceId}`
const descriptionId = `form-sheet-description-${instanceId}`

const onDismiss = () => {
  emit('close')
  open.value = false
}
</script>

<style scoped>
.admin-sheet {
  position: fixed;
  inset: 0;
  z-index: 1999;
}

.admin-sheet__backdrop {
  position: absolute;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.4);
}

.admin-sheet__panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  max-width: 100vw;
  background-color: var(--white);
  box-shadow: -24px 0 60px rgba(7, 17, 15, 0.18);
  animation: admin-sheet-in 0.22s ease;
}

.admin-sheet__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-light);
}

.admin-sheet__heading {
  min-width: 0;
}

.admin-sheet__title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--charcoal);
  line-height: 1.3;
}

.admin-sheet__description {
  margin: 0.25rem 0 0;
  color: var(--text-muted);
  font-size: 0.875rem;
  line-height: 1.4;
}

.admin-sheet__close {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border: none;
  border-radius: 10px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 0.95rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.18s ease, transform 0.18s ease;
}

.admin-sheet__close:hover {
  background-color: #f4dccb;
  transform: translateY(-1px);
}

.admin-sheet__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 1.5rem;
}

.admin-sheet__body--flush {
  padding: 0;
}

.admin-sheet__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-light);
  background-color: var(--bg-light);
}

@keyframes admin-sheet-in {
  from {
    transform: translateX(100%);
  }
  to {
    transform: translateX(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-sheet__panel {
    animation: none;
  }
}
</style>
