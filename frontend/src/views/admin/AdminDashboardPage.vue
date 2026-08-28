<template>
  <div class="content-area admin-dashboard">
    <div class="admin-dashboard__header">
      <div>
        <h1 class="admin-dashboard__title">Admin Dashboard</h1>
        <p class="admin-dashboard__subtitle">
          {{ loading ? 'Loading admin data...' : 'Global overview' }}
        </p>
      </div>
      <button class="btn btn-outline admin-dashboard__refresh" :disabled="loading" @click="load">
        <i class="fas fa-rotate-right" aria-hidden="true"></i>
        <span>Refresh</span>
      </button>
    </div>

    <div
      v-if="error"
      class="card admin-dashboard__error"
      role="alert"
    >
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>{{ error }}</span>
    </div>

    <div class="admin-dashboard__widgets">
      <div v-for="widget in widgets" :key="widget.key" class="widget">
        <div class="widget-header">
          <span class="widget-title">{{ widget.label }}</span>
          <i class="fas" :class="widget.icon" :style="{ color: widget.color }" aria-hidden="true"></i>
        </div>
        <div class="widget-value">{{ displayValue(widget.key) }}</div>
        <div
          v-if="widget.footer"
          class="widget-footer"
          :class="{ 'admin-dashboard__widget-footer--warn': widget.footer.warn }"
        >
          <span>{{ widget.footer.text }}</span>
        </div>
      </div>
    </div>

    <div class="admin-dashboard__sections">
      <section class="card" aria-labelledby="quick-links-title">
        <h2 id="quick-links-title" class="card-title">Manage</h2>
        <div class="admin-dashboard__quick-links">
          <RouterLink
            v-for="link in quickLinks"
            :key="link.to"
            :to="link.to"
            class="admin-dashboard__quick-link"
          >
            <i class="fas" :class="link.icon" aria-hidden="true"></i>
            <span>{{ link.label }}</span>
          </RouterLink>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchAdminSummary } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'

const loading = ref(false)
const error = ref('')
const summary = ref<Record<string, number>>({})

const widgets = [
  {
    key: 'total_users',
    label: 'Total Users',
    icon: 'fa-users',
    color: 'var(--eucalypt)',
    footer: { text: 'Combined active, invited/pending, suspended' }
  },
  {
    key: 'active_users',
    label: 'Active Users',
    icon: 'fa-user-check',
    color: 'var(--dark-green)',
    footer: { text: 'Active accounts' }
  },
  {
    key: 'active_groups',
    label: 'Active Groups',
    icon: 'fa-layer-group',
    color: 'var(--mint-green)',
    footer: {
      text: 'Group count',
      warn: false
    }
  },
  {
    key: 'groups_without_mentor',
    label: 'Groups Without Mentor',
    icon: 'fa-user-slash',
    color: 'var(--air-force-blue)',
    footer: { text: 'Needs a mentor assigned' }
  },
  {
    key: 'unassigned_match_recommendations',
    label: 'Pending Matches',
    icon: 'fa-user-tie',
    color: 'var(--air-force-blue)',
    footer: {
      text: 'Recommendations awaiting assignment',
      warn: false
    }
  },
  {
    key: 'upcoming_events',
    label: 'Upcoming Events',
    icon: 'fa-graduation-cap',
    color: 'var(--yellow)',
    footer: { text: 'Coming soon' }
  },
  {
    key: 'invited_or_pending_users',
    label: 'Invited / Pending',
    icon: 'fa-hourglass-half',
    color: 'var(--warning)',
    footer: {
      text: 'Accounts yet to activate',
      warn: false
    }
  },
  {
    key: 'suspended_or_deactivated_users',
    label: 'Suspended / Deactivated',
    icon: 'fa-user-xmark',
    color: 'var(--danger)',
    footer: {
      text: 'Accounts currently disabled',
      warn: false
    }
  }
]

const quickLinks = [
  { to: '/admin/users', label: 'Users', icon: 'fa-users' },
  { to: '/admin/groups', label: 'Groups', icon: 'fa-layer-group' },
  { to: '/admin/matching', label: 'Matching', icon: 'fa-user-tie' },
  { to: '/admin/events', label: 'Events', icon: 'fa-calendar' },
  { to: '/admin/resources', label: 'Resources', icon: 'fa-book' },
  { to: '/admin/announcements', label: 'Announcements', icon: 'fa-bullhorn' },
  { to: '/admin/mentors', label: 'Mentors', icon: 'fa-user-graduate' },
  { to: '/admin/tasks', label: 'Tasks', icon: 'fa-list-check' }
]

const totalUsers = computed(() => {
  return (
    Number(summary.value.active_users || 0) +
    Number(summary.value.invited_or_pending_users || 0) +
    Number(summary.value.suspended_or_deactivated_users || 0)
  )
})

const displayValue = (key: string) => {
  if (key === 'total_users') return totalUsers.value
  return Number(summary.value[key] || 0)
}

const load = async () => {
  loading.value = true
  error.value = ''

  try {
    const data = await fetchAdminSummary()
    const normalized: Record<string, number> = {}
    for (const key of Object.keys(data)) {
      normalized[key] = Number(data[key] || 0)
    }
    summary.value = normalized
  } catch (loadError) {
    logApiError('admin.summary', loadError)
    error.value =
      loadError instanceof Error
        ? loadError.message
        : 'Admin summary could not be loaded right now.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.admin-dashboard__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}

.admin-dashboard__title {
  margin: 0 0 0.25rem;
}

.admin-dashboard__subtitle {
  margin: 0;
  color: var(--text-muted);
}

.admin-dashboard__refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-dashboard__error {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  padding: 1rem 1.25rem;
  color: var(--danger);
  border-left: 4px solid var(--danger);
  background-color: rgba(220, 53, 69, 0.06);
}

.admin-dashboard__widgets {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.25rem;
  margin-bottom: 2rem;
}

.admin-dashboard__widget-footer--warn {
  color: #856404;
}

.admin-dashboard__sections .card {
  margin-bottom: 0;
}

.admin-dashboard__quick-links {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 0.75rem;
}

.admin-dashboard__quick-link {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.85rem 1rem;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  color: var(--charcoal);
  text-decoration: none;
  font-weight: 600;
  transition:
    background-color 0.18s ease,
    border-color 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
}

.admin-dashboard__quick-link:hover,
.admin-dashboard__quick-link:focus-visible {
  border-color: var(--dark-green);
  background-color: var(--light-green);
  color: var(--dark-green);
  transform: translateY(-1px);
}

.admin-dashboard__quick-link i {
  width: 20px;
  text-align: center;
  color: var(--dark-green);
}

@media (max-width: 480px) {
  .admin-dashboard__quick-links {
    grid-template-columns: 1fr;
  }
}
</style>
