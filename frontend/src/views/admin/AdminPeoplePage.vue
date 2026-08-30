<template>
  <div class="content-area admin-people">
    <div class="page-head">
      <div>
        <h1>People</h1>
        <p class="page-subtitle">Manage accounts for every class of user.</p>
      </div>
    </div>

    <div class="people-tabs" role="tablist" aria-label="People">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.key"
        class="people-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <AdminUsersView v-if="activeTab === 'users'" title="Users" noun="user" />
    <AdminStudentsView v-else-if="activeTab === 'students'" />
    <AdminMentorsView v-else-if="activeTab === 'mentors'" />
    <AdminSupervisorsView v-else />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AdminUsersView from '@/views/admin/AdminUsersView.vue'
import AdminStudentsView from '@/views/admin/AdminStudentsView.vue'
import AdminMentorsView from '@/views/admin/AdminMentorsView.vue'
import AdminSupervisorsView from '@/views/admin/AdminSupervisorsView.vue'

const tabs = [
  { key: 'users', label: 'Users' },
  { key: 'students', label: 'Students' },
  { key: 'mentors', label: 'Mentors' },
  { key: 'supervisors', label: 'Supervisors' }
] as const

const activeTab = ref<(typeof tabs)[number]['key']>('users')
</script>

<style scoped>
.people-tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.3rem;
  margin-bottom: 1.25rem;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 999px;
  box-shadow: 0 1px 2px var(--shadow);
}

.people-tab {
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: 999px;
  padding: 0.5rem 1.1rem;
  font-weight: 600;
  font-size: 0.92rem;
  cursor: pointer;
  transition: color 0.18s ease, background-color 0.18s ease;
}

.people-tab:hover:not(.active) {
  color: var(--charcoal);
  background: var(--light-green);
}

.people-tab.active {
  background: var(--dark-green);
  color: var(--white);
  box-shadow: 0 1px 3px rgba(1, 113, 81, 0.3);
}

.people-tab:focus-visible {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}
</style>