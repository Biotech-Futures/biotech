<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="admin-modal admin-modal--confirm"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
      :aria-describedby="message ? messageId : undefined"
      @keydown.esc="onCancel"
      @mousedown.self="onOverlayClick"
    >
      <div class="admin-modal__backdrop" aria-hidden="true"></div>
      <div class="admin-modal__content" :class="`admin-modal__content--${variant}`">
        <header class="admin-modal__header">
          <div class="admin-modal__icon" :aria-hidden="true">
            <i :class="iconClass"></i>
          </div>
          <h2 :id="titleId" class="admin-modal__title">{{ title }}</h2>
        </header>

        <div v-if="message" :id="messageId" class="admin-modal__body">
          <p class="admin-modal__message">{{ message }}</p>
          <slot />
        </div>

        <footer class="admin-modal__footer">
          <button
            type="button"
            class="btn btn-outline"
            :disabled="busy || disabled"
            @click="onCancel"
          >
            {{ cancelLabel }}
          </button>
          <button
            ref="confirmButtonRef"
            type="button"
            class="btn"
            :class="confirmButtonClass"
            :disabled="busy || disabled"
            @click="onConfirm"
          >
            <span v-if="busy" class="admin-modal__spinner" aria-hidden="true"></span>
            {{ busy ? busyLabel : confirmLabel }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

export type ConfirmVariant = 'default' | 'danger' | 'warning'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    message?: string
    confirmLabel?: string
    cancelLabel?: string
    busyLabel?: string
    variant?: ConfirmVariant
    busy?: boolean
    disabled?: boolean
  }>(),
  {
    message: '',
    confirmLabel: 'Confirm',
    cancelLabel: 'Cancel',
    busyLabel: 'Working...',
    variant: 'default',
    busy: false,
    disabled: false
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})

const confirmButtonRef = ref<HTMLButtonElement | null>(null)
const instanceId = `confirm-${Math.random().toString(36).slice(2, 8)}`
const titleId = `confirm-title-${instanceId}`
const messageId = `confirm-message-${instanceId}`

const iconClass = computed(() => {
  switch (props.variant) {
    case 'danger':
      return 'fas fa-triangle-exclamation'
    case 'warning':
      return 'fas fa-circle-exclamation'
    default:
      return 'fas fa-circle-question'
  }
})

const confirmButtonClass = computed(() => {
  switch (props.variant) {
    case 'danger':
      return 'btn-danger'
    case 'warning':
      return 'btn-warning'
    default:
      return 'btn-primary'
  }
})

const onConfirm = () => {
  if (props.busy || props.disabled) return
  emit('confirm')
}

const onCancel = () => {
  if (props.busy) return
  emit('cancel')
  open.value = false
}

const onOverlayClick = () => {
  onCancel()
}

const focusConfirm = async () => {
  await nextTick()
  confirmButtonRef.value?.focus()
}

watch(
  () => props.modelValue,
  (isOpen) => {
    if (isOpen) void focusConfirm()
  }
)
</script>

<style scoped>
.admin-modal {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.25rem;
}

.admin-modal__backdrop {
  position: absolute;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
}

.admin-modal__content {
  position: relative;
  width: 100%;
  max-width: 480px;
  background-color: var(--white);
  border-radius: 12px;
  box-shadow: 0 24px 60px rgba(7, 17, 15, 0.28);
  animation: admin-modal-in 0.18s ease;
  overflow: hidden;
}

.admin-modal__header {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-light);
}

.admin-modal__icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  border-radius: 12px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 1.1rem;
}

.admin-modal__content--danger .admin-modal__icon {
  background-color: rgba(220, 53, 69, 0.14);
  color: var(--danger);
}

.admin-modal__content--warning .admin-modal__icon {
  background-color: rgba(255, 193, 7, 0.18);
  color: #b8860b;
}

.admin-modal__title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--charcoal);
  line-height: 1.3;
}

.admin-modal__body {
  padding: 1.25rem 1.5rem;
}

.admin-modal__message {
  margin: 0;
  color: var(--charcoal);
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.admin-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem 1.25rem;
  border-top: 1px solid var(--border-light);
  background-color: var(--bg-light);
}

.admin-modal__spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 0.5rem;
  vertical-align: -2px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: var(--white);
  border-radius: 50%;
  animation: admin-spin 0.8s linear infinite;
}

.btn-danger {
  background-color: var(--danger);
  color: var(--white);
}

.btn-danger:hover {
  background-color: #c82333;
}

.btn-warning {
  background-color: var(--warning);
  color: var(--charcoal);
}

.btn-warning:hover {
  background-color: #e0a800;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@keyframes admin-modal-in {
  from {
    opacity: 0;
    transform: translateY(-6px) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes admin-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-modal__content,
  .admin-modal__spinner {
    animation: none;
  }
}
</style>
