<template>
  <div class="group-search">
    <i class="fas fa-magnifying-glass group-search__icon" aria-hidden="true"></i>
    <input
      :value="modelValue"
      type="text"
      :placeholder="placeholder"
      :aria-label="placeholder"
      class="group-search__input"
      autocomplete="off"
      @input="onInput"
      @focus="isOpen = true"
      @blur="isOpen = false"
    />
    <ul v-if="isOpen && suggestions.length" class="group-search__list">
      <li v-for="s in suggestions" :key="s.group_id">
        <button type="button" class="group-search__option" @mousedown.prevent="pick(s)">
          <span class="group-search__name">{{ s.group_name }}</span>
          <span class="group-search__id">ID {{ s.group_id }}</span>
        </button>
      </li>
    </ul>
  </div>
</template>

<script lang="ts">
import { fetchFinalistCandidates, type FinalistCandidateRow } from '@/utils/gradingAPI'

// One directory fetch shared by every page that mounts this input — group
// ids and names are stable enough for a session.
let directory: Promise<FinalistCandidateRow[]> | null = null
const loadDirectory = () => {
  if (!directory) {
    directory = fetchFinalistCandidates()
      .then((r) => r.rows)
      .catch(() => {
        // Let a later mount retry instead of caching the failure; typing a
        // numeric ID still works with an empty directory.
        directory = null
        return []
      })
  }
  return directory
}
</script>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{ modelValue: string; placeholder?: string }>(), {
  placeholder: 'Group name or ID'
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'select', group: { id: number; name: string }): void
}>()

const rows = ref<FinalistCandidateRow[]>([])
const isOpen = ref(false)

onMounted(async () => {
  rows.value = await loadDirectory()
})

const suggestions = computed(() => {
  const raw = props.modelValue.trim().toLowerCase()
  if (!raw) return []
  const byId = /^\d+$/.test(raw)
  return rows.value
    .filter((r) =>
      byId
        ? String(r.group_id).startsWith(raw) || r.group_name.toLowerCase().includes(raw)
        : r.group_name.toLowerCase().includes(raw)
    )
    .slice(0, 8)
})

const onInput = (event: Event) => {
  isOpen.value = true
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}

const pick = (row: FinalistCandidateRow) => {
  isOpen.value = false
  emit('update:modelValue', row.group_name)
  emit('select', { id: row.group_id, name: row.group_name })
}

/** Digits are an ID; otherwise resolve a unique (exact-first) name match. */
const resolveId = (): number | null => {
  const raw = props.modelValue.trim()
  if (!raw) return null
  if (/^\d+$/.test(raw)) {
    const n = Number(raw)
    return Number.isFinite(n) && n > 0 ? n : null
  }
  const lower = raw.toLowerCase()
  const exact = rows.value.filter((r) => r.group_name.toLowerCase() === lower)
  if (exact.length === 1) return exact[0].group_id
  const partial = rows.value.filter((r) => r.group_name.toLowerCase().includes(lower))
  if (partial.length === 1) return partial[0].group_id
  return null
}

defineExpose({ resolveId })
</script>

<style scoped>
.group-search {
  position: relative;
  width: 100%;
}

.group-search__icon {
  position: absolute;
  left: 0.65rem;
  /* The dropdown is absolutely positioned, so the container is exactly the
     input's height and 50% centres on the input. */
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.8rem;
  pointer-events: none;
}

.group-search__input {
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem 0.45rem 2rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.group-search__input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.group-search__list {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  box-shadow: 0 6px 18px var(--shadow);
  list-style: none;
  margin: 0;
  padding: 0.25rem;
  max-height: 16rem;
  overflow-y: auto;
  z-index: 30;
}

.group-search__option {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.75rem;
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  border-radius: 4px;
  padding: 0.4rem 0.5rem;
  font: inherit;
  font-size: 0.88rem;
  color: var(--charcoal);
  cursor: pointer;
}

.group-search__option:hover {
  background: var(--light-green);
}

.group-search__id {
  color: var(--text-muted);
  font-size: 0.8rem;
  white-space: nowrap;
}
</style>
