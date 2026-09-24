<template>
  <div class="content-area admin-view-executed">
    <button type="button" class="btn btn-outline back-button" @click="goBack">
      <i class="fas fa-arrow-left" aria-hidden="true"></i> Back to Views
    </button>

    <div v-if="loading && !view" class="detail-state" role="status" aria-live="polite">
      <span class="loading"></span>
      <span>Loading view...</span>
    </div>

    <div v-else-if="error && !view" class="card detail-state detail-state-error">
      <h3>View unavailable</h3>
      <p>{{ error }}</p>
      <button type="button" class="btn btn-primary" @click="reload">Retry</button>
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
              {{ totalCount }} {{ totalCount === 1 ? 'user' : 'users' }}
            </span>
          </div>
        </div>
      </header>

      <p v-if="error" class="admin-view-executed__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>

      <div class="admin-view-executed__controls">
        <div class="admin-view-executed__search">
          <i class="fas fa-magnifying-glass admin-view-executed__search-icon" aria-hidden="true"></i>
          <input
            v-model="searchInput"
            type="search"
            class="admin-view-executed__search-input"
            placeholder="Name or email"
            aria-label="Search users"
          />
        </div>

        <div class="admin-view-executed__group-by">
          <label class="admin-view-executed__group-by-label" for="view-group-by">Group by</label>
          <select
            id="view-group-by"
            :value="groupBy"
            @change="onGroupByChange(($event.target as HTMLSelectElement).value as GroupByOption)"
          >
            <option value="none">None</option>
            <option value="role">Role</option>
            <option value="status">Status</option>
          </select>
          <span v-if="groupBy !== 'none'" class="admin-view-executed__group-by-hint">
            Grouping is not yet applied server-side; results are shown sorted, not grouped.
          </span>
        </div>
      </div>

      <AdminViewResultsTable
        :columns="columns"
        :rows="rows"
        :loading="loading"
        :sort-state="sortState"
        :page="page"
        :limit="limit"
        :total-count="totalCount"
        :page-size-options="pageSizeOptions"
        :empty-message="emptyMessage"
        @update:sort="onSortChange"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AdminViewResultsTable from '@/components/admin/views/AdminViewResultsTable.vue'
import { useAdminViewExecuted, type GroupByOption } from '@/composables/admin/useAdminViewExecuted'

const route = useRoute()
const router = useRouter()

const viewId = computed(() => Number(route.params.id))

const {
  view,
  rows,
  totalCount,
  loading,
  error,
  page,
  limit,
  sortState,
  groupBy,
  searchInput,
  columns,
  emptyMessage,
  badgeLabel,
  pageSizeOptions,
  reload,
  onSortChange,
  onPageChange,
  onPageSizeChange,
  onGroupByChange
} = useAdminViewExecuted(viewId)

const goBack = (): void => {
  router.push('/admin/views')
}

watch(viewId, reload, { immediate: true })
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

.admin-view-executed__error {
  align-items: center;
  color: var(--danger);
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.admin-view-executed__controls {
  align-items: flex-end;
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.admin-view-executed__search {
  align-items: center;
  display: flex;
  max-width: 320px;
  position: relative;
  width: 100%;
}

.admin-view-executed__search-icon {
  color: var(--text-muted);
  left: 0.75rem;
  position: absolute;
}

.admin-view-executed__search-input {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 0.5rem 0.75rem 0.5rem 2.25rem;
  width: 100%;
}

.admin-view-executed__group-by {
  align-items: center;
  display: flex;
  gap: 0.5rem;
}

.admin-view-executed__group-by-label {
  color: var(--charcoal);
  font-size: 0.85rem;
  font-weight: 600;
}

.admin-view-executed__group-by select {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
}

.admin-view-executed__group-by-hint {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-style: italic;
  max-width: 220px;
}
</style>
