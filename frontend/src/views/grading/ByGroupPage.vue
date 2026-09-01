<template>
  <div class="card by-group">
    <div class="card-header">
      <h3 class="card-title">Mark by group</h3>
    </div>
    <p class="by-group__hint">Every component for a single group. Enter the group's ID.</p>
    <form class="by-group__form" @submit.prevent="open">
      <div class="by-group__input-wrap">
        <i class="fas fa-magnifying-glass by-group__search-icon" aria-hidden="true"></i>
        <input
          v-model="groupId"
          type="number"
          min="1"
          placeholder="Group ID"
          class="by-group__input"
          aria-label="Group ID"
        />
      </div>
      <button type="submit" class="btn btn-primary btn-sm">Open</button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const groupId = ref('')

const open = () => {
  const n = Number(groupId.value)
  if (!Number.isFinite(n) || n <= 0) return
  void router.push(`/grading/groups/${n}`)
}
</script>

<style scoped>
.by-group {
  max-width: 36rem;
}

.by-group__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.by-group__form {
  display: flex;
  gap: 0.5rem;
}

.by-group__input-wrap {
  position: relative;
  flex: 1;
}

.by-group__search-icon {
  position: absolute;
  left: 0.65rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.8rem;
  pointer-events: none;
}

.by-group__input {
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem 0.45rem 2rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.by-group__input:focus {
  outline: none;
  border-color: var(--dark-green);
}
</style>
