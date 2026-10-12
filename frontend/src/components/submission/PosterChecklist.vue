<template>
  <div
    class="poster-checklist"
    role="group"
    aria-labelledby="poster-checklist-title"
    data-testid="poster-checklist"
  >
    <div class="poster-checklist__head">
      <p id="poster-checklist-title" class="poster-checklist__hint">
        {{ ready ? 'Confirm each item on your poster before you submit.' : 'Upload your poster, then confirm each item.' }}
      </p>
      <span v-if="ready" class="poster-checklist__count">{{ tickedCount }} of {{ ITEMS.length }} confirmed</span>
    </div>

    <ul class="poster-checklist__list">
      <li v-for="item in ITEMS" :key="item.key">
        <label class="poster-checklist__label" :class="{ 'is-disabled': !ready || disabled }">
          <input
            :id="`checklist-${item.key}`"
            type="checkbox"
            :checked="Boolean(ticks[item.key])"
            :disabled="!ready || disabled"
            @change="emit('toggle', item.key, ($event.target as HTMLInputElement).checked)"
          />
          {{ item.label }}
        </label>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/** The five things a team confirms about its poster; detected items arrive ticked, and every tick is the team's to change. */
const props = defineProps<{ ticks: Record<string, boolean>; ready: boolean; disabled: boolean }>()
const emit = defineEmits<{ toggle: [item: string, ticked: boolean] }>()

const ITEMS = [
  { key: 'supervisor_email', label: 'Supervisor Email' },
  { key: 'btf_logo', label: 'BIOTech Futures Logo' },
  { key: 'school_logo', label: 'School Logo' },
  { key: 'team_code', label: 'Team Code' },
  { key: 'page_size', label: 'Page Size (A2 Portrait)' }
]

const tickedCount = computed(() => ITEMS.filter((item) => props.ticks[item.key]).length)
</script>

<style scoped>
.poster-checklist {
  margin-bottom: 1.5rem;
}

.poster-checklist__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
}

.poster-checklist__hint {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--muted);
}

.poster-checklist__count {
  font-size: 0.875rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.poster-checklist__list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 0.75rem 0 0;
  padding: 0;
  list-style: none;
}

.poster-checklist__label {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--body-text);
  cursor: pointer;
}

.poster-checklist__label input {
  width: 0.95rem;
  height: 0.95rem;
  margin: 0;
  flex-shrink: 0;
  accent-color: var(--accent);
  cursor: inherit;
}

.poster-checklist__label.is-disabled {
  color: var(--muted);
  cursor: default;
}
</style>
