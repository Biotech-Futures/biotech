<template>
  <div class="content-area admin-view-executed">
    <button type="button" class="btn btn-outline back-button" @click="goBack">
      <i class="fas fa-arrow-left" aria-hidden="true"></i> Back to Views
    </button>

    <div v-if="loading" class="detail-state" role="status" aria-live="polite">
      <span class="loading"></span>
      <span>Loading view...</span>
    </div>

    <div v-else-if="error" class="card detail-state detail-state-error">
      <h3>View unavailable</h3>
      <p>{{ error }}</p>
      <button type="button" class="btn btn-primary" @click="loadView">Retry</button>
    </div>

    <template v-else-if="view">
      <header class="detail-header">
        <div>
          <h1>{{ view.name }}</h1>
          <div class="admin-view-executed__meta">
            <span
              class="admin-view-executed__badge"
              :class="{ 'admin-view-executed__badge--default': view.isDefault }"
            >
              {{ badgeLabel }}
            </span>
            <span class="admin-view-executed__count">
              {{ userCount }} {{ userCount === 1 ? 'user' : 'users' }}
            </span>
          </div>
        </div>
      </header>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchAdminView, runAdminView, type AdminView } from '@/utils/adminAPI'

const route = useRoute()
const router = useRouter()

const view = ref<AdminView | null>(null)
const userCount = ref(0)
const loading = ref(false)
const error = ref('')

const viewId = computed(() => Number(route.params.id))

const badgeLabel = computed(() => (view.value?.isDefault ? 'System Default' : 'Custom View'))

const loadView = async (): Promise<void> => {
  if (!Number.isFinite(viewId.value) || viewId.value <= 0) {
    error.value = 'Invalid view id.'
    return
  }

  loading.value = true
  error.value = ''
  try {
    const [viewData, runData] = await Promise.all([
      fetchAdminView(viewId.value),
      runAdminView(viewId.value, { limit: 1 })
    ])
    view.value = viewData
    userCount.value = runData.total
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'View could not be loaded.'
  } finally {
    loading.value = false
  }
}

const goBack = (): void => {
  router.push('/admin/views')
}

watch(viewId, loadView, { immediate: true })
</script>

<style scoped>
.back-button {
  align-items: center;
  display: inline-flex;
  gap: 0.45rem;
  margin-bottom: 1rem;
}

.detail-state {
  align-items: center;
  display: flex;
  gap: 0.75rem;
}

.detail-state-error {
  align-items: flex-start;
  border-left: 4px solid var(--danger);
  flex-direction: column;
}

.detail-header {
  align-items: flex-start;
  display: flex;
  gap: 1.25rem;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.detail-header h1 {
  margin-bottom: 0.35rem;
}

.admin-view-executed__meta {
  align-items: center;
  display: flex;
  gap: 0.65rem;
}

.admin-view-executed__badge {
  background-color: var(--light-green);
  border-radius: 999px;
  color: var(--dark-green);
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
}

.admin-view-executed__badge--default {
  background-color: rgba(26, 52, 94, 0.1);
  color: var(--navy);
}

.admin-view-executed__count {
  color: var(--text-muted);
  font-size: 0.85rem;
}
</style>
