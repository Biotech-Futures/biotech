<template>
  <!-- A text box that offers suggestions as it's typed, in the site's
       dropdown list style; anything else can be typed too. Attributes
       (class, id, maxlength, data-test...) go on the box itself. -->
  <span class="app-suggest">
    <input
      v-bind="$attrs"
      :value="modelValue"
      autocomplete="off"
      role="combobox"
      aria-autocomplete="list"
      :aria-expanded="listShown"
      :aria-controls="listId"
      :aria-activedescendant="listShown && active >= 0 ? `${listId}-${active}` : undefined"
      @input="onInput"
      @focus="openList"
      @blur="listOpen = false"
      @keydown="onKeydown"
    />
    <ul v-if="listShown" :id="listId" class="app-suggest__list" role="listbox">
      <li
        v-for="(suggestion, index) in shownSuggestions"
        :id="`${listId}-${index}`"
        :key="suggestion"
        role="option"
        class="app-suggest__option"
        :class="{ 'is-active': index === active }"
        :aria-selected="index === active"
        @mousedown.prevent="pick(suggestion)"
        @mouseenter="active = index"
      >
        {{ suggestion }}
      </li>
    </ul>
  </span>
</template>

<script lang="ts">
// Each box's list its own id, however many are on the page.
let lastListId = 0
const nextListId = () => `app-suggest-${++lastListId}`
</script>

<script setup lang="ts">
import { computed, ref } from 'vue'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  modelValue: string
  /** Offered as it's typed: those holding what's typed (not just it). */
  suggestions: readonly string[]
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const listId = nextListId()
const listOpen = ref(false)
const active = ref(-1)
const shownSuggestions = computed(() => {
  const typed = props.modelValue.trim().toLowerCase()
  return props.suggestions.filter(
    (suggestion) => suggestion.toLowerCase().includes(typed) && suggestion.toLowerCase() !== typed,
  )
})
const listShown = computed(() => listOpen.value && shownSuggestions.value.length > 0)

const openList = () => {
  listOpen.value = true
  active.value = -1
}

const onInput = (event: Event) => {
  listOpen.value = true
  active.value = -1
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}

const pick = (suggestion: string) => {
  emit('update:modelValue', suggestion)
  listOpen.value = false
}

const onKeydown = (event: KeyboardEvent) => {
  const count = shownSuggestions.value.length
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    if (!count) return
    event.preventDefault()
    listOpen.value = true
    active.value = (active.value + (event.key === 'ArrowDown' ? 1 : -1) + count) % count
  } else if (event.key === 'Enter' && listShown.value && active.value >= 0) {
    event.preventDefault()
    pick(shownSuggestions.value[active.value]!)
  } else if (event.key === 'Escape' && listShown.value) {
    event.preventDefault()
    listOpen.value = false
  }
}
</script>

<style scoped>
.app-suggest {
  position: relative;
  display: block;
}

/* As wide as the shared box (app-input) in it, so its list is too. */
.app-suggest:has(> .app-input:not(.app-input--wide)) {
  max-width: var(--app-input-max-width);
}

/* As the site's dropdown lists (AppSelect's). */
.app-suggest__list {
  position: absolute;
  z-index: 20;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  box-sizing: border-box;
  max-height: 16rem;
  margin: 0;
  padding: 0.25rem;
  overflow-y: auto;
  list-style: none;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated, var(--white));
  box-shadow: 0 6px 18px var(--shadow, rgba(0, 0, 0, 0.12));
  font-weight: 400;
}

.app-suggest__option {
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  overflow: hidden;
  color: var(--teal);
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.app-suggest__option.is-active {
  background: var(--light-green);
}
</style>
