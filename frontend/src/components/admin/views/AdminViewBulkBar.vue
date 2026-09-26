<template>
  <span :title="canAssign ? undefined : assignDisabledHint">
    <button
      type="button"
      class="btn btn-sm btn-outline"
      :disabled="busy || !canAssign"
      @click="emit('assign')"
    >
      <i class="fas fa-users" aria-hidden="true"></i>
      Assign to group
    </button>
  </span>
  <button type="button" class="btn btn-sm btn-outline" :disabled="busy" @click="emit('activate')">
    <i class="fas fa-user-check" aria-hidden="true"></i>
    Activate
  </button>
  <button type="button" class="btn btn-sm btn-outline" :disabled="busy" @click="emit('deactivate')">
    <i class="fas fa-user-xmark" aria-hidden="true"></i>
    Deactivate
  </button>
  <button type="button" class="btn btn-sm btn-danger" :disabled="busy" @click="emit('delete')">
    <i class="fas fa-trash-can" aria-hidden="true"></i>
    Delete
  </button>
</template>

<script setup lang="ts">
defineProps<{
  busy: boolean
  /** True only when the current selection is non-empty and every row is a student. */
  canAssign: boolean
}>()

const emit = defineEmits<{
  (e: 'assign'): void
  (e: 'activate'): void
  (e: 'deactivate'): void
  (e: 'delete'): void
}>()

const assignDisabledHint = 'Assign to Group is only available when all selected users are students'
</script>
