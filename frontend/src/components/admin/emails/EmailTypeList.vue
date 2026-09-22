<template>
  <div class="email-type-list">
    <div class="email-type-list__search">
      <i class="fas fa-magnifying-glass" aria-hidden="true"></i>
      <input
        v-model="query"
        type="search"
        class="email-type-list__search-input"
        placeholder="Search emails"
        aria-label="Search email types"
      />
    </div>

    <p v-if="!filtered.length" class="email-type-list__empty">
      No emails match “{{ query }}”.
    </p>

    <ul v-else class="email-type-list__items">
      <li v-for="template in filtered" :key="template.key">
        <button
          type="button"
          class="email-type-list__item"
          :class="{ 'is-selected': template.key === selectedKey }"
          :aria-current="template.key === selectedKey ? 'true' : undefined"
          @click="emit('select', template.key)"
        >
          <span class="email-type-list__copy">
            <span class="email-type-list__name">
              {{ template.name }}
              <i
                v-if="template.locked"
                class="fas fa-lock email-type-list__lock"
                :title="`${template.name} is required and cannot be switched off`"
                aria-hidden="true"
              ></i>
            </span>
            <span class="email-type-list__description">{{ template.description }}</span>
          </span>
          <span
            class="email-type-list__status"
            :class="template.enabled ? 'is-on' : 'is-off'"
            :title="template.enabled ? 'Enabled' : 'Disabled'"
          >
            {{ template.enabled ? 'On' : 'Off' }}
          </span>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SystemEmailTemplate } from '@/utils/systemEmail'

const props = defineProps<{
  templates: SystemEmailTemplate[]
  selectedKey: string | null
}>()

const emit = defineEmits<{
  (e: 'select', key: string): void
}>()

const query = ref('')

const filtered = computed(() => {
  const term = query.value.trim().toLowerCase()
  if (!term) return props.templates
  return props.templates.filter(
    (template) =>
      template.name.toLowerCase().includes(term) ||
      template.description.toLowerCase().includes(term)
  )
})
</script>

<style scoped>
.email-type-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
}

.email-type-list__search {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  background: #ffffff;
  color: #9ca3af;
}

.email-type-list__search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  font-size: 0.875rem;
  color: #111827;
  background: transparent;
}

.email-type-list__empty {
  margin: 0;
  padding: 0.75rem;
  font-size: 0.8125rem;
  color: #6b7280;
}

.email-type-list__items {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.email-type-list__item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
  padding: 0.625rem 0.75rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  background: #ffffff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.email-type-list__item:hover {
  border-color: #bfdbfe;
  background: #f8fafc;
}

.email-type-list__item.is-selected {
  border-color: #2563eb;
  background: #eff6ff;
}

.email-type-list__copy {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  min-width: 0;
}

.email-type-list__name {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #111827;
}

.email-type-list__lock {
  font-size: 0.6875rem;
  color: #6b7280;
}

.email-type-list__description {
  font-size: 0.75rem;
  line-height: 1.4;
  color: #6b7280;
}

.email-type-list__status {
  flex-shrink: 0;
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.email-type-list__status.is-on {
  color: #047857;
  background: #d1fae5;
}

.email-type-list__status.is-off {
  color: #b91c1c;
  background: #fee2e2;
}
</style>
