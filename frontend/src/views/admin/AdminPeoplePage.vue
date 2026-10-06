<template>
  <div class="content-area admin-people">
    <div class="page-head">
        <h1>People</h1>
        <p class="people-subtitle">
          Manage accounts for every class of user.
        </p>
    </div>

    <div class="people-toolbar">
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

      <div class="people-toolbar__actions">
        <button
          v-if="activeTab === 'students'"
          type="button"
          class="btn btn-outline"
          :disabled="activeImportLoading"
          @click="openActiveImport"
        >
          <i class="fas fa-file-arrow-up" aria-hidden="true"></i>
          <span>Import Students CSV</span>
        </button>
        <button
          v-if="activeTab === 'mentors'"
          type="button"
          class="btn btn-outline"
          :disabled="activeImportLoading"
          @click="openActiveImport"
        >
          <i class="fas fa-file-arrow-up" aria-hidden="true"></i>
          <span>Import Mentors CSV</span>
        </button>
        <button
          v-if="activeAddLabel"
          type="button"
          class="btn btn-primary"
          :disabled="activeAddLoading"
          @click="openActiveCreate"
        >
          <i class="fas fa-plus" aria-hidden="true"></i>
          <span>{{ activeAddLabel }}</span>
        </button>
      </div>
    </div>

    <AdminUsersView v-if="activeTab === 'users'" ref="usersView" title="Users" noun="user" />
    <AdminStudentsView v-else-if="activeTab === 'students'" ref="studentsView" />
    <AdminMentorsView v-else-if="activeTab === 'mentors'" ref="mentorsView" />
    <AdminSupervisorsView v-else ref="supervisorsView" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
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

const usersView = ref<InstanceType<typeof AdminUsersView> | null>(null)
const studentsView = ref<InstanceType<typeof AdminStudentsView> | null>(null)
const supervisorsView = ref<InstanceType<typeof AdminSupervisorsView> | null>(null)
const mentorsView = ref<InstanceType<typeof AdminMentorsView> | null>(null)

interface CreateView {
  openCreate: () => void
  loading: boolean
}

const ADD_LABELS: Partial<Record<(typeof tabs)[number]['key'], string>> = {
  users: 'Add User',
  students: 'Add Student',
  supervisors: 'Add Supervisor'
}

const activeAddLabel = computed(() => ADD_LABELS[activeTab.value] ?? null)

const activeCreateView = computed<CreateView | null>(() => {
  switch (activeTab.value) {
    case 'users':
      return usersView.value
    case 'students':
      return studentsView.value
    case 'supervisors':
      return supervisorsView.value
    default:
      return null
  }
})

const activeAddLoading = computed(() => activeCreateView.value?.loading ?? false)

const activeImportLoading = computed(() =>
  activeTab.value === 'mentors'
    ? (mentorsView.value?.loading ?? false)
    : activeTab.value === 'students'
      ? (studentsView.value?.loading ?? false)
      : false
)

const openActiveCreate = () => {
  activeCreateView.value?.openCreate()
}

const openActiveImport = () => {
  if (activeTab.value === 'students') studentsView.value?.openStudentImport()
  else if (activeTab.value === 'mentors') mentorsView.value?.openMentorImport()
}
</script>

<style scoped>
.people-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.people-toolbar .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.people-subtitle {
  color: var(--text-muted);
  margin: -0.5rem 0 0.5rem;
}

.people-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
}

.people-tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.3rem;
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