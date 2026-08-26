<script setup lang="ts">
import { computed } from 'vue'
import { useAdminSummaryQuery } from '@/admin/api/summary'
import { apiErrorFromUnknown } from '@/utils/apiError'

const { data, isPending, isError, error, refetch } = useAdminSummaryQuery()

const errorMessage = computed(() =>
  isError.value ? apiErrorFromUnknown(error.value).message : '',
)

interface StatCard {
  label: string
  value: number
  icon: string
  /** Non-zero means an admin should probably act on it. */
  attention?: boolean
}

const cards = computed<StatCard[]>(() => {
  const summary = data.value
  if (!summary) return []
  return [
    { label: 'Active users', value: summary.active_users, icon: 'fas fa-user-check' },
    { label: 'Invited / pending', value: summary.invited_or_pending_users, icon: 'fas fa-envelope-open-text' },
    { label: 'Suspended / deactivated', value: summary.suspended_or_deactivated_users, icon: 'fas fa-user-slash' },
    { label: 'Active groups', value: summary.active_groups, icon: 'fas fa-users' },
    {
      label: 'Groups without mentor',
      value: summary.groups_without_mentor,
      icon: 'fas fa-user-clock',
      attention: summary.groups_without_mentor > 0,
    },
    {
      label: 'Unassigned match recommendations',
      value: summary.unassigned_match_recommendations,
      icon: 'fas fa-people-arrows',
      attention: summary.unassigned_match_recommendations > 0,
    },
    { label: 'Upcoming events', value: summary.upcoming_events, icon: 'fas fa-calendar' },
  ]
})
</script>

<template>
  <div>
    <h1 class="mb-4">Overview</h1>

    <v-progress-circular v-if="isPending" indeterminate color="primary" />

    <v-alert v-else-if="isError" type="error" variant="tonal">
      {{ errorMessage }}
      <template #append>
        <v-btn size="small" variant="text" @click="refetch()">Retry</v-btn>
      </template>
    </v-alert>

    <div v-else class="stat-grid">
      <v-card
        v-for="card in cards"
        :key="card.label"
        class="stat-card"
        :class="{ 'stat-card--attention': card.attention }"
        variant="outlined"
      >
        <div class="stat-value">{{ card.value }}</div>
        <div class="stat-label">
          <i :class="card.icon" aria-hidden="true"></i>
          <span>{{ card.label }}</span>
        </div>
      </v-card>
    </div>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
}

.stat-card {
  padding: 1rem 1.15rem;
}

.stat-card--attention {
  border-color: var(--warning);
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--dark-green);
  font-variant-numeric: tabular-nums;
}

.stat-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-muted);
  font-size: 0.88rem;
}
</style>
