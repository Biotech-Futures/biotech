<template>
  <div
    v-if="isSupervisorMode"
    class="admin-users__actions admin-users__actions--with-search"
  >
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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    isSupervisorMode: boolean
    search?: string
  }>(),
  {
    search: ''
  }
)

const emit = defineEmits<{
  (e: 'update:search', value: string): void
}>()

const search = computed({
  get: () => props.search,
  set: (value: string) => emit('update:search', value)
})
</script>

<style scoped>
.admin-users__actions--with-search {
  display: flex;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.admin-users__search {
  position: relative;
  width: 100%;
  flex: 0 1 320px;
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
  .admin-users__actions--with-search {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>