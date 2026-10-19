<template>
  <span class="log-level" :class="`log-level--${tone}`">{{ level || 'UNKNOWN' }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ level: string }>()

// The level's name is always shown, so the colour is never the only signal.
const tone = computed(() => {
  switch (props.level.toUpperCase()) {
    case 'CRITICAL':
    case 'ERROR':
      return 'danger'
    case 'WARNING':
      return 'warning'
    case 'INFO':
      return 'info'
    default:
      return 'muted'
  }
})
</script>

<style scoped>
/* A tinted pill in the theme's status colours, with the text in the
   theme's own colour so yellow never has to be read on white. */
.log-level {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border: 1px solid var(--log-level-colour);
  border-radius: 999px;
  background: color-mix(in srgb, var(--log-level-colour) 18%, transparent);
  color: var(--teal);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.log-level--danger {
  --log-level-colour: var(--danger);
}

.log-level--warning {
  --log-level-colour: var(--warning);
}

.log-level--info {
  --log-level-colour: var(--info);
}

.log-level--muted {
  --log-level-colour: var(--text-muted);
}
</style>
