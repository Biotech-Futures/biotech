<template>
  <div class="page-size">
    <span class="page-size__label" aria-hidden="true">Rows per page</span>
    <!-- aria-disabled rather than disabled while a page loads, as on the
         pager beside it: disabling the control that has focus drops keyboard
         focus to the top of the document. Each one stays focusable and does
         nothing while it is marked; the box is also read-only, so nothing
         can be typed into it that would then be ignored. -->
    <template v-if="customMode">
      <input
        ref="customBox"
        type="number"
        inputmode="numeric"
        class="page-size__box"
        :min="MIN_PAGE_SIZE"
        :max="MAX_PAGE_SIZE"
        :value="draft"
        :readonly="disabled"
        :aria-disabled="disabled ? 'true' : undefined"
        aria-label="Rows per page"
        @input="draft = ($event.target as HTMLInputElement).value"
        @blur="applyCustom"
        @keydown.enter.prevent="applyCustom"
      />
      <button
        ref="presetsButton"
        type="button"
        class="page-size__presets"
        :aria-disabled="disabled ? 'true' : undefined"
        @click="backToPresets"
      >
        Presets
      </button>
    </template>
    <select
      v-else
      ref="presetSelect"
      class="page-size__select"
      :value="String(value)"
      :aria-disabled="disabled ? 'true' : undefined"
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
import '@/components/support/ticketControls.css'

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
const presetsButton = useTemplateRef<HTMLButtonElement>('presetsButton')
const presetSelect = useTemplateRef<HTMLSelectElement>('presetSelect')

// Keep the box in step when the value changes from outside, and snap back to
// the dropdown whenever the size in force is a preset. That swap takes away
// the box, or the Presets button beside it, and when the agent was in one of
// them focus goes to the dropdown that replaces them rather than to the top
// of the document. The queue opens on 10, in the box, so typing 25 and
// pressing Enter is the everyday way to reach this.
watch(
  () => props.value,
  async (value) => {
    draft.value = String(value)
    if (!customMode.value || !isPresetPageSize(value)) return
    const active = document.activeElement
    const hadFocus =
      active !== null && (active === customBox.value || active === presetsButton.value)
    customMode.value = false
    if (!hadFocus) return
    await nextTick()
    presetSelect.value?.focus()
  }
)

function applyCustom() {
  if (props.disabled) return
  const next = clampPageSize(Number(draft.value))
  draft.value = String(next)
  if (next !== props.value) emit('change', next)
}

async function onPick(event: Event) {
  const select = event.target as HTMLSelectElement
  // A marked select still changes under the arrow keys. The pick is
  // ignored, so the select goes back to naming the size in force.
  if (props.disabled) {
    select.value = String(props.value)
    return
  }
  const picked = select.value
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

async function backToPresets() {
  if (props.disabled) return
  customMode.value = false
  if (!isPresetPageSize(props.value)) emit('change', PAGE_SIZE_PRESETS[0])
  // The button that was pressed is gone with the box; the dropdown that
  // replaced them takes focus.
  await nextTick()
  presetSelect.value?.focus()
}
</script>

<style scoped>
/* The first redesign round (October 2026): the same 36px control as the
   pager beside it, and Presets set like a link. Measured (WCAG AA):
     light  edge #84938f on white 3.21:1   Presets #017151 on the page 5.72:1
     dark   edge #70827d on the #161f1d box 4.15:1   Presets mint 6.63:1 */
.page-size {
  --page-size-edge: #84938f;
  --page-size-link: var(--dark-green);

  display: flex;
  align-items: center;
  gap: 0.75rem;
}

:root[data-theme='dark'] .page-size {
  --page-size-edge: #70827d;
  --page-size-link: var(--mint-green);
}

.page-size__label {
  font-size: 0.875rem;
}

.page-size__select,
.page-size__box {
  height: 2.25rem;
  padding: 0.2rem 0.7rem;
  border: 1px solid var(--page-size-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.875rem;
}

.page-size__select {
  appearance: none;
  padding-right: 2rem;
  background-image: var(--ticket-select-chevron);
  background-repeat: no-repeat;
  background-position: right 0.75rem center;
}

.page-size__box {
  width: 4.75rem;
}

.page-size__presets {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--page-size-link);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 700;
  cursor: pointer;
  text-underline-offset: 2px;
}

.page-size__presets:hover:not([aria-disabled='true']) {
  text-decoration: underline;
}

.page-size__presets[aria-disabled='true'],
.page-size__select[aria-disabled='true'],
.page-size__box[aria-disabled='true'] {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
