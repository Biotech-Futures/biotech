<template>
  <div ref="root" class="analytics-export-menu">
    <button
      type="button"
      class="export-button"
      :disabled="disabled"
      :aria-haspopup="hasMenu ? 'menu' : undefined"
      :aria-expanded="hasMenu ? open : undefined"
      @click="onTrigger"
    >
      <i class="fas fa-download" aria-hidden="true"></i>
      Export CSV
      <i v-if="hasMenu" class="fas fa-chevron-down analytics-export-menu__chevron" aria-hidden="true"></i>
    </button>

    <div v-if="open" class="analytics-export-menu__list" role="menu" aria-label="Choose what to export">
      <button
        v-for="option in options"
        :key="option.kind"
        type="button"
        role="menuitem"
        class="analytics-export-menu__item"
        :disabled="option.disabled"
        @click="choose(option.kind)"
      >
        <strong>{{ option.label }}</strong>
        <span>{{ option.description }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { ExportKind, ExportOption } from '@/utils/analyticsExport'

const props = defineProps<{ options: ExportOption[]; disabled?: boolean }>()
const emit = defineEmits<{ select: [kind: ExportKind] }>()

const root = ref<HTMLElement | null>(null)
const open = ref(false)
// With one file to offer, the button exports it directly.
const hasMenu = computed(() => props.options.length > 1)

function onTrigger() {
  if (!hasMenu.value) {
    const only = props.options[0]
    if (only && !only.disabled) emit('select', only.kind)
    return
  }
  open.value = !open.value
}

function choose(kind: ExportKind) {
  open.value = false
  emit('select', kind)
}

function onDocumentClick(event: MouseEvent) {
  if (open.value && root.value && !root.value.contains(event.target as Node)) open.value = false
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.analytics-export-menu {
  position: relative;
  display: inline-flex;
  align-self: flex-end;
}

/* Pages style their own export button with scoped CSS, which does not reach
   into this component, so the button carries the shared look itself. */
.export-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 142px;
  height: 46px;
  padding: 0 16px;
  border: 1px solid #5ea99e;
  border-radius: 12px;
  background: #ffffff;
  color: #017151;
  font: 700 14px Arial, sans-serif;
  white-space: nowrap;
  cursor: pointer;
}

.export-button:hover:not(:disabled) {
  background: #ecf8f4;
}

.export-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.analytics-export-menu__chevron {
  margin-left: 2px;
  font-size: 11px;
}

.analytics-export-menu__list {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 30;
  display: grid;
  gap: 2px;
  width: 260px;
  max-width: calc(100vw - 32px);
  padding: 6px;
  border: 1px solid var(--btf-mint-green, #b9dccb);
  border-radius: 10px;
  background: var(--btf-white, #fff);
  box-shadow: 0 10px 24px rgba(15, 59, 44, 0.12);
}

.analytics-export-menu__item {
  display: grid;
  gap: 2px;
  width: 100%;
  padding: 9px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--btf-dark-green, #0f3b2c);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.analytics-export-menu__item strong {
  font-size: 14px;
}

.analytics-export-menu__item span {
  color: #5d6f69;
  font-size: 12px;
  line-height: 1.4;
}

.analytics-export-menu__item:hover:not(:disabled),
.analytics-export-menu__item:focus-visible {
  background: color-mix(in srgb, var(--btf-light-green, #d8efe3) 55%, white);
  outline: none;
}

.analytics-export-menu__item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
