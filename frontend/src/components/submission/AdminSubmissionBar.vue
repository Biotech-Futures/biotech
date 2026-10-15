<template>
  <div class="admin-bar" :class="{ 'is-editing': editing }" role="region" aria-label="Admin view" data-testid="admin-bar">
    <div class="admin-bar__summary">
      <p class="admin-bar__title">
        <strong class="admin-bar__team">{{ team }}</strong>
        <span class="admin-bar__mode">{{ editing ? 'Editing as admin' : 'Admin view' }}</span>
        <span v-if="editing && dirty" class="admin-bar__unsaved">Unsaved changes</span>
      </p>
      <p class="admin-bar__facts">
        <span><span class="admin-bar__key">Entry</span> {{ entry }}</span>
        <span><span class="admin-bar__key">Students</span> {{ students }}</span>
      </p>
    </div>

    <div class="admin-bar__actions">
      <button
        v-if="!editing"
        type="button"
        class="btn btn-outline btn-sm"
        data-testid="admin-edit"
        :disabled="busy"
        @click="emit('edit')"
      >
        Edit
      </button>
      <template v-else>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          :data-testid="dirty ? 'admin-discard' : 'admin-done'"
          :disabled="busy"
          @click="dirty ? emit('discard') : emit('done')"
        >
          {{ dirty ? 'Discard' : 'Done' }}
        </button>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          data-testid="admin-save"
          :disabled="busy || !dirty"
          @click="emit('save')"
        >
          Save
        </button>
        <button
          type="button"
          class="btn btn-primary btn-sm"
          data-testid="admin-submit"
          :disabled="busy"
          @click="emit('submit')"
        >
          Submit
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
/** An admin's own controls for a team's entry: view by default, and nothing reaches the team until Save or Submit. */
defineProps<{ team: string; entry: string; students: string; editing: boolean; dirty: boolean; busy: boolean }>()
const emit = defineEmits<{ edit: []; save: []; submit: []; discard: []; done: [] }>()
</script>

<style scoped>
/* Laid out like the team's status line, and kept in view so the actions stay to hand. */
.admin-bar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem 1.5rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
  padding: 0.75rem 0.9rem;
  border-bottom: 1px solid var(--panel-border);
  background: var(--bg-light);
}

.admin-bar.is-editing {
  border-bottom-color: var(--accent);
}

.admin-bar__title {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin: 0;
}

.admin-bar__team {
  font-size: 1rem;
  font-weight: 700;
  color: var(--body-text);
}

.admin-bar__mode {
  font-size: 0.875rem;
  color: var(--muted);
}

.is-editing .admin-bar__mode {
  font-weight: 600;
  color: var(--accent);
}

.admin-bar__unsaved {
  font-size: 0.875rem;
  color: var(--accent);
}

.admin-bar__unsaved::before {
  content: '· ';
}

.admin-bar__facts {
  display: flex;
  gap: 0.4rem 1.25rem;
  flex-wrap: wrap;
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
  color: var(--muted);
}

.admin-bar__key {
  margin-right: 0.3rem;
  font-weight: 600;
  color: var(--body-text);
}

.admin-bar__actions {
  display: flex;
  gap: 0.5rem;
}
</style>
