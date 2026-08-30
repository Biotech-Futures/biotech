<template>
  <div
    class="admin-users__actions"
    :class="{ 'admin-users__actions--with-search': isSupervisorMode }"
  >
    <template v-if="isSupervisorMode">
      <div class="admin-users__search">
        <i class="fas fa-magnifying-glass admin-users__search-icon" aria-hidden="true"></i>
        <input
          v-model="search"
          type="search"
          class="admin-users__search-input"
          placeholder="Search supervisors..."
          aria-label="Search supervisors"
        />
      </div>
    </template>
    <button v-if="isStudentMode" type="button" class="btn btn-outline" title="CSV import coming soon">
      <i class="fas fa-file-arrow-up" aria-hidden="true"></i>
      <span>Import Students CSV</span>
    </button>
    <button type="button" class="btn btn-primary" :disabled="loading" @click="emit('add')">
      <i class="fas fa-plus" aria-hidden="true"></i>
      <span>{{ addLabel }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    isSupervisorMode: boolean
    isStudentMode: boolean
    addLabel: string
    loading?: boolean
    search?: string
  }>(),
  {
    loading: false,
    search: ''
  }
)

const emit = defineEmits<{
  (e: 'update:search', value: string): void
  (e: 'add'): void
}>()

const search = computed({
  get: () => props.search,
  set: (value: string) => emit('update:search', value)
})
</script>

<style scoped>
.admin-users__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.admin-users__actions .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-users__actions--with-search {
  justify-content: space-between;
}

.admin-users__search {
  position: relative;
  width: 100%;
}

.admin-users__actions--with-search .admin-users__search {
  flex: 0 1 320px;
  width: auto;
}

.admin-users__search-input {
  width: 100%;
  height: 40px;
  padding: 0.5rem 0.75rem 0.5rem 2rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
}

.admin-users__search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.85rem;
  pointer-events: none;
}

@media (max-width: 640px) {
  .admin-users__actions,
  .admin-users__actions--with-search {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>