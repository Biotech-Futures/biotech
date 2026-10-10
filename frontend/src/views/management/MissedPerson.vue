<template>
  <!-- Someone a bulk email missed, as the server lists them: "amy@x.com
       (BTF07, Amy Chen)", with a button to copy the address. -->
  <span v-if="address" class="missed-person"
    >{{ address
    }}<button
      type="button"
      class="missed-person__copy"
      :title="copied ? 'Copied' : 'Copy email address'"
      :aria-label="copied ? 'Copied' : `Copy ${address}`"
      @click="copy"
    >
      <i :class="copied ? 'fas fa-check' : 'fas fa-copy'" aria-hidden="true"></i></button
    >{{ who.slice(address.length) }}</span
  >
  <span v-else>{{ who }}</span>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

const props = defineProps<{
  /** "amy@x.com (BTF07, Amy Chen)", or an older run's "(BTF07) Amy Chen". */
  who: string
}>()

/** The address it starts with, if it does. */
const address = computed(() => /^([^\s()]+@[^\s()]+) \(/.exec(props.who)?.[1] ?? '')

const copied = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

const copy = async () => {
  try {
    await navigator.clipboard.writeText(address.value)
  } catch {
    return
  }
  copied.value = true
  if (timer !== null) clearTimeout(timer)
  timer = setTimeout(() => (copied.value = false), 1500)
}

onBeforeUnmount(() => {
  if (timer !== null) clearTimeout(timer)
})
</script>

<style scoped>
.missed-person__copy {
  border: none;
  background: none;
  padding: 0 0.15rem;
  margin-left: 0.25rem;
  /* With the space before the group: about two spaces after the button. */
  margin-right: 2em;
  color: var(--text-muted);
  font-size: 0.8em;
  cursor: pointer;
  vertical-align: baseline;
}

.missed-person__copy:hover,
.missed-person__copy:focus-visible {
  color: var(--dark-green);
}
</style>
