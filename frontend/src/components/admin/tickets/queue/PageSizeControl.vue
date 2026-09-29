<template>
  <div class="page-size">
    <span class="page-size__label" aria-hidden="true">Rows per page</span>
    <template v-if="customMode">
      <input
        ref="customBox"
        type="number"
        inputmode="numeric"
        class="page-size__box"
        :min="MIN_PAGE_SIZE"
        :max="MAX_PAGE_SIZE"
        :value="draft"
        :disabled="disabled"
        aria-label="Rows per page"
        @input="draft = ($event.target as HTMLInputElement).value"
        @blur="applyCustom"
        @keydown.enter.prevent="applyCustom"
      />
      <button type="button" class="page-size__presets" :disabled="disabled" @click="backToPresets">
        Presets
      </button>
    </template>
    <select
      v-else
      class="page-size__select"
      :value="String(value)"
      :disabled="disabled"
      aria-label="Rows per page"
      @change="onPick"
    >
      <option v-for="preset in PAGE_SIZE_PRESETS" :key="preset" :value="String(preset)">
        {{ preset }} / page
      </option>
      <option :value="CUSTOM">Custom…</option>
    </select>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, useTemplateRef, watch } from 'vue'

import {
  MAX_PAGE_SIZE,
  MIN_PAGE_SIZE,
  PAGE_SIZE_PRESETS,
  clampPageSize,
  isPresetPageSize
} from './queueRules'

/** Rows-per-page: the presets, plus a number box for any size up to the
 *  server's cap. Ported from adminweb's PageSizeSelect, including its habit
 *  of opening as the number box when the size is not a preset (the queue
 *  opens on 10). */
const props = defineProps<{ value: number; disabled: boolean }>()
const emit = defineEmits<{ change: [size: number] }>()

const CUSTOM = 'custom'

const customMode = ref(!isPresetPageSize(props.value))
const draft = ref(String(props.value))
const customBox = useTemplateRef<HTMLInputElement>('customBox')

// Keep the box in step when the value changes from outside, and snap back to
// the dropdown whenever the size in force is a preset.
watch(
  () => props.value,
  (value) => {
    draft.value = String(value)
    if (isPresetPageSize(value)) customMode.value = false
  }
)

function applyCustom() {
  const next = clampPageSize(Number(draft.value))
  draft.value = String(next)
  if (next !== props.value) emit('change', next)
}

async function onPick(event: Event) {
  const picked = (event.target as HTMLSelectElement).value
  if (picked === CUSTOM) {
    customMode.value = true
    // The select the agent was using is gone; put them in the box that
    // replaced it rather than leaving focus on nothing.
    await nextTick()
    customBox.value?.focus()
    return
  }
  emit('change', Number(picked))
}

function backToPresets() {
  customMode.value = false
  if (!isPresetPageSize(props.value)) emit('change', PAGE_SIZE_PRESETS[0])
}
</script>

<style scoped>
.page-size {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.page-size__label {
  font-size: 0.875rem;
}

.page-size__select,
.page-size__box {
  height: 2rem;
  padding: 0.2rem 0.45rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.875rem;
}

.page-size__box {
  width: 5rem;
}

.page-size__presets {
  padding: 0.25rem 0.5rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--charcoal);
  font: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}

.page-size__presets:hover:not(:disabled) {
  background: var(--accent-green-soft);
  color: var(--charcoal);
}

.page-size__presets:disabled,
.page-size__select:disabled,
.page-size__box:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
