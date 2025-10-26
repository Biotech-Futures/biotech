<template>
  <div class="content-area modern-admin" v-if="isAdmin">
    <!-- Header with Track Selector -->
    <AnimatedContent
      :distance="80"
      direction="vertical"
      :duration="0.7"
      ease="power3.out"
      :initial-opacity="0"
      :animate-opacity="true"
    >
      <div class="admin-hero">
        <div class="admin-hero-content">
          <div>
            <h1 class="admin-title">Admin Dashboard</h1>
            <p class="admin-subtitle">Manage users, groups, and platform settings</p>
          </div>
          <select
            v-model="activeTrack"
            class="track-selector"
            :disabled="statsLoading || usersLoading"
          >
            <option v-for="option in trackOptions" :key="option" :value="option">
              {{ option }}
            </option>
          </select>
        </div>
      </div>
    </AnimatedContent>

    <!-- Stats Cards -->
    <AnimatedContent
      :distance="60"
      direction="vertical"
      :duration="0.7"
      ease="power3.out"
      :initial-opacity="0"
      :animate-opacity="true"
      :delay="0.05"
    >
      <div class="stats-grid">
        <div class="stat-card" @click="handleCardClick('all')">
          <div class="stat-icon users">
            <i class="fas fa-users"></i>
          </div>
          <div class="stat-content">
            <div class="stat-label">Total Users</div>
            <div class="stat-value">
              {{ statsLoading ? '—' : totalUsers }}
            </div>
            <div class="stat-detail">{{ activeTrack }}</div>
          </div>
        </div>

        <div class="stat-card groups-card">
          <div class="stat-icon groups">
            <i class="fas fa-layer-group"></i>
          </div>
          <div class="stat-content">
            <div class="stat-label">Active Groups</div>
            <div class="stat-value">
              {{ statsLoading ? '—' : activeGroups }}
            </div>
            <div class="stat-detail">Filtered by track</div>
          </div>
        </div>

        <div class="stat-card" @click="handleCardClick('mentor')">
          <div class="stat-icon mentors">
            <i class="fas fa-user-tie"></i>
          </div>
          <div class="stat-content">
            <div class="stat-label">Mentors</div>
            <div class="stat-value">
              {{ statsLoading ? '—' : mentorTotal }}
            </div>
            <div class="stat-detail">{{ mentorActive }} active · {{ mentorPending }} pending</div>
          </div>
        </div>

        <div class="stat-card" @click="handleCardClick('student')">
          <div class="stat-icon students">
            <i class="fas fa-graduation-cap"></i>
          </div>
          <div class="stat-content">
            <div class="stat-label">Students</div>
            <div class="stat-value">
              {{ statsLoading ? '—' : studentTotal }}
            </div>
            <div class="stat-detail">{{ studentPending }} pending</div>
          </div>
        </div>
      </div>
    </AnimatedContent>

    <p v-if="statsErrorMessage" class="alert-error">{{ statsErrorMessage }}</p>

    <!-- User Management Section -->
    <AnimatedContent
      :distance="80"
      direction="vertical"
      :duration="0.75"
      ease="power3.out"
      :initial-opacity="0"
      :animate-opacity="true"
      :delay="0.1"
    >
      <div class="management-section">
        <div class="section-header">
          <div class="section-header-left">
            <h2 class="section-title">User Management</h2>
            <span v-if="users.length" class="section-count">{{ users.length }} users</span>
          </div>
          <div class="section-actions">
            <input
              v-model="userSearch"
              type="text"
              class="search-input"
              placeholder="Search users..."
              :disabled="usersLoading"
            />
            <button
              class="btn btn-outline btn-sm"
              @click="openFilterModal"
              :disabled="filterOptionsLoading"
            >
              <i class="fas fa-filter"></i> Filter
            </button>
            <button
              class="btn btn-outline btn-sm"
              @click="exportUsers"
              :disabled="exporting || usersLoading"
            >
              <i class="fas fa-download"></i> Export
            </button>
            <button
              class="btn btn-primary btn-sm"
              @click="openCreateUser"
              :disabled="creatingUser"
            >
              <i class="fas fa-user-plus"></i> Add User
            </button>
          </div>
        </div>

        <p v-if="usersErrorMessage" class="alert-error">{{ usersErrorMessage }}</p>

        <div class="table-container">
          <table class="modern-table">
            <thead>
              <tr>
                <th style="width: 40px;">
                  <input
                    type="checkbox"
                    class="checkbox-input"
                    @change="toggleSelectAll($event)"
                    :disabled="usersLoading || !users.length"
                  />
                </th>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Track</th>
                <th>Status</th>
                <th style="width: 200px;">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="usersLoading">
                <td colspan="7" class="loading-cell">
                  <div class="loading-spinner"></div>
                  Loading users...
                </td>
              </tr>
              <template v-else>
                <tr v-if="!users.length">
                  <td colspan="7" class="empty-cell">No users found</td>
                </tr>
                <tr v-else v-for="user in users" :key="user.id" class="table-row-hover">
                  <td>
                    <input
                      type="checkbox"
                      class="checkbox-input"
                      v-model="selected"
                      :value="user.id"
                    />
                  </td>
                  <td class="user-name-cell">
                    <div class="user-avatar-small">{{ getInitials(user.name) }}</div>
                    <span>{{ user.name }}</span>
                  </td>
                  <td class="text-muted">{{ user.email }}</td>
                  <td>
                    <span class="role-badge">{{ user.role }}</span>
                  </td>
                  <td class="text-muted">{{ user.track || '—' }}</td>
                  <td>
                    <span :class="['status-badge', getStatusClass(user.status)]">
                      {{ user.status }}
                    </span>
                  </td>
                  <td>
                    <div class="action-buttons">
                      <select
                        :value="user.status"
                        class="status-select"
                        @change="onChangeStatus(user.id, $event.target.value)"
                        :disabled="Boolean(updatingStatus[user.id])"
                      >
                        <option v-for="option in statusOptions" :key="option" :value="option">
                          {{ capitalize(option) }}
                        </option>
                      </select>
                      <button
                        class="btn-icon-only"
                        @click="openEditUser(user.id)"
                        :disabled="Boolean(savingUser[user.id])"
                        title="Edit user"
                      >
                        <i class="fas fa-edit"></i>
                      </button>
                      <button
                        class="btn-icon-only"
                        @click="openViewUser(user.id)"
                        title="View user"
                      >
                        <i class="fas fa-eye"></i>
                      </button>
                      <button
                        class="btn-icon-only"
                        @click="confirmDeleteUser(user.id)"
                        :disabled="Boolean(deletingUser[user.id])"
                        title="Delete user"
                      >
                        <i :class="deletingUser[user.id] ? 'fas fa-spinner fa-spin' : 'fas fa-trash-alt'"></i>
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </AnimatedContent>

    <!-- Group Management Section -->
    <AnimatedContent
      :distance="80"
      direction="vertical"
      :duration="0.75"
      ease="power3.out"
      :initial-opacity="0"
      :animate-opacity="true"
      :delay="0.15"
    >
      <div class="management-section">
        <div class="section-header">
          <div class="section-header-left">
            <h2 class="section-title">Group Management</h2>
            <span v-if="groups.length" class="section-count">{{ groups.length }} groups</span>
          </div>
          <button 
            class="btn btn-primary btn-sm" 
            @click="toggleCreateGroup"
            :disabled="loadingGroupOptions"
          >
            <i :class="showCreateGroup ? 'fas fa-times' : 'fas fa-plus'"></i>
            {{ showCreateGroup ? 'Cancel' : 'Create Group' }}
          </button>
        </div>
  
        <!-- Create Group Form -->
        <div v-if="showCreateGroup" class="create-group-panel">
          <h3 class="panel-title">Create New Group</h3>
          <form @submit.prevent="createGroup" class="group-form">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Group Code (optional)</label>
                <input
                  v-model="groupForm.groupId"
                  type="text"
                  class="form-control"
                  :disabled="creatingGroup"
                  placeholder="e.g. BTF046"
                />
              </div>
              <div class="form-group">
                <label class="form-label">Group Name *</label>
                <input
                  v-model="groupForm.name"
                  type="text"
                  class="form-control"
                  :disabled="creatingGroup"
                  placeholder="Team name"
                  required
                />
              </div>
              <div class="form-group">
                <label class="form-label">Track</label>
                <input
                  v-model="groupForm.track"
                  type="text"
                  class="form-control"
                  :disabled="creatingGroup"
                />
              </div>
            </div>
  
            <div class="form-row">
              <div class="form-group" style="flex: 1;">
                <label class="form-label">Mentor</label>
                <select
                  v-model="groupForm.mentorId"
                  class="form-control"
                  :disabled="creatingGroup || loadingGroupOptions"
                >
                  <option value="">No mentor</option>
                  <option v-for="mentor in availableMentors" :key="mentor.id" :value="String(mentor.id)">
                    {{ mentor.name }}
                  </option>
                </select>
              </div>
            </div>
  
            <div class="form-group">
              <label class="form-label">Select Students *</label>
              <p class="form-text" style="margin-bottom: 0.75rem;">
                Choose one or more students to include in this group
              </p>
              <div
                class="member-multiselect"
                ref="memberDropdownRef"
                :class="{ open: membersDropdownOpen }"
              >
                <div
                  class="member-multiselect-control"
                  role="button"
                  tabindex="0"
                  @click="toggleMembersDropdown"
                  @keydown.enter.prevent="toggleMembersDropdown"
                  @keydown.space.prevent="toggleMembersDropdown"
                >
                  <div class="member-selected-list">
                    <span v-if="!selectedMembers.length" class="member-placeholder">
                      Click to select students
                    </span>
                    <div
                      v-for="member in selectedMembers"
                      :key="member.id"
                      class="member-selected-chip"
                    >
                      <span>{{ member.name }}</span>
                      <button
                        type="button"
                        class="chip-remove-btn"
                        aria-label="Remove student"
                        @click.stop="removeMember(member.id)"
                      >
                        <i class="fas fa-times"></i>
                      </button>
                    </div>
                  </div>
                  <i class="fas" :class="membersDropdownOpen ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
                </div>
  
                <transition name="fade">
                  <div
                    v-if="membersDropdownOpen"
                    class="member-dropdown-panel"
                  >
                    <div class="member-dropdown-header">
                      <input
                        v-model="memberSearch"
                        type="text"
                        class="dropdown-search-input"
                        placeholder="Search students..."
                        :disabled="loadingGroupOptions"
                      />
                      <button
                        type="button"
                        class="clear-selection-btn"
                        @click.stop="clearMembers"
                        :disabled="!groupForm.memberIds.length"
                      >
                        Clear
                      </button>
                    </div>
                    <div class="member-dropdown-body">
                      <template v-if="loadingGroupOptions && !availableMembers.length">
                        <p class="member-empty">Loading students…</p>
                      </template>
                      <template v-else>
                        <label
                          v-for="member in filteredMembers"
                          :key="member.id"
                          class="member-dropdown-option"
                        >
                          <input
                            type="checkbox"
                            :value="member.id"
                            :checked="isSelected(member.id)"
                            @change.stop="toggleMember(member.id)"
                          />
                          <span>{{ member.name }}</span>
                        </label>
                        <p v-if="!filteredMembers.length" class="member-empty">
                          No students match your search.
                        </p>
                      </template>
                    </div>
                  </div>
                </transition>
              </div>
            </div>
  
            <div class="form-actions">
              <button
                type="button"
                class="btn btn-outline"
                @click="toggleCreateGroup"
                :disabled="creatingGroup"
              >
                Cancel
              </button>
              <button
                type="submit"
                class="btn btn-primary"
                :disabled="creatingGroup || loadingGroupOptions || !groupForm.name.trim() || groupForm.memberIds.length === 0"
              >
                <i v-if="creatingGroup" class="fas fa-spinner fa-spin"></i>
                <span v-else>Create Group</span>
              </button>
            </div>
          </form>
        </div>
  
        <p v-if="groupsError" class="alert-error">{{ groupsError }}</p>
  
        <div class="table-container">
          <table class="modern-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Mentor</th>
                <th>Members</th>
                <th>Track</th>
                <th>Status</th>
                <th style="width: 120px;">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="groupsLoading">
                <td colspan="7" class="loading-cell">
                  <div class="loading-spinner"></div>
                  Loading groups...
                </td>
              </tr>
              <template v-else>
                <tr v-if="!groups.length">
                  <td colspan="7" class="empty-cell">No groups found for this track</td>
                </tr>
                <tr v-else v-for="group in groups" :key="group.id" class="table-row-hover">
                  <td class="text-muted">{{ group.id }}</td>
                  <td class="group-name-cell">
                    <div class="group-icon">
                      <i class="fas fa-users"></i>
                    </div>
                    <span>{{ group.name }}</span>
                  </td>
                  <td>{{ group.mentor?.name || '—' }}</td>
                  <td class="text-muted">{{ group.members ?? 0 }}</td>
                  <td class="text-muted">{{ group.track || '—' }}</td>
                  <td>
                    <span class="status-badge status-active">
                      {{ group.status || 'Active' }}
                    </span>
                  </td>
                  <td>
                    <div class="action-buttons">
                      <button
                        class="btn-icon-only"
                        @click="viewGroup(group.id)"
                        title="View group"
                      >
                        <i class="fas fa-eye"></i>
                      </button>
                      <button
                        class="btn-icon-only danger"
                        @click="deleteGroup(group.id)"
                        :disabled="Boolean(deletingGroups[group.id])"
                        title="Delete group"
                      >
                        <i :class="deletingGroups[group.id] ? 'fas fa-spinner fa-spin' : 'fas fa-trash'"></i>
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </AnimatedContent>

    <!-- User Modal (Edit/View/Create) -->
    <div v-if="showUserModal" class="modal-overlay" @click.self="closeUserModal">
      <div class="modal-panel">
        <div class="modal-panel-header">
          <div>
            <h3 class="modal-panel-title">{{ userModalTitle }}</h3>
            <p class="modal-panel-subtitle">
              <template v-if="userModalMode === 'view'">
                View user profile information
              </template>
              <template v-else-if="userModalMode === 'edit'">
                Update user details and profile
              </template>
              <template v-else>
                Create a new user account
              </template>
            </p>
          </div>
          <button class="btn-icon-close" @click="closeUserModal" aria-label="Close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="modal-panel-body">
          <div v-if="userModalLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>Loading user information...</p>
          </div>
          <form
            v-else
            ref="userFormRef"
            @submit.prevent="saveUser"
            class="modal-form"
          >
            <div class="form-grid">
              <div class="form-group">
                <label class="form-label">Email</label>
                <input
                  v-model="userForm.email"
                  type="email"
                  class="form-control"
                  :readonly="userModalMode === 'view'"
                  :disabled="isSavingUser"
                  required
                />
              </div>
              <div class="form-group">
                <label class="form-label">Role</label>
                <select
                  v-model="userForm.role"
                  class="form-control"
                  :disabled="userModalMode === 'view' || isSavingUser"
                >
                  <option v-for="role in roleOptions" :key="role" :value="role">
                    {{ capitalize(role) }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Status</label>
                <select
                  v-model="userForm.status"
                  class="form-control"
                  :disabled="userModalMode === 'view' || isSavingUser"
                >
                  <option v-for="status in statusOptions" :key="status" :value="status">
                    {{ capitalize(status) }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Track</label>
                <select
                  v-model="userForm.track"
                  class="form-control"
                  :disabled="userModalMode === 'view' || isSavingUser"
                >
                  <option v-for="option in trackOptions" :key="`${option}-form`" :value="option">
                    {{ option }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">First Name</label>
                <input
                  v-model="userForm.profile.firstName"
                  type="text"
                  class="form-control"
                  :readonly="userModalMode === 'view'"
                  :disabled="isSavingUser"
                />
              </div>
              <div class="form-group">
                <label class="form-label">Last Name</label>
                <input
                  v-model="userForm.profile.lastName"
                  type="text"
                  class="form-control"
                  :readonly="userModalMode === 'view'"
                  :disabled="isSavingUser"
                />
              </div>
              <div class="form-group">
                <label class="form-label">School</label>
                <input
                  v-model="userForm.profile.schoolName"
                  type="text"
                  class="form-control"
                  :readonly="userModalMode === 'view'"
                  :disabled="isSavingUser"
                />
              </div>
              <div class="form-group">
                <label class="form-label">Year Level</label>
                <input
                  v-model="userForm.profile.yearLevel"
                  type="number"
                  min="0"
                  class="form-control"
                  :readonly="userModalMode === 'view'"
                  :disabled="isSavingUser"
                />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Areas of Interest</label>
              <textarea
                v-model="userForm.profile.areasOfInterestText"
                class="form-control"
                rows="2"
                :readonly="userModalMode === 'view'"
                :disabled="isSavingUser"
                placeholder="Comma or newline separated"
              ></textarea>
            </div>
            <div class="form-group">
              <label class="form-label">Bio</label>
              <textarea
                v-model="userForm.profile.bio"
                class="form-control"
                rows="3"
                :readonly="userModalMode === 'view'"
                :disabled="isSavingUser"
              ></textarea>
            </div>
          </form>
        </div>

        <div class="modal-panel-footer">
          <button
            v-if="userModalMode === 'edit'"
            class="btn btn-outline danger"
            type="button"
            @click="confirmDeleteUser"
            :disabled="isDeletingUser"
            style="margin-right: auto;"
          >
            <i v-if="isDeletingUser" class="fas fa-spinner fa-spin"></i>
            <span v-else>Delete</span>
          </button>
          <button
            class="btn btn-outline"
            type="button"
            @click="closeUserModal"
            :disabled="isSavingUser || isDeletingUser"
          >
            Close
          </button>
          <button
            v-if="userModalMode !== 'view'"
            class="btn btn-primary"
            type="button"
            @click="saveUser"
            :disabled="isSavingUser || isDeletingUser"
          >
            <i v-if="isSavingUser" class="fas fa-spinner fa-spin"></i>
            <span v-else>{{ userModalMode === 'create' ? 'Create' : 'Save' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Filter Modal -->
    <div v-if="showFilterModal" class="modal-overlay" @click.self="closeFilterModal">
      <div class="modal-panel small">
        <div class="modal-panel-header">
          <div>
            <h3 class="modal-panel-title">Filter Users</h3>
            <p class="modal-panel-subtitle">Refine your search criteria</p>
          </div>
          <button class="btn-icon-close" @click="closeFilterModal" aria-label="Close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="modal-panel-body">
          <div class="form-group">
            <label class="form-label">Role</label>
            <select v-model="filterForm.role" class="form-control">
              <option value="">All Roles</option>
              <option v-for="role in roleOptions" :key="role" :value="role">
                {{ capitalize(role) }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Status</label>
            <select v-model="filterForm.status" class="form-control">
              <option value="">All Statuses</option>
              <option v-for="status in statusOptions" :key="status" :value="status">
                {{ capitalize(status) }}
              </option>
            </select>
          </div>
        </div>

        <div class="modal-panel-footer">
          <button class="btn btn-outline" @click="clearFilters">Reset</button>
          <button class="btn btn-primary" @click="applyFilters">Apply Filters</button>
        </div>
      </div>
    </div>
  </div>

  <div class="content-area" v-else>
    <div class="access-denied">
      <div class="access-denied-icon">
        <i class="fas fa-lock"></i>
      </div>
      <h2>Access Restricted</h2>
      <p>This area is only available to administrators.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAdminStore } from '@/stores/admin'
import { useAuthStore } from '@/stores/auth'
import { useGroupStore } from '@/stores/groups'
import AnimatedContent from '@/components/AnimatedContent.vue'
import { safeJson } from '@/utils/http'

const router = useRouter()
const authStore = useAuthStore()
const adminStore = useAdminStore()
const groupStoreGlobal = useGroupStore()

const {
  stats,
  statsLoading,
  statsError,
  users,
  usersLoading,
  usersError,
  updatingStatus,
  filterOptions,
  filterOptionsLoading,
  filterOptionsError,
  creatingUser,
  savingUser,
  detailLoading,
  exporting,
  deletingUser
} = storeToRefs(adminStore)

const { isAdmin } = storeToRefs(authStore)

const userSearch = ref(adminStore.filters.search || '')
const filterForm = reactive({
  role: adminStore.filters.role || '',
  status: adminStore.filters.status || ''
})
const selected = ref([])

const activeTrack = ref(adminStore.filters.track || 'Global')
const showFilterModal = ref(false)
const showUserModal = ref(false)
const showCreateGroup = ref(false)

const userModalMode = ref('view')
const userModalLoading = ref(false)
const userFormRef = ref(null)

const userForm = reactive({
  id: null,
  email: '',
  role: 'student',
  track: 'Global',
  status: 'pending',
  profile: {
    firstName: '',
    lastName: '',
    schoolName: '',
    yearLevel: '',
    country: '',
    region: '',
    areasOfInterestText: '',
    availability: '',
    bio: ''
  }
})

// Groups state
const groups = ref([])
const groupsLoaded = ref(false)
const groupsLoading = ref(false)
const groupsError = ref('')
const deletingGroups = ref({})
const loadingGroupOptions = ref(false)
const groupOptionsLoaded = ref(false)
const creatingGroup = ref(false)
const availableMentors = ref([])
const availableMembers = ref([])
const groupForm = reactive({
  groupId: '',
  name: '',
  track: activeTrack.value || 'Global',
  mentorId: '',
  memberIds: []
})
const membersDropdownOpen = ref(false)
const memberDropdownRef = ref(null)
const memberSearch = ref('')

const selectedMembers = computed(() => {
  const lookup = new Map(
    availableMembers.value.map((member) => [String(member.id), member])
  )
  return groupForm.memberIds
    .map((id) => lookup.get(String(id)))
    .filter(Boolean)
})

const filteredMembers = computed(() => {
  const term = memberSearch.value.trim().toLowerCase()
  if (!term) return availableMembers.value
  return availableMembers.value.filter((member) =>
    String(member.name || '')
      .toLowerCase()
      .includes(term)
  )
})

const statusOptions = computed(() => filterOptions.value.statuses || ['active', 'pending', 'inactive'])
const roleOptions = computed(() => filterOptions.value.roles || ['student', 'mentor', 'supervisor', 'admin'])

const trackOptions = computed(() => {
  const base = filterOptions.value.tracks?.length ? filterOptions.value.tracks : ['Global', 'AUS-NSW', 'Brazil']
  const normalized = base.map((item) => (item && item.toLowerCase() !== 'global' ? item : 'Global'))
  const unique = []
  for (const item of ['Global', ...normalized]) {
    if (!unique.includes(item)) unique.push(item)
  }
  return unique
})

const totalUsers = computed(() => stats.value?.totalUsers ?? 0)
const activeGroups = computed(() => stats.value?.activeGroups ?? 0)
const mentorTotal = computed(() => stats.value?.mentors?.total ?? 0)
const mentorActive = computed(() => stats.value?.mentors?.active ?? 0)
const mentorPending = computed(() => stats.value?.mentors?.pending ?? 0)
const studentTotal = computed(() => stats.value?.students?.total ?? 0)
const studentPending = computed(() => stats.value?.students?.pending ?? 0)

const statsErrorMessage = computed(() => statsError.value?.message ?? '')
const usersErrorMessage = computed(() => usersError.value?.message ?? filterOptionsError.value?.message ?? '')

const userModalTitle = computed(() => {
  if (userModalMode.value === 'create') return 'Add User'
  if (userModalMode.value === 'edit') return 'Edit User'
  return 'View User'
})

const isSavingUser = computed(() => {
  if (userModalMode.value === 'create') return creatingUser.value
  if (userForm.id != null) {
    return Boolean(savingUser.value[userForm.id])
  }
  return false
})

const isDeletingUser = computed(() =>
  userForm.id != null ? Boolean(deletingUser.value?.[userForm.id]) : false
)

const capitalize = (str) => str ? str.charAt(0).toUpperCase() + str.slice(1) : ''

const getStatusClass = (status) => {
  const classes = {
    active: 'status-active',
    pending: 'status-pending',
    inactive: 'status-inactive'
  }
  return classes[status] || 'status-pending'
}

const getInitials = (name) =>
  String(name || '')
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || '—'

const refreshForTrack = (track) => {
  adminStore.fetchStats({ track }).catch(() => {})
  adminStore.fetchUsers({
    track,
    search: userSearch.value,
    role: filterForm.role,
    status: filterForm.status
  }).catch(() => {})
  
  // Reload groups for the new track
  if (showCreateGroup.value) {
    groupsLoaded.value = false
    groupOptionsLoaded.value = false
    fetchGroups(true).catch(() => {})
    loadGroupOptions(true).catch(() => {})
  }
}

watch(
  isAdmin,
  (value) => {
    if (value) {
      refreshForTrack(activeTrack.value)
    } else {
      adminStore.reset()
      groups.value = []
      groupsLoaded.value = false
      availableMentors.value = []
      availableMembers.value = []
      groupOptionsLoaded.value = false
      resetGroupForm()
    }
  },
  { immediate: true }
)

watch(activeTrack, (track, previous) => {
  if (!isAdmin.value || track === previous) return
  refreshForTrack(track)
  if (userModalMode.value === 'create' && showUserModal.value) {
    userForm.track = track
  }
  groupForm.track = track || 'Global'
  groupForm.memberIds = []
  memberSearch.value = ''
  membersDropdownOpen.value = false
  
  // Reload groups when track changes
  groupsLoaded.value = false
  groupOptionsLoaded.value = false
  if (showCreateGroup.value) {
    fetchGroups(true).catch(() => {})
    loadGroupOptions(true).catch(() => {})
  }
})

let searchDebounceHandle = null
watch(userSearch, (value, previous) => {
  if (!isAdmin.value) return
  if (value === previous) return
  if (searchDebounceHandle) clearTimeout(searchDebounceHandle)
  searchDebounceHandle = setTimeout(() => {
    adminStore.fetchUsers({
      track: activeTrack.value,
      search: value,
      role: filterForm.role,
      status: filterForm.status
    }).catch(() => {})
  }, 300)
})

onMounted(() => {
  adminStore.fetchFilterOptions().catch(() => {})
  // Load groups data immediately
  fetchGroups().catch(() => {})
  loadGroupOptions().catch(() => {})
  document.addEventListener('click', handleMembersClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleMembersClickOutside)
})

// User management functions
const toggleSelectAll = (event) => {
  if (event.target.checked) {
    selected.value = users.value.map((user) => user.id)
  } else {
    selected.value = []
  }
}

const onChangeStatus = async (userId, nextStatus) => {
  if (!isAdmin.value) return
  const current = users.value.find((user) => user.id === userId)?.status
  if (!nextStatus || nextStatus === current) return

  try {
    await adminStore.updateUserStatus({ userId, status: nextStatus })
  } catch (error) {
    window.alert(error?.message || 'Failed to update user status.')
  }
}

const handleCardClick = (type) => {
  if (type === 'mentor') {
    filterForm.role = 'mentor'
    filterForm.status = ''
  } else if (type === 'student') {
    filterForm.role = 'student'
    filterForm.status = ''
  } else {
    filterForm.role = ''
    filterForm.status = ''
  }
  userSearch.value = ''
  applyFilters()
  if (type === 'all') {
    nextTick(() => {
      document.querySelector('.management-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }
}

const openFilterModal = async () => {
  try {
    await adminStore.fetchFilterOptions()
  } catch (error) {
    window.alert(error?.message || 'Failed to load filter options')
    return
  }
  filterForm.role = adminStore.filters.role || ''
  filterForm.status = adminStore.filters.status || ''
  showFilterModal.value = true
}

const closeFilterModal = () => {
  showFilterModal.value = false
}

const applyFilters = async () => {
  try {
    await adminStore.fetchUsers({
      track: activeTrack.value,
      role: filterForm.role,
      status: filterForm.status,
      search: userSearch.value
    })
    showFilterModal.value = false
  } catch (error) {
    window.alert(error?.message || 'Failed to apply filters')
  }
}

const clearFilters = () => {
  filterForm.role = ''
  filterForm.status = ''
  userSearch.value = ''
  applyFilters()
}

const openCreateUser = async () => {
  userModalMode.value = 'create'
  const ready = await ensureFilterOptions()
  if (!ready) return
  resetUserForm()
  showUserModal.value = true
}

const openEditUser = async (userId) => {
  userModalMode.value = 'edit'
  const ready = await ensureFilterOptions()
  if (!ready) return
  await openUserDetail(userId)
}

const openViewUser = async (userId) => {
  userModalMode.value = 'view'
  const ready = await ensureFilterOptions()
  if (!ready) return
  await openUserDetail(userId)
}

const openUserDetail = async (userId) => {
  userModalLoading.value = true
  showUserModal.value = true
  try {
    const detail = await adminStore.fetchUserDetail(userId, { forceRefresh: true })
    populateUserForm(detail)
  } catch (error) {
    window.alert(error?.message || 'Failed to load user information')
    showUserModal.value = false
  } finally {
    userModalLoading.value = false
  }
}

const closeUserModal = () => {
  showUserModal.value = false
}

const ensureFilterOptions = async () => {
  try {
    await adminStore.fetchFilterOptions({ forceRefresh: !adminStore.filterOptions.tracks.length })
    return true
  } catch (error) {
    window.alert(error?.message || 'Failed to load filter options. Please try again later.')
    return false
  }
}

const resetUserForm = () => {
  userForm.id = null
  userForm.email = ''
  userForm.role = 'student'
  userForm.track = activeTrack.value || 'Global'
  userForm.status = 'pending'
  Object.assign(userForm.profile, {
    firstName: '',
    lastName: '',
    schoolName: '',
    yearLevel: '',
    country: '',
    region: '',
    areasOfInterestText: '',
    availability: '',
    bio: ''
  })
}

const populateUserForm = (detail) => {
  resetUserForm()
  userForm.id = detail?.id ?? null
  userForm.email = detail?.email || ''
  userForm.role = detail?.role || 'student'
  userForm.track = detail?.track ? detail.track : 'Global'
  userForm.status = detail?.status || 'pending'

  const profile = detail?.profile || {}
  userForm.profile.firstName = profile.firstName || ''
  userForm.profile.lastName = profile.lastName || ''
  userForm.profile.schoolName = profile.schoolName || ''
  userForm.profile.yearLevel = profile.yearLevel != null ? String(profile.yearLevel) : ''
  userForm.profile.country = profile.country || ''
  userForm.profile.region = profile.region || ''
  userForm.profile.areasOfInterestText = Array.isArray(profile.areasOfInterest)
    ? profile.areasOfInterest.join(', ')
    : ''
  userForm.profile.availability = profile.availability || ''
  userForm.profile.bio = profile.bio || ''
}

const buildUserPayload = () => {
  const email = String(userForm.email || '').trim().toLowerCase()
  if (!email) {
    throw new Error('Email is required')
  }
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailPattern.test(email)) {
    throw new Error('Please enter a valid email address (e.g. name@example.com).')
  }

  const payload = {
    email,
    role: userForm.role,
    status: userForm.status,
    track: userForm.track && userForm.track.toLowerCase() !== 'global' ? userForm.track : ''
  }

  const profilePayload = {}
  const pushProfile = (key, value) => {
    if (typeof value === 'string') {
      const trimmed = value.trim()
      if (trimmed || userModalMode.value === 'edit') {
        profilePayload[key] = trimmed
      }
      return
    }
    if (value != null) {
      profilePayload[key] = value
    } else if (userModalMode.value === 'edit') {
      profilePayload[key] = null
    }
  }

  pushProfile('firstName', userForm.profile.firstName)
  pushProfile('lastName', userForm.profile.lastName)
  pushProfile('schoolName', userForm.profile.schoolName)
  pushProfile('country', userForm.profile.country)
  pushProfile('region', userForm.profile.region)
  pushProfile('availability', userForm.profile.availability)
  pushProfile('bio', userForm.profile.bio)

  if (userForm.profile.yearLevel !== '') {
    const parsed = parseInt(userForm.profile.yearLevel, 10)
    if (!Number.isNaN(parsed)) {
      profilePayload.yearLevel = parsed
    } else if (userModalMode.value === 'edit') {
      profilePayload.yearLevel = null
    }
  } else if (userModalMode.value === 'edit') {
    profilePayload.yearLevel = null
  }

  const interests = userForm.profile.areasOfInterestText
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (interests.length) {
    profilePayload.areasOfInterest = interests
  } else if (userModalMode.value === 'edit') {
    profilePayload.areasOfInterest = []
  }

  if (Object.keys(profilePayload).length) {
    payload.profile = profilePayload
  }

  return payload
}

const saveUser = async () => {
  const formElement = userFormRef.value
  if (formElement && typeof formElement.reportValidity === 'function') {
    const isValid = formElement.reportValidity()
    if (!isValid) {
      return
    }
  }

  try {
    const payload = buildUserPayload()
    if (userModalMode.value === 'create') {
      await adminStore.createUser(payload)
    } else if (userModalMode.value === 'edit' && userForm.id != null) {
      await adminStore.updateUser(userForm.id, payload)
    }
    showUserModal.value = false
  } catch (error) {
    window.alert(error?.message || 'Failed to save changes')
  }
}

const confirmDeleteUser = async (userId) => {
  const targetId = userId ?? userForm.id
  if (targetId == null) return

  const target =
    users.value.find((user) => user.id === targetId) ||
    (userForm.id === targetId ? { name: `${userForm.profile.firstName} ${userForm.profile.lastName}`.trim(), email: userForm.email } : null)

  const displayName = target?.name?.trim() || target?.email || 'this user'
  const confirmed = window.confirm(`Delete ${displayName}? This action cannot be undone.`)
  if (!confirmed) return

  try {
    await adminStore.deleteUser(targetId)
    if (showUserModal.value && targetId === userForm.id) {
      showUserModal.value = false
    }
  } catch (error) {
    window.alert(error?.message || 'Failed to delete user')
  }
}

const exportUsers = async () => {
  try {
    const { blob, filename } = await adminStore.exportUsers()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    window.alert(error?.message || 'Failed to export data')
  }
}

// Group management functions
const toggleCreateGroup = () => {
  showCreateGroup.value = !showCreateGroup.value
  membersDropdownOpen.value = false
  if (showCreateGroup.value) {
    resetGroupForm()
    if (!groupOptionsLoaded.value) {
      loadGroupOptions(true).catch(() => {})
    }
  }
}

const resetGroupForm = () => {
  groupForm.groupId = ''
  groupForm.name = ''
  groupForm.track = activeTrack.value || 'Global'
  groupForm.mentorId = ''
  groupForm.memberIds = []
  memberSearch.value = ''
  membersDropdownOpen.value = false
}

const isSelected = (memberId) => {
  return groupForm.memberIds.includes(String(memberId))
}

const toggleMember = (memberId) => {
  const id = String(memberId)
  const index = groupForm.memberIds.indexOf(id)
  if (index > -1) {
    groupForm.memberIds.splice(index, 1)
  } else {
    groupForm.memberIds.push(id)
  }
}

const removeMember = (memberId) => {
  const id = String(memberId)
  const index = groupForm.memberIds.indexOf(id)
  if (index > -1) {
    groupForm.memberIds.splice(index, 1)
  }
}

const clearMembers = () => {
  groupForm.memberIds = []
  memberSearch.value = ''
}

const toggleMembersDropdown = async () => {
  if (!membersDropdownOpen.value && !groupOptionsLoaded.value) {
    await loadGroupOptions(true).catch(() => {})
  }
  membersDropdownOpen.value = !membersDropdownOpen.value
  if (membersDropdownOpen.value) {
    await nextTick()
    const input = memberDropdownRef.value?.querySelector('.dropdown-search-input')
    input?.focus()
  }
}

const handleMembersClickOutside = (event) => {
  if (!membersDropdownOpen.value) return
  const root = memberDropdownRef.value
  if (!root) return
  if (!root.contains(event.target)) {
    membersDropdownOpen.value = false
  }
}

const fetchGroups = async (force = false) => {
  if (!isAdmin.value) return []
  if (groupsLoading.value) return groups.value
  if (groupsLoaded.value && !force) return groups.value

  groupsLoading.value = true
  groupsError.value = ''

  try {
    const params = new URLSearchParams()
    params.append('status', 'active')
    if (activeTrack.value && activeTrack.value.toLowerCase() !== 'global') {
      params.append('track', activeTrack.value)
    }

    const response = await authStore.authenticatedFetch(
      `/groups/${params.toString() ? `?${params.toString()}` : ''}`
    )
    const data = await safeJson(response)
    if (!response.ok) {
      throw new Error(data?.error || 'Failed to load groups')
    }

    groups.value = Array.isArray(data?.groups) ? data.groups : []
    groupsLoaded.value = true
    return groups.value
  } catch (error) {
    groupsError.value = error?.message || 'Failed to fetch groups'
    throw error
  } finally {
    groupsLoading.value = false
  }
}

const loadGroupOptions = async (force = false) => {
  if (!isAdmin.value) return
  if (loadingGroupOptions.value) return
  if (groupOptionsLoaded.value && !force) return

  loadingGroupOptions.value = true

  const fetchUserOptions = async (query) => {
    const response = await authStore.authenticatedFetch(`/admin/users/${query}`)
    const data = await safeJson(response)
    if (!response.ok) {
      throw new Error(data?.error || 'Failed to load user options')
    }

    const results = Array.isArray(data?.results)
      ? data.results
      : Array.isArray(data)
        ? data
        : []

    return results.map((item) => ({
      id: item.id,
      name: item.name || item.email
    }))
  }

  const trackValue = (activeTrack.value || '').trim()
  const trackQuery =
    trackValue && trackValue.toLowerCase() !== 'global'
      ? `&track=${encodeURIComponent(trackValue)}`
      : ''

  try {
    availableMentors.value = await fetchUserOptions(`?status=active&role=mentor${trackQuery}&page_size=200`)
    availableMembers.value = await fetchUserOptions(`?status=active&role=student${trackQuery}&page_size=500`)
    groupOptionsLoaded.value = true
  } catch (error) {
    window.alert(error?.message || 'Failed to load user options')
  } finally {
    loadingGroupOptions.value = false
  }
}

const createGroup = async () => {
  const name = groupForm.name.trim()
  if (!name) {
    window.alert('Group name is required')
    return
  }

  if (!groupForm.memberIds.length) {
    window.alert('Please select at least one member')
    return
  }

  creatingGroup.value = true

  let mentorId =
    groupForm.mentorId === null || groupForm.mentorId === ''
      ? null
      : Number(groupForm.mentorId)

  if (mentorId !== null && !Number.isFinite(mentorId)) {
    mentorId = null
  }

  const memberIds = Array.from(
    new Set(
      groupForm.memberIds
        .map((id) => Number(id))
        .filter((id) => Number.isFinite(id))
    )
  )

  const payload = {
    groupId: groupForm.groupId.trim() || null,
    name,
    track:
      (groupForm.track || '').trim().toLowerCase() === 'global'
        ? ''
        : (groupForm.track || '').trim(),
    mentorId,
    members: memberIds.map((id) => ({ userId: id, role: 'student' }))
  }

  try {
    const response = await authStore.authenticatedFetch('/groups/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    const data = await safeJson(response)
    if (!response.ok) {
      throw new Error(data?.error || 'Failed to create group')
    }

    await fetchGroups(true)
    await adminStore.fetchStats({ track: activeTrack.value })
    groupStoreGlobal.fetchAllGroups({ forceRefresh: true }).catch(() => {})
    groupStoreGlobal.fetchMyGroups({ forceRefresh: true }).catch(() => {})
    resetGroupForm()
    showCreateGroup.value = false
    window.alert('Group created successfully')
  } catch (error) {
    window.alert(error?.message || 'Failed to create group')
  } finally {
    creatingGroup.value = false
  }
}

const viewGroup = (groupId) => {
  router.push(`/groups/${groupId}`)
}

const deleteGroup = async (groupId) => {
  if (!groupId) return
  const confirmed = window.confirm('Delete this group? This action cannot be undone.')
  if (!confirmed) return

  deletingGroups.value = { ...deletingGroups.value, [groupId]: true }

  try {
    const response = await authStore.authenticatedFetch(`/groups/${groupId}/`, {
      method: 'DELETE'
    })

    if (!response.ok && response.status !== 204) {
      const data = await safeJson(response)
      throw new Error(data?.error || 'Failed to delete group')
    }

    await adminStore.fetchStats({ track: activeTrack.value })
    await fetchGroups(true)
    groupStoreGlobal.fetchAllGroups({ forceRefresh: true }).catch(() => {})
    groupStoreGlobal.fetchMyGroups({ forceRefresh: true }).catch(() => {})
  } catch (error) {
    window.alert(error?.message || 'Failed to delete group')
  } finally {
    const { [groupId]: _discard, ...rest } = deletingGroups.value
    deletingGroups.value = rest
  }
}
</script>

<style scoped>
.modern-admin {
  max-width: 1600px;
  margin: 0 auto;
}

/* Hero Section */
.admin-hero {
  background: linear-gradient(135deg, var(--dark-green) 0%, #018a63 100%);
  border-radius: var(--radius-xl);
  padding: 2.5rem;
  margin-bottom: 2rem;
  box-shadow: var(--shadow-lg);
}

.admin-hero-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 2rem;
}

.admin-title {
  font-size: 2.25rem;
  font-weight: 700;
  color: var(--white);
  margin: 0 0 0.5rem;
  letter-spacing: -0.02em;
}

.admin-subtitle {
  font-size: 1.125rem;
  color: rgba(255, 255, 255, 0.85);
  margin: 0;
}

.track-selector {
  padding: 0.875rem 1.5rem;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(10px);
  color: var(--white);
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  transition: var(--transition);
  min-width: 220px;
}

.track-selector:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.4);
}

.track-selector option {
  background: var(--charcoal);
  color: var(--white);
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(220px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2.5rem;
  align-items: stretch;
}

.stat-card {
  background: linear-gradient(135deg, var(--white) 0%, var(--bg-lighter) 100%);
  border-radius: var(--radius-lg);
  padding: 1.75rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  box-shadow: var(--shadow);
  border: 1.5px solid var(--border-lighter);
  transition: var(--transition);
  cursor: pointer;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: var(--dark-green);
}

.stat-card.groups-card {
  cursor: default;
}

.stat-card.groups-card:hover {
  transform: translateY(-2px);
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }
}

@media (max-width: 720px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}

.stat-icon {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.75rem;
  color: var(--white);
  flex-shrink: 0;
}

.stat-icon.users {
  background: linear-gradient(135deg, var(--eucalypt) 0%, var(--mint-green) 100%);
}

.stat-icon.groups {
  background: linear-gradient(135deg, var(--mint-green) 0%, var(--air-force-blue) 100%);
}

.stat-icon.mentors {
  background: linear-gradient(135deg, var(--air-force-blue) 0%, var(--navy) 100%);
}

.stat-icon.students {
  background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
}

.stat-content {
  flex: 1;
}

.stat-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #6c757d;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.375rem;
}

.stat-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: var(--charcoal);
  letter-spacing: -0.02em;
  margin-bottom: 0.25rem;
}

.stat-detail {
  font-size: 0.875rem;
  color: #6c757d;
}

/* Management Sections */
.management-section {
  background: var(--white);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  margin-bottom: 2rem;
  border: 1.5px solid var(--border-lighter);
  overflow: hidden;
}

.section-header {
  padding: 2rem 2.5rem;
  background: linear-gradient(135deg, var(--bg-lighter) 0%, var(--white) 100%);
  border-bottom: 1.5px solid var(--border-lighter);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 2rem;
  flex-wrap: wrap;
}

.section-header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--charcoal);
  margin: 0;
  letter-spacing: -0.01em;
}

.section-count {
  padding: 0.375rem 0.875rem;
  background: linear-gradient(135deg, var(--light-green) 0%, rgba(252, 237, 226, 0.5) 100%);
  color: var(--dark-green);
  border-radius: 999px;
  font-size: 0.875rem;
  font-weight: 600;
}

.section-actions {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.search-input {
  padding: 0.625rem 1.125rem;
  border: 1.5px solid var(--border-light);
  border-radius: var(--radius);
  font-size: 0.9375rem;
  min-width: 280px;
  transition: var(--transition);
}

.search-input:hover {
  border-color: var(--dark-green);
}

.search-input:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.1);
}

/* Table Styles */
.table-container {
  overflow-x: auto;
}

.modern-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}

.modern-table thead {
  background: linear-gradient(135deg, var(--light-green) 0%, rgba(252, 237, 226, 0.5) 100%);
}

.modern-table th {
  padding: 1.125rem 1.75rem;
  text-align: left;
  font-weight: 600;
  color: var(--charcoal);
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.modern-table td {
  padding: 1.125rem 1.75rem;
  font-size: 0.9375rem;
  color: var(--charcoal);
  border-top: 1px solid var(--border-lighter);
}

.modern-table tbody tr {
  transition: var(--transition);
}

.table-row-hover:hover {
  background: linear-gradient(135deg, rgba(1, 113, 81, 0.02) 0%, rgba(1, 113, 81, 0.04) 100%);
}

.loading-cell,
.empty-cell {
  text-align: center;
  padding: 3rem 2rem;
  color: #6c757d;
  font-size: 0.9375rem;
}

.loading-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
}

.text-muted {
  color: #6c757d;
}

.user-name-cell,
.group-name-cell {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  font-weight: 500;
}

.user-avatar-small {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--mint-green) 0%, var(--eucalypt) 100%);
  color: var(--white);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8125rem;
  font-weight: 600;
  flex-shrink: 0;
}

.group-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius);
  background: linear-gradient(135deg, var(--dark-green) 0%, var(--mint-green) 100%);
  color: var(--white);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.role-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background: linear-gradient(135deg, rgba(1, 113, 81, 0.1) 0%, rgba(1, 113, 81, 0.15) 100%);
  color: var(--dark-green);
  border-radius: 999px;
  font-size: 0.8125rem;
  font-weight: 600;
  text-transform: capitalize;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.status-select {
  padding: 0.375rem 0.75rem;
  border: 1.5px solid var(--border-light);
  border-radius: var(--radius-sm);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition);
  background: var(--white);
}

.status-select:hover:not(:disabled) {
  border-color: var(--dark-green);
}

.status-select:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 2px rgba(1, 113, 81, 0.1);
}

.btn-icon-only {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: var(--radius-sm);
  background: rgba(1, 113, 81, 0.08);
  color: var(--dark-green);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition);
  flex-shrink: 0;
}

.btn-icon-only:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(1, 113, 81, 0.15) 0%, rgba(1, 113, 81, 0.2) 100%);
  transform: translateY(-1px);
}

.btn-icon-only.danger {
  background: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.btn-icon-only.danger:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(220, 53, 69, 0.15) 0%, rgba(220, 53, 69, 0.2) 100%);
}

.btn-icon-only:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.checkbox-input {
  width: 18px;
  height: 18px;
  cursor: pointer;
  border-radius: var(--radius-sm);
}

/* Create Group Panel */
.create-group-panel {
  padding: 2.5rem;
  background: linear-gradient(135deg, var(--bg-lighter) 0%, var(--white) 100%);
  border-bottom: 1.5px solid var(--border-lighter);
}

.panel-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--charcoal);
  margin-bottom: 1.5rem;
}

.group-form {
  max-width: 1200px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.25rem;
  margin-bottom: 1.25rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-weight: 600;
  color: var(--charcoal);
  font-size: 0.9375rem;
}

.form-text {
  font-size: 0.875rem;
  color: #6c757d;
}

.member-multiselect {
  position: relative;
  border-radius: var(--radius);
  border: 1.5px solid var(--border-lighter);
  background: var(--white);
  box-shadow: var(--shadow-sm);
  transition: var(--transition);
}

.member-multiselect.open {
  border-color: rgba(1, 113, 81, 0.35);
  box-shadow: var(--shadow);
}

.member-multiselect-control {
  min-height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  cursor: pointer;
}

.member-multiselect-control i {
  color: #6c757d;
  transition: var(--transition);
}

.member-selected-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}

.member-placeholder {
  font-size: 0.9rem;
  color: #6c757d;
}

.member-selected-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.65rem;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(1, 113, 81, 0.12) 0%, rgba(1, 113, 81, 0.18) 100%);
  color: var(--dark-green);
  font-size: 0.85rem;
  font-weight: 500;
  border: 1px solid rgba(1, 113, 81, 0.18);
}

.chip-remove-btn {
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  padding: 0;
}

.member-dropdown-panel {
  position: absolute;
  top: calc(100% + 0.5rem);
  left: 0;
  right: 0;
  z-index: 20;
  background: var(--white);
  border-radius: var(--radius-lg);
  border: 1.5px solid var(--border-lighter);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.member-dropdown-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-lighter);
  background: var(--bg-lighter);
}

.dropdown-search-input {
  flex: 1;
  border: 1.5px solid var(--border-light);
  border-radius: var(--radius);
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  transition: var(--transition);
}

.dropdown-search-input:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 2px rgba(1, 113, 81, 0.15);
}

.clear-selection-btn {
  border: none;
  background: transparent;
  color: var(--dark-green);
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
}

.clear-selection-btn:hover:not(:disabled) {
  text-decoration: underline;
}

.clear-selection-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.member-dropdown-body {
  max-height: 320px;
  overflow-y: auto;
  padding: 0.5rem 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.member-dropdown-option {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.5rem 0.25rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition);
}

.member-dropdown-option span {
  flex: 1;
  min-width: 0;
  font-size: 0.9rem;
}

.member-dropdown-option:hover {
  background: rgba(1, 113, 81, 0.06);
}

.member-dropdown-option input {
  width: 18px;
  height: 18px;
}

.member-empty {
  padding: 0.75rem 0;
  text-align: center;
  color: #6c757d;
  font-size: 0.875rem;
}

@media (max-width: 640px) {
  .member-multiselect-control {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .member-multiselect-control i {
    align-self: flex-end;
  }

  .member-selected-list {
    width: 100%;
  }
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1.5px solid var(--border-lighter);
}

/* Modal Overlay */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(23, 66, 67, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 2rem;
  animation: fadeIn 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.modal-panel {
  width: min(640px, 100%);
  max-height: 90vh;
  background: var(--white);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  border: 1.5px solid var(--border-lighter);
  display: flex;
  flex-direction: column;
  animation: slideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.modal-panel.small {
  width: min(480px, 100%);
}

.modal-panel-header {
  padding: 2rem 2.5rem;
  border-bottom: 1.5px solid var(--border-lighter);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 2rem;
  background: linear-gradient(135deg, var(--bg-lighter) 0%, var(--white) 100%);
}

.modal-panel-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--charcoal);
  margin: 0 0 0.375rem;
  letter-spacing: -0.01em;
}

.modal-panel-subtitle {
  font-size: 0.9375rem;
  color: #6c757d;
  margin: 0;
}

.btn-icon-close {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.05);
  color: #6c757d;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition);
  flex-shrink: 0;
}

.btn-icon-close:hover {
  background: rgba(0, 0, 0, 0.1);
  color: var(--charcoal);
}

.modal-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 2.5rem;
}

.modal-panel-footer {
  padding: 1.75rem 2.5rem;
  border-top: 1.5px solid var(--border-lighter);
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  background: linear-gradient(135deg, var(--white) 0%, var(--bg-lighter) 100%);
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.25rem;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  gap: 1rem;
  color: #6c757d;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-light);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.alert-error {
  padding: 1rem 1.5rem;
  background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
  border: 1.5px solid #f5c6cb;
  border-radius: var(--radius);
  color: #721c24;
  margin: 1.5rem 0;
  font-weight: 500;
}

/* Access Denied */
.access-denied {
  text-align: center;
  padding: 4rem 2rem;
  max-width: 480px;
  margin: 0 auto;
}

.access-denied-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--light-green) 0%, rgba(252, 237, 226, 0.7) 100%);
  color: var(--dark-green);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 2.5rem;
  margin-bottom: 1.5rem;
}

.access-denied h2 {
  color: var(--charcoal);
  margin-bottom: 0.75rem;
}

.access-denied p {
  color: #6c757d;
  font-size: 1.0625rem;
}

/* Responsive */
@media (max-width: 1024px) {
  .admin-hero-content {
    flex-direction: column;
    align-items: stretch;
  }

  .track-selector {
    width: 100%;
  }

  .section-header {
    flex-direction: column;
    align-items: stretch;
  }

  .section-actions {
    width: 100%;
    flex-direction: column;
  }

  .search-input {
    width: 100%;
    min-width: auto;
  }

  .modern-table th,
  .modern-table td {
    padding: 0.875rem 1rem;
  }
}

@media (max-width: 640px) {
  .admin-hero {
    padding: 1.75rem 1.5rem;
  }

  .admin-title {
    font-size: 1.75rem;
  }

  .stat-card {
    padding: 1.25rem;
  }

  .stat-icon {
    width: 52px;
    height: 52px;
    font-size: 1.5rem;
  }

  .stat-value {
    font-size: 1.875rem;
  }

  .section-header {
    padding: 1.5rem;
  }

  .section-title {
    font-size: 1.25rem;
  }

  .create-group-panel {
    padding: 1.5rem;
  }

  .modal-panel-header,
  .modal-panel-body,
  .modal-panel-footer {
    padding: 1.5rem;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideIn {
  from {
    transform: translateY(-20px) scale(0.95);
    opacity: 0;
  }
  to {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
}
</style>
