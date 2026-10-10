<template>
  <Transition name="typing-fade">
    <p v-if="label" class="typing-indicator" role="status">{{ label }}</p>
  </Transition>
</template>

<script setup lang="ts">
/** naming the teammates typing in a field; nothing when nobody is. */
import { computed } from 'vue'
import { typingLabel } from '@/composables/useLiveRoom'

const props = defineProps<{ names: string[] }>()
const label = computed(() => typingLabel(props.names))
</script>

<style scoped>
.typing-indicator {
  margin: 0.3rem 0 0 auto;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.typing-fade-enter-active,
.typing-fade-leave-active {
  transition: opacity 0.15s ease;
}

.typing-fade-enter-from,
.typing-fade-leave-to {
  opacity: 0;
}
</style>
