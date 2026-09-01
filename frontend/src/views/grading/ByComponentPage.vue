<template>
  <div class="card by-component">
    <div class="card-header">
      <h3 class="card-title">Mark by component</h3>
    </div>
    <p class="by-component__hint">One component at a time, across every group.</p>
    <ul class="by-component__list">
      <li v-for="c in COMPONENTS" :key="c.code">
        <RouterLink :to="`/grading/components/${c.code}`" class="by-component__item">
          <span>{{ c.name }}</span>
          <i class="fas fa-chevron-right" aria-hidden="true"></i>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
// Component codes are hard-coded to match the backend seed migration; a proper
// admin-editable list can replace this once component CRUD lands.
const COMPONENTS: { code: string; name: string }[] = [
  { code: 'SAQ', name: 'Short Answer Questions' },
  { code: 'POSTER', name: 'A2 Poster' },
  { code: 'REPORT', name: 'Scientific Report' },
  { code: 'PROTOTYPE', name: 'Prototype' }
]
</script>

<style scoped>
.by-component {
  max-width: 36rem;
}

.by-component__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.by-component__list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0;
  padding: 0;
}

.by-component__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.6rem 0.85rem;
  font-size: 0.95rem;
  color: var(--charcoal);
  text-decoration: none;
  background: var(--surface-elevated);
  transition:
    border-color 0.15s ease,
    color 0.15s ease;
}

.by-component__item:hover {
  border-color: var(--dark-green);
  color: var(--dark-green);
}

.by-component__item i {
  font-size: 0.75rem;
  color: var(--text-muted);
}
</style>
