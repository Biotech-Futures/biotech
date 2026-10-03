<template>
  <!-- A Hide / Show switch: both words always there, the knob behind the one
       that's on. Asks to change (``change``) rather than changing itself, so
       the page can confirm first; anything in the slot shows below it. -->
  <label class="hide-show" :class="{ 'is-disabled': disabled }">
    <input
      type="checkbox"
      class="sr-only"
      role="switch"
      :checked="on"
      :disabled="disabled"
      :aria-label="label"
      @change="ask"
    />
    <span class="hide-show__track" aria-hidden="true">
      <span class="hide-show__knob"></span>
      <span class="hide-show__text hide-show__text--hide">Hide</span>
      <span class="hide-show__text hide-show__text--show">Show</span>
    </span>
    <slot />
  </label>
</template>

<script setup lang="ts">
const props = defineProps<{
  /** Showing. */
  on: boolean
  disabled?: boolean
  /** What it shows, for screen readers, e.g. "Show marks to students". */
  label: string
}>()

const emit = defineEmits<{ (e: 'change', on: boolean): void }>()

// It stays as it is until the page says otherwise.
const ask = (event: Event) => {
  const input = event.target as HTMLInputElement
  const wanted = input.checked
  input.checked = props.on
  emit('change', wanted)
}
</script>

<style scoped>
.hide-show {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.75rem;
  cursor: pointer;
}

.hide-show.is-disabled {
  cursor: not-allowed;
}

.hide-show__track {
  position: relative;
  display: inline-grid;
  grid-template-columns: 1fr 1fr;
  align-items: center;
  width: 7.5rem;
  height: 2rem;
  border-radius: 999px;
  background: #d1d5db;
  transition: background-color 0.15s ease;
}

.hide-show input:checked + .hide-show__track {
  background: var(--dark-green);
}

.hide-show input:disabled + .hide-show__track {
  opacity: 0.5;
}

.hide-show input:focus-visible + .hide-show__track {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

.hide-show__knob {
  position: absolute;
  top: 0.2rem;
  bottom: 0.2rem;
  left: 0.2rem;
  width: calc(50% - 0.2rem);
  border-radius: 999px;
  background: #ffffff;
  transition: transform 0.15s ease;
}

.hide-show input:checked + .hide-show__track .hide-show__knob {
  transform: translateX(100%);
}

/* The word the knob is behind reads bold and dark on white; the other is
   light on the track. */
.hide-show__text {
  position: relative;
  z-index: 1;
  text-align: center;
  font-size: 0.75rem;
  font-weight: 400;
  color: #9ca3af;
  transition: color 0.15s ease;
}

.hide-show__text--hide {
  font-weight: 700;
  color: var(--charcoal);
}

.hide-show input:checked + .hide-show__track .hide-show__text--hide {
  font-weight: 400;
  color: rgba(255, 255, 255, 0.5);
}

.hide-show input:checked + .hide-show__track .hide-show__text--show {
  font-weight: 700;
  color: var(--dark-green);
}
</style>
