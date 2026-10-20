<template>
  <!-- A dropdown. This is its box: the page's classes, styles and data-test
       land here, so it's drawn as the page drew its select. The field inside
       has no look of its own. The choices open in a white list over the page,
       where nothing can cut them off; long lists can be typed in to search. -->
  <div
    ref="boxRef"
    v-bind="boxAttrs"
    class="app-select"
    :class="{ 'is-open': open, 'is-disabled': disabled, 'is-large': size === 'large' }"
    @mousedown="onBoxMousedown"
  >
    <input
      :id="id"
      ref="inputRef"
      v-bind="inputAttrs"
      :value="open && canSearch ? query : selectedLabel"
      class="app-select__input"
      :class="{ 'is-static': !canSearch }"
      :readonly="!canSearch"
      size="1"
      type="text"
      role="combobox"
      autocomplete="off"
      aria-autocomplete="list"
      :placeholder="open && canSearch && selectedLabel ? selectedLabel : placeholder"
      :aria-expanded="open"
      :aria-controls="listId"
      :aria-activedescendant="open && active >= 0 ? `${listId}-${active}` : undefined"
      :aria-required="required || undefined"
      :disabled="disabled"
      @input="onInput"
      @keydown="onKeydown"
      @blur="closeList"
    />
    <i class="fas fa-chevron-down app-select__arrow" aria-hidden="true"></i>
    <!-- As wide as the longest choice, as a select is. -->
    <span class="app-select__sizer" aria-hidden="true">
      <span v-for="option in options" :key="String(option.value)">{{ option.label }}</span>
      <span v-if="placeholder">{{ placeholder }}</span>
    </span>
    <!-- Keeps a form that needs a choice from saving without one, as a select does. -->
    <input
      v-if="required"
      ref="validatorRef"
      class="app-select__validator"
      tabindex="-1"
      aria-hidden="true"
      :value="hasValue ? '1' : ''"
      @focus="inputRef?.focus()"
    />
    <Teleport to="body">
      <ul
        v-if="open"
        :id="listId"
        ref="listRef"
        class="app-select__list"
        role="listbox"
        :style="listStyle"
        @mousedown.prevent.stop
      >
        <li v-if="loading" class="app-select__empty">Loading…</li>
        <li v-else-if="!matches.length" class="app-select__empty">{{ emptyText }}</li>
        <template v-else>
          <template v-for="(option, index) in matches" :key="String(option.value)">
            <li
              v-if="option.group && option.group !== matches[index - 1]?.group"
              class="app-select__group"
              role="presentation"
            >
              {{ option.group }}
            </li>
            <li
              :id="`${listId}-${index}`"
              role="option"
              class="app-select__option"
              :class="{
                'is-active': index === active,
                'is-selected': isSelected(option),
                'is-disabled': option.disabled
              }"
              :aria-selected="isSelected(option)"
              :aria-disabled="option.disabled || undefined"
              @mousedown.prevent="pick(option)"
              @mouseenter="active = index"
            >
              <span class="app-select__text">
                <span class="app-select__label">{{ option.label }}</span>
                <span v-if="option.detail" class="app-select__detail">{{ option.detail }}</span>
              </span>
              <i v-if="isSelected(option)" class="fas fa-check app-select__check" aria-hidden="true"></i>
            </li>
          </template>
        </template>
      </ul>
    </Teleport>
  </div>
</template>

<script lang="ts">
// Each dropdown's list its own id, across every app on the page (useId
// starts again for each one): counted once here, not per dropdown.
let lastListId = 0
const nextListId = () => `app-select-${++lastListId}`
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useAttrs, watch, watchEffect } from 'vue'

export type AppSelectValue = string | number | boolean | null

export interface AppSelectOption {
  value: AppSelectValue
  label: string
  /** A second, quieter line under the label. */
  detail?: string
  /** Shown but can't be picked (a full group). */
  disabled?: boolean
  /** The heading it's listed under; options under one heading go together. */
  group?: string
}

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    modelValue?: AppSelectValue
    options: AppSelectOption[]
    id?: string
    /** Shown while nothing is chosen. */
    placeholder?: string
    emptyText?: string
    loading?: boolean
    disabled?: boolean
    /** A form with it can't be saved until something is chosen. */
    required?: boolean
    /** Typing in the box to search: by default, for lists of more than 10. */
    searchable?: boolean | 'auto'
    /** Small, as tall as a select (the default); large, as tall as the
     *  page's text boxes beside it. */
    size?: 'small' | 'large'
  }>(),
  {
    modelValue: null,
    id: undefined,
    placeholder: '',
    emptyText: 'No matches',
    loading: false,
    disabled: false,
    required: false,
    searchable: 'auto',
    size: 'small'
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: AppSelectValue]
  /** After a choice, as a select's change event. */
  change: [value: AppSelectValue]
}>()

// The page's classes, styles and data-test draw and name the box; the rest
// (aria-*, title, name) go to the field, as they would on a select.
const attrs = useAttrs()
const isBoxAttr = (key: string) => key === 'class' || key === 'style' || key.startsWith('data-')
const boxAttrs = computed(() => Object.fromEntries(Object.entries(attrs).filter(([key]) => isBoxAttr(key))))
const inputAttrs = computed(() => Object.fromEntries(Object.entries(attrs).filter(([key]) => !isBoxAttr(key))))

const listId = nextListId()
const boxRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)
const listRef = ref<HTMLElement | null>(null)
const validatorRef = ref<HTMLInputElement | null>(null)
const open = ref(false)
const query = ref('')
// The highlighted choice, for the arrow keys and Enter.
const active = ref(-1)

const canSearch = computed(() =>
  props.searchable === 'auto' ? props.options.length > 10 : props.searchable
)

const isSelected = (option: AppSelectOption) => option.value === props.modelValue
const selectedLabel = computed(() => props.options.find(isSelected)?.label ?? '')
const hasValue = computed(
  () => props.modelValue !== null && props.modelValue !== undefined && props.modelValue !== ''
)

watchEffect(() => {
  validatorRef.value?.setCustomValidity?.(
    props.required && !hasValue.value ? 'Please select an item in the list.' : ''
  )
})

// The choices with what's typed in their label, second line or heading.
const matches = computed(() => {
  const typed = query.value.trim().toLowerCase()
  if (!typed) return props.options
  return props.options.filter((option) =>
    `${option.label} ${option.detail ?? ''} ${option.group ?? ''}`.toLowerCase().includes(typed)
  )
})

const firstPickable = (from: number, step: 1 | -1) => {
  for (let index = from; index >= 0 && index < matches.value.length; index += step) {
    if (!matches.value[index].disabled) return index
  }
  return -1
}

// --- where the list goes: under the box, or over it with no room below ------

const listStyle = ref<Record<string, string>>({})

const place = () => {
  const box = boxRef.value
  if (!box || !open.value) return
  const rect = box.getBoundingClientRect()
  const list = listRef.value
  const height = list?.offsetHeight ?? 0
  const width = list?.offsetWidth ?? rect.width
  const below = window.innerHeight - rect.bottom
  const upward = height + 8 > below && rect.top > below
  const left = Math.max(8, Math.min(rect.left, window.innerWidth - 8 - width))
  listStyle.value = {
    left: `${left}px`,
    top: upward ? 'auto' : `${rect.bottom + 4}px`,
    bottom: upward ? `${window.innerHeight - rect.top + 4}px` : 'auto',
    minWidth: `${rect.width}px`,
    maxWidth: `min(${Math.max(rect.width, 384)}px, calc(100vw - 16px))`,
    // Its text as the box's, as a select's list is.
    fontSize: getComputedStyle(box).fontSize
  }
}

const follow = () => place()
watch(open, (isOpen) => {
  if (isOpen) {
    window.addEventListener('scroll', follow, true)
    window.addEventListener('resize', follow)
    nextTick(() => {
      place()
      // Measured once drawn, so it can open upward or keep on screen.
      nextTick(place)
    })
  } else {
    window.removeEventListener('scroll', follow, true)
    window.removeEventListener('resize', follow)
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', follow, true)
  window.removeEventListener('resize', follow)
})

const showActive = () =>
  nextTick(() => document.getElementById(`${listId}-${active.value}`)?.scrollIntoView?.({ block: 'nearest' }))

// --- opening, choosing, closing ------------------------------------------------

const openList = () => {
  if (open.value || props.disabled) return
  open.value = true
  query.value = ''
  const selected = matches.value.findIndex(isSelected)
  active.value = selected >= 0 ? selected : firstPickable(0, 1)
  showActive()
}

const closeList = () => {
  open.value = false
  query.value = ''
}

// A click on the box opens or closes it; one in a field to type in opens it
// and leaves the caret where it was put.
const onBoxMousedown = (event: MouseEvent) => {
  if (props.disabled || event.button !== 0) return
  // A choice clicked in its own list (in the box when Teleport is stubbed)
  // is the list's, whatever Vue's same-moment check let through.
  if (listRef.value?.contains(event.target as Node)) return
  if (event.target === inputRef.value && canSearch.value) {
    openList()
    return
  }
  event.preventDefault()
  inputRef.value?.focus()
  if (open.value) closeList()
  else openList()
}

const onInput = (event: Event) => {
  query.value = (event.target as HTMLInputElement).value
  open.value = true
  active.value = firstPickable(0, 1)
}

const pick = (option: AppSelectOption) => {
  if (option.disabled) return
  closeList()
  if (option.value === props.modelValue) return
  emit('update:modelValue', option.value)
  emit('change', option.value)
}

// A letter jumps to the next choice starting with it, as in a select.
const jumpTo = (letter: string) => {
  const count = matches.value.length
  for (let step = 1; step <= count; step += 1) {
    const index = (active.value + step) % count
    const option = matches.value[index]
    if (!option.disabled && option.label.toLowerCase().startsWith(letter)) {
      active.value = index
      showActive()
      return
    }
  }
}

const onKeydown = (event: KeyboardEvent) => {
  const key = event.key
  if (key === 'ArrowDown' || key === 'ArrowUp') {
    event.preventDefault()
    if (!open.value) {
      openList()
      return
    }
    const step = key === 'ArrowDown' ? 1 : -1
    const next = firstPickable(active.value + step, step)
    if (next >= 0) active.value = next
    showActive()
  } else if (key === 'Home' || key === 'End') {
    if (!open.value) return
    event.preventDefault()
    active.value = key === 'Home' ? firstPickable(0, 1) : firstPickable(matches.value.length - 1, -1)
    showActive()
  } else if (key === 'Enter' || (key === ' ' && !canSearch.value)) {
    // Opens or picks, rather than saving the form.
    event.preventDefault()
    if (!open.value) {
      openList()
      return
    }
    const option = matches.value[active.value]
    if (option) pick(option)
  } else if (key === 'Escape' && open.value) {
    // Closes the list, not the sheet it's in.
    event.preventDefault()
    event.stopPropagation()
    closeList()
  } else if (!canSearch.value && open.value && key.length === 1 && /\S/.test(key)) {
    jumpTo(key.toLowerCase())
  }
}
</script>

<style scoped>
/* The box as a select is drawn when the page doesn't draw it. No
   specificity, so a page's own classes and styles win. */
:where(.app-select) {
  display: inline-block;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
  color: var(--teal);
  font: inherit;
  vertical-align: middle;
}

.app-select {
  position: relative;
  box-sizing: border-box;
  /* The text in the middle of a box given a fixed height, as in a select. */
  align-content: center;
  cursor: pointer;
}

.app-select.is-disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

/* The focus ring a select has. */
.app-select:has(.app-select__input:focus-visible) {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

/* The field: the box's text, with room on the right for the arrow. */
.app-select__input {
  display: block;
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  margin: 0;
  padding: 0 1.25rem 0 0;
  border: 0;
  outline: none;
  box-shadow: none;
  background: transparent;
  color: inherit;
  font: inherit;
  /* A select's line height, not the page's 1.6, so the box is as tall as one. */
  line-height: normal;
  text-overflow: ellipsis;
}

/* Large, or the shared text box (app-input): the page's line height, as
   the text boxes beside it have, so it's as tall as they are. */
.app-select.is-large .app-select__input,
.app-select.app-input .app-select__input {
  line-height: inherit;
}

.app-select__input.is-static {
  cursor: pointer;
  caret-color: transparent;
}

.app-select.is-disabled .app-select__input {
  cursor: not-allowed;
}

.app-select__input::placeholder {
  color: var(--text-muted);
  opacity: 1;
}

.app-select__arrow {
  position: absolute;
  top: 50%;
  right: 0.6rem;
  color: var(--text-muted);
  font-size: 0.7em;
  pointer-events: none;
  transform: translateY(-50%);
  transition: transform 160ms ease;
}

.app-select.is-open .app-select__arrow {
  transform: translateY(-50%) rotate(180deg);
}

.app-select__sizer {
  display: block;
  height: 0;
  overflow: hidden;
  padding-right: 1.25rem;
  visibility: hidden;
  white-space: nowrap;
}

.app-select__sizer > span {
  display: block;
}

.app-select__validator {
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 1px;
  height: 1px;
  padding: 0;
  border: 0;
  opacity: 0;
  pointer-events: none;
}

/* The list, over the page. */
.app-select__list {
  position: fixed;
  z-index: 2200;
  box-sizing: border-box;
  width: max-content;
  max-height: 16rem;
  margin: 0;
  padding: 0.25rem;
  overflow-y: auto;
  list-style: none;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
  box-shadow: 0 6px 18px var(--shadow);
  font-family: inherit;
}

.app-select__option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  color: var(--teal);
  cursor: pointer;
}

.app-select__option.is-active {
  background: var(--light-green);
}

.app-select__option.is-selected .app-select__label {
  font-weight: 600;
}

.app-select__option.is-disabled {
  color: var(--text-muted);
  cursor: not-allowed;
}

.app-select__option.is-disabled.is-active {
  background: transparent;
}

.app-select__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.app-select__label,
.app-select__detail {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-select__detail {
  color: var(--text-muted);
  font-size: 0.85em;
}

.app-select__check {
  flex-shrink: 0;
  color: var(--dark-green);
  font-size: 0.8em;
}

.app-select__group {
  padding: 0.4rem 0.5rem 0.15rem;
  color: var(--text-muted);
  font-size: 0.75em;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.app-select__empty {
  padding: 0.3rem 0.5rem;
  color: var(--text-muted);
}
</style>
