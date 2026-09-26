<template>
  <div class="admin-view-bulk-bar">
    <div class="admin-view-bulk-bar__buttons">
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
    </div>

    <p v-if="!canAssign" class="admin-view-bulk-bar__hint">
      ⓘ Group assignment is only available when all selected users are students.
    </p>
  </div>
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

<style scoped>
/* A single wrapper (one flex item inside the parent BulkActionsBar's actions
   slot) so the button row's own layout never depends on whether the hint is
   showing: the buttons always render first, identically, in their own row;
   the hint is a second, separate row underneath, only added when invalid.
   align-items: flex-end keeps both rows right-aligned as a unit, matching the
   buttons already being the rightmost content in the bar. Normal document
   flow (not absolute positioning) so the hint stays inside the bordered card
   like the rest of the bar's content, instead of overflowing past its edge. */
.admin-view-bulk-bar {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.35rem;
}

.admin-view-bulk-bar__buttons {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
}

/* Muted, plain informational text — matches StudentAssignDialog's
   .assign-dialog__hint treatment (no border/background/icon), not an error. */
.admin-view-bulk-bar__hint {
  margin: 0;
  max-width: 100%;
  color: var(--text-muted);
  font-size: 0.8rem;
  text-align: right;
}
</style>
