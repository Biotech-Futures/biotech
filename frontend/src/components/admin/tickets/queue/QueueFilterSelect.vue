<template>
  <div
    ref="rootRef"
    v-bind="boxAttrs"
    class="filter-select"
    :class="{ 'is-open': open }"
    @mousedown="onBoxMousedown"
    @focusout="onFocusOut"
    @keydown.esc="onEscape"
  >
    <!-- One of the queue's filters with check boxes, so that several of a kind
         can be picked (client item C-27). Drawn as the platform's AppSelect is
         (a box with a chevron, a white list over the page), because the client
         asked for that look on every dropdown too (C-29); AppSelect itself
         holds one value, so it could not be this. The page's classes size the
         box, as they did the select this replaced. -->
    <button
      :id="id"
      ref="buttonRef"
      v-bind="buttonAttrs"
      type="button"
      class="filter-select__button"
      :aria-expanded="open ? 'true' : 'false'"
      :aria-controls="panelId"
      :aria-describedby="summaryId"
      @click="toggle"
      @keydown.down.prevent="openAndFocus(0)"
    >
      <span :id="summaryId" class="filter-select__text">{{ summary }}</span>
    </button>
    <i class="fas fa-chevron-down filter-select__arrow" aria-hidden="true"></i>

    <!-- A group of real check boxes rather than a listbox: each one is a
         native control that says whether it is ticked, Space ticks it, and Tab
         walks them. A mousedown in here keeps focus where it was, so picking
         with the mouse does not blur the box and close the list under the
         pointer. -->
    <div
      v-if="open"
      :id="panelId"
      ref="panelRef"
      class="filter-select__panel"
      role="group"
      :aria-label="groupLabel"
      @mousedown.prevent
      @keydown.down.prevent="moveFocus(1)"
      @keydown.up.prevent="moveFocus(-1)"
    >
      <label v-for="option in options" :key="option.value" class="filter-select__option">
        <input
          type="checkbox"
          class="filter-select__check"
          :value="option.value"
          :checked="chosen.has(option.value)"
          @change="setTicked(option.value, ($event.target as HTMLInputElement).checked)"
        />
        <span class="filter-select__label">{{ option.label }}</span>
      </label>
      <p v-if="!options.length" class="filter-select__empty">Nothing to choose yet</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useAttrs, useId, watch } from 'vue'

import { filterSummary, type FilterOption } from './queueFilters'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    modelValue?: string[]
    options: FilterOption[]
    /** What the box says when nothing narrows it: "Any status". */
    anyLabel: string
    id?: string
  }>(),
  { modelValue: () => [], id: undefined }
)

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
  /** After a box is ticked or cleared, with everything now ticked. */
  change: [value: string[]]
}>()

// As AppSelect splits them: the page's classes, styles and data-test draw and
// name the box; the rest (aria-label, title) go to the button.
const attrs = useAttrs()
const isBoxAttr = (key: string) => key === 'class' || key === 'style' || key.startsWith('data-')
const boxAttrs = computed(() => Object.fromEntries(Object.entries(attrs).filter(([key]) => isBoxAttr(key))))
const buttonAttrs = computed(() => Object.fromEntries(Object.entries(attrs).filter(([key]) => !isBoxAttr(key))))
// The group is the list the button opens, so it carries the button's name.
const groupLabel = computed(() => (typeof attrs['aria-label'] === 'string' ? attrs['aria-label'] : undefined))

const panelId = `filter-select-${useId()}`
const summaryId = `${panelId}-summary`
const rootRef = ref<HTMLElement | null>(null)
const buttonRef = ref<HTMLButtonElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const open = ref(false)

const chosen = computed(() => new Set(props.modelValue))
const summary = computed(() => filterSummary(props.modelValue, props.options, props.anyLabel))

// From the box's own state rather than flipping what was ticked: a change
// event that arrives twice still leaves the box saying what the list holds.
function setTicked(value: string, ticked: boolean) {
  const next = new Set(chosen.value)
  if (ticked) next.add(value)
  else next.delete(value)
  // In the list's own order, so the same ticks always read the same way and
  // send the same request. Values the list does not have yet are kept, after.
  const ordered = [
    ...props.options.map((option) => option.value).filter((option) => next.has(option)),
    ...[...next].filter((value) => !props.options.some((option) => option.value === value))
  ]
  emit('update:modelValue', ordered)
  emit('change', ordered)
}

function toggle() {
  open.value = !open.value
}

function checkboxes(): HTMLInputElement[] {
  return Array.from(panelRef.value?.querySelectorAll<HTMLInputElement>('input[type="checkbox"]') ?? [])
}

async function openAndFocus(index: number) {
  open.value = true
  await nextTick()
  checkboxes()[index]?.focus()
}

function moveFocus(step: number) {
  const boxes = checkboxes()
  const at = boxes.indexOf(document.activeElement as HTMLInputElement)
  boxes[Math.min(Math.max(at + step, 0), boxes.length - 1)]?.focus()
}

function close() {
  open.value = false
}

function onEscape(event: KeyboardEvent) {
  if (!open.value) return
  event.preventDefault()
  close()
  buttonRef.value?.focus()
}

// A press on the box's padding or chevron opens it as one on its words does.
function onBoxMousedown(event: MouseEvent) {
  const target = event.target as Node
  if (event.button !== 0 || buttonRef.value?.contains(target) || panelRef.value?.contains(target)) return
  event.preventDefault()
  buttonRef.value?.focus()
  toggle()
}

// Focus leaving the box altogether (Tab past the last check box, or into the
// page) closes the list; moving within it does not.
function onFocusOut(event: FocusEvent) {
  const next = event.relatedTarget as Node | null
  if (next && rootRef.value?.contains(next)) return
  close()
}

// A press anywhere else on the page closes it, as a select's list closes.
function onDocumentMousedown(event: MouseEvent) {
  if (!rootRef.value?.contains(event.target as Node)) close()
}

watch(open, (isOpen) => {
  if (isOpen) document.addEventListener('mousedown', onDocumentMousedown, true)
  else document.removeEventListener('mousedown', onDocumentMousedown, true)
})

onBeforeUnmount(() => document.removeEventListener('mousedown', onDocumentMousedown, true))
</script>

<style scoped>
/* The box as AppSelect draws one when the page does not: the page's own
   classes win, because :where() adds no weight. */
:where(.filter-select) {
  display: inline-flex;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
  color: var(--teal);
  font: inherit;
}

.filter-select {
  position: relative;
  box-sizing: border-box;
  align-items: center;
  cursor: pointer;
}

/* AppSelect's focus ring, on the box rather than the bare button. Dark takes
   the queue's dark ring: --dark-green, which the theme does not redefine, is
   about 2.8:1 on the dark grounds, under the 3:1 a focus indicator needs. */
.filter-select:has(.filter-select__button:focus-visible) {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

:root[data-theme='dark'] .filter-select:has(.filter-select__button:focus-visible) {
  outline-color: var(--mint-green);
}

.filter-select__button {
  flex: 1 1 auto;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: inherit;
  font: inherit;
  line-height: normal;
  text-align: left;
  cursor: pointer;
}

.filter-select__text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* AppSelect's chevron, turned over while the list is open. */
.filter-select__arrow {
  position: absolute;
  top: 50%;
  right: 0.9rem;
  color: var(--text-muted);
  font-size: 0.7em;
  pointer-events: none;
  transform: translateY(-50%);
  transition: transform 160ms ease;
}

.filter-select.is-open .filter-select__arrow {
  transform: translateY(-50%) rotate(180deg);
}

/* AppSelect's list: white, edged, over whatever sits below. Under the box
   rather than on the page's top layer, so it scrolls with the filters; the
   queue holds nothing above it that could cut it off. */
.filter-select__panel {
  position: absolute;
  top: calc(100% + 4px);
  left: -1px;
  z-index: 30;
  box-sizing: border-box;
  min-width: calc(100% + 2px);
  width: max-content;
  max-width: 22rem;
  max-height: 16rem;
  padding: 0.25rem;
  overflow-y: auto;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
  box-shadow: 0 6px 18px var(--shadow);
  cursor: default;
}

.filter-select__option {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.35rem 0.5rem;
  border-radius: 4px;
  color: var(--teal);
  white-space: nowrap;
  cursor: pointer;
}

/* AppSelect's highlight for the choice under the pointer or the keyboard. */
.filter-select__option:hover,
.filter-select__option:has(.filter-select__check:focus-visible) {
  background: var(--light-green);
}

.filter-select__check {
  flex-shrink: 0;
  width: 1rem;
  height: 1rem;
  margin: 0;
  accent-color: var(--dark-green);
  cursor: pointer;
}

.filter-select__empty {
  margin: 0;
  padding: 0.35rem 0.5rem;
  color: var(--text-muted);
}
</style>
