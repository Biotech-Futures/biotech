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
    <!-- The platform's own dropdown (AppSelect) since the 2026-10-22 client
         meeting (C-29). Marked rather than disabled while a page loads, as
         the box above is: AppSelect hands aria-disabled to its field, and a
         pick made while it is marked is ignored (onPick), so the box keeps
         naming the size in force. -->
    <AppSelect
      v-else
      :id="presetId"
      class="page-size__select"
      :model-value="String(value)"
      :options="PRESET_OPTIONS"
      :searchable="false"
      :aria-disabled="disabled ? 'true' : undefined"
      aria-label="Rows per page"
      @change="onPick"
    />
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, useId, useTemplateRef, watch } from 'vue'

import AppSelect, { type AppSelectOption, type AppSelectValue } from '@/components/AppSelect.vue'

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

const PRESET_OPTIONS: AppSelectOption[] = [
  ...PAGE_SIZE_PRESETS.map((preset) => ({ value: String(preset), label: `${preset} / page` })),
  { value: CUSTOM, label: 'Custom…' }
]

const customMode = ref(!isPresetPageSize(props.value))
const draft = ref(String(props.value))
const customBox = useTemplateRef<HTMLInputElement>('customBox')
const presetsButton = useTemplateRef<HTMLButtonElement>('presetsButton')
const presetId = useId()
// The dropdown's own field, which takes focus as the select did.
const focusPresets = () => document.getElementById(presetId)?.focus()

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
    focusPresets()
  }
)

function applyCustom() {
  if (props.disabled) return
  const next = clampPageSize(Number(draft.value))
  draft.value = String(next)
  if (next !== props.value) emit('change', next)
}

async function onPick(value: AppSelectValue) {
  // A pick made while the control is marked is ignored, and the box goes on
  // naming the size in force, because it shows the value it is given.
  if (props.disabled) return
  const picked = String(value)
  if (picked === CUSTOM) {
    customMode.value = true
    // The dropdown the agent was using is gone; put them in the box that
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
  focusPresets()
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
  color: var(--teal);
  font: inherit;
  font-size: 0.875rem;
}

/* AppSelect draws the chevron and the list. */
.page-size__select {
  min-width: 7.5rem;
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

/* AppSelect rings its box in --dark-green when its field has keyboard focus,
   which the dark theme does not redefine: about 2.8:1 on the dark grounds,
   under the 3:1 a focus indicator needs. The queue's dark ring (TicketQueuePage.vue). */
:root[data-theme='dark'] .page-size__select:has(:focus-visible) {
  outline-color: var(--mint-green);
}
</style>
