<template>
  <div class="admin-mentors">
    <!-- Header -->
    <div class="admin-mentors__header">
      <p class="admin-mentors__count">
        {{ mentors.length }} mentor{{ mentors.length === 1 ? '' : 's' }} registered
      </p>
      <div class="admin-mentors__header-actions">
        <button type="button" class="btn btn-sm btn-outline" :disabled="loading" @click="mentorImportOpen = true">
          <i class="fas fa-file-arrow-up" aria-hidden="true"></i>
          Import Mentors CSV
        </button>
        <div class="admin-mentors__inactive-days">
          <label for="inactive-days-input" class="admin-mentors__inactive-label">Inactive after</label>
          <input
            id="inactive-days-input"
            type="number"
            min="1"
            :value="inactiveDays"
            class="admin-mentors__inactive-input"
            @change="onInactiveDaysChange"
          />
          <span class="admin-mentors__inactive-label">days</span>
        </div>
        <button
          v-if="inactiveGroups.length > 0"
          type="button"
          class="btn btn-sm btn-outline"
          @click="replaceDialogOpen = true"
        >
          <i class="fas fa-sync-alt" aria-hidden="true"></i>
          Replace Inactive Mentors
          <span class="admin-mentors__badge">{{ inactiveGroups.length }}</span>
        </button>
      </div>
    </div>

    <p v-if="error" class="admin-mentors__error" role="alert">{{ error }}</p>

    <!-- Bulk actions -->
    <BulkActionsBar
      v-if="selectedIds.size > 0"
      :count="selectedIds.size"
      noun="mentor"
      :disabled="statusBusy"
      @clear="clearSelection"
    >
      <button type="button" class="btn btn-sm btn-outline" :disabled="statusBusy" @click="openBulk('activate')">
        Activate
      </button>
      <button type="button" class="btn btn-sm btn-outline" :disabled="statusBusy" @click="openBulk('deactivate')">
        Deactivate
      </button>
    </BulkActionsBar>

    <!-- Table -->
    <div
      class="admin-mentors__card"
      :class="{ 'admin-mentors__card--loading': loading && mentors.length > 0 }"
    >
      <template v-if="loading && mentors.length === 0">
        <div class="admin-mentors__state">
          <span class="admin-mentors__spinner" aria-hidden="true"></span>
          <span>Loading mentors...</span>
        </div>
      </template>

      <template v-else-if="sortedMentors.length === 0">
        <div class="admin-mentors__state admin-mentors__state--empty">
          No mentors registered yet.
        </div>
      </template>

      <div v-else class="admin-mentors__scroll">
        <table class="admin-mentors__table">
          <thead>
            <tr>
              <th class="admin-mentors__check">
                <input
                  type="checkbox"
                  :checked="headerChecked === true"
                  :indeterminate.prop="headerChecked === 'indeterminate'"
                  aria-label="Select all mentors"
                  :disabled="loading || mentors.length === 0"
                  @change="toggleAll"
                />
              </th>
              <th class="admin-mentors__expand" aria-hidden="true"></th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('name')" @click="setSort('name')">
                  <span>Name</span>
                  <i class="fas admin-mentors__sort-icon" :class="sortIcon('name')" aria-hidden="true"></i>
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('country')" @click="setSort('country')">
                  <span>Country</span>
                  <i class="fas admin-mentors__sort-icon" :class="sortIcon('country')" aria-hidden="true"></i>
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('institution')" @click="setSort('institution')">
                  <span>Institution</span>
                  <i class="fas admin-mentors__sort-icon" :class="sortIcon('institution')" aria-hidden="true"></i>
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('capacity')" @click="setSort('capacity')">
                  <span>Capacity</span>
                  <i class="fas admin-mentors__sort-icon" :class="sortIcon('capacity')" aria-hidden="true"></i>
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('lastMessage')" @click="setSort('lastMessage')">
                  <span>Last Message</span>
                  <i class="fas admin-mentors__sort-icon" :class="sortIcon('lastMessage')" aria-hidden="true"></i>
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('status')" @click="setSort('status')">
                  <span>Status</span>
                  <i class="fas admin-mentors__sort-icon" :class="sortIcon('status')" aria-hidden="true"></i>
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('loggedIn')" @click="setSort('loggedIn')">
                  <span>Logged In</span>
                  <i class="fas admin-mentors__sort-icon" :class="sortIcon('loggedIn')" aria-hidden="true"></i>
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="mentor in sortedMentors" :key="mentor.mentorId">
              <AdminMentorRow
                :mentor="mentor"
                :selected="selectedIds.has(mentor.mentorId)"
                :expanded="expandedIds.has(mentor.mentorId)"
                :status-busy="statusBusy"
                :loading="loading"
                :inactive-days="inactiveDays"
                @toggle-select="toggleOne"
                @toggle-expand="toggleExpand"
                @toggle-active="toggleActive"
              />
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Bulk status confirm -->
    <ConfirmDialog
      v-model="bulkAction.open"
      :title="bulkTitle"
      :message="bulkMessage"
      :confirm-label="bulkAction.action === 'activate' ? 'Activate' : 'Deactivate'"
      :variant="bulkAction.action === 'activate' ? 'default' : 'warning'"
      :busy="statusBusy"
      @confirm="runBulkStatus"
    />

    <!-- Replace inactive mentors -->
    <MentorReplaceDialog
      v-model:open="replaceDialogOpen"
      :inactive-groups="inactiveGroups"
      :mentors="mentorList"
      @confirmed="onReplaceConfirmed"
    />

    <AdminMentorImportSheet
      v-model="mentorImportOpen"
      @imported="onMentorsImported"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import MentorReplaceDialog from '@/components/admin/MentorReplaceDialog.vue'
import AdminMentorImportSheet from '@/components/admin/mentors/AdminMentorImportSheet.vue'
import AdminMentorRow from '@/components/admin/mentors/AdminMentorRow.vue'
import { useAdminMentorsView } from '@/composables/admin/useAdminMentorsView'

const {
  loading,
  statusBusy,
  error,
  mentors,
  mentorList,
  inactiveDays,
  expandedIds,
  selectedIds,
  bulkAction,
  replaceDialogOpen,
  inactiveGroups,
  sortedMentors,
  headerChecked,
  setSort,
  toggleExpand,
  toggleAll,
  toggleOne,
  clearSelection,
  onInactiveDaysChange,
  toggleActive,
  openBulk,
  bulkTitle,
  bulkMessage,
  runBulkStatus,
  onReplaceConfirmed,
  sortClass,
  sortIcon,
  load
} = useAdminMentorsView()

const mentorImportOpen = ref(false)

onMounted(() => {
  void load()
})

const onMentorsImported = () => {
  void load()
}
</script>

<style scoped>
.admin-mentors {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-mentors__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.admin-mentors__count {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.admin-mentors__header-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.admin-mentors__inactive-days {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-mentors__inactive-label {
  font-size: 0.9rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.admin-mentors__inactive-input {
  width: 4.5rem;
  height: 2rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--white);
  color: var(--charcoal);
  font-size: 0.9rem;
}

.admin-mentors__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.4rem;
  height: 1.4rem;
  padding: 0 0.35rem;
  margin-left: 0.4rem;
  border-radius: 999px;
  background-color: var(--danger);
  border: 1px solid rgba(255, 255, 255, 0.4);
  color: var(--white);
  font-size: 0.75rem;
  font-weight: 600;
}

.admin-mentors__error {
  margin: 0;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.875rem;
}

.admin-mentors__card {
  background-color: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(7, 17, 15, 0.03);
  overflow: hidden;
}

.admin-mentors__card--loading {
  opacity: 0.6;
  pointer-events: none;
}

.admin-mentors__scroll {
  width: 100%;
  overflow-x: auto;
}

.admin-mentors__table {
  width: 100%;
  border-collapse: collapse;
}

.admin-mentors__check {
  width: 42px;
  padding: 0.75rem 0.5rem;
  text-align: center;
}

.admin-mentors__check input[type='checkbox'] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--dark-green);
}

.admin-mentors__expand {
  width: 34px;
  padding: 0.75rem 0.25rem;
}

.admin-mentors__head {
  padding: 0.85rem 1rem;
  text-align: center;
  font-weight: 600;
  color: var(--charcoal);
  background-color: var(--light-green);
  border-bottom: 2px solid var(--border-light);
  white-space: nowrap;
}

.admin-mentors__sort {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.admin-mentors__sort:hover,
.admin-mentors__sort--active {
  color: var(--dark-green);
}

.admin-mentors__sort-icon {
  font-size: 0.8rem;
  color: #c0c8c4;
}

.admin-mentors__sort--active .admin-mentors__sort-icon {
  color: var(--dark-green);
}

.admin-mentors__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 2.5rem 1rem;
  color: var(--text-muted);
}

.admin-mentors__state--empty {
  border: 1px dashed var(--border-light);
  border-radius: 10px;
  background-color: var(--bg-light);
}

.admin-mentors__spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-light);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: admin-mentors-spin 0.8s linear infinite;
}

@keyframes admin-mentors-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-mentors__spinner {
    animation: none;
  }
}
</style>
