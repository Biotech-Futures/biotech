<template>
  <span v-if="selectAllMatching" class="admin-users__select-all-hint">
    All matching {{ pluralNoun }} selected
  </span>
  <template v-if="isStudentMode">
    <span :title="groupActionsHint">
      <button
        type="button"
        class="btn btn-sm btn-outline"
        :disabled="busy || selectAllMatching"
        @click="emit('assign')"
      >
        <i class="fas fa-users" aria-hidden="true"></i>
        Assign to group
      </button>
    </span>
    <span :title="removeGroupActionsHint">
      <button
        type="button"
        class="btn btn-sm btn-outline"
        :disabled="busy || selectAllMatching || groupedCount === 0"
        @click="emit('remove')"
      >
        <i class="fas fa-user-minus" aria-hidden="true"></i>
        Remove from group{{ groupedCount > 0 ? ` (${groupedCount})` : '' }}
      </button>
    </span>
  </template>
  <button type="button" class="btn btn-sm btn-outline" :disabled="busy" @click="emit('activate')">
    <i class="fas fa-user-check" aria-hidden="true"></i>
    Activate
  </button>
  <button type="button" class="btn btn-sm btn-outline" :disabled="busy" @click="emit('deactivate')">
    <i class="fas fa-user-xmark" aria-hidden="true"></i>
    Deactivate
  </button>
  <button
    v-if="!isSupervisorMode"
    type="button"
    class="btn btn-sm btn-danger"
    :disabled="busy"
    @click="emit('delete')"
  >
    <i class="fas fa-trash-can" aria-hidden="true"></i>
    Delete
  </button>
</template>

<script setup lang="ts">
defineProps<{
  busy: boolean
  isStudentMode: boolean
  isSupervisorMode: boolean
  selectAllMatching: boolean
  groupActionsHint?: string
  removeGroupActionsHint?: string
  groupedCount: number
  pluralNoun: string
}>()

const emit = defineEmits<{
  (e: 'assign'): void
  (e: 'remove'): void
  (e: 'activate'): void
  (e: 'deactivate'): void
  (e: 'delete'): void
}>()
</script>

<style scoped>
.admin-users__select-all-hint {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--dark-green);
}
</style>